# app/core/llm.py
import asyncio
import logging
from typing import Tuple, Optional, Dict, Any

from app.config import get_settings
from app.core.llm_service import LLMService

# Configuration du logger
logger = logging.getLogger(__name__)

# Récupérer les paramètres de configuration
settings = get_settings()


async def generate_sql(
    prompt: str, 
    provider: str = None,
    model: str = None, 
    temperature: float = None
) -> Optional[str]:
    """
    Envoie le prompt au service LLM et récupère la requête SQL générée.
    
    Args:
        prompt: Le prompt pour générer la requête SQL
        provider: Le fournisseur LLM à utiliser
        model: Le modèle LLM à utiliser
        temperature: La température pour la génération
        
    Returns:
        La requête SQL générée, ou None si la génération a échoué, "READONLY_VIOLATION" 
        si une violation a été détectée, ou "IMPOSSIBLE" si la requête est impossible
    """
    # Définir le message système et utilisateur
    messages = [
        {
            "role": "system", 
            "content": "Tu es un expert SQL spécialisé dans la traduction de langage naturel en requêtes SQL optimisées. Tu dois retourner UNIQUEMENT le code SQL, sans explications ni formatage markdown. Tu fais tout ton possible pour comprendre l'intention de l'utilisateur, même si la demande est vague."
        },
        {
            "role": "user", 
            "content": prompt
        }
    ]
    
    logger.debug(f"Génération de requête SQL avec le fournisseur {provider or settings.DEFAULT_PROVIDER} et le modèle {model or 'par défaut'}")
    
    try:
        # Générer la réponse via le service LLM
        generated_response = await LLMService.generate_completion(
            messages=messages,
            provider=provider,
            model=model,
            temperature=temperature
        )
        
        # Vérifier si la réponse est "READONLY_VIOLATION"
        if generated_response.upper() == "READONLY_VIOLATION":
            logger.info("Violation de lecture seule détectée")
            return "READONLY_VIOLATION"
        
        # Vérifier si la réponse est "IMPOSSIBLE"
        if generated_response.upper() == "IMPOSSIBLE":
            logger.info("La requête a été jugée impossible à traduire en SQL")
            return "IMPOSSIBLE"
        
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
            
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la requête SQL: {str(e)}")
        raise RuntimeError(f"Erreur lors de l'appel au service LLM: {str(e)}")


async def validate_sql_query(
    sql_query: str, 
    original_request: str, 
    schema: str, 
    provider: str = None,
    model: str = None
) -> Tuple[bool, str]:
    """
    Valide la requête SQL en vérifiant si elle correspond bien à la demande originale
    et si elle est compatible avec le schéma de la base de données.
    
    Args:
        sql_query: La requête SQL à valider
        original_request: La demande originale en langage naturel
        schema: Le schéma de la base de données
        provider: Le fournisseur LLM à utiliser
        model: Le modèle LLM à utiliser
        
    Returns:
        Un tuple (valid, message) où valid est un booléen indiquant si la requête est valide,
        et message est un message explicatif
    """
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
    
    messages = [
        {
            "role": "system", 
            "content": "Tu es un expert SQL qui valide la correspondance entre une demande utilisateur et une requête SQL générée. Ta priorité est d'être utile plutôt que strictement correct."
        },
        {
            "role": "user", 
            "content": prompt
        }
    ]
    
    logger.debug(f"Validation de la requête SQL avec le fournisseur {provider or settings.DEFAULT_PROVIDER}")
    
    try:
        # Générer la réponse via le service LLM
        validation_result = await LLMService.generate_completion(
            messages=messages,
            provider=provider,
            model=model,
            temperature=0.1  # Faible température pour une réponse plus déterministe
        )
        
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
    provider: str = None,
    model: str = None
) -> str:
    """
    Obtient une explication en langage naturel de ce que fait la requête SQL.
    
    Args:
        sql_query: La requête SQL à expliquer
        original_request: La demande originale en langage naturel
        provider: Le fournisseur LLM à utiliser
        model: Le modèle LLM à utiliser
        
    Returns:
        Une explication en langage naturel de la requête SQL
    """
    prompt = f"""Tu es un expert SQL chargé d'expliquer des requêtes SQL en langage simple.
    
La requête SQL suivante a été générée pour répondre à cette demande utilisateur: "{original_request}"

Requête SQL générée:
```sql
{sql_query}
```

Explique ce que fait cette requête SQL en une phrase courte et simple, sans termes techniques complexes.
Si la requête est éloignée de la demande originale, mentionne-le également de manière concise.
"""
    
    messages = [
        {
            "role": "system", 
            "content": "Tu es un expert SQL qui explique des requêtes SQL en langage simple et accessible."
        },
        {
            "role": "user", 
            "content": prompt
        }
    ]
    
    logger.debug(f"Génération d'explication pour la requête SQL avec le fournisseur {provider or settings.DEFAULT_PROVIDER}")
    
    try:
        # Générer la réponse via le service LLM
        explanation = await LLMService.generate_completion(
            messages=messages,
            provider=provider,
            model=model,
            temperature=0.3  # Température légèrement plus élevée pour une explication plus naturelle
        )
        
        logger.debug(f"Explication générée avec succès ({len(explanation)} caractères)")
        return explanation
    
    except Exception as e:
        logger.error(f"Erreur lors de l'obtention de l'explication SQL: {str(e)}")
        return "Impossible d'obtenir une explication pour cette requête."


