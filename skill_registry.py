"""
BEK-v15.2 HYBRID - Dynamic Skill Registry
-----------------------------------------
Module d'indexation, de scoring et de gestion des compétences (Skills)
pour l'orchestrateur GOAP, Hermes Core V2 et SecurityGuard.

v18.12 (2026-10-04) : ★ Ajout chargement alter egos
  - SKILLS_DIR pointe UNIQUEMENT sur ./skills
  - Suppression du dossier parasite awesome-openclaw-skills
  - Filtre strict des extensions (.json, .md, .txt)
  - ★ v18.12 : load_alter_egos() pour charger skills/alter-egos/
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bek.skill_registry")

# ── Dossiers ────────────────────────────────────────────────────────────────
WORKSPACE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = WORKSPACE_DIR / "skills"

# Extensions autorisées pour les skills
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
    required_tools: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    score: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "command": self.command,
            "category": self.category,
            "risk_level": self.risk_level,
            "required_tools": self.required_tools,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "score": round(self.score, 2),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "enabled": self.enabled,
        }


class SkillRegistry:
    """
    Registre dynamique des compétences BEK.
    Thread-safe, synchronisé avec Neon DB et compatible SecurityGuard.
    """

    ALTER_EGO_DIR_NAME = "alter-egos"

    def __init__(self, directories: Optional[List[Path]] = None):
        if directories is None:
            dirs: List[Path] = [SKILLS_DIR]
        else:
            dirs = list(directories)

        for d in dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.warning("Impossible de créer %s : %s", d, exc)

        self.directories = dirs
        self.skills: Dict[str, Skill] = {}
        self.alter_egos: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._initialized = False

    # ────────────────────────────────────────────────────────────────────────
    # CHARGEMENT
    # ────────────────────────────────────────────────────────────────────────
    def load_skills(self) -> int:
        """Scanne les répertoires et charge les skills avec leurs scores Neon DB."""
        scores_db = self._fetch_db_scores()
        loaded_skills: Dict[str, Skill] = {}

        for directory in self.directories:
            if not directory.exists() or not directory.is_dir():
                continue

            try:
                entries = os.listdir(directory)
            except Exception as exc:
                logger.warning("Impossible de lister %s : %s", directory, exc)
                continue

            for filename in entries:
                filepath = directory / filename
                if not filepath.is_file() or filename.startswith("."):
                    continue

                if filepath.suffix.lower() not in _ALLOWED_EXTENSIONS:
                    continue

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

        # ★ v18.12 — Charger les alter egos séparément
        self.load_alter_egos()

        return len(loaded_skills)

    # ────────────────────────────────────────────────────────────────────────
    # ★ v18.12 — CHARGEMENT DES ALTER EGOS
    # ────────────────────────────────────────────────────────────────────────
    def load_alter_egos(self) -> Dict[str, str]:
        """
        ★ v18.12 — Charge les alter egos spécialisés depuis skills/alter-egos/.

        Structure attendue :
            skills/alter-egos/suntzu/SKILL.md
            skills/alter-egos/nova/SKILL.md
            skills/alter-egos/atlas/SKILL.md
            skills/alter-egos/belfort/SKILL.md
            skills/alter-egos/mentor/SKILL.md
            skills/alter-egos/oracle/SKILL.md

        Returns:
            dict: {"suntzu": "contenu complet", "nova": "...", ...}
        """
        alter_egos: Dict[str, str] = {}
        alter_ego_dir = SKILLS_DIR / self.ALTER_EGO_DIR_NAME

        if not alter_ego_dir.exists() or not alter_ego_dir.is_dir():
            logger.info(
                "[Alter Egos] Dossier %s non trouvé → skip",
                alter_ego_dir
            )
            with self._lock:
                self.alter_egos = alter_egos
            return alter_egos

        # Scanner les sous-dossiers (1 alter ego = 1 dossier)
        for subdir in alter_ego_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith("."):
                continue

            skill_file = subdir / "SKILL.md"
            if not skill_file.exists() or not skill_file.is_file():
                logger.debug(
                    "[Alter Egos] Pas de SKILL.md dans %s → skip",
                    subdir.name
                )
                continue

            try:
                with skill_file.open("r", encoding="utf-8") as fh:
                    content = fh.read().strip()

                if not content:
                    logger.warning(
                        "[Alter Egos] Fichier vide : %s",
                        skill_file
                    )
                    continue

                alter_egos[subdir.name] = content
                logger.info(
                    "[Alter Egos] ✅ Chargé : %s (%d chars)",
                    subdir.name, len(content)
                )
            except Exception as exc:
                logger.warning(
                    "[Alter Egos] Erreur lecture %s : %s",
                    skill_file, exc
                )

        with self._lock:
            self.alter_egos = alter_egos

        logger.info(
            "[Alter Egos] Total : %d alter egos chargés (%s)",
            len(alter_egos),
            ", ".join(alter_egos.keys()) if alter_egos else "aucun"
        )
        return alter_egos

    def get_alter_ego(self, ego_name: str) -> Optional[str]:
        """Retourne le prompt d'un alter ego par son nom."""
        with self._lock:
            return self.alter_egos.get(ego_name)

    def list_alter_egos(self) -> List[str]:
        """Liste les alter egos disponibles."""
        with self._lock:
            return list(self.alter_egos.keys())

    # ────────────────────────────────────────────────────────────────────────
    # SCORES NEON DB
    # ────────────────────────────────────────────────────────────────────────
    def _fetch_db_scores(self) -> Dict[str, Tuple[int, int, float]]:
        """Récupère les statistiques de performance depuis Neon DB si disponible."""
        scores: Dict[str, Tuple[int, int, float]] = {}
        try:
            from memory import get_db_connection  # type: ignore
            conn = get_db_connection()
            if not conn:
                return scores

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT skill_name, success_count, failure_count, last_score
                    FROM skill_performance_metrics;
                    """
                )
                for row in cur.fetchall():
                    scores[row[0]] = (int(row[1]), int(row[2]), float(row[3]))
            conn.close()
        except Exception as exc:
            logger.debug("Neon DB non disponible pour les scores skills : %s", exc)

        return scores

    # ────────────────────────────────────────────────────────────────────────
    # PARSING
    # ────────────────────────────────────────────────────────────────────────
    def _parse_skill_file(
        self, filepath: Path, scores_db: Dict[str, Tuple[int, int, float]]
    ) -> Optional[Skill]:
        """Convertit un fichier JSON, MD ou TXT en objet Skill unifié."""
        if filepath.suffix.lower() not in _ALLOWED_EXTENSIONS:
            return None

        name = filepath.stem
        skill_id = re.sub(r"[^a-zA-Z0-9_]+", "_", name).lower().strip("_")
        if not skill_id:
            return None

        success_count, failure_count, score = scores_db.get(name, (0, 0, 1.0))
        if name not in scores_db:
            success_count, failure_count, score = scores_db.get(skill_id, (0, 0, 1.0))

        if filepath.suffix.lower() == ".json":
            with filepath.open("r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return None

            skill_name = data.get("name", name)
            return Skill(
                skill_id=skill_id,
                name=skill_name,
                description=data.get("description", ""),
                prompt=data.get("prompt", ""),
                command=data.get("command", filepath.name),
                category=data.get("category", "general"),
                risk_level=data.get("risk_level", "L1"),
                required_tools=data.get("required_tools", []),
                preconditions=data.get("preconditions", []),
                effects=data.get("effects", []),
                score=score,
                success_count=success_count,
                failure_count=failure_count,
            )

        elif filepath.suffix.lower() in {".txt", ".md"}:
            with filepath.open("r", encoding="utf-8", errors="replace") as fh:
                content = fh.read().strip()
            lines = content.split("\n", 1)
            skill_name = lines[0].replace("#", "").strip() if lines else name
            desc = "Document de compétence"
            return Skill(
                skill_id=skill_id,
                name=skill_name or name,
                description=desc,
                prompt=content,
                command=filepath.name,
                category="documentation",
                risk_level="L1",
                score=score,
                success_count=success_count,
                failure_count=failure_count,
            )

        return None

    # ────────────────────────────────────────────────────────────────────────
    # API PUBLIQUE
    # ────────────────────────────────────────────────────────────────────────
    def register_custom_skill(self, skill: Skill) -> None:
        """Enregistre ou met à jour dynamiquement une compétence à chaud."""
        with self._lock:
            self.skills[skill.skill_id] = skill
            logger.info(
                "Compétence manuelle enregistrée | id=%s | score=%.2f",
                skill.skill_id, skill.score,
            )

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        with self._lock:
            return self.skills.get(skill_id.lower().strip())

    def search_skills(self, query: str, limit: int = 5) -> List[Skill]:
        """Recherche sémantique basique par mots-clés et tri par score."""
        with self._lock:
            if not self._initialized:
                self.load_skills()

            q = query.lower().strip()
            tokens = set(q.split())
            matches: List[Tuple[float, Skill]] = []

            for s in self.skills.values():
                if not s.enabled:
                    continue
                match_weight = 0.0
                full_text = f"{s.name} {s.description} {s.command} {s.category}".lower()
                for token in tokens:
                    if token in full_text:
                        match_weight += 1.0

                if match_weight > 0 or not tokens:
                    relevance = match_weight * s.score
                    matches.append((relevance, s))

            matches.sort(key=lambda x: x[0], reverse=True)
            return [s for _, s in matches[:limit]]

    def list_all_skills(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._initialized:
                self.load_skills()
            return [
                s.to_dict()
                for s in sorted(self.skills.values(), key=lambda x: x.score, reverse=True)
            ]

    def record_feedback(self, skill_id: str, success: bool) -> None:
        """Met à jour le score en mémoire et persiste dans Neon DB."""
        with self._lock:
            skill = self.skills.get(skill_id)
            if skill:
                if success:
                    skill.success_count += 1
                    skill.score = min(2.0, skill.score + 0.1)
                else:
                    skill.failure_count += 1
                    skill.score = max(0.1, skill.score - 0.2)

        try:
            from app import record_skill_feedback  # type: ignore
            record_skill_feedback(skill_id, success)
        except Exception:
            pass


# Instance Singleton globale
skill_registry = SkillRegistry()