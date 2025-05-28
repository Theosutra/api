import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import os
import asyncio

from app.config import get_settings
from app.api.routes import router
from app.security import configure_security

# Import des services (Service Layer)
from app.core.llm_service import initialize_llm_service, cleanup_llm_service
from app.services.translation_service import TranslationService
from app.services.validation_service import ValidationService

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Services globaux (initialisés au démarrage)
translation_service: TranslationService = None
validation_service: ValidationService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application avec Service Layer.
    Remplace les anciens on_event("startup") et on_event("shutdown").
    """
    global translation_service, validation_service
    
    # === STARTUP ===
    logger.info("🚀 Démarrage de NL2SQL API v2.0.0 - Service Layer Architecture")
    
    try:
        # 1. Initialiser le service LLM
        logger.info("📡 Initialisation du service LLM...")
        await initialize_llm_service()
        logger.info("✅ Service LLM initialisé avec succès")
        
        # 2. Initialiser les services métier
        logger.info("⚙️ Initialisation des services métier...")
        
        # Service de validation unifié
        validation_service = ValidationService(settings)
        logger.info("✅ Service de validation initialisé")
        
        # Service de traduction principal
        translation_service = TranslationService(settings)
        logger.info("✅ Service de traduction initialisé")
        
        # 3. Vérifier la santé des services
        logger.info("🔍 Vérification de la santé des services...")
        health_status = await translation_service.get_health_status()
        
        if health_status["status"] == "ok":
            logger.info("✅ Tous les services sont opérationnels")
        else:
            logger.warning(f"⚠️ Certains services présentent des problèmes:")
            for service_name, service_info in health_status["services"].items():
                if service_info.get("status") != "ok":
                    logger.warning(f"  - {service_name}: {service_info.get('status', 'unknown')}")
        
        # 4. Afficher les informations de configuration
        logger.info("📋 Configuration des services:")
        logger.info(f"  - Provider LLM par défaut: {settings.DEFAULT_PROVIDER}")
        logger.info(f"  - Cache activé: {settings.CACHE_ENABLED}")
        logger.info(f"  - Mode debug: {settings.DEBUG}")
        logger.info(f"  - Schéma: {settings.SCHEMA_PATH}")
        
        # 5. Afficher les providers LLM configurés
        try:
            from app.core.llm_service import LLMService
            configured_providers = LLMService.get_configured_providers()
            logger.info(f"  - Providers LLM configurés: {configured_providers}")
        except Exception as e:
            logger.warning(f"  - Impossible de récupérer les providers LLM: {e}")
        
        # 6. Test rapide des services critiques
        logger.info("🧪 Test rapide des services critiques...")
        try:
            # Test du service de validation
            test_sql = "SELECT * FROM test"
            is_valid, _ = validation_service.validate_sql_syntax(test_sql)
            if is_valid:
                logger.info("✅ Service de validation fonctionnel")
            else:
                logger.warning("⚠️ Service de validation: test de syntaxe échoué")
            
            # Test du service de traduction (basique)
            test_request = {"query": "test query"}
            is_valid_request, _ = translation_service.validate_translation_request(test_request)
            if is_valid_request:
                logger.info("✅ Service de traduction fonctionnel")
            else:
                logger.warning("⚠️ Service de traduction: validation de requête échouée")
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors des tests de services: {e}")
        
        logger.info("🎯 API prête à recevoir des requêtes - Service Layer activé")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage: {e}")
        logger.warning("L'application démarre malgré les erreurs d'initialisation")
    
    # Application prête - yield permet à FastAPI de continuer
    yield
    
    # === SHUTDOWN ===
    logger.info("🛑 Arrêt de NL2SQL API - Service Layer")
    
    try:
        # 1. Nettoyer les services métier
        logger.info("🧹 Nettoyage des services métier...")
        
        if translation_service:
            translation_service = None
            logger.info("✅ Service de traduction nettoyé")
        
        if validation_service:
            validation_service = None
            logger.info("✅ Service de validation nettoyé")
        
        # 2. Nettoyer le service LLM
        logger.info("🧹 Nettoyage du service LLM...")
        await cleanup_llm_service()
        logger.info("✅ Service LLM nettoyé")
        
        # 3. Nettoyer les autres services si nécessaire
        try:
            from app.core.embedding import cleanup_embedding_service
            await cleanup_embedding_service()
            logger.info("✅ Service d'embedding nettoyé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors du nettoyage d'embedding: {e}")
        
        try:
            from app.core.vector_search import cleanup_vector_service
            await cleanup_vector_service()
            logger.info("✅ Service de recherche vectorielle nettoyé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors du nettoyage vectoriel: {e}")
        
        try:
            from app.utils.cache import cleanup_cache_service
            await cleanup_cache_service()
            logger.info("✅ Service de cache nettoyé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors du nettoyage cache: {e}")
        
        logger.info("✅ Arrêt propre de l'application - Service Layer")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'arrêt: {e}")


# Créer l'application FastAPI avec le nouveau gestionnaire de cycle de vie
app = FastAPI(
    title="NL2SQL API",
    description="""
    API pour traduire des requêtes en langage naturel en SQL.
    Utilise une combinaison de recherche vectorielle et de génération via LLM pour produire des requêtes SQL optimisées.
    
    Version 2.0.0 - Architecture Service Layer avec validation unifiée.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan  # Nouveau gestionnaire de cycle de vie
)

