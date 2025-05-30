# ⚙️ Guide de Configuration Complète

Ce guide détaille toutes les variables d'environnement et options de configuration de NL2SQL API v2.0.0 pour un setup optimal en développement et production.

## 🎯 Vue d'Ensemble

### Configuration par Environnement

| Environnement | Priorité | Sécurité | Performance | Monitoring |
|---------------|----------|----------|-------------|------------|
| **Développement** | Fonctionnalité | Basique | Locale | Debug |
| **Test/Staging** | Stabilité | Intermédiaire | Optimisée | Logs |
| **Production** | Sécurité | Maximale | Haute | Métriques |

### Fichiers de Configuration

```
nl2sql-api/
├── .env.example          # Template de configuration
├── .env                  # Configuration locale (git-ignored)
├── app/config.py         # Validation Pydantic
├── docker-compose.yml    # Configuration Docker
└── docker/
    └── Dockerfile        # Configuration conteneur
```

## 🔑 Variables d'Environnement Obligatoires

### API Keys - Services Externes

```env
# 🔑 PINECONE (Obligatoire)
PINECONE_API_KEY=your_pinecone_key_here
PINECONE_INDEX_NAME=kpi-to-sql-gemini
PINECONE_ENVIRONMENT=gcp-starter

# 🤖 OPENAI (Obligatoire) 
OPENAI_API_KEY=sk-your_openai_key_here

# 🧠 ANTHROPIC (Optionnel - pour Claude)
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here

# 🌟 GOOGLE (Recommandé - pour embedding)
GOOGLE_API_KEY=AIza_your_google_key_here
```

### Configuration Embedding

```env
# 🔍 EMBEDDING GOOGLE (Nouveau v2.0.0)
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_PROVIDER=google
EMBEDDING_DIMENSIONS=768

# 📊 RECHERCHE VECTORIELLE
EXACT_MATCH_THRESHOLD=0.95
TOP_K_RESULTS=5
```

## 🤖 Configuration LLM Multi-Provider

### Providers et Modèles par Défaut

```env
# 🎯 PROVIDER PRINCIPAL
DEFAULT_PROVIDER=openai

# 🚀 MODÈLES PAR DÉFAUT
DEFAULT_OPENAI_MODEL=gpt-4o
DEFAULT_ANTHROPIC_MODEL=claude-3-opus-20240229
DEFAULT_GOOGLE_MODEL=gemini-pro

# ⚙️ PARAMÈTRES LLM
LLM_TEMPERATURE=0.2
LLM_TIMEOUT=30
```

### Modèles Disponibles par Provider

**OpenAI** :
```env
# Production recommandé
DEFAULT_OPENAI_MODEL=gpt-4o

# Alternatives selon usage
DEFAULT_OPENAI_MODEL=gpt-4o-mini      # Économique
DEFAULT_OPENAI_MODEL=gpt-4-turbo      # Contexte long
DEFAULT_OPENAI_MODEL=gpt-4            # Stable
DEFAULT_OPENAI_MODEL=gpt-3.5-turbo    # Rapide/test
```

**Anthropic** :
```env
# Expert en raisonnement
DEFAULT_ANTHROPIC_MODEL=claude-3-opus-20240229

# Équilibré
DEFAULT_ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Rapide
DEFAULT_ANTHROPIC_MODEL=claude-3-haiku-20240307

# Dernière version
DEFAULT_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

**Google** :
```env
# Standard production
DEFAULT_GOOGLE_MODEL=gemini-pro

# Contexte ultra-long (1M tokens)
DEFAULT_GOOGLE_MODEL=gemini-1.5-pro

# Ultra-rapide
DEFAULT_GOOGLE_MODEL=gemini-1.5-flash
```

## 🗄️ Configuration Base de Données

### Schéma et Documentation

```env
# 📋 SCHÉMA SQL/MARKDOWN
SCHEMA_PATH=app/schemas/datasulting.md

