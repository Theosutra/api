FROM python:3.10-slim

LABEL maintainer="Datasulting <contact@datasulting.fr>"
LABEL version="1.0.0"
LABEL description="API NL2SQL pour transformer des requêtes en langage naturel en SQL"

# Définir les variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Créer un utilisateur non-root
RUN addgroup --system app && \
    adduser --system --group app

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Créer les répertoires nécessaires s'ils n'existent pas
RUN mkdir -p app/schemas

# Changer les permissions pour l'utilisateur app
RUN chown -R app:app /app

# Basculer vers l'utilisateur non-root
USER app

# Exposer le port de l'application
EXPOSE ${PORT}

# Configurer l'exécution de l'application
CMD ["python", "-m", "app.main"]