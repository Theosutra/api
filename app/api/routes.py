from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
import logging
import time
from typing import Optional, List

from app.api.models import (
    SQLTranslationRequest, SQLTranslationResponse, HealthCheckResponse,
    SQLFrameworkValidationRequest, SQLFrameworkValidationResponse,
    AvailableModelsResponse
)
from app.core.llm_service import LLMService
from app.dependencies import get_api_key, rate_limit
from app.utils.schema_loader import get_available_schemas

# IMPORTS SERVICE LAYER (remplace translator.py)
from app.services.translation_service import TranslationService
from app.services.validation_service import ValidationService
from app.core.exceptions import (
    LLMError, LLMNetworkError, LLMAuthError, LLMQuotaError,
    ValidationError, FrameworkError, EmbeddingError, 
    VectorSearchError, SchemaError, CacheError
)

# Configuration du logger
logger = logging.getLogger(__name__)

# Créer le routeur d'API
router = APIRouter(
    tags=["nl2sql"],
    dependencies=[Depends(get_api_key)]
)

# Initialisation des services (singleton pattern)
_translation_service = None
_validation_service = None

def get_translation_service() -> TranslationService:
    """Récupère l'instance du service de traduction (singleton)."""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service

def get_validation_service() -> ValidationService:
    """Récupère l'instance du service de validation (singleton)."""
    global _validation_service
    if _validation_service is None:
        _validation_service = ValidationService()
    return _validation_service


@router.post(
    "/translate",
    response_model=SQLTranslationResponse,
    summary="Traduire du langage naturel en SQL",
    description="Traduit une requête en langage naturel en SQL optimisé avec respect du framework obligatoire (filtre ID_USER, hashtags). Service Layer architecture avec validation unifiée.",
    response_description="La requête SQL générée et les métadonnées associées, avec validation du framework"
)
async def translate_to_sql(
    request: SQLTranslationRequest,
    req: Request,
    include_similar: bool = False  # Pour rétrocompatibilité (format simplifié)
):
    """
    Endpoint principal pour traduire une requête en langage naturel en SQL.
    Version simplifiée utilisant le Service Layer pattern.
    
    Args:
        request: La requête contenant le texte en langage naturel et les paramètres
        req: L'objet Request de FastAPI (pour la limitation de débit)
        include_similar: Indique si les requêtes similaires doivent être incluses dans la réponse
        
    Returns:
        SQLTranslationResponse: La requête SQL correspondante et les métadonnées
    """
    # Appliquer la limitation de débit
    try:
        await rate_limit(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la limitation de débit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne lors de la vérification du débit"
        )
    
    # Récupérer le service de traduction
    translation_service = get_translation_service()
    
    try:
        # Validation préalable de la requête
        is_valid, validation_message = translation_service.validate_translation_request(request.dict())
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_message
            )
        
        # Appel au service de traduction centralisé
        result = await translation_service.translate(
            user_query=request.query,
            schema_path=request.schema_path,
            validate=request.should_validate,
            explain=request.explain,
            store_result=False,  # Politique de stockage définie par l'équipe
            return_similar_queries=include_similar,
            user_id_placeholder=request.user_id_placeholder,
            use_cache=request.use_cache,
            provider=request.provider,
            model=request.model,
            include_similar_details=request.include_similar_details
        )
        
        # Vérifier le résultat
        if result["status"] == "error":
            # Déterminer le code d'erreur HTTP approprié selon le message
            error_message = result.get("validation_message", "Erreur lors de la traduction")
            
            if any(keyword in error_message.lower() for keyword in ["non autorisée", "readonly", "destructive"]):
                status_code = status.HTTP_403_FORBIDDEN
            elif any(keyword in error_message.lower() for keyword in ["pertinente", "concerne", "ressources humaines"]):
                status_code = status.HTTP_400_BAD_REQUEST
            elif any(keyword in error_message.lower() for keyword in ["service llm", "indisponible", "temporairement"]):
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            elif any(keyword in error_message.lower() for keyword in ["framework", "conforme"]):
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            else:
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            
            # Ajouter des suggestions d'amélioration
            error_type = "generic"
            if "pertinente" in error_message.lower():
                error_type = "relevance"
            elif "framework" in error_message.lower():
                error_type = "framework"
            elif "service llm" in error_message.lower():
                error_type = "llm_service"
            
            suggestions = translation_service.get_translation_suggestions(error_type, {"message": error_message})
            
            # Réponse d'erreur enrichie
            error_response = {
                "detail": error_message,
                "error_type": error_type,
                "suggestions": suggestions[:3],  # Limiter à 3 suggestions
                "query": request.query
            }
            
            raise HTTPException(status_code=status_code, detail=error_response)
        
        # Créer la réponse de succès
        response = SQLTranslationResponse(**result)
        
        # Déterminer le code de statut HTTP
        if result["status"] == "success":
            if not result.get("framework_compliant", False):
                # Framework non respecté mais corrigé
                return JSONResponse(
                    status_code=status.HTTP_206_PARTIAL_CONTENT,
                    content=response.dict()
                )
            else:
                # Succès complet
                return response
        elif result["status"] == "warning":
            # Avertissement
            return JSONResponse(
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                content=response.dict()
            )
        else:
            # Erreur non gérée
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get("validation_message", "Erreur lors de la traduction")
            )
    
    # Gestion spécialisée des exceptions avec le Service Layer
    except ValidationError as e:
        logger.warning(f"Erreur de validation: {e}")
        suggestions = translation_service.get_translation_suggestions("validation", {"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Données d'entrée invalides: {str(e)}",
                "suggestions": suggestions[:2]
            }
        )
    
    except FrameworkError as e:
        logger.warning(f"Erreur de framework: {e}")
        suggestions = translation_service.get_translation_suggestions("framework", {"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": f"Requête non conforme au framework de sécurité: {str(e)}",
                "suggestions": suggestions[:2]
            }
        )
    
    except (LLMAuthError, LLMQuotaError) as e:
        logger.error(f"Erreur LLM critique: {e}")
        suggestions = translation_service.get_translation_suggestions("llm_service", {"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"Service LLM temporairement indisponible: {e.message}",
                "suggestions": suggestions[:2]
            }
        )
    
    except LLMNetworkError as e:
        logger.error(f"Erreur réseau LLM: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"Erreur de connexion au service LLM: {e.message}",
                "retry_after": "30"
            }
        )
    
    except LLMError as e:
        logger.error(f"Erreur LLM générique: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erreur du service LLM: {e.message}"
        )
    
    except (EmbeddingError, VectorSearchError) as e:
        logger.error(f"Erreur de service interne: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur du service interne: {str(e)}"
        )
    
    except SchemaError as e:
        logger.error(f"Erreur de schéma: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de configuration du schéma: {str(e)}"
        )
    
    except CacheError as e:
        logger.warning(f"Erreur de cache (retry sans cache): {e}")
        # Retry automatique sans cache
        try:
            result = await translation_service.translate(
                user_query=request.query,
                schema_path=request.schema_path,
                validate=request.should_validate,
                explain=request.explain,
                store_result=False,
                return_similar_queries=include_similar,
                user_id_placeholder=request.user_id_placeholder,
                use_cache=False,  # Forcer sans cache
                provider=request.provider,
                model=request.model,
                include_similar_details=request.include_similar_details
            )
            result["from_cache"] = False
            return SQLTranslationResponse(**result)
        
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service temporairement indisponible"
            )
    
    except HTTPException:
        # Re-propager les HTTPException
        raise
    
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la traduction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne du serveur: {str(e)}"
        )


