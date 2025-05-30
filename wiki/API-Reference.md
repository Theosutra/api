# 📖 Référence API Complète

Documentation détaillée de tous les endpoints de NL2SQL API v2.0.0 avec exemples réels et formats de réponse.

## 🌐 Base URL

```
https://your-domain.com/api/v1
```

**En développement** :
```
http://localhost:8000/api/v1
```

## 🔐 Authentification

### API Key (Optionnelle)

Si configurée, ajoutez l'en-tête d'authentification :

```http
X-API-Key: your_secret_api_key
```

**Configuration** :
```env
API_KEY=your_secret_api_key  # Optionnel
API_KEY_NAME=X-API-Key       # Nom de l'en-tête
```

## 🔄 Endpoint Principal : Traduction NL2SQL

### `POST /translate`

Traduit une requête en langage naturel en SQL optimisé.

#### Paramètres de Requête

```json
{
  "query": "string",                    // OBLIGATOIRE
  "provider": "openai|anthropic|google", // Optionnel
  "model": "string",                    // Optionnel  
  "validate": true,                     // Optionnel
  "explain": true,                      // Optionnel
  "use_cache": true,                    // Optionnel
  "include_similar_details": false,     // Optionnel
  "schema_path": "string",              // Optionnel
  "user_id_placeholder": "?"            // Optionnel
}
```

#### Description des Paramètres

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `query` | `string` | **REQUIS** | Question en langage naturel (3-1000 caractères) |
| `provider` | `string` | `"openai"` | Fournisseur LLM : `openai`, `anthropic`, `google` |
| `model` | `string` | auto | Modèle spécifique (ex: `gpt-4o`, `claude-3-opus-20240229`) |
| `validate` | `boolean` | `true` | Activer la validation complète de la requête SQL |
| `explain` | `boolean` | `true` | Générer une explication en langage naturel |
| `use_cache` | `boolean` | `true` | Utiliser le cache Redis si disponible |
| `include_similar_details` | `boolean` | `false` | Inclure les détails des 5 vecteurs similaires |
| `schema_path` | `string` | auto | Chemin personnalisé vers le schéma SQL |
| `user_id_placeholder` | `string` | `"?"` | Placeholder pour l'ID utilisateur dans le SQL |

#### Exemples de Requêtes

<details>
<summary><b>Requête Simple</b></summary>

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Combien d'\''employés en CDI ?"
  }'
```

</details>

<details>
<summary><b>Requête Avancée avec Anthropic</b></summary>

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "query": "Quel est l'\''âge moyen de mes collaborateurs par département ?",
    "provider": "anthropic",
    "model": "claude-3-opus-20240229",
    "include_similar_details": true,
    "use_cache": false
  }'
```

</details>

<details>
<summary><b>Requête avec Google Gemini</b></summary>

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Liste des top 10 salaires en 2023",
    "provider": "google",
    "model": "gemini-1.5-pro",
    "explain": true,
    "include_similar_details": true
  }'