# Configurer la sécurité de l'application
configure_security(app)

# Inclure les routes
app.include_router(router, prefix=settings.API_PREFIX)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware pour journaliser les requêtes et mesurer leur temps d'exécution.
    Version améliorée avec informations Service Layer.
    
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
        
        # Informations Service Layer dans les logs
        service_info = ""
        if "/translate" in url:
            service_info = " [TranslationService]"
        elif "/validate-framework" in url:
            service_info = " [ValidationService]"
        elif "/health" in url:
            service_info = " [HealthService]"
        
        logger.log(
            log_level,
            f"{status_emoji} {method} {url}{service_info} -> {response.status_code} ({process_time:.3f}s)"
        )
        
        # Ajouter les en-têtes de réponse
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        response.headers["X-API-Version"] = "2.0.0"
        response.headers["X-Architecture"] = "Service-Layer"
        
        return response
    
    except Exception as e:
        # Journaliser l'erreur
        process_time = time.time() - start_time
        logger.error(f"💥 {method} {url} -> ERROR ({process_time:.3f}s): {str(e)}", exc_info=True)
        
        # Renvoyer une réponse d'erreur enrichie
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Erreur interne du serveur: {str(e)}",
                "error_type": "internal_server_error",
                "request_id": id(request),  # Simple request ID pour le debugging
                "architecture": "service_layer"
            },
            headers={
                "X-Process-Time": f"{process_time:.3f}",
                "X-API-Version": "2.0.0",
                "X-Architecture": "Service-Layer"
            }
        )


@app.get("/", tags=["info"])
async def root():
    """
    Endpoint racine qui renvoie des informations de base sur l'API.
    Version Service Layer avec statistiques enrichies.
    
    Returns:
        Informations de base sur l'API avec statistiques des services
    """
    try:
        # Récupérer les informations via les services
        from app.core.llm_service import LLMService
        
        configured_providers = LLMService.get_configured_providers()
        available_models = await LLMService.get_available_models()
        
        # Statistiques des services
        service_stats = {
            "configured_providers": configured_providers,
            "total_models": len(available_models),
            "default_provider": settings.DEFAULT_PROVIDER,
            "services_initialized": {
                "translation_service": translation_service is not None,
                "validation_service": validation_service is not None,
                "llm_service": True,
                "cache_enabled": settings.CACHE_ENABLED
            }
        }
        
        return {
            "message": "🚀 Bienvenue sur l'API NL2SQL v2.0.0 - Service Layer!",
            "description": "API intelligente de traduction langage naturel vers SQL",
            "version": "2.0.0",
            "architecture": "Service Layer Pattern",
            "documentation": f"{settings.API_PREFIX}/docs",
            "redoc": f"{settings.API_PREFIX}/../redoc",
            "health_check": f"{settings.API_PREFIX}/health",
            "services": service_stats,
            "features": [
                "🧠 Multi-LLM (OpenAI, Anthropic, Google)",
                "🔍 Recherche vectorielle sémantique", 
                "🛡️ Framework de sécurité obligatoire",
                "💾 Cache Redis intelligent",
                "✅ Validation unifiée centralisée",
                "🔄 Retry automatique avec backoff",
                "🏗️ Architecture Service Layer",
                "📊 Health checks avancés"
            ],
            "endpoints": {
                "translate": f"{settings.API_PREFIX}/translate",
                "validate": f"{settings.API_PREFIX}/validate-framework",
                "models": f"{settings.API_PREFIX}/models",
                "schemas": f"{settings.API_PREFIX}/schemas",
                "cache_stats": f"{settings.API_PREFIX}/cache/stats"
            }
        }
    
    except Exception as e:
        logger.error(f"Erreur dans endpoint racine: {e}")
        return {
            "message": "🚀 Bienvenue sur l'API NL2SQL v2.0.0 - Service Layer!",
            "version": "2.0.0",
            "architecture": "Service Layer Pattern",
            "documentation": f"{settings.API_PREFIX}/docs",
            "status": "Service partiellement disponible",
            "error": "Impossible de récupérer les informations complètes des services"
        }


