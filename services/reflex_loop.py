# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Reflex Loop v3 (Observation + Critic + Forge)
# ------------------------------------------------------------------------------
# Cycle analytique complet :
#   1. Lit les épisodes des dernières 24h depuis episodic_log (DuckDB)
#   2. Regroupe par (action, status, error_type)
#   3. Filtre les patterns récurrents (count >= MIN_OCCURRENCES)
#   4. [OPTIONNEL] Appelle le Critic LLM sur les patterns en erreur
#   5. [OPTIONNEL] Appelle la Forge sur les critiques récentes
#   6. Écrit un rapport JSON + lisible dans data/reflex_reports/
#
# v3 (2026-09-22) — C6.2 :
#   - Ajout paramètre with_forge (défaut False)
#   - Ajout paramètre forge_dry_run (défaut False)
#   - Lecture de BEK_FORGE_AUTO_STAGING (env.txt)
#   - Lecture de BEK_FORGE_MIN_CONFIDENCE (env.txt)
#   - Lecture de BEK_FORGE_MAX_PROPOSALS_PER_CYCLE (env.txt)
#   - Section "forge" ajoutée au rapport JSON
#   - Zéro régression sur le mode sans forge
# ==============================================================================
from __future__ import annotations

import json
import logging
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.episode_logger import fetch_recent_episodes

logger = logging.getLogger("bek.reflex_loop")


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_HOURS = 24
MIN_OCCURRENCES = 3
TOP_N = 20
REPORTS_DIR = "./data/reflex_reports"