```

</details>

#### Format de Réponse

```json
{
  "query": "string",                    // Requête originale
  "sql": "string",                      // SQL généré
  "valid": true,                        // Validation réussie
  "validation_message": "string",       // Message de validation
  "explanation": "string",              // Explication en français
  "is_exact_match": false,              // Trouvé dans la base
  "status": "success|warning|error",    // Statut de traitement
  "processing_time": 2.34,              // Temps en secondes
  "similar_queries": null,              // Format simple (rétrocompatibilité)
  "similar_queries_details": [...],     // Détails complets des vecteurs
  "framework_compliant": true,          // Respect du framework sécurité
  "framework_details": {...},          // Détails framework (debug)
  "from_cache": false,                  // Résultat du cache
  "provider": "openai",                 // Provider utilisé
  "model": "gpt-4o"                     // Modèle utilisé
}
```

#### Exemple de Réponse Complète

<details>
<summary><b>Réponse Success avec Requêtes Similaires</b></summary>

```json
{
  "query": "Quel est l'âge moyen de mes collaborateurs ?",
  "sql": "SELECT ROUND(AVG(TRUNCATE(b.AGE, 0)), 2) AS Age_Moyen\nFROM depot a\nINNER JOIN facts b ON a.ID = b.ID_NUMDEPOT\nWHERE a.ID_USER = ?\nAND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)\nAND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (\n    SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))\n    FROM depot w\n    WHERE w.periode IN (#PERIODE#)\n    AND w.id_user = a.id_user\n);\n#DEPOT_a# #FACTS_b# #PERIODE#",
  "valid": true,
  "validation_message": "Validation complète réussie",
  "explanation": "Cette requête calcule l'âge moyen des collaborateurs d'un utilisateur spécifique, en tenant compte uniquement de ceux qui sont encore en contrat. Elle se base sur les informations les plus récentes disponibles pour cet utilisateur.",
  "is_exact_match": false,
  "status": "success",
  "processing_time": 8.979,
  "similar_queries": null,
  "similar_queries_details": [
    {
      "score": 0.724,
      "texte_complet": "Age moyen par établissement",
      "requete": "SELECT STRAIGHT_JOIN concat(d.DENOMINATION, ' - ', d.ADRESSE2), ROUND(AVG(b.AGE), 2) FROM depot a INNER JOIN facts b ON (a.ID=b.ID_NUMDEPOT) INNER JOIN entreprise d ON (CONCAT(a.SIREN, a.nic)=d.SIRET) WHERE a.ID_USER=? #DEPOT_a# #FACTS_b# group BY a.siren, a.nic",
      "id": "gemini_load_1748246903_1381"
    },
    {
      "score": 0.7164,
      "texte_complet": "EFFECTIFS - Personnes Physiques - âge moyen",
      "requete": "select 'Age moyen' Union select round(avg(truncate(datediff(p.datefin,c.date_nai)/365.25,0)),2) from (select distinct a.id_user, a.siren, a.nic, b.matricule, b.date_nai from depot a inner join facts b on (a.ID=b.ID_NUMDEPOT) where a.ID_USER=?) c inner join referentiel_periode p on (c.id_user=p.id_user) where p.id_user=?",
      "id": "gemini_load_1748246903_365"
    }
  ],
  "framework_compliant": true,
  "framework_details": {
    "compliant": true,
    "message": "Requête conforme au framework obligatoire",
    "elements": {
      "has_user_filter": true,
      "has_depot_table": true,
      "has_hashtags": true,
      "is_select_query": true,
      "depot_aliases": ["a", "w"],
      "facts_aliases": ["b"],
      "found_hashtags": ["PERIODE", "DEPOT_a", "FACTS_b", "PERIODE"]
    }
  },
  "from_cache": false,
  "provider": "openai",
  "model": "gpt-4o"
}
```

</details>

#### Codes de Statut HTTP

| Code | Statut | Description |
|------|--------|-------------|
| `200` | ✅ Success | Traduction réussie |
| `200` | ⚠️ Warning | SQL généré avec corrections |
| `206` | 🔧 Partial | Framework corrigé automatiquement |
| `400` | ❌ Bad Request | Paramètres invalides |
| `401` | 🔐 Unauthorized | Clé API invalide |
| `403` | 🚫 Forbidden | Opération non autorisée |
| `422` | 🛡️ Framework Error | Framework non conforme |
| `429` | ⏱️ Rate Limited | Trop de requêtes |
| `503` | 🔧 Service Unavailable | Service LLM indisponible |

## 🏥 Health Check

### `GET /health`

Vérifie l'état de santé de tous les services.

#### Réponse

```json
{
  "status": "ok|error",
  "version": "2.0.0",
  "services": {
    "pinecone": {
      "status": "ok",
      "index": "kpi-to-sql-gemini",
      "vector_count": 2500,
      "test_successful": true
    },
    "llm": {
      "status": "ok",
      "default_provider": "openai",
      "providers": {
        "openai": {"status": "ok", "model": "gpt-4o"},
        "anthropic": {"status": "ok", "model": "claude-3-opus-20240229"},
        "google": {"status": "ok", "model": "gemini-pro"}
      }
    },
    "embedding": {
      "status": "ok",
      "model": "text-embedding-004",
      "provider": "google",
      "dimensions": 768
    },
    "cache": {
      "status": "ok",
      "memory_used": "2.1M",
      "hit_rate": 87.5
    },
    "prompts": {
      "status": "ok",
      "templates": ["sql_generation.j2", "sql_validation.j2"],
      "template_count": 2
    }
  }
}
```

## 🤖 Modèles Disponibles

### `GET /models`

Liste tous les modèles LLM disponibles.

#### Réponse

```json
{
  "models": [
    {
      "provider": "openai",
      "id": "gpt-4o",
      "name": "GPT-4o"
    },
    {
      "provider": "openai", 
      "id": "gpt-4o-mini",
      "name": "GPT-4o Mini"
    },
    {
      "provider": "anthropic",
      "id": "claude-3-opus-20240229",
      "name": "Claude 3 Opus"
    },
    {
      "provider": "google",
      "id": "gemini-1.5-pro",
      "name": "Gemini 1.5 Pro"
    }
  ]
}
```

## 📋 Schémas Disponibles

### `GET /schemas`

Liste les fichiers de schéma SQL disponibles.

#### Réponse

```json
[
  "datasulting.md",
  "custom_schema.sql",
  "test_schema.sql"
]
```

## ✅ Validation Framework

### `POST /validate-framework`

Valide qu'une requête SQL respecte le framework obligatoire.

#### Paramètres

```json
{
  "sql_query": "string",              // OBLIGATOIRE
  "user_id_placeholder": "?"          // Optionnel
}
```

#### Exemple

```bash
curl -X POST "http://localhost:8000/api/v1/validate-framework" \
  -H "Content-Type: application/json" \
  -d '{
    "sql_query": "SELECT f.NOM FROM facts f WHERE f.ID_USER = ?;"
  }'