@router.get(
    "/models",
    response_model=AvailableModelsResponse,
    summary="Obtenir les modèles LLM disponibles",
    description="Récupère la liste des modèles LLM disponibles par fournisseur (OpenAI, Anthropic, Google)."
)
async def get_available_models():
    """Endpoint pour récupérer la liste des modèles LLM disponibles."""
    try:
        models = await LLMService.get_available_models()
        return AvailableModelsResponse(models=models)
    
    except (LLMError, LLMNetworkError, LLMAuthError) as e:
        logger.error(f"Erreur LLM lors de la récupération des modèles: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Impossible de récupérer les modèles: {e.message}"
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modèles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des modèles: {str(e)}"
        )


@router.get(
    "/schemas",
    response_model=List[str],
    summary="Obtenir les schémas disponibles",
    description="Récupère la liste des fichiers de schéma SQL disponibles dans le répertoire app/schemas."
)
async def get_schemas():
    """Endpoint pour récupérer la liste des schémas SQL disponibles."""
    try:
        schemas = await get_available_schemas()
        return schemas
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des schémas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des schémas: {str(e)}"
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Vérifier l'état de santé",
    description="Vérifie l'état de santé des services dépendants via le Service Layer."
)
async def get_health():
    """Endpoint pour vérifier l'état de santé de l'API et de ses dépendances."""
    try:
        translation_service = get_translation_service()
        result = await translation_service.get_health_status()
        
        # Si l'un des services est en erreur, renvoyer un code 503
        if result["status"] != "ok":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=result
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de santé: {str(e)}")
        error_result = {
            "status": "error",
            "version": "2.0.0", 
            "services": {},
            "error": f"Erreur lors de la vérification: {str(e)}"
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_result
        )