# 📂 SCHÉMAS DISPONIBLES
# app/schemas/datasulting.md     # Schéma RH principal
# app/schemas/custom_schema.sql  # Schéma personnalisé
# app/schemas/test_schema.md     # Schéma de test
```

### Configuration Pinecone

```env
# 🏷️ INDEX PRINCIPAL
PINECONE_INDEX_NAME=kpi-to-sql-gemini

# 🌍 ENVIRONNEMENT PINECONE
PINECONE_ENVIRONMENT=gcp-starter      # Gratuit
PINECONE_ENVIRONMENT=us-east-1-aws    # Production AWS
PINECONE_ENVIRONMENT=us-central1-gcp  # Production GCP

# 📊 PARAMÈTRES DE RECHERCHE
TOP_K_RESULTS=5                       # Nombre de vecteurs similaires
EXACT_MATCH_THRESHOLD=0.95            # Seuil correspondance exacte
```

## 💾 Configuration Cache Redis

### Setup Redis

```env
# 🔗 CONNEXION REDIS
REDIS_URL=redis://localhost:6379/0
REDIS_URL=redis://redis:6379/0        # Docker
REDIS_URL=redis://user:pass@host:6379/0  # Authentifié

# ⏱️ PARAMÈTRES CACHE
REDIS_TTL=3600                        # 1 heure
CACHE_ENABLED=true
```

### Configuration Avancée Cache

```env
# 🎛️ CACHE GRANULAIRE
CACHE_ENABLED=true                    # Cache global activé
# Note: use_cache=false par requête possible

# ⏰ TTL PAR TYPE
TRANSLATION_CACHE_TTL=3600           # Traductions: 1h
VALIDATION_CACHE_TTL=7200            # Validations: 2h  
HEALTH_CACHE_TTL=300                 # Health checks: 5min

# 🧹 NETTOYAGE AUTOMATIQUE
CACHE_CLEANUP_INTERVAL=3600          # Nettoyage toutes les heures
CACHE_MAX_MEMORY=100MB               # Limite mémoire
```

## 🔐 Configuration Sécurité

### Authentification API

```env
# 🔑 CLÉ API (Optionnelle)
API_KEY=your_strong_secret_api_key_here
API_KEY_NAME=X-API-Key

# 🔐 ADMIN (Pour endpoints sensibles)
ADMIN_SECRET=your_admin_secret_here
```

### Restrictions d'Accès

```env
# 🌐 HÔTES AUTORISÉS
ALLOWED_HOSTS=["*"]                              # Développement
ALLOWED_HOSTS=["localhost","127.0.0.1"]         # Local seulement
ALLOWED_HOSTS=["api.yourcompany.com"]            # Production
ALLOWED_HOSTS=["api.yourcompany.com","admin.yourcompany.com"]  # Multi-domaines
```

### Rate Limiting

```env
# ⏱️ LIMITATION DÉBIT (dans code)
# 60 requêtes/minute/IP par défaut
# Configurable via dependencies.py
```

## 🏗️ Configuration API

### Serveur et Endpoints

```env
# 🌐 CONFIGURATION SERVEUR
API_PREFIX=/api/v1
HOST=0.0.0.0
PORT=8000

# 🐛 MODE DEBUG
DEBUG=false                          # Production
DEBUG=true                           # Développement

# 📊 FONCTIONNALITÉS AVANCÉES
METRICS_ENABLED=true
```

### Logging et Monitoring

```env
# 📝 NIVEAU DE LOGS
LOG_LEVEL=INFO                       # Production
LOG_LEVEL=DEBUG                      # Développement

# 📊 MÉTRIQUES
METRICS_ENABLED=true
PROMETHEUS_PORT=9090                 # Si métriques Prometheus

# 🏥 HEALTH CHECKS
HEALTH_CHECK_INTERVAL=30             # Secondes
HEALTH_CHECK_TIMEOUT=10
```

## 🐳 Configuration Docker

### Variables Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    environment:
      # Surcharge pour container
      - REDIS_URL=redis://redis:6379/0
      - HOST=0.0.0.0
      - PORT=8000
    env_file:
      - ./.env
```

### Variables Dockerfile

```dockerfile
# Dockerfile
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV TRANSFORMERS_CACHE=/home/app/.cache/huggingface/transformers
ENV HF_HOME=/home/app/.cache/huggingface
```

## 📋 Templates de Configuration

### 🔧 Développement Local

```env
# ==============================================
# CONFIGURATION DÉVELOPPEMENT - NL2SQL API
# ==============================================

# 🔑 Clés API (Obligatoires)
PINECONE_API_KEY=your_pinecone_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key

# 🤖 Configuration LLM
DEFAULT_PROVIDER=openai
DEFAULT_OPENAI_MODEL=gpt-4o
LLM_TEMPERATURE=0.2
LLM_TIMEOUT=30

# 🔍 Embedding et Recherche
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_PROVIDER=google
PINECONE_INDEX_NAME=kpi-to-sql-gemini
TOP_K_RESULTS=5

# 💾 Cache Redis (Local)
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
REDIS_TTL=3600

# 🐛 Debug et Développement
DEBUG=true
LOG_LEVEL=DEBUG
METRICS_ENABLED=true

# 🌐 Serveur Local
HOST=127.0.0.1
PORT=8000
API_PREFIX=/api/v1
ALLOWED_HOSTS=["*"]

# 📋 Schéma
SCHEMA_PATH=app/schemas/datasulting.md
```

### 🚀 Production

```env
# ==============================================
# CONFIGURATION PRODUCTION - NL2SQL API
# ==============================================

# 🔑 Clés API Sécurisées
PINECONE_API_KEY=${PINECONE_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
GOOGLE_API_KEY=${GOOGLE_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# 🤖 Configuration LLM Optimisée
DEFAULT_PROVIDER=openai
DEFAULT_OPENAI_MODEL=gpt-4o
LLM_TEMPERATURE=0.1
LLM_TIMEOUT=45

# 🔍 Recherche Optimisée
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_PROVIDER=google
PINECONE_INDEX_NAME=prod-kpi-to-sql
TOP_K_RESULTS=5
EXACT_MATCH_THRESHOLD=0.97

# 💾 Cache Redis Production
REDIS_URL=${REDIS_URL}
CACHE_ENABLED=true
REDIS_TTL=7200

# 🔐 Sécurité Production
API_KEY=${API_SECRET_KEY}
ADMIN_SECRET=${ADMIN_SECRET}
ALLOWED_HOSTS=["api.yourcompany.com"]

# 🏥 Production Settings
DEBUG=false
LOG_LEVEL=INFO
METRICS_ENABLED=true

# 🌐 Serveur Production
HOST=0.0.0.0
PORT=8000
API_PREFIX=/api/v1

# 📋 Schéma Production
SCHEMA_PATH=app/schemas/production_schema.md
```

### 🧪 Test/Staging

```env
# ==============================================
# CONFIGURATION STAGING - NL2SQL API
# ==============================================

# 🔑 Clés API Test
PINECONE_API_KEY=test_pinecone_key
OPENAI_API_KEY=test_openai_key
GOOGLE_API_KEY=test_google_key

# 🤖 Configuration Test
DEFAULT_PROVIDER=openai
DEFAULT_OPENAI_MODEL=gpt-3.5-turbo    # Économique pour tests
LLM_TEMPERATURE=0.0                   # Déterministe
LLM_TIMEOUT=20

# 🔍 Test Configuration
EMBEDDING_MODEL=text-embedding-004
PINECONE_INDEX_NAME=test-kpi-to-sql
TOP_K_RESULTS=3

# 💾 Cache Test
REDIS_URL=redis://redis-test:6379/0
CACHE_ENABLED=false                   # Désactivé pour tests
REDIS_TTL=300

# 🧪 Test Settings
DEBUG=true
LOG_LEVEL=DEBUG
METRICS_ENABLED=false

# 🌐 Serveur Test
HOST=0.0.0.0
PORT=8000
ALLOWED_HOSTS=["staging.yourcompany.com","localhost"]

# 📋 Schéma Test
SCHEMA_PATH=app/schemas/test_schema.md
```

## 🔧 Configuration Avancée