```

#### Réponse

```json
{
  "sql_query": "SELECT f.NOM FROM facts f WHERE f.ID_USER = ?;",
  "framework_compliant": false,
  "message": "Éléments manquants: table DEPOT, hashtags (#DEPOT_alias#)",
  "details": {
    "has_user_filter": true,
    "has_depot_table": false,
    "has_hashtags": false,
    "is_select_query": true
  },
  "corrected_query": "SELECT f.NOM FROM depot a INNER JOIN facts f ON a.ID = f.ID_NUMDEPOT WHERE a.ID_USER = ?; #DEPOT_a# #FACTS_f#"
}
```

## 🎯 Système de Prompts Jinja2

### `GET /prompts/templates`

Liste les templates de prompts Jinja2 disponibles.

#### Réponse

```json
{
  "status": "ok",
  "templates": {
    "sql_generation.j2": {
      "macros": [
        "system_message",
        "generate_sql_prompt",
        "check_relevance_prompt",
        "explain_sql_prompt"
      ],
      "valid": true,
      "macro_count": 4
    },
    "sql_validation.j2": {
      "macros": [
        "semantic_validation_prompt",
        "framework_validation_prompt"
      ],
      "valid": true,
      "macro_count": 2
    }
  },
  "total_templates": 2,
  "jinja2_available": true
}
```

### `POST /prompts/render-test`

Teste le rendu d'une macro de prompt avec des paramètres.

#### Paramètres Query

- `template_name`: Nom du template (ex: `sql_generation.j2`)
- `macro_name`: Nom de la macro (ex: `generate_sql_prompt`)

#### Body

```json
{
  "user_query": "test query",
  "schema": "test schema",
  "context": {"period": "2023"}
}
```

## 💾 Gestion du Cache

### `GET /cache/stats`

Statistiques du cache Redis.

#### Réponse

```json
{
  "status": "ok",
  "memory_used": "2.1M",
  "connected_clients": 3,
  "total_commands_processed": 1547,
  "keyspace_hits": 234,
  "keyspace_misses": 45,
  "hit_rate": 83.87
}
```

### `POST /cache/invalidate`

Invalide les entrées de cache correspondant à un motif.

#### Paramètres Query

- `pattern`: Motif de clé (défaut: `nl2sql:*`)

#### Exemple

```bash
curl -X POST "http://localhost:8000/api/v1/cache/invalidate?pattern=nl2sql:translation:*"
```

#### Réponse

```json
{
  "status": "success",
  "pattern": "nl2sql:translation:*",
  "invalidated_keys": 12,
  "message": "12 clés invalidées"
}
```

## 🐛 Debug (Mode Développement)

### `GET /debug/service-status`

Statut détaillé des services (disponible uniquement si `DEBUG=true`).

#### Réponse

```json
{
  "health": {
    "status": "ok",
    "services": {...}
  },
  "debug": {
    "translation_service": {
      "class": "TranslationService",
      "config": {
        "default_provider": "openai",
        "cache_enabled": true
      },
      "prompt_manager": {
        "available": true,
        "class": "PromptManager"
      }
    },
    "validation_service": {
      "class": "ValidationService",
      "patterns_count": {
        "forbidden_operations": 9,
        "framework_patterns": 4,
        "injection_patterns": 7
      }
    }
  },
  "timestamp": 1717065626.31
}
```

## 🔧 Configuration via API

### `GET /validation/suggestions`

Obtient des suggestions pour corriger une requête SQL.

#### Paramètres Query

- `sql_query`: Requête SQL à analyser

#### Exemple

```bash
curl -X GET "http://localhost:8000/api/v1/validation/suggestions?sql_query=SELECT%20*%20FROM%20facts"
```

#### Réponse

```json
{
  "sql_query": "SELECT * FROM facts",
  "suggestions": [
    "Ajoutez la table DEPOT avec un alias (ex: DEPOT a)",
    "Ajoutez le filtre WHERE a.ID_USER = ?",
    "Ajoutez les hashtags appropriés (#DEPOT_a# #FACTS_b#)"
  ],
  "count": 3
}
```

## 📊 Endpoints d'Information

### `GET /`

Information générale sur l'API avec statistiques.

### `GET /metrics`

Métriques de performance de l'API.

### `GET /service-info`

Informations détaillées sur l'architecture Service Layer.

## 🚨 Gestion d'Erreurs

### Format d'Erreur Standard

```json
{
  "detail": "string",              // Message d'erreur principal
  "error_type": "string",          // Type d'erreur
  "suggestions": ["string"],       // Suggestions d'amélioration
  "query": "string",               // Requête originale (si applicable)
  "debug_info": {                  // Informations de debug
    "sql_generated": false,
    "framework_compliant": false,
    "processing_time": 1.23
  }
}
```

### Types d'Erreurs

| Type | Description | Action Recommandée |
|------|-------------|-------------------|
| `relevance` | Question hors RH | Reformuler pour inclure des termes RH |
| `framework` | Non-conformité sécurité | Vérifier les règles obligatoires |
| `llm_service` | Service LLM indisponible | Réessayer ou changer de provider |
| `validation` | Données invalides | Corriger les paramètres d'entrée |
| `semantic` | Requête ambiguë | Être plus spécifique |

## 📝 Exemples d'Intégration

### Python avec requests

```python
import requests

