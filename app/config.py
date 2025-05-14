# app/config.py - Solution directe pour les problèmes de Pydantic v2
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configuration de l'application avec Pydantic.
    Lit les variables d'environnement ou le fichier .env
    """
    # Clés API
    PINECONE_API_KEY: str = Field(..., env="PINECONE_API_KEY")
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    
    # Paramètres de Pinecone
    PINECONE_INDEX_NAME: str = Field("nl2sql", env="PINECONE_INDEX_NAME")
    PINECONE_ENVIRONMENT: str = Field("gcp-starter", env="PINECONE_ENVIRONMENT")
    
    # Paramètres du modèle d'embedding
    EMBEDDING_MODEL: str = Field("all-mpnet-base-v2", env="EMBEDDING_MODEL")
    
    # Paramètres OpenAI
    OPENAI_MODEL: str = Field("gpt-4o", env="OPENAI_MODEL")
    OPENAI_TEMPERATURE: float = Field(0.2, env="OPENAI_TEMPERATURE")
    OPENAI_TIMEOUT: int = Field(30, env="OPENAI_TIMEOUT")
    
    # Paramètres de traduction
    EXACT_MATCH_THRESHOLD: float = Field(0.95, env="EXACT_MATCH_THRESHOLD")
    TOP_K_RESULTS: int = Field(5, env="TOP_K_RESULTS")
    SCHEMA_PATH: str = Field("app/schemas/datasulting.sql", env="SCHEMA_PATH")
    
    # Paramètres de l'API
    API_PREFIX: str = Field("/api/v1", env="API_PREFIX")
    
    # Sécurité
    API_KEY: Optional[str] = Field(None, env="API_KEY")
    API_KEY_NAME: str = Field("X-API-Key", env="API_KEY_NAME")
    ALLOWED_HOSTS: List[str] = Field(["*"], env="ALLOWED_HOSTS")
    SQL_READ_ONLY: bool = Field(True, env="SQL_READ_ONLY")  # Restreint aux requêtes SELECT uniquement
    
    # Cache Redis
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    REDIS_TTL: int = Field(3600, env="REDIS_TTL")  # 1 heure par défaut
    CACHE_ENABLED: bool = Field(True, env="CACHE_ENABLED")
    
    # Paramètres serveur
    DEBUG: bool = Field(False, env="DEBUG")
    
    # Variables supplémentaires trouvées dans le fichier .env
    ADMIN_SECRET: Optional[str] = Field(None, env="ADMIN_SECRET")
    METRICS_ENABLED: bool = Field(False, env="METRICS_ENABLED")
    
    # Validateur pour ALLOWED_HOSTS pour supporter le format avec virgules
    @classmethod
    def validate_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(',')]
        return v
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_file_encoding": "utf-8",
        # Si vous voulez aussi ignorer d'autres champs inconnus dans le futur
        "extra": "ignore"  # Permet les champs supplémentaires non déclarés
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Récupère les paramètres de configuration avec mise en cache.
    Cette fonction est décorée avec lru_cache pour éviter de relire
    les paramètres à chaque appel.
    """
    return Settings()