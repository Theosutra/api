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
    
    # Paramètres serveur
    DEBUG: bool = Field(False, env="DEBUG")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """
    Récupère les paramètres de configuration avec mise en cache.
    Cette fonction est décorée avec lru_cache pour éviter de relire
    les paramètres à chaque appel.
    """
    return Settings()