class NL2SQLClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def translate(self, query, **kwargs):
        data = {"query": query, **kwargs}
        response = requests.post(
            f"{self.base_url}/translate",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self):
        response = requests.get(f"{self.base_url}/health")
        return response.json()

# Utilisation
client = NL2SQLClient("http://localhost:8000/api/v1", "your_api_key")

# Traduction simple
result = client.translate("Combien d'employés en CDI ?")
print(f"SQL: {result['sql']}")

# Traduction avancée
result = client.translate(
    "Âge moyen des collaborateurs par département",
    provider="anthropic",
    include_similar_details=True,
    use_cache=False
)

for similar in result.get("similar_queries_details", []):
    print(f"Similaire: {similar['score']:.3f} - {similar['texte_complet']}")
```

### JavaScript/Node.js

```javascript
class NL2SQLClient {
    constructor(baseUrl, apiKey = null) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json',
            ...(apiKey && { 'X-API-Key': apiKey })
        };
    }

    async translate(query, options = {}) {
        const response = await fetch(`${this.baseUrl}/translate`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ query, ...options })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }
        
        return response.json();
    }

    async healthCheck() {
        const response = await fetch(`${this.baseUrl}/health`);
        return response.json();
    }
}

// Utilisation
const client = new NL2SQLClient('http://localhost:8000/api/v1', 'your_api_key');

