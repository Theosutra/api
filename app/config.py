from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configuration de l'application avec Pydantic.
    Lit les variables d'environnement ou le fichier .env
    """
    # Clés API (requis)
    PINECONE_API_KEY: str = Field(..., env="PINECONE_API_KEY")
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    GOOGLE_API_KEY: Optional[str] = Field(None, env="GOOGLE_API_KEY")
    
    # Paramètres Pinecone
    PINECONE_INDEX_NAME: str = Field("kpi-to-sql", env="PINECONE_INDEX_NAME")
    PINECONE_ENVIRONMENT: str = Field("gcp-starter", env="PINECONE_ENVIRONMENT")
    
    # Paramètres du modèle d'embedding
    EMBEDDING_MODEL: str = Field("all-mpnet-base-v2", env="EMBEDDING_MODEL")
    
    # Paramètres LLM
    DEFAULT_PROVIDER: str = Field("openai", env="DEFAULT_PROVIDER")
    DEFAULT_OPENAI_MODEL: str = Field("gpt-4o", env="DEFAULT_OPENAI_MODEL")
    DEFAULT_ANTHROPIC_MODEL: str = Field("claude-3-opus-20240229", env="DEFAULT_ANTHROPIC_MODEL")
    DEFAULT_GOOGLE_MODEL: str = Field("gemini-pro", env="DEFAULT_GOOGLE_MODEL")
    LLM_TEMPERATURE: float = Field(0.2, env="LLM_TEMPERATURE")
    LLM_TIMEOUT: int = Field(30, env="LLM_TIMEOUT")
    
    # Paramètres de traduction
    EXACT_MATCH_THRESHOLD: float = Field(0.95, env="EXACT_MATCH_THRESHOLD")
    TOP_K_RESULTS: int = Field(5, env="TOP_K_RESULTS")
    SCHEMA_PATH: str = Field("app/schemas/datasulting.md", env="SCHEMA_PATH")
    
    # Paramètres de l'API
    API_PREFIX: str = Field("/api/v1", env="API_PREFIX")
    
    # Sécurité (facultatif - si non défini, pas d'authentification)
    API_KEY: Optional[str] = Field(None, env="API_KEY")
    API_KEY_NAME: str = Field("X-API-Key", env="API_KEY_NAME")
    ADMIN_SECRET: Optional[str] = Field(None, env="ADMIN_SECRET")
    ALLOWED_HOSTS: List[str] = Field(["*","localhost","127.0.0.1"], env="ALLOWED_HOSTS")
    
    # Paramètres serveur
    DEBUG: bool = Field(False, env="DEBUG")
    
    # Cache Redis
    REDIS_URL: Optional[str] = Field("redis://localhost:6379/0", env="REDIS_URL")
    REDIS_TTL: int = Field(3600, env="REDIS_TTL")
    CACHE_ENABLED: bool = Field(True, env="CACHE_ENABLED")
    
    # Fonctionnalités avancées
    METRICS_ENABLED: bool = Field(True, env="METRICS_ENABLED")
    
    # Propriétés de compatibilité pour l'ancien code (si nécessaire)
    @property
    def OPENAI_MODEL(self) -> str:
        return self.DEFAULT_OPENAI_MODEL
    
    @property
    def OPENAI_TEMPERATURE(self) -> float:
        return self.LLM_TEMPERATURE
    
    @property
    def OPENAI_TIMEOUT(self) -> int:
        return self.LLM_TIMEOUT
    
    @property
    def PINECONE_INDEX(self) -> str:
        return self.PINECONE_INDEX_NAME
    
    @classmethod
    def parse_env_var(cls, field_name: str, raw_val: str):
        """Parse les variables d'environnement personnalisées"""
        if field_name == 'ALLOWED_HOSTS':
            # Gérer le format JSON du .env
            if raw_val.startswith('[') and raw_val.endswith(']'):
                import json
                return json.loads(raw_val)
            # Gérer le format CSV simple
            return [host.strip() for host in raw_val.split(',')]
        return raw_val

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore les champs supplémentaires non déclarés


@lru_cache()
def get_settings() -> Settings:
    """
    Récupère les paramètres de configuration avec mise en cache.
    Cette fonction est décorée avec lru_cache pour éviter de relire
    les paramètres à chaque appel.
    """
    return Settings()