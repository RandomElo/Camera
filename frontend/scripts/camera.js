document.addEventListener("DOMContentLoaded", async () => {

    // ===============================
    // Récupération IP caméra
    // ===============================
    const ip = new URLSearchParams(window.location.search).get("ip");
    if (!ip) {
        console.error("Aucune IP fournie");
        return;
    }

    const img = document.getElementById("video");
    const loader = document.getElementById("videoLoader");
    const pNbr = document.getElementById("pNbrVisages");
    const divVisages = document.getElementById("divListeVisages");

    // ===============================
    // WebSocket stream caméra
    // ===============================
    const ws = new WebSocket(`ws://localhost:8000/ws/stream/${ip}`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        // Première image → hide loader
        if (loader && loader.style.display !== "none") {
            loader.style.display = "none";
            img.style.display = "block";
        }

        img.src = `data:image/jpeg;base64,${data.image}`;

        // Statistiques
        if (pNbr) pNbr.textContent = data.nbr || 0;

        if (divVisages) {
            divVisages.innerHTML = data.tetes?.length
                ? data.tetes.map(v => `<p>${v}</p>`).join("")
                : "Aucun";
        }
    };

    // ===============================
    // Bouton Ajouter visage
    // ===============================
    const btnAjouter = document.getElementById("buttonAjouterVisage");
    if (btnAjouter) {
        btnAjouter.addEventListener("click", () => {
            askNameModal(async (nom) => {
                try {
                    const req = await fetch("http://localhost:8000/api/ajouter-visage", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ nom, ip:window.location.toString().split("=")[1] })
                    });

                    if (req.ok) {
                        showModal("Visage ajouté : " + nom);
                    } else {
                        showModal("❌ Erreur ajout visage");
                    }
                } catch {
                    showModal("❌ Erreur réseau");
                }
            });
        });
    }

    // ===============================
    // Mode cinéma
    // ===============================
    const cinemaBtn = document.getElementById("cinemaBtn");
    if (cinemaBtn) {
        cinemaBtn.addEventListener("click", () => {
            document.body.classList.toggle("cinema-mode");
            cinemaBtn.textContent = document.body.classList.contains("cinema-mode") ? "✕" : "⛶";
        });
    }

    // ===============================
    // Déplacement caméra
    // ===============================
    document.querySelectorAll(".arrow").forEach(btn => {
        btn.addEventListener("click", async () => {
            await fetch("http://localhost:8000/api/bouger-camera", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ip,
                    mouvement: btn.dataset.direction
                })
            });
        });
    });

    const requeteListeCameras = await fetch("http://127.0.0.1:8000/api/liste-cameras");
    if (!requeteListeCameras.ok) {
        console.error("Erreur récupération caméras");
        return;
    }
    const reponseListeCameras = await requeteListeCameras.json();
    let navHtml = `
    <li><a href="./">Accueil</a></li>
    <li><a href="./liste-visages.html">Liste des visages</a></li>
    `;

    reponseListeCameras.ip.forEach((ip, i) => {
        navHtml += `<li><a href="./camera.html?ip=${ip}">Caméra ${i + 1}</a></li>`;
    });

    document.querySelector(".navbar ul").innerHTML = navHtml;

});

const modal = document.getElementById("resultModal");
const modalText = document.getElementById("modalText");
const closeModal = document.getElementById("closeModal");
const modalInput = document.getElementById("modalInput");
const modalBtn = document.getElementById("modalBtn");
const modalTitle = document.getElementById("modalTitle");

function showModal(text) {
    modalText.style.display = "block";
    modalText.textContent = text;
    modalInput.style.display = "none";
    modalBtn.style.display = "none";
    modal.style.display = "flex";
}

function askNameModal(onConfirm) {
    modalTitle.textContent = "Ajouter un visage";
    modalText.style.display = "none";
    modalInput.style.display = "block";
    modalBtn.style.display = "inline-block";
    modalInput.value = "";

    modal.style.display = "flex";
    modalInput.focus();

    modalBtn.onclick = () => {
        if (!modalInput.value.trim()) {
            showModal("❗ Entrez un nom");
            return;
        }
        modal.style.display = "none";
        onConfirm(modalInput.value.trim());
    };
}

if (closeModal) {
    closeModal.onclick = () => modal.style.display = "none";
}

window.onclick = (e) => {
    if (e.target === modal) modal.style.display = "none";
};