// Traduction avec gestion d'erreurs
try {
    const result = await client.translate(
        "Liste des salaires moyens par département",
        { 
            provider: "google",
            model: "gemini-1.5-pro",
            include_similar_details: true
        }
    );
    
    console.log('SQL généré:', result.sql);
    console.log('Explication:', result.explanation);
    
    if (result.similar_queries_details) {
        console.log('Requêtes similaires:');
        result.similar_queries_details.forEach((item, index) => {
            console.log(`${index + 1}. Score: ${item.score.toFixed(3)} - ${item.texte_complet}`);
        });
    }
    
} catch (error) {
    console.error('Erreur de traduction:', error.message);
}
```

### cURL Avancé

```bash
#!/bin/bash

# Configuration
API_BASE="http://localhost:8000/api/v1"
API_KEY="your_api_key"

# Fonction de traduction
translate_query() {
    local query="$1"
    local provider="${2:-openai}"
    
    curl -s -X POST "${API_BASE}/translate" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${API_KEY}" \
        -d "{
            \"query\": \"${query}\",
            \"provider\": \"${provider}\",
            \"include_similar_details\": true,
            \"explain\": true
        }" | jq '.'
}

# Health check
echo "=== Health Check ==="
curl -s "${API_BASE}/health" | jq '.services | keys[]'

# Tests de traduction
echo "=== Test OpenAI ==="
translate_query "Combien d'employés en CDI ?" "openai"

echo "=== Test Anthropic ==="
translate_query "Âge moyen par département" "anthropic"

echo "=== Test Google ==="
translate_query "Top 10 salaires 2023" "google"
```

## 📊 Limites et Quotas

### Limites par Défaut

| Limite | Valeur | Configuration |
|--------|--------|---------------|
| **Taille requête** | 1000 caractères | `query` max length |
| **Rate limiting** | 60 req/min/IP | `rate_limit()` middleware |
| **Timeout LLM** | 30 secondes | `LLM_TIMEOUT` |
| **Cache TTL** | 1 heure | `REDIS_TTL` |
| **Top-K résultats** | 5 vecteurs | `TOP_K_RESULTS` |
| **Correspondance exacte** | Seuil 0.95 | `EXACT_MATCH_THRESHOLD` |

### Optimisation des Performances

**Utilisation du Cache** :
```json
{
  "query": "votre question",
  "use_cache": true,          // Utiliser le cache Redis
  "provider": "openai"        // Cache par provider
}
```

**Requêtes Similaires Conditionnelles** :
```json
{
  "query": "votre question",
  "include_similar_details": false,  // Économise la bande passante
  "explain": false                   // Plus rapide sans explication
}
```

## 🔐 Sécurité API

### Headers de Sécurité

L'API ajoute automatiquement :

```http
X-Process-Time: 2.340
X-API-Version: 2.0.0
X-Architecture: Service-Layer
```

### Validation des Entrées

- **Sanitisation** : Caractères de contrôle supprimés
- **Validation longueur** : 3-1000 caractères
- **Détection injection** : Patterns SQL suspects
- **Whitelist providers** : Seuls les providers configurés

### Framework de Sécurité SQL

Toutes les requêtes SQL générées respectent :

1. **Filtre utilisateur** : `WHERE depot.ID_USER = ?`
2. **Table de sécurité** : DEPOT toujours présente
3. **Hashtags traçabilité** : `#DEPOT_alias# #FACTS_alias#`
4. **Lecture seule** : Uniquement SELECT

