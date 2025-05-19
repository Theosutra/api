FROM python:3.10-slim

LABEL maintainer="Datasulting <contact@datasulting.fr>"
LABEL version="1.0.0"
LABEL description="API NL2SQL pour transformer des requêtes en langage naturel en SQL"

# Définir les variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    # Configuration de Hugging Face
    TRANSFORMERS_CACHE=/home/app/.cache/huggingface/transformers \
    HF_HOME=/home/app/.cache/huggingface \
    XDG_CACHE_HOME=/home/app/.cache

# Créer un utilisateur non-root avec un répertoire home valide
RUN addgroup --system app && \
    adduser --system --home /home/app --group app && \
    mkdir -p /home/app/.cache && \
    chown -R app:app /home/app

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    sed -i 's/pinecone-client/pinecone-python-client/g' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copier et corriger le fichier .env
COPY .env .
RUN sed -i 's|redis://localhost:6379/0|redis://redis:6379/0|g' .env || true

# Changer vers l'utilisateur app pour le téléchargement du modèle
USER app

# Précharger le modèle d'embedding avec journalisation détaillée
RUN python -c "import logging; logging.basicConfig(level=logging.INFO); from sentence_transformers import SentenceTransformer; print('Téléchargement du modèle...'); model = SentenceTransformer('all-mpnet-base-v2'); print('Modèle téléchargé avec succès'); print(f'Modèle stocké dans: {model._cache_dir}')"

# Revenir à l'utilisateur root pour copier le reste des fichiers
USER root

# Copier le code de l'application
COPY --chown=app:app . .

# Créer les répertoires nécessaires s'ils n'existent pas
RUN mkdir -p app/schemas && chown -R app:app /app

# Basculer vers l'utilisateur non-root
USER app

# Exposer le port de l'application
EXPOSE ${PORT}

# Configurer l'exécution de l'application
CMD ["python", "-m", "app.main"]