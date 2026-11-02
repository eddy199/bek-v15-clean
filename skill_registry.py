"""
BEK-v15.2 HYBRID - Dynamic Skill Registry (v19.9 - Scan Récursif)
"""
from __future__ import annotations
import json, logging, os, re, threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bek.skill_registry")
WORKSPACE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = WORKSPACE_DIR / "skills"
_ALLOWED_EXTENSIONS = {".json", ".md", ".txt"}

@dataclass
class Skill:
    skill_id: str
    name: str
    description: str = ""
    prompt: str = ""
    command: str = ""
    category: str = "general"
    risk_level: str = "L1"
    score: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "command": self.command,
            "category": self.category,
            "risk_level": self.risk_level,
            "score": round(self.score, 2),
            "enabled": self.enabled,
        }

class SkillRegistry:
    ALTER_EGO_DIR_NAME = "alter-egos"

    def __init__(self, directories: Optional[List[Path]] = None):
        self.directories = [SKILLS_DIR] if directories is None else directories
        for d in self.directories:
            d.mkdir(parents=True, exist_ok=True)
        self.skills: Dict[str, Skill] = {}
        self.alter_egos: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._initialized = False

    def load_skills(self) -> int:
        scores_db = self._fetch_db_scores()
        loaded_skills: Dict[str, Skill] = {}

        for directory in self.directories:
            if not directory.exists(): continue

            # ★ SCAN RÉCURSIF AVEC rglob
            for filepath in directory.rglob("*"):
                if not filepath.is_file() or filepath.name.startswith("."): continue
                if filepath.suffix.lower() not in _ALLOWED_EXTENSIONS: continue
                if self.ALTER_EGO_DIR_NAME in filepath.parts: continue # Géré à part

                try:
                    skill = self._parse_skill_file(filepath, scores_db)
                    if skill and skill.skill_id not in loaded_skills:
                        loaded_skills[skill.skill_id] = skill
                except Exception as exc:
                    logger.debug("Erreur parsing skill %s : %s", filepath, exc)

        with self._lock:
            self.skills = loaded_skills
            self._initialized = True

        logger.info("Skill Registry initialisé | %d skills chargées.", len(loaded_skills))
        self.load_alter_egos()
        return len(loaded_skills)

    def load_alter_egos(self) -> Dict[str, str]:
        alter_egos = {}
        alter_ego_dir = SKILLS_DIR / self.ALTER_EGO_DIR_NAME
        if alter_ego_dir.exists() and alter_ego_dir.is_dir():
            for subdir in alter_ego_dir.iterdir():
                if not subdir.is_dir(): continue
                skill_file = subdir / "SKILL.md"
                if skill_file.exists():
                    try:
                        with skill_file.open("r", encoding="utf-8") as fh:
                            content = fh.read().strip()
                        if content: alter_egos[subdir.name] = content
                    except Exception: pass
        with self._lock:
            self.alter_egos = alter_egos
        return alter_egos

    def get_alter_ego(self, ego_name: str) -> Optional[str]:
        return self.alter_egos.get(ego_name)

    def list_alter_egos(self) -> List[str]:
        return list(self.alter_egos.keys())

    def _fetch_db_scores(self) -> Dict[str, Tuple[int, int, float]]:
        return {} # Simplifié pour éviter l'erreur DB

    def _parse_skill_file(self, filepath: Path, scores_db: Dict) -> Optional[Skill]:
        name = filepath.stem
        skill_id = re.sub(r"[^a-zA-Z0-9_]+", "_", name).lower().strip("_")
        if not skill_id: return None

        category = "general"
        if "game-studios" in filepath.parts: category = "Jeu"
        elif "alter-egos" in filepath.parts: category = "Alter Ego"

        if filepath.suffix.lower() == ".json":
            with filepath.open("r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            if not isinstance(data, dict): return None
            return Skill(skill_id=skill_id, name=data.get("name", name), description=data.get("description", ""), command=data.get("command", filepath.name), category=category)

        elif filepath.suffix.lower() in {".txt", ".md"}:
            with filepath.open("r", encoding="utf-8", errors="replace") as fh:
                content = fh.read().strip()
            return Skill(skill_id=skill_id, name=name, description="Document de compétence", prompt=content, command=filepath.name, category=category)
        return None

    def register_custom_skill(self, skill: Skill) -> None:
        with self._lock: self.skills[skill.skill_id] = skill

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self.skills.get(skill_id.lower().strip())

    def search_skills(self, query: str, limit: int = 5) -> List[Skill]:
        return list(self.skills.values())[:limit]

    def list_all_skills(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._initialized: self.load_skills()
            return [s.to_dict() for s in self.skills.values()]

    def record_feedback(self, skill_id: str, success: bool) -> None:
        pass

skill_registry = SkillRegistry()