### Optimisations Performance

```env
# ⚡ PERFORMANCE LLM
LLM_TEMPERATURE=0.1                   # Plus déterministe
LLM_TIMEOUT=45                        # Plus de temps en prod
LLM_MAX_RETRIES=3                     # Retry automatique

# 🔍 OPTIMISATION VECTORIELLE
EMBEDDING_BATCH_SIZE=100              # Traitement par batch
VECTOR_SEARCH_TIMEOUT=10              # Timeout Pinecone
PINECONE_POOL_SIZE=10                 # Pool connexions

# 💾 OPTIMISATION CACHE
REDIS_POOL_SIZE=20                    # Pool connexions Redis
CACHE_COMPRESSION=true                # Compression données
CACHE_SERIALIZATION=json              # Format sérialisation
```

### Configuration Prompts Jinja2

```env
# 🎯 SYSTÈME PROMPTS
PROMPTS_TEMPLATES_DIR=app/prompts
PROMPTS_DEBUG=false
PROMPTS_FALLBACK_ENABLED=true
PROMPTS_CACHE_TEMPLATES=true

# 📄 TEMPLATES DISPONIBLES
# app/prompts/sql_generation.j2
# app/prompts/sql_validation.j2
```

### Configuration Monitoring

```env
# 📊 MÉTRIQUES AVANCÉES
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
GRAFANA_DASHBOARD=true

# 🏥 HEALTH CHECKS
HEALTH_CHECK_DEEP=true               # Vérifications approfondies
HEALTH_CHECK_EXTERNAL=true           # APIs externes
HEALTH_CHECK_CACHE_TTL=60            # Cache health status

# 📝 LOGGING AVANCÉ
LOG_FORMAT=json                      # Format structuré
LOG_FILE=/var/log/nl2sql.log         # Fichier de logs
LOG_ROTATION=daily                   # Rotation quotidienne
LOG_RETENTION=30                     # 30 jours de rétention
```

## 🛡️ Validation Configuration

### Validation Pydantic

La configuration est validée automatiquement via **Pydantic** dans `app/config.py` :

```python
class Settings(BaseSettings):
    # Validation automatique des types
    PINECONE_API_KEY: str = Field(..., env="PINECONE_API_KEY")
    LLM_TEMPERATURE: float = Field(0.2, ge=0.0, le=1.0)
    TOP_K_RESULTS: int = Field(5, ge=1, le=100)
    
    @validator('OPENAI_API_KEY')
    def validate_openai_key(cls, v):
        if v and not v.startswith('sk-'):
            raise ValueError("Clé OpenAI invalide")
        return v
```

### Validation au Démarrage

```python
# Vérification automatique dans main.py
def validate_environment():
    required_vars = [
        'PINECONE_API_KEY',
        'OPENAI_API_KEY'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"Variables manquantes: {missing}")
```

## 🧪 Test de Configuration

### Script de Validation

```bash
#!/bin/bash
# scripts/validate_config.sh

echo "🔍 Validation Configuration NL2SQL API"

# Test variables obligatoires
if [[ -z "$PINECONE_API_KEY" ]]; then
    echo "❌ PINECONE_API_KEY manquante"
    exit 1
fi

if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "❌ OPENAI_API_KEY manquante"  
    exit 1
fi

# Test connexion Pinecone
echo "🔍 Test connexion Pinecone..."
python -c "
import pinecone
pinecone.init(api_key='$PINECONE_API_KEY')
print('✅ Pinecone OK')
"

# Test connexion OpenAI
echo "🔍 Test connexion OpenAI..."
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  | jq -r '.data[0].id' && echo "✅ OpenAI OK"

# Test Redis (optionnel)
if [[ -n "$REDIS_URL" ]]; then
    echo "🔍 Test connexion Redis..."
    redis-cli -u $REDIS_URL ping && echo "✅ Redis OK"
fi

echo "🎉 Configuration validée avec succès!"
```

### Test via API