def _env_bool(name: str, default: bool = False) -> bool:
    """Lit une variable d'env booléenne."""
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    """Lit une variable d'env flottante."""
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    """Lit une variable d'env entière."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ==============================================================================
# REFLEX LOOP
# ==============================================================================
class ReflexLoop:
    """
    Cycle d'observation analytique avec option de critique LLM et de forge.

    Usage :
        # Mode observation seule (par défaut)
        loop = ReflexLoop()
        report = loop.run_cycle(hours=24)

        # Mode observation + critique
        report = loop.run_cycle(hours=24, with_critic=True)

        # Mode complet : observation + critique + forge
        report = loop.run_cycle(
            hours=24,
            with_critic=True,
            with_forge=True,
            forge_dry_run=False,
        )
    """

    def __init__(
        self,
        hours: int = DEFAULT_HOURS,
        min_occurrences: int = MIN_OCCURRENCES,
        top_n: int = TOP_N,
        reports_dir: str = REPORTS_DIR,
    ) -> None:
        self.hours = hours
        self.min_occurrences = min_occurrences
        self.top_n = top_n
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # CYCLE PRINCIPAL
    # --------------------------------------------------------------------------
    def run_cycle(
        self,
        hours: Optional[int] = None,
        with_critic: bool = False,
        critic_max_patterns: int = 10,
        with_forge: bool = False,
        forge_dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Exécute un cycle complet : lecture → mining → [critique] → [forge] → rapport.

        Args:
            hours: fenêtre en heures (défaut self.hours)
            with_critic: si True, le Critic LLM analyse les patterns en erreur
            critic_max_patterns: quota max de patterns analysés par le Critic
            with_forge: si True, la Forge génère des propositions
            forge_dry_run: si True, la Forge ne soumet PAS à approval_manager
                          (priorité : paramètre > BEK_FORGE_AUTO_STAGING inversé)
        """
        h = hours if hours is not None else self.hours
        started_at = datetime.now(timezone.utc)

        logger.info(
            "🧠 [ReflexLoop] Cycle démarré | hours=%d | min_occurrences=%d | "
            "with_critic=%s | with_forge=%s",
            h, self.min_occurrences, with_critic, with_forge,
        )

        # --- 1. Collecte ---
        episodes = fetch_recent_episodes(hours=h, limit=5000)
        logger.info("  → %d épisodes lus", len(episodes))

        if not episodes:
            report = self._empty_report(h, started_at)
            self._write_report(report)
            return report

        # --- 2. Mining ---
        patterns = self._mine_patterns(episodes)
        logger.info("  → %d patterns détectés (avant filtre)", len(patterns))

        # --- 3. Filtrage par récurrence ---
        significant = [
            p for p in patterns
            if p["count"] >= self.min_occurrences
        ]
        logger.info(
            "  → %d patterns significatifs (count >= %d)",
            len(significant), self.min_occurrences,
        )

        # --- 4. Tri : count * avg_latency décroissant ---
        significant.sort(
            key=lambda p: p["count"] * p["avg_latency_ms"],
            reverse=True,
        )
        top_patterns = significant[: self.top_n]

        # --- 5. Statistiques globales ---
        stats = self._compute_global_stats(episodes)

        # --- 6. Critique LLM (optionnelle) ---
        critiques: List[Dict[str, Any]] = []
        critic_meta: Dict[str, Any] = {
            "enabled": with_critic,
            "max_patterns": critic_max_patterns,
            "analyzed": 0,
            "succeeded": 0,
            "failed": 0,
        }

        if with_critic:
            critiques, critic_meta = self._run_critic(
                top_patterns, max_patterns=critic_max_patterns
            )

        # --- 7. Forge (optionnelle) ---
        forge_result: Dict[str, Any] = {
            "enabled": with_forge,
            "dry_run": forge_dry_run,
            "auto_staging": _env_bool("BEK_FORGE_AUTO_STAGING", False),
            "analyzed": 0,
            "proposed": 0,
            "skipped": 0,
            "proposals": [],
        }

        if with_forge:
            forge_result = self._run_forge(
                forge_dry_run=forge_dry_run,
                max_proposals=_env_int("BEK_FORGE_MAX_PROPOSALS_PER_CYCLE", 5),
                min_confidence=_env_float("BEK_FORGE_MIN_CONFIDENCE", 0.75),
            )

        # --- 8. Construction du rapport ---
        finished_at = datetime.now(timezone.utc)
        report = {
            "report_id": f"reflex_{started_at.strftime('%Y%m%d_%H%M%S')}",
            "generated_at_utc": started_at.isoformat(),
            "duration_ms": round(
                (finished_at - started_at).total_seconds() * 1000, 2
            ),
            "window_hours": h,
            "min_occurrences": self.min_occurrences,
            "top_n": self.top_n,
            "summary": {
                "total_episodes": stats["total"],
                "success_count": stats["success"],
                "error_count": stats["error"],
                "success_rate": stats["success_rate"],
                "unique_actions": stats["unique_actions"],
                "unique_error_types": stats["unique_error_types"],
                "patterns_total": len(patterns),
                "patterns_significant": len(significant),
            },
            "top_patterns": top_patterns,
            "action_breakdown": stats["action_breakdown"],
            "critic": critic_meta,
            "critiques": critiques,
            "forge": forge_result,
        }

        # --- 9. Persistance + log ---
        self._write_report(report)
        self._log_summary(report)

        return report

    # --------------------------------------------------------------------------
    # CRITIC (Étape 8)
    # --------------------------------------------------------------------------
    def _run_critic(
        self,
        top_patterns: List[Dict[str, Any]],
        max_patterns: int = 10,
    ) -> tuple:
        """Appelle le Critic sur les top patterns en erreur."""
        from services.critic import Critic

        error_patterns = [
            p for p in top_patterns
            if p.get("signature", {}).get("status") == "error"
        ][:max_patterns]

        meta = {
            "enabled": True,
            "max_patterns": max_patterns,
            "error_patterns_available": len([
                p for p in top_patterns
                if p.get("signature", {}).get("status") == "error"
            ]),
            "analyzed": 0,
            "succeeded": 0,
            "failed": 0,
        }

        if not error_patterns:
            logger.info("🧠 [ReflexLoop] Critic : aucun pattern en erreur à analyser.")
            return [], meta

        logger.info(
            "🧠 [ReflexLoop] Critic : analyse de %d patterns en erreur (max=%d)...",
            len(error_patterns), max_patterns,
        )

        critic = Critic(dry_run=True)
        critiques: List[Dict[str, Any]] = []

        for p in error_patterns:
            meta["analyzed"] += 1
            try:
                result = critic.analyze_pattern(p)
                critiques.append(result)
                if result.get("status") == "success":
                    meta["succeeded"] += 1
                else:
                    meta["failed"] += 1
            except Exception as exc:
                logger.exception("🧠 [ReflexLoop] Critic : échec sur un pattern")
                meta["failed"] += 1
                critiques.append({
                    "status": "exception",
                    "error": str(exc)[:300],
                    "pattern_signature": p.get("signature", {}),
                })

        logger.info(
            "🧠 [ReflexLoop] Critic : terminé | %d/%d succès",
            meta["succeeded"], meta["analyzed"],
        )
        return critiques, meta

    # --------------------------------------------------------------------------
    # FORGE (Étape 9 — C6.2)
    # --------------------------------------------------------------------------
    def _run_forge(
        self,
        forge_dry_run: bool = False,
        max_proposals: int = 5,
        min_confidence: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Appelle la Forge pour générer des propositions à partir des critiques
        non encore forgées.
        """
        try:
            from services.forge import forge_batch
        except ImportError as exc:
            logger.warning("🔥 [ReflexLoop] Forge indisponible : %s", exc)
            return {
                "enabled": True,
                "error": f"forge import failed: {exc}",
                "analyzed": 0,
                "proposed": 0,
                "skipped": 0,
                "proposals": [],
            }

        logger.info(
            "🔥 [ReflexLoop] Forge : démarrage batch | dry_run=%s | max=%d | min_conf=%.2f",
            forge_dry_run, max_proposals, min_confidence,
        )

        try:
            batch = forge_batch(
                max_proposals=max_proposals,
                dry_run=forge_dry_run,
                min_confidence=min_confidence,
            )
        except Exception as exc:
            logger.exception("🔥 [ReflexLoop] Forge : échec batch")
            return {
                "enabled": True,
                "error": str(exc)[:300],
                "analyzed": 0,
                "proposed": 0,
                "skipped": 0,
                "proposals": [],
            }

        proposals = batch.get("proposals", []) or []
        result = {
            "enabled": True,
            "dry_run": forge_dry_run,
            "auto_staging": _env_bool("BEK_FORGE_AUTO_STAGING", False),
            "analyzed": batch.get("analyzed", 0),
            "proposed": batch.get("proposed", 0),
            "skipped": batch.get("skipped", 0),
            "proposals": proposals,
        }

        logger.info(
            "🔥 [ReflexLoop] Forge : terminé | analyzed=%d | proposed=%d | skipped=%d",
            result["analyzed"], result["proposed"], result["skipped"],
        )
        return result

    # --------------------------------------------------------------------------
    # NETTOYAGE DE VALEURS
    # --------------------------------------------------------------------------
    @staticmethod
    def _clean_str(value: Any, default: str = "") -> str:
        """Normalise une valeur en string propre, en traitant None et NaN."""
        if value is None:
            return default
        if isinstance(value, float):
            if math.isnan(value):
                return default
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return default
        return s

    # --------------------------------------------------------------------------
    # MINING
    # --------------------------------------------------------------------------
    def _mine_patterns(
        self,
        episodes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Regroupe les épisodes par (action, status, error_type)."""
        buckets: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

        for ep in episodes:
            action = self._clean_str(ep.get("action"), "unknown")
            status = self._clean_str(ep.get("status"), "unknown")
            error_type = self._clean_str(ep.get("error_type"), "")
            signature = (action, status, error_type)
            buckets[signature].append(ep)

        patterns: List[Dict[str, Any]] = []
        for (action, status, error_type), group in buckets.items():
            latencies = []
            for e in group:
                try:
                    latencies.append(float(e.get("latency_ms") or 0.0))
                except (TypeError, ValueError):
                    latencies.append(0.0)

            timestamps = [
                e.get("ts_utc") for e in group if e.get("ts_utc")
            ]
            messages = [
                str(e.get("message", ""))[:200]
                for e in group if e.get("message")
            ]
            params = [
                e.get("parameters") for e in group if e.get("parameters")
            ]

            pattern = {
                "signature": {
                    "action": action,
                    "status": status,
                    "error_type": error_type,
                },
                "count": len(group),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2)
                if latencies else 0.0,
                "min_latency_ms": round(min(latencies), 2) if latencies else 0.0,
                "max_latency_ms": round(max(latencies), 2) if latencies else 0.0,
                "first_seen": str(min(timestamps)) if timestamps else None,
                "last_seen": str(max(timestamps)) if timestamps else None,
                "sample_messages": messages[:3],
                "sample_parameters": [str(p)[:200] for p in params[:3]],
            }
            patterns.append(pattern)

        return patterns

    # --------------------------------------------------------------------------
    # STATISTIQUES GLOBALES
    # --------------------------------------------------------------------------
    def _compute_global_stats(
        self,
        episodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total = len(episodes)
        success = sum(
            1 for e in episodes if self._clean_str(e.get("status")) == "success"
        )
        error = sum(
            1 for e in episodes if self._clean_str(e.get("status")) == "error"
        )

        actions = {
            self._clean_str(e.get("action"))
            for e in episodes if e.get("action")
        }
        actions.discard("")
        actions.discard("unknown")

        error_types = {
            self._clean_str(e.get("error_type"))
            for e in episodes if e.get("error_type")
        }
        error_types.discard("")

        action_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "error": 0, "other": 0}
        )
        for e in episodes:
            action = self._clean_str(e.get("action"), "unknown")
            status = self._clean_str(e.get("status"), "other")
            if status == "success":
                action_stats[action]["success"] += 1
            elif status == "error":
                action_stats[action]["error"] += 1
            else:
                action_stats[action]["other"] += 1

        return {
            "total": total,
            "success": success,
            "error": error,
            "success_rate": round(success / total, 4) if total else 0.0,
            "unique_actions": len(actions),
            "unique_error_types": len(error_types),
            "action_breakdown": dict(action_stats),
        }

    # --------------------------------------------------------------------------
    # RAPPORT
    # --------------------------------------------------------------------------
    def _write_report(self, report: Dict[str, Any]) -> Path:
        filename = f"{report['report_id']}.json"
        path = self.reports_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            logger.info("  → Rapport écrit : %s", path)
        except Exception as exc:
            logger.exception("Échec d'écriture du rapport : %s", exc)
        return path

    def _log_summary(self, report: Dict[str, Any]) -> None:
        s = report["summary"]
        logger.info(
            "🧠 [ReflexLoop] Résumé | episodes=%d | success=%d | error=%d | "
            "patterns_significant=%d",
            s["total_episodes"], s["success_count"],
            s["error_count"], s["patterns_significant"],
        )
        for p in report["top_patterns"][:5]:
            sig = p["signature"]
            et = sig.get("error_type") or "-"
            logger.info(
                "    • %s/%s/%s | count=%d | avg=%.1fms",
                sig["action"], sig["status"], et,
                p["count"], p["avg_latency_ms"],
            )

        critic_meta = report.get("critic", {})
        if critic_meta.get("enabled"):
            logger.info(
                "🧠 [ReflexLoop] Critic | %d/%d succès sur %d patterns en erreur",
                critic_meta.get("succeeded", 0),
                critic_meta.get("analyzed", 0),
                critic_meta.get("error_patterns_available", 0),
            )
            for c in report.get("critiques", [])[:3]:
                if c.get("status") == "success":
                    logger.info(
                        "    ⚖️  %s | %s | conf=%.2f | %s",
                        c.get("category"), c.get("severity"),
                        c.get("confidence", 0.0),
                        (c.get("root_cause") or "")[:80],
                    )

        forge_meta = report.get("forge", {})
        if forge_meta.get("enabled") and not forge_meta.get("error"):
            logger.info(
                "🔥 [ReflexLoop] Forge | %d propositions | dry_run=%s | auto_staging=%s",
                forge_meta.get("proposed", 0),
                forge_meta.get("dry_run", False),
                forge_meta.get("auto_staging", False),
            )
            for prop in forge_meta.get("proposals", [])[:3]:
                logger.info(
                    "    🔨 %s | %s | status=%s",
                    prop.get("proposal_id"),
                    prop.get("rule_type"),
                    prop.get("status"),
                )

    def _empty_report(
        self,
        hours: int,
        started_at: datetime,
    ) -> Dict[str, Any]:
        return {
            "report_id": f"reflex_{started_at.strftime('%Y%m%d_%H%M%S')}",
            "generated_at_utc": started_at.isoformat(),
            "duration_ms": 0.0,
            "window_hours": hours,
            "min_occurrences": self.min_occurrences,
            "top_n": self.top_n,
            "summary": {
                "total_episodes": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0.0,
                "unique_actions": 0,
                "unique_error_types": 0,
                "patterns_total": 0,
                "patterns_significant": 0,
            },
            "top_patterns": [],
            "action_breakdown": {},
            "critic": {"enabled": False, "analyzed": 0, "succeeded": 0, "failed": 0},
            "critiques": [],
            "forge": {"enabled": False, "analyzed": 0, "proposed": 0, "skipped": 0},
            "note": "Aucun épisode dans la fenêtre analysée.",
        }


