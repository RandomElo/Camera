# ============================
# IMPORTS
# ============================
import uvicorn
import threading
import base64
import numpy as np
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import cv2
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from pydantic import BaseModel
from insightface.app import FaceAnalysis
import sqlite3
import json
from pydantic import BaseModel
import requests

DB_FILE = "tetes.db"

from bdd import initialisationBDD
from recuperationCameras import recuperation

# ============================
# CONFIGURATION FASTAPI + CORS
# ============================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"], # Autorisation du frontend local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialisationBDD() # Initialisation de la base si nécessaire

# ============================
# VARIABLES GLOBALES
# ============================
latest_frame = None                              # Dernière trame capturée
running = True                                   # Flag d'exécution global
compare_app = None                               # Instance InsightFace
known_embeddings_cache = []                      # Cache des embeddings visage en BDD
cache_loaded = False                             # État du cache
cache_lock = threading.Lock()                    # Sécurisation multithread du cache

# Récupération automatique des caméras sur un sous-réseau
tableauIpCameras = recuperation("172.20.21.0/24")
cameras = {}  # Stockage des threads RTSP + frames

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_ROOT = os.path.join(BASE_DIR)

print(MODEL_ROOT)

# ============================
# THREAD DE CAPTURE PAR CAMÉRA
# ============================
def start_camera_thread(ip):
    rtsp = f"rtsp://camera:camera@{ip}:554/live/ch0"

    cameras[ip] = {
        "latest_frame": None,
        "running": True
    }

    def rtsp_reader():
        cap = cv2.VideoCapture(rtsp)
        if not cap.isOpened():
            print(f"rtsp://camera:camera@{ip}:554/live/ch0")
            print(f"[ERREUR] Impossible d'ouvrir RTSP : {ip}")
            return
        
        print(f"[OK] Capture démarrée : {ip}")
        while cameras[ip]["running"]:
            ret, frame = cap.read()
            if ret:
                cameras[ip]["latest_frame"] = frame
        
        cap.release()

    t = threading.Thread(target=rtsp_reader, daemon=True)
    t.start()
    cameras[ip]["thread"] = t

for ip in tableauIpCameras:
    start_camera_thread(ip)

print(f"[INIT] {len(cameras)} caméras initialisées.")

