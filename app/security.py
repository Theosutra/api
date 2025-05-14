from fastapi import Request, HTTPException, status, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
from app.config import get_settings

# Configuration du logger
logger = logging.getLogger(__name__)
settings = get_settings()


class AllowedHostsMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour restreindre les hôtes autorisés à accéder à l'API.
    Bloque les requêtes provenant d'hôtes non autorisés.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Vérifier que l'hôte est autorisé seulement si la liste est restrictive
        if settings.ALLOWED_HOSTS[0] != "*":
            host = request.headers.get("host", "").split(":")[0]
            if host not in settings.ALLOWED_HOSTS:
                logger.warning(f"Tentative d'accès depuis un hôte non autorisé: {host}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Hôte non autorisé: {host}"
                )
        response = await call_next(request)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour journaliser les requêtes entrantes et leur temps d'exécution.
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extraire les informations de la requête
        method = request.method
        url = str(request.url)
        client_host = request.client.host if request.client else "unknown"
        
        # Journaliser la requête entrante
        logger.info(f"Requête entrante: {method} {url} de {client_host}")
        
        # Traiter la requête
        response = await call_next(request)
        
        # Calculer la durée de traitement
        process_time = time.time() - start_time
        
        # Journaliser la réponse
        logger.info(f"Réponse: {response.status_code} en {process_time:.4f}s")
        
        # Ajouter un en-tête de temps de traitement
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


def configure_security(app: FastAPI) -> FastAPI:
    """
    Configure la sécurité de l'application FastAPI.
    Ajoute les middlewares nécessaires pour la sécurité et la journalisation.
    
    Args:
        app: L'instance FastAPI à configurer
        
    Returns:
        L'instance FastAPI configurée avec les middlewares
    """
    # Configuration CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS if settings.ALLOWED_HOSTS[0] != "*" else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Middleware de journalisation
    app.add_middleware(LoggingMiddleware)
    
    # Vérification des hôtes autorisés si la liste est restrictive
    if settings.ALLOWED_HOSTS[0] != "*":
        app.add_middleware(AllowedHostsMiddleware)
    
    # Configuration du niveau de journalisation en fonction du mode DEBUG
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    return app