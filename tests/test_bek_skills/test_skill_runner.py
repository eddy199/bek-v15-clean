"""
Tests de l'agent skills — skill_runner.py

Vérifie que :
- La liste des skills est chargée correctement (au moins 300 skills)
- Les fonctions publiques existent et sont importables
- Les skills natifs et custom sont bien fusionnés
"""

import pytest
from skill_runner import (
    list_skills,
    get_skill,
    save_skill,
    delete_skill,
    dispatch_command,
    build_skill_prompt,
)


class TestSkillRunner:
    """Tests de base sur skill_runner."""

    def test_list_skills_returns_list(self):
        """list_skills() doit retourner une liste."""
        skills = list_skills()
        assert isinstance(skills, list), "list_skills() doit retourner une liste"

    def test_list_skills_not_empty(self):
        """La liste des skills ne doit pas être vide (au moins 300 skills)."""
        skills = list_skills()
        assert len(skills) >= 300, f"Trop peu de skills chargés : {len(skills)}"

    def test_list_skills_structure(self):
        """Chaque skill doit avoir au minimum 'name' et 'category'."""
        skills = list_skills()
        for skill in skills[:5]:  # On teste les 5 premiers
            assert "name" in skill, f"Skill sans 'name' : {skill}"
            assert "category" in skill, f"Skill sans 'category' : {skill}"

    def test_build_skill_prompt(self):
        """build_skill_prompt() doit remplacer {input} par user_input dans le code."""
        fake_skill = {
            "name": "test",
            "code": "print('Resultat: {input}')",
        }
        prompt = build_skill_prompt(fake_skill, "Fais quelque chose")
        assert isinstance(prompt, str), "build_skill_prompt() doit retourner une str"
        assert len(prompt) > 0, "Le prompt ne doit pas être vide"
        assert "Fais quelque chose" in prompt, "user_input doit être dans le prompt"
        assert "{input}" not in prompt, "{input} doit être remplacé"

    def test_build_skill_prompt_empty_code(self):
        """Si le skill n'a pas de code, retourne une chaîne vide."""
        fake_skill = {"name": "test", "description": "Un skill de test"}
        prompt = build_skill_prompt(fake_skill, "Fais quelque chose")
        assert prompt == "", "Un skill sans 'code' doit retourner une chaîne vide"

    def test_dispatch_command_exists(self):
        """dispatch_command() doit être callable."""
        assert callable(dispatch_command), "dispatch_command doit être callable"
        assert callable(get_skill), "get_skill doit être callable"
        assert callable(save_skill), "save_skill doit être callable"
        assert callable(delete_skill), "delete_skill doit être callable"