## 📈 Monitoring API

### Métriques Automatiques

```http
GET /metrics
```

**Métriques disponibles** :
- Temps de réponse par endpoint
- Taux de succès/erreur
- Distribution par provider LLM
- Utilisation du cache (hit/miss rate)
- Qualité des vecteurs similaires

### Logs Structurés

**Format standard** :
```
2025-05-30 09:20:26 - app.services.translation_service - INFO - 
Traduction terminée en 9.524s (statut: success, framework: conforme, vecteurs similaires: 5)
```

**Niveaux de logs** :
- `DEBUG` : Détails techniques (si `DEBUG=true`)
- `INFO` : Opérations normales
- `WARNING` : Problèmes non critiques
- `ERROR` : Erreurs nécessitant attention

## 🚀 Nouveautés v2.0.0

### Endpoints Ajoutés

- `GET /prompts/templates` - Gestion prompts Jinja2
- `POST /prompts/render-test` - Test de rendu prompts
- `GET /prompts/health` - Santé système prompts
- `GET /debug/service-status` - Debug services (dev)
- `GET /validation/suggestions` - Suggestions validation

### Réponses Enrichies

**Nouveaux champs** :
- `similar_queries_details` - Détails complets vecteurs
- `framework_details` - Debug framework sécurité
- `provider` + `model` - Traçabilité LLM utilisé
- `from_cache` - Provenance cache

### Gestion d'Erreurs Améliorée

**Format enrichi** :
```json
{
  "detail": "Message principal",
  "error_type": "relevance|framework|llm_service|validation",
  "suggestions": ["Suggestion 1", "Suggestion 2"],
  "debug_info": {
    "sql_generated": true,
    "framework_compliant": false,
    "processing_time": 2.34
  }
}
```

## ❓ FAQ API

<details>
<summary><b>Comment choisir le bon provider LLM ?</b></summary>

**Recommandations par cas d'usage** :
- **OpenAI (GPT-4o)** : Équilibre qualité/vitesse, bon par défaut
- **Anthropic (Claude)** : Meilleur pour requêtes complexes
- **Google (Gemini)** : Plus rapide, bon pour requêtes simples

</details>

<details>
<summary><b>Que signifient les scores des requêtes similaires ?</b></summary>

Les scores vont de 0 à 1 :
- **0.95-1.0** : Correspondance quasi-exacte
- **0.85-0.95** : Très similaire  
- **0.70-0.85** : Moyennement similaire
- **< 0.70** : Peu similaire

</details>

<details>
<summary><b>Comment optimiser les performances ?</b></summary>

1. **Utiliser le cache** : `"use_cache": true`
2. **Provider rapide** : `"provider": "google"`
3. **Pas d'explication** : `"explain": false`
4. **Moins de détails** : `"include_similar_details": false`

</details>

<details>
<summary><b>Comment débugger une erreur ?</b></summary>

1. Vérifiez `/health` pour l'état des services
2. Regardez le `error_type` dans la réponse d'erreur
3. Suivez les `suggestions` fournies
4. Consultez les logs avec `DEBUG=true`

</details>

---

## 🎯 Navigation

**Précédent** : [Service Layer Architecture](Service-Layer-Architecture)  
**Suivant** : [Exemples d'Utilisation](Usage-Examples)

**Voir aussi** :
- [Guide de Démarrage Rapide](Quick-Start-Guide)
- [Configuration Complète](Configuration-Guide)
- [Gestion des Erreurs](Error-Handling)

---

*Documentation API NL2SQL v2.0.0 - Interface moderne pour la traduction intelligente NL2SQL* 📖✨