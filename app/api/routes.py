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
from app.core.translator import translate_nl_to_sql, health_check
from app.core.llm_service import LLMService
from app.dependencies import get_api_key, rate_limit
from app.utils.schema_loader import get_available_schemas

# Configuration du logger
logger = logging.getLogger(__name__)

# Créer le routeur d'API
router = APIRouter(
    tags=["nl2sql"],
    dependencies=[Depends(get_api_key)]
)


@router.post(
    "/translate",
    response_model=SQLTranslationResponse,
    summary="Traduire du langage naturel en SQL",
    description="Traduit une requête en langage naturel en SQL optimisé avec respect du framework obligatoire (filtre ID_USER, hashtags). Permet de choisir le fournisseur LLM et le modèle. Option pour inclure les détails complets des vecteurs similaires.",
    response_description="La requête SQL générée et les métadonnées associées, avec validation du framework"
)
async def translate_to_sql(
    request: SQLTranslationRequest,
    req: Request,
    include_similar: bool = False  # Pour rétrocompatibilité (format simplifié)
):
    """
    Endpoint principal pour traduire une requête en langage naturel en SQL.
    Intègre la validation du framework obligatoire et le choix du provider/modèle.
    
    Args:
        request: La requête contenant le texte en langage naturel et les paramètres
        req: L'objet Request de FastAPI (pour la limitation de débit)
        include_similar: Indique si les requêtes similaires doivent être incluses dans la réponse (format simplifié, rétrocompatibilité)
        
    Returns:
        SQLTranslationResponse: La requête SQL correspondante et les métadonnées associées, 
                              avec informations sur la conformité au framework
    """
    # Appliquer la limitation de débit
    await rate_limit(req)
    
    try:
        # Appel à la fonction principale de traduction avec tous les paramètres
        result = await translate_nl_to_sql(
            user_query=request.query,
            schema_path=request.schema_path,
            validate=request.should_validate,
            explain=request.explain,
            store_result=False,  # Toujours stocker les résultats pour améliorer la base de connaissances
            return_similar_queries=include_similar,  # Format simplifié pour rétrocompatibilité
            user_id_placeholder=request.user_id_placeholder,
            use_cache=request.use_cache,
            provider=request.provider,
            model=request.model,
            include_similar_details=request.include_similar_details  # NOUVEAU : Détails complets des vecteurs
        )
        
        # Si la traduction a échoué, renvoyer une erreur
        if result["status"] == "error" and result["sql"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result["validation_message"] or "Impossible de traduire la requête"
            )
        
        # Convertir le résultat en modèle de réponse avec tous les champs
        response_data = {
            "query": request.query,
            "sql": result["sql"],
            "valid": result["valid"],
            "validation_message": result["validation_message"],
            "explanation": result["explanation"],
            "is_exact_match": result["is_exact_match"],
            "status": result["status"],
            "processing_time": result["processing_time"],
            "similar_queries": result["similar_queries"],  # Format simplifié (rétrocompatibilité)
            "similar_queries_details": result["similar_queries_details"],  # NOUVEAU : Détails complets
            "framework_compliant": result.get("framework_compliant", False),
            "framework_details": result.get("framework_details"),
            "from_cache": result.get("from_cache", False),
            "provider": result.get("provider"),
            "model": result.get("model")
        }
        
        response = SQLTranslationResponse(**response_data)
        
        # Déterminer le code de statut HTTP approprié
        if result["status"] == "success":
            if not result.get("framework_compliant", False):
                # Si le framework n'est pas respecté, retourner un avertissement
                return JSONResponse(
                    status_code=status.HTTP_206_PARTIAL_CONTENT,
                    content=response.dict()
                )
            else:
                # Succès complet
                return response
        elif result["status"] == "warning":
            # Avertissement (framework respecté mais autres problèmes mineurs)
            return JSONResponse(
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                content=response.dict()
            )
        else:
            # Erreur
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result["validation_message"] or "Erreur lors de la traduction"
            )
    
    except HTTPException:
        # Re-propager les HTTPException
        raise
    
    except Exception as e:
        logger.error(f"Erreur lors de la traduction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la traduction: {str(e)}"
        )


@router.get(
    "/models",
    response_model=AvailableModelsResponse,
    summary="Obtenir les modèles LLM disponibles",
    description="Récupère la liste des modèles LLM disponibles par fournisseur (OpenAI, Anthropic, Google)."
)
async def get_available_models():
    """
    Endpoint pour récupérer la liste des modèles LLM disponibles.
    
    Returns:
        Liste des modèles disponibles par provider
    """
    try:
        models = await LLMService.get_available_models()
        return AvailableModelsResponse(models=models)
    
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
    """
    Endpoint pour récupérer la liste des schémas SQL disponibles.
    
    Returns:
        Liste des noms de fichiers de schéma disponibles
    """
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
    description="Vérifie l'état de santé des services dépendants (Pinecone, LLM providers, SentenceTransformer, Redis)."
)
async def get_health():
    """
    Endpoint pour vérifier l'état de santé de l'API et de ses dépendances.
    
    Returns:
        État de santé des services
    """
    try:
        result = await health_check()
        
        # Si l'un des services est en erreur, renvoyer un code 503
        if result["status"] != "ok":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=result
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de santé: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la vérification de santé: {str(e)}"
        )


@router.post(
    "/validate-framework",
    response_model=SQLFrameworkValidationResponse,
    summary="Valider le framework d'une requête SQL",
    description="Valide qu'une requête SQL respecte le framework obligatoire (filtre ID_USER, hashtags, etc.)"
)
async def validate_framework(
    request: SQLFrameworkValidationRequest
):
    """
    Endpoint pour valider qu'une requête SQL respecte le framework obligatoire.
    Utile pour tester des requêtes SQL existantes.
    
    Args:
        request: Requête contenant la SQL à valider et les paramètres
        
    Returns:
        Résultat de la validation du framework
    """
    try:
        from app.utils.simple_framework_check import validate_framework_compliance, add_missing_framework_elements
        
        framework_compliant, framework_message = validate_framework_compliance(request.sql_query)
        
        # Préparer les détails de validation
        details = {
            "has_user_filter": "ID_USER" in request.sql_query.upper(),
            "has_depot_table": "DEPOT" in request.sql_query.upper(),
            "has_hashtags": "#" in request.sql_query,
            "is_select_query": request.sql_query.strip().upper().startswith("SELECT")
        }
        
        # Si non conforme, essayer de corriger
        corrected_query = None
        if not framework_compliant:
            corrected_query = add_missing_framework_elements(request.sql_query)
        
        return SQLFrameworkValidationResponse(
            sql_query=request.sql_query,
            framework_compliant=framework_compliant,
            message=framework_message,
            details=details,
            corrected_query=corrected_query
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la validation du framework: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la validation du framework: {str(e)}"
        )