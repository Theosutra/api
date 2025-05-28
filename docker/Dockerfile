FROM python:3.10-slim

LABEL maintainer="Datasulting <contact@datasulting.fr>"
LABEL version="2.0.0"
LABEL description="API NL2SQL pour transformer des requêtes en langage naturel en SQL avec prompts Jinja2"

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

# Installer les dépendances Python (incluant Jinja2)
RUN pip install --no-cache-dir --upgrade pip && \
    sed -i 's/pinecone-client/pinecone-python-client/g' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Vérifier que Jinja2 est installé
RUN python -c "import jinja2; print(f'Jinja2 {jinja2.__version__} installé avec succès')"

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
RUN mkdir -p app/schemas app/prompts && chown -R app:app /app

# Vérifier que les templates de prompts sont présents
RUN if [ ! -f "app/prompts/sql_generation.j2" ]; then \
        echo "ATTENTION: Templates de prompts manquants, utilisation des prompts par défaut"; \
        echo "L'API fonctionnera avec les prompts de fallback intégrés"; \
    else \
        echo "✅ Templates de prompts Jinja2 détectés"; \
        # Valider la syntaxe des templates si disponibles
        python -c "from jinja2 import Environment, FileSystemLoader; \
                   env = Environment(loader=FileSystemLoader('app/prompts')); \
                   templates = ['sql_generation.j2', 'sql_validation.j2']; \
                   for t in templates: \
                       try: \
                           env.get_template(t); \
                           print(f'✅ Template {t} valide'); \
                       except Exception as e: \
                           print(f'⚠️ Template {t}: {e}')"; \
    fi

# Test rapide du système de prompts
RUN python -c "
try:
    from app.prompts.prompt_manager import get_prompt_manager
    pm = get_prompt_manager()
    templates = pm.list_available_templates()
    print(f'✅ PromptManager initialisé: {len(templates)} template(s)')
    if templates:
        for template in templates:
            macros = pm.list_template_macros(template)
            print(f'  - {template}: {len(macros)} macro(s)')
except ImportError:
    print('⚠️ PromptManager non disponible, utilisation des prompts par défaut')
except Exception as e:
    print(f'⚠️ Erreur PromptManager: {e}')
    print('L\'API fonctionnera avec les prompts de fallback')
" || echo "Validation prompts échouée, fallback disponible"

# Basculer vers l'utilisateur non-root
USER app

# Exposer le port de l'application
EXPOSE ${PORT}

# Healthcheck pour vérifier que l'API répond
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1

# Configurer l'exécution de l'application
CMD ["python", "-m", "app.main"]