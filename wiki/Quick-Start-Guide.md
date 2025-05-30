# 🏁 Guide de Démarrage Rapide

Ce guide vous permettra d'avoir NL2SQL API fonctionnelle en **moins de 10 minutes** ! ⏱️

## 🎯 Objectif

À la fin de ce guide, vous pourrez :
- ✅ Faire fonctionner l'API localement
- ✅ Effectuer votre première traduction NL2SQL
- ✅ Comprendre la réponse avec requêtes similaires
- ✅ Valider que tous les services sont opérationnels

## 📋 Prérequis

### Obligatoires
- **Python 3.8+** ou **Docker**
- **Clés API** :
  - 🔑 **Pinecone API Key** (obligatoire)
  - 🔑 **OpenAI API Key** (obligatoire)
  - 🔑 **Google API Key** (recommandé pour embedding)

### Optionnelles
- **Anthropic API Key** (pour Claude)
- **Redis** (pour le cache - auto-désactivé si absent)

## 🚀 Installation Express (Docker - Recommandé)

### 1. Cloner le Repository

```bash
git clone https://github.com/datasulting/nl2sql-api.git
cd nl2sql-api
```

### 2. Configuration Express

```bash
# Copier le template de configuration
cp .env.example .env

# Éditer avec vos clés API
nano .env  # ou votre éditeur préféré
```

**Configuration minimale dans `.env` :**
```env
# 🔑 Clés API Obligatoires
PINECONE_API_KEY=your_pinecone_key_here
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here

# 🗄️ Configuration Pinecone
PINECONE_INDEX_NAME=kpi-to-sql-gemini
PINECONE_ENVIRONMENT=gcp-starter

# 🤖 Configuration par défaut
DEFAULT_PROVIDER=openai
EMBEDDING_PROVIDER=google
EMBEDDING_MODEL=text-embedding-004
```

### 3. Lancement avec Docker

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier que tout fonctionne
docker-compose logs -f api
```

**Vous devriez voir :**
```
✅ Service LLM initialisé avec succès
✅ Service de traduction initialisé  
✅ Système de prompts Jinja2 initialisé
🎯 API prête à recevoir des requêtes
```

### 4. Test de Fonctionnement

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Premier test de traduction
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Combien d'\''employés en CDI ?",
    "include_similar_details": true
  }'
```

## 🐍 Installation Python (Alternative)

Si vous préférez Python directement :

### 1. Environment Setup

```bash
# Créer l'environnement virtuel
python -m venv venv

# Activer l'environnement
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copier et éditer la configuration
cp .env.example .env
# Éditer .env avec vos clés API (même config que Docker)
```

### 3. Lancement

```bash
# Démarrer l'API
python -m app.main

# L'API sera disponible sur http://localhost:8000
```

## 🧪 Premiers Tests

### Test 1 : Health Check

```bash
curl http://localhost:8000/api/v1/health
```

**Réponse attendue :**
```json
{
  "status": "ok",
  "version": "2.0.0",
  "services": {
    "pinecone": {"status": "ok"},
    "llm": {"status": "ok", "default_provider": "openai"},
    "embedding": {"status": "ok", "model": "text-embedding-004"},
    "cache": {"status": "ok"} // ou "unavailable" si pas de Redis
  }
}
```

### Test 2 : Première Traduction Simple

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Quel est l'\''âge moyen de mes collaborateurs ?",
    "provider": "openai"
  }'
```

**Réponse attendue :**
```json
{
  "query": "Quel est l'âge moyen de mes collaborateurs ?",
  "sql": "SELECT ROUND(AVG(TRUNCATE(b.AGE, 0)), 2) AS Age_Moyen FROM depot a INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT WHERE a.ID_USER = ? AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin); #DEPOT_a# #FACTS_b#",
  "valid": true,
  "explanation": "Cette requête calcule l'âge moyen des collaborateurs...",
  "status": "success",
  "framework_compliant": true
}
```

### Test 3 : Avec Requêtes Similaires

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Liste des employés en CDI embauchés en 2023",
    "include_similar_details": true,
    "explain": true
  }'
```

**Réponse enrichie avec `similar_queries_details` :**
```json
{
  "query": "Liste des employés en CDI embauchés en 2023",
  "sql": "SELECT b.NOM, b.PRENOM, b.DEBUT_CONTRAT FROM depot a...",
  "similar_queries_details": [
    {
      "score": 0.89,
      "texte_complet": "Liste des employés en CDI",
      "requete": "SELECT b.NOM, b.PRENOM FROM depot a...",
      "id": "vec_123456"
    }
  ],
  "status": "success"
}
```

## 📖 Interface de Documentation

Une fois l'API démarrée, explorez la documentation interactive :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **OpenAPI JSON** : http://localhost:8000/openapi.json

## 🔍 Vérifications Importantes

### ✅ Checklist de Fonctionnement

| Service | Commande de Test | Status Attendu |
|---------|------------------|----------------|
| **API** | `curl http://localhost:8000/` | 200 OK |
| **Health** | `curl http://localhost:8000/api/v1/health` | `"status": "ok"` |
| **Pinecone** | Dans health check | `"pinecone": {"status": "ok"}` |
| **LLM** | Dans health check | `"llm": {"status": "ok"}` |
| **Embedding** | Dans health check | `"embedding": {"status": "ok"}` |
| **Cache** | Dans health check | `"cache": {"status": "ok"}` ou `"unavailable"` |

### 🐛 Troubleshooting Rapide

#### Problème : "Pinecone index not found"
```bash
# Vérifiez votre nom d'index
echo $PINECONE_INDEX_NAME
# Connectez-vous à Pinecone Console pour vérifier
```

#### Problème : "OpenAI API key invalid"
```bash
# Testez votre clé directement
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

#### Problème : "Redis connection refused"
```bash
# Normal si pas de Redis - le cache sera désactivé
# Pour activer Redis :
docker run -d -p 6379:6379 redis:alpine
```

## 🎯 Prochaines Étapes

Maintenant que votre API fonctionne :

1. **📚 Explorer l'API** : [Référence API Complète](API-Reference)
2. **🏗️ Comprendre l'Architecture** : [Service Layer Architecture](Service-Layer-Architecture)
3. **⚙️ Configuration Avancée** : [Guide de Configuration](Configuration-Guide)
4. **🛡️ Sécurité** : [Framework de Sécurité](Security-Framework)
5. **🎯 Personnaliser** : [Système de Prompts Jinja2](Jinja2-Prompts-System)

## 📝 Configuration Recommandée pour Production

```env
# Production optimisée
DEBUG=false
CACHE_ENABLED=true
METRICS_ENABLED=true

# Sécurité
API_KEY=your_strong_secret_key
ALLOWED_HOSTS=["your-domain.com"]

# Performance
REDIS_TTL=7200
TOP_K_RESULTS=5
LLM_TIMEOUT=30
```

## 🤝 Besoin d'Aide ?

- 📖 **Documentation** : [Wiki Complet](Home)
- 🐛 **Bug Report** : [GitHub Issues](https://github.com/datasulting/nl2sql-api/issues)
- 💬 **Support** : support@datasulting.com
- 🚀 **Déploiement** : [Guide Docker](Docker-Deployment)

---

**🎉 Félicitations !** Votre NL2SQL API est maintenant opérationnelle ! 

**Prochain objectif** : [Découvrir l'Architecture Service Layer](Service-Layer-Architecture) 🏗️