# ==============================================================================
# TEST AUTONOME
# ==============================================================================
if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    from services.episode_logger import configure, close_all, log_episode, count_episodes

    TEST_DB = "./data/test_reflex_loop_v3.duckdb"
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
            print(f"🗑️  DB de test supprimée : {TEST_DB}")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer {TEST_DB} : {e}")

    configure(TEST_DB)

    print("\n=== PREP : injection de 14 épisodes synthétiques ===")
    before = count_episodes()
    assert before == 0, f"DB devrait être vide, reçu {before}"

    for i in range(6):
        log_episode(
            action="web_sync", parameters={"query": f"test_{i}"},
            status="error", message="Timeout DDG",
            error_type="TimeoutError", latency_ms=5000.0 + i * 10,
        )
    for i in range(4):
        log_episode(
            action="web_sync", parameters={"query": f"ok_{i}"},
            status="success", message="3 résultats",
            latency_ms=120.0 + i * 5,
        )
    for i in range(3):
        log_episode(
            action="create_dynamic_skill",
            parameters={"skill_name": f"evil_{i}"},
            status="error", message="Sandbox AST refus",
            error_type="SandboxRejection", latency_ms=8.0,
        )
    log_episode(
        action="rare_action", parameters={},
        status="error", message="one shot",
        error_type="OneShot", latency_ms=42.0,
    )

    after = count_episodes()
    print(f"Épisodes injectés : {after - before}")
    assert after - before == 14

    print("\n=== TEST 1 : cycle observation pure ===")
    loop = ReflexLoop(hours=1, min_occurrences=3, top_n=20)
    report = loop.run_cycle(hours=1)

    assert report["summary"]["total_episodes"] >= 14
    assert report["critic"]["enabled"] is False
    assert report["forge"]["enabled"] is False
    assert len(report["top_patterns"]) == 3
    print("✅ TEST 1 OK (observation seule)")

    print("\n=== TEST 2 : cycle observation + forge (dry_run) ===")
    # On injecte une critique factice dans reflection_log pour que la forge ait
    # quelque chose à traiter.
    from services.episode_logger import _get_conn
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reflection_log (
            critique_id     VARCHAR PRIMARY KEY,
            pattern_sig     VARCHAR,
            action          VARCHAR,
            status          VARCHAR,
            error_type      VARCHAR,
            pattern_count   INTEGER,
            category        VARCHAR,
            severity        VARCHAR,
            root_cause      VARCHAR,
            fix_suggestion  VARCHAR,
            confidence      DOUBLE,
            tags            VARCHAR,
            provider        VARCHAR,
            model           VARCHAR,
            latency_ms      DOUBLE,
            ts_utc          TIMESTAMP,
            dry_run         BOOLEAN,
            raw_response    VARCHAR
        );
    """)
    conn.execute("""
        INSERT INTO reflection_log
        (critique_id, action, status, error_type, pattern_count,
         category, severity, root_cause, fix_suggestion, confidence, tags,
         provider, model, latency_ms, ts_utc, dry_run, raw_response)
        VALUES
        ('crit_REFLEX_TEST', 'web_sync', 'error', 'TimeoutError', 6,
         'RESEARCH_FAIL', 'HIGH',
         'DDG timeout systématique', 'Router vers Mojeek si DDG timeout',
         0.92, '["web", "timeout"]',
         'nvidia', 'nemotron-ultra', 5000.0, now(), TRUE, '')
    """)

    report2 = loop.run_cycle(
        hours=1,
        with_forge=True,
        forge_dry_run=True,
    )
    assert report2["forge"]["enabled"] is True
    assert report2["forge"]["dry_run"] is True
    assert report2["forge"]["proposed"] >= 1
    print(f"  → Forge proposed : {report2['forge']['proposed']}")
    print(f"  → dry_run : {report2['forge']['dry_run']}")
    print(f"  → auto_staging : {report2['forge']['auto_staging']}")
    print("✅ TEST 2 OK")

    print("\n=== TEST 3 : rapport sur disque avec section forge ===")
    path = loop.reports_dir / f"{report2['report_id']}.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert "forge" in reloaded
    assert "critic" in reloaded
    assert "critiques" in reloaded
    print(f"  → Rapport : {path}")
    print("✅ TEST 3 OK")

    close_all()

    try:
        from event_bus_client import shutdown_event_bus_sync
        shutdown_event_bus_sync()
        print("🔌 EventBus fermé proprement.")
    except Exception as exc:
        print(f"⚠️  EventBus shutdown : {exc}")

    print("\n🎉 TOUS LES TESTS PASSENT — REFLEX LOOP v3 VALIDÉ.\n")