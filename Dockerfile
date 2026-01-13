FROM python:3.10-slim

# Dépendances nécessaires à opencv, insightface, onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier le backend + le frontend (inclut models + tetes.db)
COPY backend ./backend
COPY frontend ./frontend

# Installer les dépendances Python
WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

# Exposer port Uvicorn
EXPOSE 8000

# Démarrage du serveur
CMD ["uvicorn", "serveur:app", "--host", "0.0.0.0", "--port", "8000"]