import sys
import subprocess
import traceback
from pathlib import Path

# Preserve module metadata
__file__ = __file__  # noqa: F821
__name__ = __name__  # noqa: F821

# Base directory of the current module – works on Windows and Linux
BASE_DIR = Path(__file__).resolve().parent


def _run_subprocess(command: list[str]) -> str:
    """Execute a command with the current Python interpreter.

    All I/O is forced to UTF‑8 and any error raises a RuntimeError with
    the captured stderr for easier debugging.
    """
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
    """Launch a dynamic skill located in the ``skills`` sub‑directory.

    The skill is executed as a separate Python process using ``sys.executable``
    to guarantee the same interpreter (important for Windows vs. Linux Render).
    ``args`` are passed verbatim to the skill script.
    """
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
    """Write *content* to *relative_path* using UTF‑8 encoding.

    The function creates parent directories as needed and wraps all I/O in a
    strict ``try/except`` block.
    """
    try:
        file_path = (BASE_DIR / relative_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to write file '{relative_path}': {e}") from e


def read_text_file(relative_path: str) -> str:
    """Read and return the contents of *relative_path* using UTF‑8 encoding.
    """
    try:
        file_path = (BASE_DIR / relative_path).resolve()
        with file_path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to read file '{relative_path}': {e}") from e


if __name__ == "__main__":
    # Simple demo – attempts to run a skill named ``example_skill``
    try:
        output = run_dynamic_skill("example_skill", "--demo", "123")
        print("Skill output:\n", output)
    except Exception as exc:
        print(f"Error during skill execution: {exc}")
