import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import os

from app.config import get_settings
from app.api.routes import router
from app.security import configure_security

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
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configurer la sécurité de l'application
configure_security(app)

# Inclure les routes
app.include_router(router, prefix=settings.API_PREFIX)


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
    
    # Journaliser la requête entrante
    logger.info(f"Requête entrante: {method} {url} de {client_host}")
    
    try:
        # Traiter la requête
        response = await call_next(request)
        
        # Calculer la durée de traitement
        process_time = time.time() - start_time
        
        # Journaliser la réponse
        logger.info(f"Réponse: {response.status_code} en {process_time:.4f}s")
        
        # Ajouter un en-tête de temps de traitement
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    except Exception as e:
        # Journaliser l'erreur
        logger.error(f"Erreur lors du traitement de la requête: {str(e)}", exc_info=True)
        
        # Calculer la durée de traitement
        process_time = time.time() - start_time
        
        # Renvoyer une réponse d'erreur
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erreur interne du serveur: {str(e)}"}
        )


@app.get("/", tags=["info"])
async def root():
    """
    Endpoint racine qui renvoie des informations de base sur l'API.
    
    Returns:
        Informations de base sur l'API
    """
    return {
        "message": "Bienvenue sur l'API NL2SQL!",
        "documentation": f"{settings.API_PREFIX}/docs",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    # Récupérer le port à partir des variables d'environnement ou utiliser 8000 par défaut
    port = int(os.environ.get("PORT", 8000))
    
    # Démarrer le serveur
    logger.info(f"Démarrage du serveur sur le port {port}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )