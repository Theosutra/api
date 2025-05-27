import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import os
import asyncio

from app.config import get_settings
from app.api.routes import router
from app.security import configure_security

# Import du nouveau service LLM
from app.core.llm_service import initialize_llm_service, cleanup_llm_service

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Créer l'application FastAPI
app = FastAPI(
    title="NL2SQL API",
    description="""
    API pour traduire des requêtes en langage naturel en SQL.
    Utilise une combinaison de recherche vectorielle et de génération via LLM pour produire des requêtes SQL optimisées.
    
    Version 2.0.0 - Architecture optimisée avec Factory Pattern pour les LLM.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configurer la sécurité de l'application
configure_security(app)

# Inclure les routes
app.include_router(router, prefix=settings.API_PREFIX)


@app.on_event("startup")
async def startup_event():
    """
    Événements de démarrage de l'application.
    
    Initialise tous les services nécessaires au bon fonctionnement de l'API.
    """
    logger.info("🚀 Démarrage de NL2SQL API v2.0.0")
    
    try:
        # Initialiser le service LLM avec la nouvelle architecture
        logger.info("Initialisation du service LLM...")
        await initialize_llm_service()
        logger.info("✅ Service LLM initialisé avec succès")
        
        # Vérifier les services essentiels
        logger.info("Vérification des services...")
        from app.core.translator import health_check
        health_status = await health_check()
        
        if health_status["status"] == "ok":
            logger.info("✅ Tous les services sont opérationnels")
        else:
            logger.warning(f"⚠️ Certains services présentent des problèmes: {health_status}")
        
        # Afficher les providers LLM configurés
        from app.core.llm_service import LLMService
        configured_providers = LLMService.get_configured_providers()
        logger.info(f"📋 Providers LLM configurés: {configured_providers}")
        
        logger.info("🎯 API prête à recevoir des requêtes")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage: {e}")
        # Ne pas faire planter l'application, mais alerter
        logger.warning("L'application démarre malgré les erreurs d'initialisation")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Événements d'arrêt de l'application.
    
    Nettoie proprement toutes les ressources avant l'arrêt.
    """
    logger.info("🛑 Arrêt de NL2SQL API")
    
    try:
        # Nettoyer le service LLM
        logger.info("Nettoyage du service LLM...")
        await cleanup_llm_service()
        logger.info("✅ Service LLM nettoyé")
        
        logger.info("✅ Arrêt propre de l'application")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'arrêt: {e}")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware pour journaliser les requêtes et mesurer leur temps d'exécution.
    
    Args:
        request: L'objet Request de FastAPI
        call_next: La fonction à appeler pour traiter la requête
        
    Returns:
        La réponse HTTP
    """
    start_time = time.time()
    
    # Extraire les informations de la requête
    method = request.method
    url = str(request.url)
    client_host = request.client.host if request.client else "unknown"
    
    # Journaliser la requête entrante (niveau DEBUG pour éviter le spam)
    logger.debug(f"📨 {method} {url} <- {client_host}")
    
    try:
        # Traiter la requête
        response = await call_next(request)
        
        # Calculer la durée de traitement
        process_time = time.time() - start_time
        
        # Journaliser la réponse avec niveau approprié
        log_level = logging.INFO if response.status_code < 400 else logging.WARNING
        status_emoji = "✅" if response.status_code < 400 else "⚠️" if response.status_code < 500 else "❌"
        
        logger.log(
            log_level,
            f"{status_emoji} {method} {url} -> {response.status_code} ({process_time:.3f}s)"
        )
        
        # Ajouter un en-tête de temps de traitement
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        response.headers["X-API-Version"] = "2.0.0"
        
        return response
    
    except Exception as e:
        # Journaliser l'erreur
        process_time = time.time() - start_time
        logger.error(f"💥 {method} {url} -> ERROR ({process_time:.3f}s): {str(e)}", exc_info=True)
        
        # Renvoyer une réponse d'erreur
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Erreur interne du serveur: {str(e)}",
                "error_type": "internal_server_error",
                "request_id": id(request)  # Simple request ID pour le debugging
            },
            headers={
                "X-Process-Time": f"{process_time:.3f}",
                "X-API-Version": "2.0.0"
            }
        )


@app.get("/", tags=["info"])
async def root():
    """
    Endpoint racine qui renvoie des informations de base sur l'API.
    
    Returns:
        Informations de base sur l'API avec statistiques des providers
    """
    try:
        # Récupérer les informations sur les providers configurés
        from app.core.llm_service import LLMService
        configured_providers = LLMService.get_configured_providers()
        available_models = await LLMService.get_available_models()
        
        return {
            "message": "🚀 Bienvenue sur l'API NL2SQL v2.0.0!",
            "description": "API intelligente de traduction langage naturel vers SQL",
            "version": "2.0.0",
            "architecture": "Factory Pattern optimisé",
            "documentation": f"{settings.API_PREFIX}/docs",
            "redoc": f"{settings.API_PREFIX}/../redoc",
            "health_check": f"{settings.API_PREFIX}/health",
            "providers": {
                "configured": configured_providers,
                "default": settings.DEFAULT_PROVIDER,
                "total_models": len(available_models)
            },
            "features": [
                "Multi-LLM (OpenAI, Anthropic, Google)",
                "Recherche vectorielle sémantique", 
                "Framework de sécurité obligatoire",
                "Cache Redis intelligent",
                "Validation avancée",
                "Retry automatique avec backoff"
            ]
        }
    
    except Exception as e:
        logger.error(f"Erreur dans endpoint racine: {e}")
        return {
            "message": "🚀 Bienvenue sur l'API NL2SQL v2.0.0!",
            "version": "2.0.0",
            "documentation": f"{settings.API_PREFIX}/docs",
            "status": "Service partiellement disponible",
            "error": "Impossible de récupérer les informations des providers"
        }


@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Endpoint pour récupérer les métriques de performance (optionnel).
    
    Returns:
        Métriques de performance de l'API
    """
    try:
        # Récupérer les statistiques du service LLM
        health_status = await LLMService.check_services_health()
        
        # Métriques de base
        metrics = {
            "api_version": "2.0.0",
            "llm_services": health_status,
            "timestamp": time.time()
        }
        
        # Ajouter les statistiques HTTP si disponibles
        # (pourrait être étendu avec un système de métriques plus avancé)
        
        return metrics
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques: {e}")
        return {
            "error": "Impossible de récupérer les métriques",
            "timestamp": time.time()
        }


if __name__ == "__main__":
    # Récupérer le port à partir des variables d'environnement ou utiliser 8000 par défaut
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Configuration des logs pour le développement
    log_level = "debug" if settings.DEBUG else "info"
    
    # Démarrer le serveur
    logger.info(f"🚀 Démarrage du serveur NL2SQL API v2.0.0")
    logger.info(f"📡 Host: {host}:{port}")
    logger.info(f"🔧 Debug: {settings.DEBUG}")
    logger.info(f"📝 Log level: {log_level}")
    
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=settings.DEBUG,
            log_level=log_level,
            access_log=settings.DEBUG,  # Logs d'accès uniquement en debug
            server_header=False,  # Cacher la version uvicorn
            date_header=False     # Pas besoin du header date
        )
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"💥 Erreur fatale lors du démarrage: {e}")
        exit(1)