# ============================
# WEBSOCKET STREAM AVEC RECO FACIALE
# ============================
@app.websocket("/ws/stream/{ip}")
async def stream(ws: WebSocket, ip: str):
    await ws.accept()

    if ip not in cameras:
        await ws.send_text(json.dumps({"error": "Caméra introuvable"}))
        return
    
    global compare_app

    if compare_app is None:
        print("[INIT] Chargement buffalo_sface...")
        compare_app = FaceAnalysis(
            name="buffalo_sface",
            allowed_modules=["detection", "recognition"],
            root=MODEL_ROOT
        )
        compare_app.prepare(ctx_id=-1)
        load_known_faces_embeddings(compare_app)
        print("[INIT] IA prête.")

    def similarity(v1, v2):
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    while True:
        frame = cameras[ip]["latest_frame"]
        if frame is None:
            await asyncio.sleep(0.01)
            continue

        faces = compare_app.get(frame)
        tetes_detectees = []

        with cache_lock:
            known = list(known_embeddings_cache)

        for f in faces:
            x1, y1, x2, y2 = f.bbox.astype(int)
            emb = f.embedding

            best_name = "Inconnu"
            best_score = -1

            for name, db_emb in known:
                score = similarity(emb, db_emb)
                if score > best_score:
                    best_score = score
                    best_name = name
            
            if best_score < 0.40:
                best_name = "Inconnu"

            tetes_detectees.append(best_name)

            color = (0,255,0) if best_name != "Inconnu" else (0,0,255)
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cv2.putText(frame, best_name, (x1, y1-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        _, buffer = cv2.imencode(".jpg", frame)
        jpg_b64 = base64.b64encode(buffer).decode("utf-8")

        await ws.send_text(json.dumps({
            "camera": ip,
            "image": jpg_b64,
            "tetes": [t for t in tetes_detectees if t != "Inconnu"],
            "nbr": len(tetes_detectees)
        }))

        await asyncio.sleep(0.03)

# ============================
# CHARGEMENT DU CACHE DES VISAGES
# ============================
def load_known_faces_embeddings(app):
    global known_embeddings_cache, cache_loaded

    with cache_lock:
        if cache_loaded:
            return known_embeddings_cache

        print("[CACHE] Chargement des visages enregistrés...")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT name, image FROM faces")
        rows = c.fetchall()
        conn.close()

        for name, img_bytes in rows:
            npimg = np.frombuffer(img_bytes, np.uint8)
            face_img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

            faces = app.get(face_img)
            if len(faces) == 0:
                continue

            emb = faces[0].embedding
            known_embeddings_cache.append((name, emb))

        cache_loaded = True
        print(f"[CACHE] {len(known_embeddings_cache)} visages chargés")

    return known_embeddings_cache

# ============================
# SECOND WEBSOCKET : STREAM SIMPLE
# ============================
cameras_frames = {} 

def start_camera(ip):
    rtsp_url = f"rtsp://camera:camera@{ip}:554/live/ch0"
    cameras_frames[ip] = {"latest_frame": None, "running": True}

    def capture_loop():
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            print(f"[ERREUR] Impossible d'ouvrir le flux RTSP {ip}")
            return
        print(f"[OK] Capture RTSP démarrée pour {ip}")
        while cameras_frames[ip]["running"]:
            ret, frame = cap.read()
            if ret:
                cameras_frames[ip]["latest_frame"] = frame
        cap.release()
        print(f"[STOP] Capture RTSP arrêtée pour {ip}")

    threading.Thread(target=capture_loop, daemon=True).start()

# Démarrage des caméras pour ce mode
for ip in tableauIpCameras:
    start_camera(ip)

@app.websocket("/ws/camera")
async def camera(ws: WebSocket):
    await ws.accept()
    ip = ws.query_params.get("ip")
    if not ip or ip not in cameras_frames:
        await ws.send_text("Erreur : caméra introuvable")
        await ws.close()
        return

    try:
        while True:
            frame = cameras_frames[ip]["latest_frame"]
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            _, buffer = cv2.imencode(".jpg", frame)
            jpg_as_text = base64.b64encode(buffer).decode("utf-8")

            await ws.send_text(jpg_as_text)
            await asyncio.sleep(0.03) 
    except Exception as e:
        print(f"WebSocket fermée pour {ip} :", e)

# ============================
# API - LISTE CAMÉRAS
# ============================
@app.get("/api/liste-cameras")
def listeCameras():
    global tableauIpCameras
    return {"ip":tableauIpCameras}


class VisageRequest(BaseModel):
    nom: str
    ip:str

# ============================
# API - AJOUT VISAGE EN BDD
# ============================
@app.post("/api/ajouter-visage")
def controleurAjouterVisage(data: VisageRequest):
    global known_embeddings_cache, cache_loaded

    frame = cameras[data.ip]["latest_frame"]
    img = frame.copy()

    cut_top = 100
    cut_left = 250
    cut_right = 250
    h, w, _ = img.shape
    cropped = img[cut_top:h, cut_left:w - cut_right]

    _, buffer = cv2.imencode(".jpg", cropped)
    img_bytes = buffer.tobytes()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO faces (name, image) VALUES (?, ?)", (data.nom, img_bytes))
    conn.commit()
    conn.close()

    with cache_lock:
        known_embeddings_cache = []
        cache_loaded = False

    if compare_app is not None:
        load_known_faces_embeddings(compare_app)

    return {"etat": 1}

# ============================
# ONVIF – COMMANDES PTZ
# ============================
def construire_continuous_move_xml(profile_token: str, mouvement: str) -> str:
    x, y = 0.0, 0.0
    if mouvement == "droite":
        x = 0.1
    elif mouvement == "gauche":
        x = -0.1
    elif mouvement == "haut":
        y = 0.1
    elif mouvement == "bas":
        y = -0.1

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
            <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
                <tptz:ContinuousMove xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
                <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
                <tptz:Velocity>
                    <tptz:PanTilt x="{x}" y="{y}" xmlns="http://www.onvif.org/ver10/schema"/>
                </tptz:Velocity>
                </tptz:ContinuousMove>
            </s:Body>
            </s:Envelope>"""
    return xml

def construire_stop_xml(profile_token: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
        <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
        <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
            <tptz:Stop xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
            <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
            <tptz:PanTilt>true</tptz:PanTilt>
            <tptz:Zoom>false</tptz:Zoom>
            </tptz:Stop>
        </s:Body>
        </s:Envelope>"""

class BougerCameraRequete(BaseModel):
    ip: str
    mouvement: str

@app.post("/api/bouger-camera")
def controleurBougerCamera(data: BougerCameraRequete):
    CAMERA_IP = data.ip
    PROFILE_TOKEN = "Profile_token1"
    print(f"http://{CAMERA_IP}:8899/onvif/device_service")
    url = f"http://{CAMERA_IP}:8899/onvif/device_service"
    headers = {"Content-Type": "application/soap+xml; charset=utf-8"}

    move_xml = construire_continuous_move_xml("Profile_token1", data.mouvement)
    try:
        requests.post(url, headers=headers, data=move_xml, timeout=5)
    except Exception as e:
        return {"status": "erreur", "detail": str(e)}   

    import time
    time.sleep(1)
    stop_xml = construire_stop_xml(PROFILE_TOKEN)
    try:
        resp = requests.post(url, headers=headers, data=stop_xml, timeout=5)
        return {"status": "ok", "response": resp.text}
    except Exception as e:
        return {"status": "erreur", "detail": str(e)}

# ============================
# API – RÉCUPÉRATION VISAGES STOCKÉS
# ============================
@app.get("/api/visages-enregistrer")
def controleurVisagesEnregistrer():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT id, name, image FROM faces")
    rows = c.fetchall()
    conn.close()

    resultat = []

    for row in rows:
        id_, name, img_bytes = row

        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        resultat.append({
            "id": id_,
            "name": name,
            "image": img_b64
        })

    return resultat

# ============================
# API – MODIFICATION NOM VISAGE
# ============================
class MajNomVisage(BaseModel):
    id: int
    nom: str

@app.post("/api/modifier-nom")
def modifier_nom_visage(data: MajNomVisage):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT id FROM faces WHERE id = ?", (data.id,))
    row = c.fetchone()

    if row is None:
        conn.close()
        return {"status": "error", "message": "Visage introuvable"}

    c.execute(
        "UPDATE faces SET name = ? WHERE id = ?",
        (data.nom, data.id)
    )
    conn.commit()
    conn.close()
    
    return "a"

# ============================
# SERVEUR FRONTEND
# ============================
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# ============================
# ENTRYPOINT UVICORN
# ============================
if __name__ == "__main__":
    uvicorn.run("serveur:app", host="0.0.0.0", port=8000, reload=True)