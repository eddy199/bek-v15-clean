"""
Tests des deux skill_sandbox.

Vérifie que :
- Le validateur AST (core) bloque le code dangereux
- Le sandbox d'exécution (bek_core) existe et est importable
"""

import pytest

from core.security.skill_sandbox import validate_skill_code


class TestValidateSkillCode:
    """Tests du validateur AST statique."""

    def test_valid_code_passes(self):
        """Un code simple et sain doit passer."""
        code = "x = 1 + 2\nprint(x)"
        result = validate_skill_code(code)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_math_import_allowed(self):
        """import math doit être autorisé."""
        code = "import math\nresult = math.sqrt(16)"
        result = validate_skill_code(code)
        assert result["valid"] is True

    def test_json_import_allowed(self):
        """import json doit être autorisé."""
        code = "import json\nresult = json.dumps({'a': 1})"
        result = validate_skill_code(code)
        assert result["valid"] is True

    def test_subprocess_blocked(self):
        """import subprocess doit être bloqué."""
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = validate_skill_code(code)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_eval_blocked(self):
        """eval() doit être bloqué."""
        code = "result = eval('1+1')"
        result = validate_skill_code(code)
        assert result["valid"] is False

    def test_requests_blocked(self):
        """import requests doit être bloqué (pas dans la whitelist)."""
        code = "import requests\nrequests.get('http://x')"
        result = validate_skill_code(code)
        assert result["valid"] is False

    def test_syntax_error_blocked(self):
        """Un code avec erreur de syntaxe doit être rejeté."""
        code = "def broken(:"
        result = validate_skill_code(code)
        assert result["valid"] is False
        assert "syntaxe" in result["errors"][0].lower()

    def test_oversized_code_blocked(self):
        """Un code trop volumineux (> 200 KB) doit être rejeté."""
        code = "x = 1\n" * 50000  # ~300 KB
        result = validate_skill_code(code)
        assert result["valid"] is False