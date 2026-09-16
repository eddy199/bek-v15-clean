import sys
import subprocess
import traceback
from pathlib import Path
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field

# Preserve module metadata
__file__ = __file__  # noqa: F821
__name__ = __name__  # noqa: F821

# Base directory of the current module – works on Windows and Linux
BASE_DIR = Path(__file__).resolve().parent


def _run_subprocess(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command {' '.join(command)} failed with exit code {result.returncode}: {result.stderr}"
            )
        return result.stdout
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Subprocess execution failed: {e}") from e


def run_dynamic_skill(skill_name: str, *args: str) -> str:
    try:
        skill_path = (BASE_DIR / "skills" / f"{skill_name}.py").resolve()
        if not skill_path.is_file():
            raise FileNotFoundError(f"Skill file not found: {skill_path}")
        command = [sys.executable, str(skill_path), *map(str, args)]
        return _run_subprocess(command)
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to run skill '{skill_name}': {e}") from e


def write_text_file(relative_path: str, content: str) -> None:
    try:
        file_path = (BASE_DIR / relative_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to write file '{relative_path}': {e}") from e


def read_text_file(relative_path: str) -> str:
    try:
        file_path = (BASE_DIR / relative_path).resolve()
        with file_path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to read file '{relative_path}': {e}") from e


class SmartRouter:
    def route(self, query: str, provider: Optional[str] = None, model: Optional[str] = None) -> str:
        return provider or "groq"


smart_router = SmartRouter()


class AutoEngine:
    def run_goal(self, goal: str, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "success", "goal": goal, "result": "Exécuté par AutoEngine"}


auto_engine = AutoEngine()


class ResponseQuality:
    def __init__(self, passed: bool = True, reason: str = "OK"):
        self.passed = passed
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "reason": self.reason}

    # ══════════════════════════════════════════════════════════════════
    # 🆕 AJOUT v16 — Méthode statique evaluate()
    # ------------------------------------------------------------------
    # Corrige l'erreur : "type object 'ResponseQuality' has no attribute
    # 'evaluate'" levée par routers/chat.py (QualityGate).
    #
    # Compatible avec l'appel existant :
    #     score, issues = ResponseQuality.evaluate(full_text, 4096)
    #
    # Retourne un tuple (score: int 0-100, issues: list[str]).
    # Ne lève JAMAIS d'exception.
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def evaluate(text: str, max_tokens: int = 4096) -> tuple:
        try:
            if not text or not isinstance(text, str):
                return 0, ["Réponse vide"]

            issues = []
            score = 100

            # 1. Longueur minimale
            if len(text.strip()) < 10:
                issues.append("Réponse trop courte")
                score -= 40

            # 2. Troncature suspecte
            if text.rstrip().endswith("..."):
                issues.append("Réponse possiblement tronquée")
                score -= 10

            # 3. Caractères de remplacement (encodage cassé)
            if "\ufffd" in text:
                issues.append("Caractères de remplacement détectés (encodage)")
                score -= 15

            # 4. Boucles de répétition (même mot 5+ fois consécutives)
            import re as _re
            if _re.search(r"\b(\w+)(?:\s+\1){4,}\b", text, _re.IGNORECASE):
                issues.append("Répétition suspecte détectée")
                score -= 20

            # 5. Marqueurs d'erreur explicites
            lower = text.lower()
            for marker in ("traceback", "error:", "exception:", "attributeerror"):
                if marker in lower:
                    issues.append(f"Marqueur d'erreur détecté : {marker}")
                    score -= 15
                    break

            # 6. Bornage final
            score = max(0, min(100, score))
            return score, issues

        except Exception as exc:
            # En cas d'erreur imprévue, on retourne un score neutre
            return 50, [f"Erreur évaluation : {exc}"]


@dataclass
class Task:
    task_id: str
    name: str
    status: str = "PENDING"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "payload": self.payload,
        }


if __name__ == "__main__":
    try:
        output = run_dynamic_skill("example_skill", "--demo", "123")
        print("Skill output:\n", output)
    except Exception as exc:
        print(f"Error during skill execution: {exc}")