async def check_query_relevance(
    user_query: str, 
    provider: str = None,
    model: str = None
) -> bool:
    """
    Vérifie si la requête utilisateur est pertinente pour une base de données RH.
    
    Args:
        user_query: La requête utilisateur à vérifier
        provider: Le fournisseur LLM à utiliser
        model: Le modèle LLM à utiliser
        
    Returns:
        True si la requête est pertinente pour une base de données RH, False sinon
    """
    prompt = f"""Tu es un expert en ressources humaines chargé de déterminer si une question est pertinente pour une base de données RH.

La base de données RH contient des informations sur :
- Dépôts de déclarations sociales (DSN)
- Employés (données personnelles, contrats, rémunérations)
- Entreprises et établissements
- Absences et arrêts de travail
- Types de contrats et statuts
- Paie et rémunérations

Question à évaluer : "{user_query}"

Cette question est-elle pertinente pour une interrogation de base de données RH ? 
Réponds UNIQUEMENT par "OUI" si la question concerne clairement les ressources humaines, ou "NON" si la question n'a aucun rapport avec les RH (par exemple, sport, météo, politique, etc.).
"""
    
    messages = [
        {
            "role": "system", 
            "content": "Tu es un expert en ressources humaines qui détermine si une question est pertinente pour une base de données RH."
        },
        {
            "role": "user", 
            "content": prompt
        }
    ]
    
    logger.debug(f"Vérification de la pertinence de la requête: '{user_query}'")
    
    try:
        # Générer la réponse via le service LLM
        validation_result = await LLMService.generate_completion(
            messages=messages,
            provider=provider,
            model=model,
            temperature=0.1  # Faible température pour une réponse plus déterministe
        )
        
        is_relevant = "OUI" in validation_result.upper() or "YES" in validation_result.upper()
        
        if not is_relevant:
            logger.info(f"Requête non pertinente détectée: '{user_query}'")
        
        return is_relevant
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de pertinence: {str(e)}")
        # En cas d'erreur, on considère la requête comme pertinente par défaut
        return True


async def check_llm_service() -> Dict[str, Any]:
    """
    Vérifie que les services LLM fonctionnent correctement.
    
    Returns:
        Dictionnaire indiquant le statut des services
    """
    services_status = {}
    
    # Vérifier OpenAI
    if settings.OPENAI_API_KEY:
        try:
            messages = [{"role": "user", "content": "Hello"}]
            await LLMService._generate_openai(messages, temperature=0.1)
            services_status["openai"] = {
                "status": "ok",
                "model": settings.DEFAULT_OPENAI_MODEL
            }
        except Exception as e:
            services_status["openai"] = {
                "status": "error",
                "message": str(e)
            }
    else:
        services_status["openai"] = {
            "status": "not_configured"
        }
    
    # Vérifier Anthropic
    if settings.ANTHROPIC_API_KEY:
        try:
            messages = [{"role": "user", "content": "Hello"}]
            await LLMService._generate_anthropic(messages, temperature=0.1)
            services_status["anthropic"] = {
                "status": "ok",
                "model": settings.DEFAULT_ANTHROPIC_MODEL
            }
        except Exception as e:
            services_status["anthropic"] = {
                "status": "error",
                "message": str(e)
            }
    else:
        services_status["anthropic"] = {
            "status": "not_configured"
        }
    
    # Vérifier Google
    if settings.GOOGLE_API_KEY:
        try:
            messages = [{"role": "user", "content": "Hello"}]
            await LLMService._generate_google(messages, temperature=0.1)
            services_status["google"] = {
                "status": "ok",
                "model": settings.DEFAULT_GOOGLE_MODEL
            }
        except Exception as e:
            services_status["google"] = {
                "status": "error",
                "message": str(e)
            }
    else:
        services_status["google"] = {
            "status": "not_configured"
        }
    
    # Déterminer le statut global
    global_status = "ok"
    default_provider = settings.DEFAULT_PROVIDER
    
    if default_provider in services_status and services_status[default_provider]["status"] != "ok":
        global_status = "error"
    
    return {
        "status": global_status,
        "default_provider": default_provider,
        "providers": services_status
    }