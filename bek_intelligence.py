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