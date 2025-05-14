# NL2SQL API

Une API FastAPI pour traduire des requêtes en langage naturel en SQL, en utilisant une combinaison de recherche vectorielle et de génération via LLM.

## Fonctionnalités

- Traduction de requêtes en langage naturel vers SQL optimisé
- Vectorisation des requêtes avec SentenceTransformer
- Recherche de requêtes similaires avec Pinecone
- Génération et validation de requêtes SQL avec OpenAI
- API RESTful sécurisée avec authentication par clé API
- Documentation interactive avec Swagger UI et ReDoc
- Conteneurisation avec Docker et Docker Compose

## Architecture

L'application est structurée de manière modulaire, avec une séparation claire des responsabilités :

- `app/api` : Endpoints de l'API
- `app/core` : Logique métier principale
  - `translator.py` : Traducteur langage naturel vers SQL
  - `embedding.py` : Vectorisation avec SentenceTransformer
  - `vector_search.py` : Recherche vectorielle avec Pinecone
  - `llm.py` : Interaction avec l'API OpenAI
- `app/utils` : Utilitaires
  - `schema_loader.py` : Chargement des schémas SQL
  - `validators.py` : Validation des entrées/sorties
- `app/schemas` : Schémas SQL

## Prérequis

- Python 3.8+
- Clé API Pinecone
- Clé API OpenAI
- Docker & Docker Compose (pour le déploiement conteneurisé)

## Installation

### Installation standard

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/datasulting/nl2sql-api.git
   cd nl2sql-api
   ```

2. Créer un environnement virtuel :
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

4. Créer un fichier `.env` à partir du modèle :
   ```bash
   cp .env.example .env
   ```

5. Modifier le fichier `.env` avec vos clés API et paramètres :
   ```
   PINECONE_API_KEY=votre_clé_pinecone
   OPENAI_API_KEY=votre_clé_openai
   # Autres paramètres selon vos besoins
   ```

### Installation avec Docker

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/datasulting/nl2sql-api.git
   cd nl2sql-api
   ```

2. Créer un fichier `.env` à partir du modèle :
   ```bash
   cp .env.example .env
   ```

3. Modifier le fichier `.env` avec vos clés API et paramètres.

4. Lancer l'application avec Docker Compose :
   ```bash
   cd docker
   docker-compose up -d
   ```

## Utilisation

### Démarrer l'application en mode développement

```bash
python -m app.main
```

L'API sera accessible à l'adresse http://localhost:8000

### Documentation de l'API

La documentation interactive est disponible aux adresses suivantes :

- Swagger UI : http://localhost:8000/docs
- ReDoc : http://localhost:8000/redoc

### Exemples d'utilisation

#### Traduire une requête en langage naturel en SQL

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/translate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: votre_clé_api' \
  -d '{
  "query": "Liste des clients qui ont effectué plus de 5 commandes en 2023",
  "schema_path": null,
  "validate": true,
  "explain": true
}'
```

#### Vérifier l'état de santé de l'API

```bash
curl -X 'GET' \
  'http://localhost:8000/api/v1/health' \
  -H 'accept: application/json' \
  -H 'X-API-Key: votre_clé_api'
```

## Configuration

L'application est configurable via le fichier `.env` ou via des variables d'environnement :

- **Clés API** :
  - `PINECONE_API_KEY` : Clé API Pinecone
  - `OPENAI_API_KEY` : Clé API OpenAI

- **Paramètres Pinecone** :
  - `PINECONE_INDEX_NAME` : Nom de l'index Pinecone (par défaut : `nl2sql`)
  - `PINECONE_ENVIRONMENT` : Environnement Pinecone (par défaut : `gcp-starter`)

- **Paramètres de traduction** :
  - `EMBEDDING_MODEL` : Modèle d'embedding (par défaut : `all-MiniLM-L6-v2`)
  - `OPENAI_MODEL` : Modèle OpenAI (par défaut : `gpt-4o`)
  - `OPENAI_TEMPERATURE` : Température pour la génération (par défaut : `0.2`)
  - `EXACT_MATCH_THRESHOLD` : Seuil pour la correspondance exacte (par défaut : `0.95`)
  - `TOP_K_RESULTS` : Nombre de résultats similaires à récupérer (par défaut : `5`)
  - `SCHEMA_PATH` : Chemin vers le fichier de schéma SQL (par défaut : `app/schemas/datasulting.sql`)

- **Sécurité** :
  - `API_KEY` : Clé API pour l'authentification (facultatif)
  - `API_KEY_NAME` : Nom de l'en-tête pour la clé API (par défaut : `X-API-Key`)
  - `ALLOWED_HOSTS` : Liste des hôtes autorisés, séparés par des virgules (par défaut : `*`)

## Intégration avec n8n

Pour intégrer cette API avec n8n :

1. Ajoutez un nœud HTTP Request dans votre workflow n8n.
2. Configurez le nœud comme suit :
   - Méthode : POST
   - URL : http://votre-serveur:8000/api/v1/translate
   - En-têtes : X-API-Key: votre_clé_api
   - Corps de la requête (JSON) :
     ```json
     {
       "query": "{{$input.item.json.query}}",
       "validate": true,
       "explain": true
     }
     ```

3. Vous pouvez ensuite utiliser la réponse dans les nœuds suivants de votre workflow, par exemple :
   - `{{$node["HTTP Request"].json.sql}}` pour la requête SQL générée
   - `{{$node["HTTP Request"].json.explanation}}` pour l'explication

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.

## Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou à soumettre une pull request.