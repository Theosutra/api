import os
import logging
from pathlib import Path
from typing import Optional
import aiofiles

# Configuration du logger
logger = logging.getLogger(__name__)


async def load_schema(schema_path: str) -> str:
    """
    Charge le schéma SQL depuis un fichier de manière asynchrone.
    
    Args:
        schema_path: Chemin vers le fichier de schéma SQL
        
    Returns:
        Contenu du fichier de schéma SQL sous forme de chaîne de caractères
        
    Raises:
        FileNotFoundError: Si le fichier de schéma est introuvable
        IOError: Si une erreur se produit lors de la lecture du fichier
    """
    try:
        # Vérifier que le fichier existe
        if not os.path.exists(schema_path):
            logger.error(f"Fichier de schéma '{schema_path}' introuvable")
            raise FileNotFoundError(f"Fichier de schéma '{schema_path}' introuvable")
        
        # Lire le fichier de manière asynchrone
        async with aiofiles.open(schema_path, 'r', encoding='utf-8') as f:
            schema_content = await f.read()
        
        logger.debug(f"Schéma SQL chargé depuis '{schema_path}' ({len(schema_content)} caractères)")
        return schema_content
    
    except FileNotFoundError:
        logger.error(f"Fichier de schéma '{schema_path}' introuvable")
        raise
    
    except Exception as e:
        logger.error(f"Erreur lors du chargement du schéma depuis '{schema_path}': {str(e)}")
        raise IOError(f"Erreur lors du chargement du schéma: {str(e)}")


async def get_available_schemas() -> list:
    """
    Récupère la liste des schémas SQL disponibles dans le répertoire app/schemas.
    
    Returns:
        Liste des noms de fichiers de schéma disponibles
    """
    schemas_dir = Path("app/schemas")
    
    try:
        if not schemas_dir.exists():
            logger.warning(f"Répertoire de schémas '{schemas_dir}' introuvable")
            return []
        
        # Récupérer tous les fichiers .sql dans le répertoire
        schema_files = [f.name for f in schemas_dir.glob("*.sql")]
        logger.debug(f"Schémas disponibles: {schema_files}")
        
        return schema_files
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des schémas disponibles: {str(e)}")
        return []