import asyncio
import aiohttp
import logging
import json
from typing import Tuple, Optional, Dict, Any

from app.config import get_settings

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


async def generate_sql(
    prompt: str, 
    model: str = None, 
    temperature: float = None
) -> Optional[str]:
    """
    Envoie le prompt à l'API OpenAI et récupère la requête SQL générée.
    
    Args:
        prompt: Le prompt pour générer la requête SQL
        model: Le modèle OpenAI à utiliser (par défaut, celui de la configuration)
        temperature: La température pour la génération (par défaut, celle de la configuration)
        
    Returns:
        La requête SQL générée, ou None si la génération a échoué ou retourné "IMPOSSIBLE"
        
    Raises:
        RuntimeError: Si une erreur se produit lors de l'appel à l'API OpenAI
    """
    # Utiliser les paramètres par défaut si non spécifiés
    if model is None:
        model = settings.OPENAI_MODEL
    
    if temperature is None:
        temperature = settings.OPENAI_TEMPERATURE
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": "Tu es un expert SQL spécialisé dans la traduction de langage naturel en requêtes SQL optimisées. Tu dois retourner UNIQUEMENT le code SQL, sans explications ni formatage markdown. Tu fais tout ton possible pour comprendre l'intention de l'utilisateur, même si la demande est vague."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": temperature
    }
    
    logger.debug(f"Génération de requête SQL avec le modèle {model} (temperature: {temperature})")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.OPENAI_TIMEOUT
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Erreur OpenAI ({response.status}): {error_text}")
                    raise RuntimeError(f"Erreur lors de l'appel à l'API OpenAI: {response.status} - {error_text}")
                
                result = await response.json()
                
                # Extraire la réponse
                generated_response = result["choices"][0]["message"]["content"].strip()
                
                # Vérifier si la réponse est "IMPOSSIBLE"
                if generated_response.upper() == "IMPOSSIBLE":
                    logger.info("La requête a été jugée impossible à traduire en SQL")
                    return None
                
                # Retirer les blocs de code markdown si présents
                if generated_response.startswith("```sql"):
                    generated_response = generated_response.replace("```sql", "", 1)
                    if generated_response.endswith("```"):
                        generated_response = generated_response[:-3]
                elif generated_response.startswith("```"):
                    generated_response = generated_response.replace("```", "", 1)
                    if generated_response.endswith("```"):
                        generated_response = generated_response[:-3]
                
                generated_response = generated_response.strip()
                
                logger.debug(f"Requête SQL générée avec succès ({len(generated_response)} caractères)")
                return generated_response
    
    except aiohttp.ClientError as e:
        logger.error(f"Erreur de connexion à l'API OpenAI: {str(e)}")
        raise RuntimeError(f"Erreur de connexion à l'API OpenAI: {str(e)}")
    
    except json.JSONDecodeError as e:
        logger.error(f"Erreur lors du décodage de la réponse OpenAI: {str(e)}")
        raise RuntimeError(f"Réponse invalide de l'API OpenAI: {str(e)}")
    
    except asyncio.TimeoutError:
        logger.error(f"Timeout lors de l'appel à l'API OpenAI")
        raise RuntimeError(f"Délai d'attente dépassé lors de l'appel à l'API OpenAI")
    
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'appel à l'API OpenAI: {str(e)}")
        raise RuntimeError(f"Erreur lors de l'appel à l'API OpenAI: {str(e)}")


