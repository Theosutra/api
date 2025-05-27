import re
import logging
from typing import Tuple

from app.core.exceptions import FrameworkError, ValidationError  # NOUVELLES IMPORTS

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
        
    Raises:
        ValidationError: Si les paramètres d'entrée sont invalides
    """
    # Validation des paramètres d'entrée
    if not sql_query:
        raise ValidationError("sql_query ne peut pas être vide", "sql_query", sql_query)
    
    if not isinstance(sql_query, str):
        raise ValidationError("sql_query doit être une chaîne de caractères", "sql_query", type(sql_query))
    
    sql_query = sql_query.strip()
    if len(sql_query) == 0:
        return False, "Requête SQL vide après nettoyage"
    
    try:
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
        if not sql_query.upper().startswith('SELECT'):
            return False, "Seules les requêtes SELECT sont autorisées"
        
        return True, "Requête conforme au framework obligatoire"
    
    except Exception as e:
        logger.error(f"Erreur lors de la validation du framework: {e}")
        raise ValidationError(f"Erreur lors de la validation du framework: {e}", "framework_validation", sql_query)


def add_missing_framework_elements(sql_query: str) -> str:
    """
    Tente d'ajouter automatiquement les éléments manquants du framework.
    Version simplifiée qui ajoute les éléments de base.
    
    Args:
        sql_query: La requête SQL originale
        
    Returns:
        La requête SQL modifiée
        
    Raises:
        ValidationError: Si les paramètres d'entrée sont invalides
        FrameworkError: Si la correction automatique échoue
    """
    # Validation des paramètres d'entrée
    if not sql_query:
        raise ValidationError("sql_query ne peut pas être vide", "sql_query", sql_query)
    
    if not isinstance(sql_query, str):
        raise ValidationError("sql_query doit être une chaîne de caractères", "sql_query", type(sql_query))
    
    modified_query = sql_query.strip()
    
    if len(modified_query) == 0:
        raise ValidationError("sql_query ne peut pas être vide après nettoyage", "sql_query", sql_query)
    
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
            else:
                # Pas de table DEPOT trouvée, impossible de corriger
                raise FrameworkError("Impossible d'ajouter le filtre ID_USER: table DEPOT non trouvée", modified_query)
        
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
            else:
                # Ajouter au moins le hashtag DEPOT minimal
                if depot_match:
                    hashtag_string = f" #DEPOT_{depot_match.group(1)}#"
                    if modified_query.rstrip().endswith(';'):
                        modified_query = modified_query.rstrip()[:-1] + hashtag_string + ';'
                    else:
                        modified_query = modified_query + hashtag_string
                else:
                    raise FrameworkError("Impossible d'ajouter les hashtags: aucune table reconnue", modified_query)
        
        logger.debug(f"Requête corrigée automatiquement: ajout d'éléments du framework")
        return modified_query
    
    except FrameworkError:
        # Re-propager les erreurs FrameworkError
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout des éléments du framework: {str(e)}")
        raise FrameworkError(f"Erreur lors de la correction automatique: {str(e)}", sql_query)


def check_framework_elements(sql_query: str) -> Dict[str, bool]:
    """
    Vérifie individuellement chaque élément du framework.
    Utile pour le debugging et les rapports détaillés.
    
    Args:
        sql_query: La requête SQL à analyser
        
    Returns:
        Dictionnaire avec le statut de chaque élément
        
    Raises:
        ValidationError: Si les paramètres d'entrée sont invalides
    """
    if not sql_query or not isinstance(sql_query, str):
        raise ValidationError("sql_query doit être une chaîne non vide", "sql_query", sql_query)
    
    sql_query = sql_query.strip()
    
    try:
        results = {
            "has_user_filter": bool(re.search(r'\b\w+\.ID_USER\s*=\s*\?', sql_query, re.IGNORECASE)),
            "has_depot_table": bool(re.search(r'\bDEPOT\s+\w+', sql_query, re.IGNORECASE)),
            "has_hashtags": bool(re.search(r'#\w+#', sql_query)),
            "is_select_query": sql_query.upper().startswith('SELECT'),
            "has_where_clause": bool(re.search(r'\bWHERE\b', sql_query, re.IGNORECASE)),
            "has_join_depot": bool(re.search(r'\bJOIN\s+DEPOT\b', sql_query, re.IGNORECASE))
        }
        
        # Vérifications supplémentaires
        depot_aliases = re.findall(r'\bDEPOT\s+(\w+)', sql_query, re.IGNORECASE)
        facts_aliases = re.findall(r'\bFACTS\s+(\w+)', sql_query, re.IGNORECASE)
        
        results["depot_aliases"] = depot_aliases
        results["facts_aliases"] = facts_aliases
        results["has_depot_alias"] = len(depot_aliases) > 0
        results["has_facts_alias"] = len(facts_aliases) > 0
        
        # Vérifier les hashtags spécifiques
        hashtags = re.findall(r'#(\w+)#', sql_query)
        results["found_hashtags"] = hashtags
        results["has_depot_hashtag"] = any(tag.startswith('DEPOT_') for tag in hashtags)
        results["has_facts_hashtag"] = any(tag.startswith('FACTS_') for tag in hashtags)
        results["has_periode_hashtag"] = 'PERIODE' in hashtags
        
        return results
    
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse des éléments du framework: {e}")
        raise ValidationError(f"Erreur lors de l'analyse du framework: {e}", "framework_analysis", sql_query)


def suggest_framework_corrections(sql_query: str) -> List[str]:
    """
    Suggère des corrections pour respecter le framework.
    
    Args:
        sql_query: La requête SQL à analyser
        
    Returns:
        Liste des suggestions de correction
        
    Raises:
        ValidationError: Si les paramètres d'entrée sont invalides
    """
    if not sql_query or not isinstance(sql_query, str):
        raise ValidationError("sql_query doit être une chaîne non vide", "sql_query", sql_query)
    
    try:
        suggestions = []
        elements = check_framework_elements(sql_query)
        
        if not elements["is_select_query"]:
            suggestions.append("Utilisez uniquement des requêtes SELECT")
        
        if not elements["has_depot_table"]:
            suggestions.append("Ajoutez la table DEPOT avec un alias (ex: DEPOT a)")
        
        if not elements["has_user_filter"]:
            if elements["has_depot_alias"]:
                alias = elements["depot_aliases"][0]
                suggestions.append(f"Ajoutez le filtre WHERE {alias}.ID_USER = ?")
            else:
                suggestions.append("Ajoutez le filtre WHERE [alias_depot].ID_USER = ?")
        
        if not elements["has_hashtags"]:
            hashtag_suggestions = []
            if elements["has_depot_alias"]:
                hashtag_suggestions.append(f"#DEPOT_{elements['depot_aliases'][0]}#")
            if elements["has_facts_alias"]:
                hashtag_suggestions.append(f"#FACTS_{elements['facts_aliases'][0]}#")
            
            if hashtag_suggestions:
                suggestions.append(f"Ajoutez les hashtags: {' '.join(hashtag_suggestions)}")
            else:
                suggestions.append("Ajoutez les hashtags appropriés (#DEPOT_alias# #FACTS_alias#)")
        
        if not elements["has_join_depot"] and elements["has_facts_alias"]:
            depot_alias = elements["depot_aliases"][0] if elements["depot_aliases"] else "a"
            facts_alias = elements["facts_aliases"][0]
            suggestions.append(f"Ajoutez la jointure: JOIN DEPOT {depot_alias} ON {facts_alias}.ID_NUMDEPOT = {depot_alias}.ID")
        
        return suggestions
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération des suggestions: {e}")
        raise ValidationError(f"Erreur lors de la génération des suggestions: {e}", "framework_suggestions", sql_query)


# Import nécessaire pour le type Dict
from typing import Dict, List