```bash
# Test health check complet
curl http://localhost:8000/api/v1/health | jq '.services'

# Test endpoints de configuration
curl http://localhost:8000/api/v1/models
curl http://localhost:8000/api/v1/schemas
```

## 🔄 Gestion Environnements

### Switching Entre Environnements

```bash
# Développement
cp .env.development .env
docker-compose up -d

# Staging  
cp .env.staging .env
docker-compose -f docker-compose.staging.yml up -d

# Production
cp .env.production .env
docker-compose -f docker-compose.prod.yml up -d
```

### Variables par Environnement

```bash
# .env.development
DEBUG=true
LOG_LEVEL=DEBUG
CACHE_ENABLED=true

# .env.staging  
DEBUG=false
LOG_LEVEL=INFO
CACHE_ENABLED=true

# .env.production
DEBUG=false
LOG_LEVEL=WARNING
CACHE_ENABLED=true
METRICS_ENABLED=true
```

## 📊 Monitoring Configuration

### Métriques de Configuration

```python
# Endpoint /config/status
{
    "environment": "production",
    "debug_mode": false,
    "services_configured": {
        "openai": true,
        "anthropic": true, 
        "google": true,
        "pinecone": true,
        "redis": true
    },
    "features_enabled": {
        "cache": true,
        "metrics": true,
        "prompts_jinja2": true
    }
}
```

### Alertes Configuration

```env
# Alertes sur configuration
CONFIG_ALERTS_ENABLED=true
CONFIG_SLACK_WEBHOOK=https://hooks.slack.com/...
CONFIG_EMAIL_ALERTS=admin@yourcompany.com

# Seuils d'alerte
API_KEY_EXPIRY_DAYS=30               # Alerte expiration clés
CACHE_HIT_RATE_MIN=0.7               # Alerte taux cache faible
ERROR_RATE_MAX=0.05                  # Alerte taux erreur élevé
```

## 🚨 Troubleshooting Configuration

### Problèmes Courants

**1. Clé API Invalide** :
```bash
# Tester manuellement
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**2. Index Pinecone Introuvable** :
```python
# Vérifier index existant
import pinecone
pinecone.init(api_key=API_KEY)
print(pinecone.list_indexes())
```

**3. Redis Non Accessible** :
```bash
# Test connexion
redis-cli -u $REDIS_URL ping
# Résultat attendu: PONG
```

**4. Schéma Introuvable** :
```bash
# Vérifier chemin
ls -la app/schemas/
cat app/schemas/datasulting.md | head -10
```

### Logs de Démarrage

```
2025-05-30 09:20:26 - app.main - INFO - 🚀 Démarrage NL2SQL API v2.0.0
2025-05-30 09:20:26 - app.config - INFO - Configuration chargée: 25 variables
2025-05-30 09:20:27 - app.core.embedding - INFO - Google text-embedding-004 initialisé
2025-05-30 09:20:27 - app.core.vector_search - INFO - Pinecone index 'kpi-to-sql-gemini' connecté
2025-05-30 09:20:28 - app.services.translation_service - INFO - Service de traduction initialisé
2025-05-30 09:20:28 - app.main - INFO - ✅ Tous les services sont opérationnels
```

## 🔮 Configuration Avancée Future

### Fonctionnalités Prévues

1. **Configuration Dynamique** : Rechargement sans redémarrage
2. **Vault Integration** : Secrets management avec HashiCorp Vault
3. **Configuration UI** : Interface web de configuration
4. **Feature Flags** : Activation/désactivation dynamique
5. **Multi-Tenant Config** : Configuration par tenant

---

## 🎯 Navigation

**Précédent** : [Système de Prompts Jinja2](Jinja2-Prompts-System)  
**Suivant** : [Framework de Sécurité](Security-Framework)

**Voir aussi** :
- [Guide de Démarrage Rapide](Quick-Start-Guide) - Setup initial
- [Docker Deployment](Docker-Deployment) - Déploiement conteneurisé
- [Monitoring & Métriques](Monitoring-Metrics) - Surveillance

---

*Guide de Configuration NL2SQL API v2.0.0 - Setup optimal pour tous environnements* ⚙️✨