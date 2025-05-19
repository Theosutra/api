import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def validate_framework_compliance(sql_query: str) -> Tuple[bool, str]:
    """
    Validation simple pour vérifier que la requête SQL respecte le framework obligatoire.
    
    Args:
        sql_query: La requête SQL à valider
        
    Returns:
        Tuple (is_compliant, message) où:
        - is_compliant: booléen indiquant si la requête respecte le framework
        - message: message explicatif
    """
    if not sql_query:
        return False, "Requête SQL vide"
    
    # 1. Vérifier la présence du filtre ID_USER
    user_filter_pattern = r'\b\w+\.ID_USER\s*=\s*\?'
    if not re.search(user_filter_pattern, sql_query, re.IGNORECASE):
        return False, "Filtre WHERE [alias].ID_USER = ? obligatoire manquant"
    
    # 2. Vérifier la présence de la table DEPOT
    depot_pattern = r'\bDEPOT\s+\w+'
    if not re.search(depot_pattern, sql_query, re.IGNORECASE):
        return False, "Table DEPOT obligatoire manquante"
    
    # 3. Vérifier la présence d'au moins un hashtag
    hashtag_pattern = r'#\w+#'
    if not re.search(hashtag_pattern, sql_query):
        return False, "Hashtags obligatoires manquants (ex: #DEPOT_d#)"
    
    # 4. Vérifier que c'est une requête SELECT
    if not sql_query.strip().upper().startswith('SELECT'):
        return False, "Seules les requêtes SELECT sont autorisées"
    
    return True, "Requête conforme au framework obligatoire"


def add_missing_framework_elements(sql_query: str) -> str:
    """
    Tente d'ajouter automatiquement les éléments manquants du framework.
    Version simplifiée qui ajoute les éléments de base.
    
    Args:
        sql_query: La requête SQL originale
        
    Returns:
        La requête SQL modifiée
    """
    modified_query = sql_query
    
    try:
        # 1. Ajouter le filtre ID_USER si manquant
        if not re.search(r'\b\w+\.ID_USER\s*=\s*\?', modified_query, re.IGNORECASE):
            # Essayer de trouver une table DEPOT avec alias
            depot_match = re.search(r'\bDEPOT\s+(\w+)', modified_query, re.IGNORECASE)
            if depot_match:
                depot_alias = depot_match.group(1)
                # Ajouter le filtre dans la clause WHERE
                if ' WHERE ' in modified_query.upper():
                    modified_query = re.sub(
                        r'(\bWHERE\s+)', 
                        f'\\1{depot_alias}.ID_USER = ? AND ', 
                        modified_query, 
                        flags=re.IGNORECASE
                    )
                else:
                    # Ajouter une clause WHERE avant GROUP BY, ORDER BY ou à la fin
                    insert_patterns = [
                        (r'(\s+GROUP\s+BY)', f' WHERE {depot_alias}.ID_USER = ?\\1'),
                        (r'(\s+ORDER\s+BY)', f' WHERE {depot_alias}.ID_USER = ?\\1'),
                        (r'(\s*;?\s*$)', f' WHERE {depot_alias}.ID_USER = ?\\1')
                    ]
                    
                    for pattern, replacement in insert_patterns:
                        if re.search(pattern, modified_query, re.IGNORECASE):
                            modified_query = re.sub(pattern, replacement, modified_query, flags=re.IGNORECASE)
                            break
        
        # 2. Ajouter les hashtags si manquants
        if not re.search(r'#\w+#', modified_query):
            # Trouver les alias des tables
            depot_match = re.search(r'\bDEPOT\s+(\w+)', modified_query, re.IGNORECASE)
            facts_match = re.search(r'\bFACTS\s+(\w+)', modified_query, re.IGNORECASE)
            
            hashtags = []
            if depot_match:
                hashtags.append(f"#DEPOT_{depot_match.group(1)}#")
            if facts_match:
                hashtags.append(f"#FACTS_{facts_match.group(1)}#")
            
            # Vérifier si c'est une requête temporelle
            if re.search(r'\bPERIODE\b|\bDATE\b|\bMOIS\b|\bANNEE\b', modified_query, re.IGNORECASE):
                hashtags.append("#PERIODE#")
            
            if hashtags:
                # Ajouter les hashtags à la fin, après le point-virgule s'il existe
                hashtag_string = " " + " ".join(hashtags)
                if modified_query.rstrip().endswith(';'):
                    modified_query = modified_query.rstrip()[:-1] + hashtag_string + ';'
                else:
                    modified_query = modified_query + hashtag_string
    
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout des éléments du framework: {str(e)}")
        return sql_query
    
    return modified_query