@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Endpoint pour récupérer les métriques de performance avec Service Layer.
    
    Returns:
        Métriques de performance de l'API et des services
    """
    try:
        from app.core.llm_service import LLMService
        
        # Métriques des services LLM
        llm_health = await LLMService.check_services_health()
        
        # Métriques de l'API
        metrics = {
            "api": {
                "version": "2.0.0",
                "architecture": "service_layer",
                "uptime": time.time(),  # Approximatif depuis le démarrage
                "timestamp": time.time()
            },
            "services": {
                "llm": llm_health,
                "translation": {
                    "status": "ok" if translation_service else "not_initialized",
                    "class": translation_service.__class__.__name__ if translation_service else None
                },
                "validation": {
                    "status": "ok" if validation_service else "not_initialized", 
                    "class": validation_service.__class__.__name__ if validation_service else None
                }
            }
        }
        
        # Ajouter les métriques de cache si disponibles
        try:
            from app.utils.cache import get_cache_stats
            cache_stats = await get_cache_stats()
            metrics["services"]["cache"] = cache_stats
        except Exception as e:
            metrics["services"]["cache"] = {"status": "error", "message": str(e)}
        
        # Ajouter les métriques du service de traduction si disponible
        if translation_service:
            try:
                translation_health = await translation_service.get_health_status()
                metrics["services"]["translation"]["health"] = translation_health
            except Exception as e:
                metrics["services"]["translation"]["health_error"] = str(e)
        
        return metrics
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques: {e}")
        return {
            "error": "Impossible de récupérer les métriques",
            "timestamp": time.time(),
            "architecture": "service_layer"
        }


@app.get("/service-info", tags=["monitoring"])
async def get_service_info():
    """
    Endpoint pour récupérer les informations détaillées des services.
    
    Returns:
        Informations détaillées sur l'architecture Service Layer
    """
    try:
        service_info = {
            "architecture": "Service Layer Pattern",
            "version": "2.0.0",
            "services": {
                "translation_service": {
                    "initialized": translation_service is not None,
                    "class": translation_service.__class__.__name__ if translation_service else None,
                    "description": "Service principal de traduction NL2SQL",
                    "responsibilities": [
                        "Orchestration du processus de traduction",
                        "Gestion des correspondances exactes",
                        "Coordination des validations",
                        "Formatage des réponses"
                    ]
                },
                "validation_service": {
                    "initialized": validation_service is not None,
                    "class": validation_service.__class__.__name__ if validation_service else None,
                    "description": "Service unifié de validation",
                    "responsibilities": [
                        "Validation syntaxique SQL",
                        "Validation de sécurité",
                        "Validation du framework obligatoire",
                        "Correction automatique",
                        "Validation sémantique"
                    ]
                },
                "llm_service": {
                    "description": "Service LLM avec Factory Pattern",
                    "responsibilities": [
                        "Gestion multi-provider LLM",
                        "Génération SQL",
                        "Validation sémantique",
                        "Explication des requêtes"
                    ]
                }
            },
            "benefits": [
                "Séparation claire des responsabilités",
                "Code plus maintenable et testable",
                "Réutilisabilité des services",
                "Gestion centralisée des erreurs",
                "Évolutivité simplifiée"
            ],
            "config": {
                "default_provider": settings.DEFAULT_PROVIDER,
                "cache_enabled": settings.CACHE_ENABLED,
                "debug_mode": settings.DEBUG
            }
        }
        
        return service_info
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des infos services: {e}")
        return {
            "error": "Impossible de récupérer les informations des services",
            "architecture": "service_layer"
        }


if __name__ == "__main__":
    # Récupérer le port à partir des variables d'environnement ou utiliser 8000 par défaut
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Configuration des logs pour le développement
    log_level = "debug" if settings.DEBUG else "info"
    
    # Démarrer le serveur
    logger.info(f"🚀 Démarrage du serveur NL2SQL API v2.0.0 - Service Layer")
    logger.info(f"📡 Host: {host}:{port}")
    logger.info(f"🔧 Debug: {settings.DEBUG}")
    logger.info(f"📝 Log level: {log_level}")
    logger.info(f"🏗️ Architecture: Service Layer Pattern")
    
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