@router.post(
    "/validate-framework",
    response_model=SQLFrameworkValidationResponse,
    summary="Valider le framework d'une requête SQL",
    description="Valide qu'une requête SQL respecte le framework obligatoire via le Service de Validation unifié."
)
async def validate_framework(request: SQLFrameworkValidationRequest):
    """
    Endpoint pour valider qu'une requête SQL respecte le framework obligatoire.
    Utilise le service de validation unifié.
    """
    try:
        validation_service = get_validation_service()
        
        # Validation complète via le service unifié
        validation_result = await validation_service.validate_complete(
            sql_query=request.sql_query,
            auto_fix=True
        )
        
        # Préparer la réponse
        framework_details = validation_result["details"].get("framework", {})
        
        return SQLFrameworkValidationResponse(
            sql_query=request.sql_query,
            framework_compliant=validation_result["valid"],
            message=validation_result["message"],
            details=framework_details.get("elements", {}),
            corrected_query=validation_result["final_query"] if validation_result["corrected"] else None
        )
    
    except ValidationError as e:
        logger.warning(f"Erreur de validation framework: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Données d'entrée invalides: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la validation du framework: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la validation du framework: {str(e)}"
        )


@router.get(
    "/cache/stats",
    summary="Statistiques du cache",
    description="Récupère les statistiques du cache Redis via le Service Layer."
)
async def get_cache_stats():
    """Endpoint pour récupérer les statistiques du cache."""
    try:
        from app.utils.cache import get_cache_stats
        stats = await get_cache_stats()
        return stats
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats cache: {e}")
        return {
            "status": "error", 
            "message": f"Erreur: {str(e)}"
        }


@router.post(
    "/cache/invalidate",
    summary="Invalider le cache",
    description="Invalide les entrées de cache correspondant à un motif."
)
async def invalidate_cache(pattern: str = "nl2sql:*"):
    """Endpoint pour invalider le cache."""
    try:
        from app.utils.cache import cache_pattern_invalidate
        
        validation_service = get_validation_service()
        
        # Valider le pattern
        if not pattern or not isinstance(pattern, str):
            raise ValidationError("Le motif doit être une chaîne non vide", "pattern", pattern)
        
        # Sécurité: limiter aux clés nl2sql uniquement
        if not pattern.startswith("nl2sql:"):
            pattern = f"nl2sql:{pattern}"
        
        count = await cache_pattern_invalidate(pattern)
        
        return {
            "status": "success",
            "pattern": pattern,
            "invalidated_keys": count,
            "message": f"{count} clés invalidées"
        }
    
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation cache: {e}")
        return {
            "status": "error",
            "message": f"Erreur: {str(e)}",
            "invalidated_keys": 0
        }


@router.get(
    "/validation/suggestions",
    summary="Suggestions de validation",
    description="Obtient des suggestions pour corriger une requête SQL non conforme."
)
async def get_validation_suggestions(sql_query: str):
    """
    Endpoint pour obtenir des suggestions de validation.
    Utilise le service de validation unifié.
    """
    try:
        validation_service = get_validation_service()
        
        # Valider l'entrée
        if not sql_query or len(sql_query.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sql_query est obligatoire"
            )
        
        # Obtenir les suggestions
        suggestions = validation_service.get_validation_suggestions(sql_query)
        
        return {
            "sql_query": sql_query,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération de suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération de suggestions: {str(e)}"
        )


@router.get(
    "/debug/service-status",
    summary="Statut détaillé des services",
    description="Endpoint de debug pour obtenir le statut détaillé de tous les services (développement uniquement)."
)
async def get_detailed_service_status():
    """
    Endpoint de debug pour obtenir le statut détaillé des services.
    À utiliser uniquement en développement.
    """
    # Vérifier que nous sommes en mode debug
    from app.config import get_settings
    settings = get_settings()
    
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint non disponible en production"
        )
    
    try:
        translation_service = get_translation_service()
        validation_service = get_validation_service()
        
        # Récupérer le statut complet
        health_status = await translation_service.get_health_status()
        
        # Ajouter des informations de debug
        debug_info = {
            "translation_service": {
                "class": translation_service.__class__.__name__,
                "config": {
                    "default_provider": translation_service.config.DEFAULT_PROVIDER,
                    "cache_enabled": translation_service.config.CACHE_ENABLED,
                    "debug": translation_service.config.DEBUG
                }
            },
            "validation_service": {
                "class": validation_service.__class__.__name__,
                "patterns_count": {
                    "forbidden_operations": len(validation_service.forbidden_operations),
                    "framework_patterns": len(validation_service.framework_patterns),
                    "injection_patterns": len(validation_service.injection_patterns)
                }
            }
        }
        
        return {
            "health": health_status,
            "debug": debug_info,
            "timestamp": time.time()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut de debug: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du statut: {str(e)}"
        )


