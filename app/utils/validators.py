import re
import logging
from typing import Optional, Tuple, Dict, Any

# Configuration du logger
logger = logging.getLogger(__name__)


def validate_sql_syntax(sql_query: str) -> Tuple[bool, Optional[str]]:
    """
    Effectue une validation basique de la syntaxe SQL.
    
    Args:
        sql_query: La requête SQL à valider
        
    Returns:
        Un tuple (valide, message) où valide est un booléen indiquant si la requête semble valide,
        et message est un message explicatif en cas d'erreur
    """
    if not sql_query or not isinstance(sql_query, str):
        return False, "La requête SQL est vide ou non valide"
    
    # Vérifications de base
    sql_query = sql_query.strip()
    
    # Vérifier les mots-clés SQL de base
    basic_keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'JOIN',
                      'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'OUTER JOIN', 'UNION',
                      'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE']
    
    has_keyword = False
    for keyword in basic_keywords:
        if re.search(r'\b' + keyword + r'\b', sql_query, re.IGNORECASE):
            has_keyword = True
            break
    
    if not has_keyword:
        return False, "La requête ne contient aucun mot-clé SQL standard"
    
    # Vérifier l'équilibre des parenthèses
    if sql_query.count('(') != sql_query.count(')'):
        return False, "Les parenthèses ne sont pas équilibrées"
    
    # Vérifier les guillemets
    single_quotes = sql_query.count("'")
    double_quotes = sql_query.count('"')
    backticks = sql_query.count('`')
    
    if single_quotes % 2 != 0:
        return False, "Les guillemets simples (') ne sont pas équilibrés"
    
    if double_quotes % 2 != 0:
        return False, "Les guillemets doubles (\") ne sont pas équilibrés"
    
    if backticks % 2 != 0:
        return False, "Les backticks (`) ne sont pas équilibrés"
    
    # Vérifier si la requête commence par un mot-clé SQL valide
    first_word = sql_query.split(' ')[0].upper()
    valid_first_words = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 
                         'TRUNCATE', 'WITH', 'EXPLAIN', 'DESCRIBE', 'SHOW']
    
    if first_word not in valid_first_words:
        return False, f"La requête commence par '{first_word}', qui n'est pas un mot-clé SQL standard"
    
    # Vérifier la présence d'un point-virgule à la fin
    if not sql_query.rstrip().endswith(';'):
        logger.info("La requête SQL ne se termine pas par un point-virgule")
        # Ne pas considérer cela comme une erreur, juste un avertissement
    
    return True, None


def sanitize_input(input_text: str) -> str:
    """
    Sanitize l'entrée de l'utilisateur pour éviter les injections.
    
    Args:
        input_text: Le texte à sanitizer
        
    Returns:
        Le texte sanitizé
    """
    if not input_text:
        return ""
    
    # Supprimer les caractères dangereux
    sanitized = re.sub(r'[;<>\\$]', '', input_text)
    
    # Limiter la longueur
    if len(sanitized) > 5000:
        sanitized = sanitized[:5000]
        logger.warning("L'entrée a été tronquée car elle dépassait 5000 caractères.")
    
    return sanitized


def validate_schema_path(schema_path: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Valide le chemin du schéma SQL.
    
    Args:
        schema_path: Le chemin vers le fichier de schéma SQL
        
    Returns:
        Un tuple (valide, message) où valide est un booléen indiquant si le chemin semble valide,
        et message est un message explicatif en cas d'erreur
    """
    if not schema_path:
        return True, None
    
    # Vérifier l'extension
    if not schema_path.endswith('.sql'):
        return False, "Le fichier de schéma doit avoir l'extension .sql"
    
    # Vérifier les caractères dangereux
    if '../' in schema_path or './' in schema_path or '~' in schema_path:
        return False, "Le chemin du schéma contient des caractères non autorisés"
    
    # Vérifier que le chemin est dans le répertoire schemas
    if not (schema_path.startswith('app/schemas/') or schema_path.startswith('schemas/')):
        return False, "Le chemin du schéma doit être dans le répertoire schemas"
    
    return True, None


def format_sql_query(sql_query: str) -> str:
    """
    Formate une requête SQL pour améliorer sa lisibilité.
    Cette fonction est basique et peut être améliorée.
    
    Args:
        sql_query: La requête SQL à formater
        
    Returns:
        La requête SQL formatée
    """
    if not sql_query:
        return ""
    
    # Ajouter un point-virgule à la fin si absent
    if not sql_query.rstrip().endswith(';'):
        sql_query = sql_query.rstrip() + ';'
    
    # Mettre en majuscule les mots-clés SQL principaux (basique)
    keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'JOIN',
                'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'OUTER JOIN', 'UNION',
                'INSERT', 'UPDATE', 'DELETE', 'AS', 'ON', 'AND', 'OR', 'NOT',
                'IN', 'LIKE', 'BETWEEN', 'IS NULL', 'IS NOT NULL', 'ASC', 'DESC']
    
    # Cette méthode simple a des limites, notamment avec les chaînes SQL complexes
    formatted = sql_query
    for keyword in keywords:
        pattern = r'\b' + keyword + r'\b'
        formatted = re.sub(pattern, keyword, formatted, flags=re.IGNORECASE)
    
    return formatted