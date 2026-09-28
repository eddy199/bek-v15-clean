# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-LOOP Recorder
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-LOOP-v1.0
# 📄 Doc : docs/brevets/BREVET_LOOP.md
# 🎯 Rôle : Enregistrement et analyse des épisodes
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.loop")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_LOOP_DEFAULT_HOURS = 24
BEK_LOOP_STORAGE_FILE = "data/bek_loop_episodes.json"
BEK_LOOP_MAX_EPISODES = 10000


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekLoopRecorder:
    """
    Enregistreur BEK-LOOP.

    Enregistre chaque épisode d'exécution et permet l'analyse
    des patterns pour l'amélioration continue.

    Usage :
        recorder = BekLoopRecorder()
        recorder.record({
            "query": "Cherche Bitcoin",
            "tier": "TIER_2",
            "success": True,
            "time_ms": 35000
        })
        
        analysis = recorder.analyze(hours=24)
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or BEK_LOOP_STORAGE_FILE)
        self._episodes: List[Dict[str, Any]] = []
        self._load()

    # ──────────────────────────────────────────────────────────────────────────
    # CHARGEMENT / SAUVEGARDE
    # ──────────────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Charge les épisodes depuis le disque."""
        if not self.storage_path.exists():
            self._episodes = []
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._episodes = data.get("episodes", [])
            logger.info("BekLoop : %d épisodes chargés", len(self._episodes))
        except Exception as exc:
            logger.warning("BekLoop : erreur chargement : %s", exc)
            self._episodes = []

    def _save(self) -> None:
        """Sauvegarde les épisodes sur le disque."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Limiter la taille
            if len(self._episodes) > BEK_LOOP_MAX_EPISODES:
                self._episodes = self._episodes[-BEK_LOOP_MAX_EPISODES:]

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"episodes": self._episodes},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as exc:
            logger.error("BekLoop : erreur sauvegarde : %s", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # ENREGISTREMENT
    # ──────────────────────────────────────────────────────────────────────────

    def record(self, episode: Dict[str, Any]) -> str:
        """
        Enregistre un épisode d'exécution.

        Args:
            episode: {
                "query": str,
                "tier": str,
                "success": bool,
                "time_ms": float,
                "result": str (optionnel),
                "error": str (optionnel)
            }

        Returns:
            str: episode_id
        """
        episode_id = f"ep_{uuid.uuid4().hex[:12]}"

        episode_record = {
            "episode_id": episode_id,
            "timestamp": time.time(),
            "query": episode.get("query", ""),
            "tier": episode.get("tier", "TIER_3"),
            "success": bool(episode.get("success", False)),
            "time_ms": float(episode.get("time_ms", 0.0)),
            "result_summary": str(episode.get("result", ""))[:200],
            "error": episode.get("error"),
            "metadata": episode.get("metadata", {}),
        }

        self._episodes.append(episode_record)

        # Sauvegarder à chaque enregistrement (démo + robustesse)
        self._save()

        logger.debug(
            "BekLoop : épisode %s enregistré | tier=%s | success=%s",
            episode_id,
            episode_record["tier"],
            episode_record["success"],
        )

        return episode_id

    # ──────────────────────────────────────────────────────────────────────────
    # ANALYSE
    # ──────────────────────────────────────────────────────────────────────────

    def analyze(self, hours: int = BEK_LOOP_DEFAULT_HOURS) -> Dict[str, Any]:
        """
        Analyse les épisodes récents.

        Args:
            hours: Fenêtre d'analyse en heures

        Returns:
            dict: {
                "total": int,
                "success_rate": float,
                "avg_time_ms": float,
                "by_tier": {...},
                "patterns": [...],
                "errors": [...]
            }
        """
        cutoff = time.time() - (hours * 3600)
        recent = [e for e in self._episodes if e.get("timestamp", 0) >= cutoff]

        if not recent:
            return {
                "total": 0,
                "success_rate": 0.0,
                "avg_time_ms": 0.0,
                "by_tier": {},
                "patterns": [],
                "errors": [],
            }

        # Statistiques globales
        total = len(recent)
        success_count = sum(1 for e in recent if e.get("success"))
        total_time = sum(e.get("time_ms", 0) for e in recent)

        # Par tier
        by_tier = defaultdict(lambda: {"count": 0, "success": 0, "time_ms": 0.0})
        for e in recent:
            tier = e.get("tier", "UNKNOWN")
            by_tier[tier]["count"] += 1
            if e.get("success"):
                by_tier[tier]["success"] += 1
            by_tier[tier]["time_ms"] += e.get("time_ms", 0.0)

        by_tier_summary = {
            tier: {
                "count": stats["count"],
                "success_rate": round(stats["success"] / stats["count"], 3) if stats["count"] else 0.0,
                "avg_time_ms": round(stats["time_ms"] / stats["count"], 2) if stats["count"] else 0.0,
            }
            for tier, stats in by_tier.items()
        }

        # Patterns d'échec
        failures = [e for e in recent if not e.get("success")]
        patterns = self._detect_failure_patterns(failures)

        # Erreurs fréquentes
        errors = self._collect_errors(failures)

        return {
            "total": total,
            "success_rate": round(success_count / total, 3),
            "avg_time_ms": round(total_time / total, 2),
            "by_tier": by_tier_summary,
            "patterns": patterns,
            "errors": errors,
            "window_hours": hours,
        }

    def _detect_failure_patterns(
        self,
        failures: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Détecte les patterns d'échec répétés."""
        # Grouper par tier
        by_tier = defaultdict(int)
        for e in failures:
            by_tier[e.get("tier", "UNKNOWN")] += 1

        # Patterns = tiers avec >= 3 échecs
        patterns = []
        for tier, count in by_tier.items():
            if count >= 3:
                patterns.append({
                    "type": "repeated_failure",
                    "tier": tier,
                    "count": count,
                    "suggestion": f"Reconsidérer le routing vers {tier}",
                })

        return patterns

    def _collect_errors(
        self,
        failures: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Collecte les erreurs fréquentes."""
        error_count = defaultdict(int)
        for e in failures:
            err = e.get("error")
            if err:
                error_count[err[:100]] += 1

        return [
            {"error": err, "count": count}
            for err, count in sorted(
                error_count.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Nombre total d'épisodes."""
        return len(self._episodes)

    def clear(self) -> int:
        """Efface tous les épisodes."""
        count = len(self._episodes)
        self._episodes = []
        self._save()
        return count


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_loop_record(episode: Dict[str, Any]) -> str:
    """Enregistre un épisode."""
    recorder = BekLoopRecorder()
    return recorder.record(episode)


def bek_loop_analyze(hours: int = BEK_LOOP_DEFAULT_HOURS) -> Dict[str, Any]:
    """Analyse les épisodes récents."""
    recorder = BekLoopRecorder()
    return recorder.analyze(hours=hours)


def bek_loop_count() -> int:
    """Nombre total d'épisodes."""
    recorder = BekLoopRecorder()
    return recorder.count()