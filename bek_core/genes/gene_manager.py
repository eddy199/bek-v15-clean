# -*- coding: utf-8 -*-
# bek_core/genes/gene_manager.py
import logging
from typing import Optional
from bek_ga_light import BEKGeneticEngineCPU

logger = logging.getLogger("bek.genes.manager")

class GeneManager:
    """
    Gestionnaire de Gènes.
    Il fait le pont entre ton moteur génétique (bek_ga_light.py) 
    et les règles spécifiques aux moteurs/langages.
    """
    def __init__(self):
        # On utilise ton moteur existant
        self.engine = BEKGeneticEngineCPU()
        
    def get_best_gene_with_rules(self, engine_type: str = "generic") -> str:
        """
        Récupère le meilleur gène du GA et y ajoute les règles du moteur ciblé.
        """
        best_gene = self.engine.select_best_gene()
        base_prompt = best_gene.prompt_template
        
        logger.info(f"[GeneManager] Gène sélectionné : {best_gene.gene_id} (fitness: {best_gene.fitness})")
        
        # Ajout des règles spécifiques selon le moteur/langage
        engine_lower = engine_type.lower()
        
        if engine_lower == "godot":
            rules = self._get_godot_rules()
        elif engine_lower == "pygame":
            rules = self._get_pygame_rules()
        elif engine_lower == "web" or engine_lower == "frontend":
            rules = self._get_web_rules()
        elif engine_lower == "python" or engine_lower == "backend":
            rules = self._get_python_backend_rules()
        elif engine_lower == "data":
            rules = self._get_data_science_rules()
        elif engine_lower == "mobile":
            rules = self._get_mobile_rules()
        else:
            rules = self._get_generic_rules()
            
        return f"{base_prompt}\n\n{rules}"
        
    def _get_godot_rules(self) -> str:
        return """
=== RÈGLES SPÉCIFIQUES : GODOT 4 (GDScript) ===
1. Chaque script (.gd) DOIT commencer par "extends CharacterBody2D" ou "extends Node2D".
2. Chaque scène (.tscn) DOIT commencer par "[gd_scene load_steps=...".
3. N'utilise JAMAIS de Python dans les fichiers Godot.
4. Pour tester, n'utilise pas bash. Écris juste les fichiers.
"""

    def _get_pygame_rules(self) -> str:
        return """
=== RÈGLES SPÉCIFIQUES : PYGAME (Python) ===
1. Utilise TOUJOURS des imports relatifs (ex: "from .config import ...").
2. Structure le projet avec un dossier "src/".
3. Assure-toi que main.py fait "from src.game import Game".
4. Tu peux tester avec bash (python main.py) si besoin.
"""

    def _get_web_rules(self) -> str:
        return """
=== RÈGLES SPÉCIFIQUES : WEB (HTML5/JS/CSS) ===
1. Sépare strictement le HTML, le CSS et le JS.
2. Utilise les modules ES6 (import / export) si le JS est complexe.
3. Ne génère pas de fichiers de plus de 200 lignes.
4. Assure-toi que le fichier index.html inclut bien le script JS et le CSS.
"""

    def _get_python_backend_rules(self) -> str:
        return """
=== RÈGLES SPÉCIFIQUES : PYTHON BACKEND (API/SCRIPT) ===
1. Utilise le typage (type hints) pour toutes les fonctions.
2. Sépare les routes, la logique métier et la base de données.
3. Gère les erreurs avec des blocs "try/except" clairs.
4. Crée un fichier "requirements.txt" avec les dépendances.
5. Écris des tests unitaires (pytest) dans le dossier "tests/".
"""

    def _get_data_science_rules(self) -> str:
        return """
=== RÈGLES SPÉCIFIQUES : DATA SCIENCE / IA ===
1. Utilise Pandas pour la manipulation de données et NumPy pour les calculs.
2. Documente chaque étape avec des docstrings claires.
3. Sauvegarde les graphiques dans un dossier "output/".
4. Ne charge pas de datasets trop lourds sans gestion de la mémoire.
"""

    def _get_mobile_rules(self) -> str:
        return """
=== RÈGLES SPÉCIFIQUES : MOBILE (React Native / Flutter) ===
1. Sépare les composants UI des composants logiques.
2. Utilise des styles réutilisables (StyleSheet ou Theme).
3. Gère les états (useState, Redux ou Provider).
4. Assure-toi que le code est compatible Android et iOS.
"""

    def _get_generic_rules(self) -> str:
        return """
=== RÈGLES GÉNÉRIQUES ===
1. Réponds en JSON strict.
2. 1 étape = 1 fichier.
3. Termine chaque étape par {"tool":"done"}.
4. Si une erreur survient, utilise edit_file pour corriger.
"""

# Instance globale
gene_manager = GeneManager()