async def validate_sql_query(
    sql_query: str, 
    original_request: str, 
    schema: str, 
    model: str = None
) -> Tuple[bool, str]:
    """
    Valide la requête SQL en vérifiant si elle correspond bien à la demande originale
    et si elle est compatible avec le schéma de la base de données.
    
    Args:
        sql_query: La requête SQL à valider
        original_request: La demande originale en langage naturel
        schema: Le schéma de la base de données
        model: Le modèle OpenAI à utiliser (par défaut, celui de la configuration)
        
    Returns:
        Un tuple (valid, message) où valid est un booléen indiquant si la requête est valide,
        et message est un message explicatif
    """
    # Utiliser le modèle par défaut si non spécifié
    if model is None:
        model = settings.OPENAI_MODEL
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
    }
    
    prompt = f"""Tu es un expert SQL chargé d'analyser et de valider des requêtes SQL.
    
La requête SQL suivante a été générée pour répondre à cette demande utilisateur: "{original_request}"

Requête SQL générée:
```sql
{sql_query}
```

Voici le schéma de la base de données:
```sql
{schema}
```

TÂCHE:
1. Vérifie si la demande utilisateur concerne une requête SQL sur cette base de données. Tu dois uniquement répondre "HORS SUJET" si la demande est totalement sans rapport (par exemple, une recette de cuisine ou une prévision météo).
2. Si la demande concerne la base de données, analyse si la requête SQL est compatible avec le schéma fourni.
3. Évalue si la requête répond à l'intention de l'utilisateur, même partiellement.
4. RÉPONDS UNIQUEMENT PAR "OUI" ou "NON" à la question: Cette requête SQL répond-elle correctement à la demande de l'utilisateur et est-elle compatible avec le schéma de la base de données?
"""
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": "Tu es un expert SQL qui valide la correspondance entre une demande utilisateur et une requête SQL générée. Ta priorité est d'être utile plutôt que strictement correct."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 50
    }
    
    logger.debug(f"Validation de la requête SQL avec le modèle {model}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.OPENAI_TIMEOUT
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Erreur OpenAI ({response.status}): {error_text}")
                    return None, f"Erreur lors de la validation: {response.status}"
                
                result = await response.json()
                validation_result = result["choices"][0]["message"]["content"].strip()
                
                # Vérifier si la demande est hors sujet
                if "HORS SUJET" in validation_result.upper():
                    logger.info("La demande a été jugée hors sujet")
                    return False, "Cette demande ne semble pas concerner une requête SQL sur cette base de données. Veuillez reformuler ou préciser votre demande."
                
                # On extrait OUI ou NON de la réponse
                if "OUI" in validation_result.upper():
                    logger.info("La requête SQL a été validée")
                    return True, "La requête SQL correspond bien à votre demande et est compatible avec le schéma."
                elif "NON" in validation_result.upper():
                    logger.warning("La requête SQL n'a pas été validée")
                    return False, "La requête SQL pourrait ne pas correspondre parfaitement à votre demande ou contenir des erreurs. Veuillez vérifier les résultats."
                else:
                    # Si la réponse n'est pas clairement OUI ou NON, on penche vers la validation
                    logger.info("Validation incertaine, on considère la requête comme valide")
                    return True, "La requête SQL semble correspondre à votre demande, mais pourrait nécessiter des ajustements."
    
    except Exception as e:
        logger.error(f"Erreur lors de la validation de la requête SQL: {str(e)}")
        return False, f"Impossible de valider la requête SQL: {str(e)}"


async def get_sql_explanation(
    sql_query: str, 
    original_request: str, 
    model: str = None
) -> str:
    """
    Obtient une explication en langage naturel de ce que fait la requête SQL.
    
    Args:
        sql_query: La requête SQL à expliquer
        original_request: La demande originale en langage naturel
        model: Le modèle OpenAI à utiliser (par défaut, celui de la configuration)
        
    Returns:
        Une explication en langage naturel de la requête SQL
    """
    # Utiliser le modèle par défaut si non spécifié
    if model is None:
        model = settings.OPENAI_MODEL
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
    }
    
    prompt = f"""Tu es un expert SQL chargé d'expliquer des requêtes SQL en langage simple.
    
La requête SQL suivante a été générée pour répondre à cette demande utilisateur: "{original_request}"

Requête SQL générée:
```sql
{sql_query}
```

Explique ce que fait cette requête SQL en une phrase courte et simple, sans termes techniques complexes.
"""
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": "Tu es un expert SQL qui explique des requêtes SQL en langage simple et accessible."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 100
    }
    
    logger.debug(f"Génération d'explication pour la requête SQL avec le modèle {model}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.OPENAI_TIMEOUT
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Erreur OpenAI ({response.status}): {error_text}")
                    return "Impossible d'obtenir une explication pour cette requête."
                
                result = await response.json()
                explanation = result["choices"][0]["message"]["content"].strip()
                
                logger.debug(f"Explication générée avec succès ({len(explanation)} caractères)")
                return explanation
    
    except Exception as e:
        logger.error(f"Erreur lors de l'obtention de l'explication SQL: {str(e)}")
        return "Impossible d'obtenir une explication pour cette requête."


async def check_openai_service() -> dict:
    """
    Vérifie que le service OpenAI fonctionne correctement.
    
    Returns:
        Dictionnaire indiquant le statut du service
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
    }
    
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 5
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.OPENAI_TIMEOUT
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "status": "error",
                        "message": f"Erreur API ({response.status}): {error_text}"
                    }
                
                result = await response.json()
                
                return {
                    "status": "ok",
                    "model": settings.OPENAI_MODEL,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
                }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }