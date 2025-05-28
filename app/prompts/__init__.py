"""
Package de gestion des prompts avec Jinja2.

Ce package centralise tous les prompts de l'application NL2SQL
en utilisant des templates Jinja2 modulaires et réutilisables.

Author: Datasulting
Version: 2.0.0
"""

from .prompt_manager import (
    PromptManager,
    get_prompt_manager,
    render_sql_prompt,
    render_validation_prompt
)

__all__ = [
    "PromptManager",
    "get_prompt_manager", 
    "render_sql_prompt",
    "render_validation_prompt"
]

# Version du système de prompts
__version__ = "2.0.0"