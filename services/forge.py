# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Forge (Étape 9 — C6.1)
# ------------------------------------------------------------------------------
# Transforme les critiques du Critic en PROPOSITIONS actionnables :
#   - Règles sémantiques (fallback, retry, bypass, parallelize, cache, escalate)
#   - Skills code (Python, validés par sandbox AST)
#
# Pipeline :
#   reflection_log (Critic)  →  forge.py  →  forge_proposals (DuckDB)
#                                        →  EventBus (skills-index)
#                                        →  approval_manager (staging)
#
# CORRECTIF C6.1-bis (2026-09-22) :
#   - Flag _FORGE_SHUTDOWN : stoppe les publications pendant l'arrêt
#   - _publish_event protégé contre "interpreter shutdown"
#   - Appel à shutdown_event_bus_sync() en fin de __main__
#   - Zéro spam de retry, fin de programme rapide
# ==============================================================================
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.episode_logger import _get_conn

logger = logging.getLogger("bek.forge")


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_STAGING_TTL_S = 86400    # 24h
DEFAULT_BATCH_SIZE = 5
DEFAULT_MIN_CONFIDENCE = 0.75    # Critic doit avoir confiance >= 75%
FORGE_PROPOSALS_DIR = "./data/forge_proposals"


# ==============================================================================
# ÉTAT SHUTDOWN (C6.1-bis)
# ==============================================================================
_FORGE_SHUTDOWN = False


# ==============================================================================
# SCHÉMA forge_proposals
# ==============================================================================
_SCHEMA_READY = False


def _ensure_forge_schema() -> None:
    """Crée la table forge_proposals si elle n'existe pas."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    try:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forge_proposals (
                proposal_id       VARCHAR PRIMARY KEY,
                proposal_type     VARCHAR NOT NULL,
                rule_type         VARCHAR,
                critique_id       VARCHAR,
                content           VARCHAR NOT NULL,
                confidence        DOUBLE,
                status            VARCHAR NOT NULL,
                approval_id       VARCHAR,
                applied_count     INTEGER DEFAULT 0,
                success_count     INTEGER DEFAULT 0,
                last_applied_at   TIMESTAMP,
                ts_utc            TIMESTAMP,
                expires_at        TIMESTAMP,
                dry_run           BOOLEAN,
                extra             VARCHAR
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_forge_status
            ON forge_proposals(status, ts_utc);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_forge_critique
            ON forge_proposals(critique_id);
        """)
        _SCHEMA_READY = True
        logger.debug("Forge : schéma forge_proposals prêt")
    except Exception as exc:
        logger.exception("Forge : échec création schéma : %s", exc)


# ==============================================================================
# HELPERS
# ==============================================================================
def _stable_hash(*parts: str) -> str:
    """Hash stable (sha256 tronqué) pour déduplication."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_tags(raw: Any) -> List[str]:
    """Normalise les tags (string JSON ou list)."""
    if isinstance(raw, list):
        return [str(t)[:40] for t in raw[:8]]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(t)[:40] for t in parsed[:8]]
        except Exception:
            pass
    return []


# ==============================================================================
# CHARGEMENT DES CRITIQUES
# ==============================================================================
def fetch_unforged_critiques(
    limit: int = 10,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> List[Dict[str, Any]]:
    """Récupère les critiques de reflection_log qui n'ont pas encore été forgées."""
    _ensure_forge_schema()
    conn = _get_conn()

    query = """
        SELECT r.critique_id, r.action, r.status, r.error_type,
               r.pattern_count, r.category, r.severity,
               r.root_cause, r.fix_suggestion, r.confidence,
               r.tags, r.provider, r.model, r.ts_utc
        FROM reflection_log r
        WHERE r.confidence >= ?
          AND r.category IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM forge_proposals f
              WHERE f.critique_id = r.critique_id
          )
        ORDER BY r.ts_utc DESC
        LIMIT ?
    """
    try:
        rows = conn.execute(query, (float(min_confidence), int(limit))).fetchdf()
        return rows.to_dict(orient="records")
    except Exception:
        logger.exception("Forge : échec fetch critiques")
        return []


# ==============================================================================
# GÉNÉRATION DE RÈGLE SÉMANTIQUE
# ==============================================================================
def _build_rule_from_critique(critique: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Construit une règle sémantique JSON à partir d'une critique."""
    category = str(critique.get("category") or "").upper()
    action = str(critique.get("action") or "").strip()
    error_type = str(critique.get("error_type") or "").strip()
    pattern_count = int(critique.get("pattern_count") or 0)
    confidence = float(critique.get("confidence") or 0.0)
    fix_suggestion = str(critique.get("fix_suggestion") or "").strip()
    tags = _parse_tags(critique.get("tags"))

    if not action:
        return None

    rule_type_map = {
        "RESEARCH_FAIL":  "fallback",
        "CODE_SYNTAX":    "bypass",
        "CODE_LOGIC":     "retry",
        "TOOL_MISUSE":    "retry",
        "PLANNER_LOOP":   "bypass",
        "HALLUCINATION":  "escalate",
    }
    rule_type = rule_type_map.get(category, "fallback")

    trigger = {
        "action": action,
        "status": "error",
        "error_type": error_type or None,
        "min_occurrences": max(3, pattern_count),
    }

    action_block: Dict[str, Any] = {
        "type": rule_type,
        "description": fix_suggestion[:400],
    }

    if rule_type == "fallback":
        action_block["fallback_chain"] = ["alternative_provider", "retry", "degrade"]
    elif rule_type == "retry":
        action_block["max_retries"] = 2
        action_block["backoff_factor"] = 2.0
    elif rule_type == "bypass":
        action_block["block_when"] = "matching_trigger"
        action_block["message"] = fix_suggestion[:200]
    elif rule_type == "parallelize":
        action_block["max_parallel"] = 3
    elif rule_type == "cache":
        action_block["ttl_seconds"] = 600
    elif rule_type == "escalate":
        action_block["to_risk_level"] = "L4"
        action_block["reason"] = fix_suggestion[:200]

    rule = {
        "rule_version": "1.0",
        "rule_id": f"rule_{_stable_hash(action, error_type, rule_type, fix_suggestion)}",
        "rule_type": rule_type,
        "priority": 50,
        "trigger": trigger,
        "action": action_block,
        "confidence": confidence,
        "source_critique_id": critique.get("critique_id"),
        "created_at": _now_utc().isoformat(),
        "applied_count": 0,
        "success_count": 0,
        "last_applied_at": None,
        "tags": tags,
    }
    return rule


# ==============================================================================
# CRÉATION DE PROPOSITION
# ==============================================================================
def _persist_proposal(
    proposal_id: str,
    proposal_type: str,
    rule_type: Optional[str],
    critique_id: Optional[str],
    content: Dict[str, Any],
    confidence: float,
    dry_run: bool,
    expires_at: datetime,
    approval_id: str = "",
    status: str = "staging",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Insère une proposition dans forge_proposals."""
    _ensure_forge_schema()
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO forge_proposals (
                proposal_id, proposal_type, rule_type, critique_id,
                content, confidence, status, approval_id,
                applied_count, success_count, last_applied_at,
                ts_utc, expires_at, dry_run, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                proposal_type,
                rule_type,
                critique_id,
                json.dumps(content, ensure_ascii=False),
                float(confidence),
                status,
                approval_id,
                0,
                0,
                None,
                _now_utc(),
                expires_at,
                bool(dry_run),
                json.dumps(extra or {}, ensure_ascii=False),
            ),
        )
    except Exception:
        logger.exception("Forge : échec insertion forge_proposals")


def _write_proposal_json(proposal_id: str, content: Dict[str, Any]) -> Path:
    """Écrit une copie lisible sur disque pour inspection humaine."""
    out_dir = Path(FORGE_PROPOSALS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{proposal_id}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        logger.exception("Forge : échec écriture JSON proposition")
    return path


def _publish_event(action: str, extra: Dict[str, Any]) -> None:
    """
    Publie sur EventBus unifié (best-effort, ne casse jamais).
    C6.1-bis : protégé contre les publications pendant l'arrêt.
    """
    global _FORGE_SHUTDOWN
    if _FORGE_SHUTDOWN:
        return

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(
            "skills-index",
            {"action": action, "source": "forge", **extra},
        )
    except RuntimeError as exc:
        if "interpreter shutdown" in str(exc).lower():
            _FORGE_SHUTDOWN = True
            logger.debug("Forge : EventBus désactivé (shutdown détecté)")
        else:
            logger.debug("Forge : EventBus RuntimeError : %s", exc)
    except Exception as exc:
        logger.debug("Forge : EventBus indisponible : %s", exc)


# ==============================================================================
# API PUBLIQUE — FORGE FROM CRITIQUE
# ==============================================================================
def forge_from_critique(
    critique: Dict[str, Any],
    dry_run: bool = True,
    staging_ttl_s: int = DEFAULT_STAGING_TTL_S,
) -> Optional[Dict[str, Any]]:
    """Transforme une critique en proposition + la persiste."""
    _ensure_forge_schema()

    critique_id = str(critique.get("critique_id") or "").strip()
    if not critique_id:
        logger.warning("Forge : critique sans critique_id, ignorée")
        return None

    rule = _build_rule_from_critique(critique)
    if rule is None:
        logger.warning("Forge : impossible de construire une règle pour %s", critique_id)
        return None

    # Déduplication par rule_id
    rule_id = rule["rule_id"]
    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT proposal_id, status FROM forge_proposals WHERE content LIKE ? LIMIT 1",
            (f'%"rule_id": "{rule_id}"%',),
        ).fetchone()
        if existing:
            logger.info(
                "Forge : règle déjà proposée (proposal=%s, status=%s), skip",
                existing[0], existing[1],
            )
            return None
    except Exception:
        pass

    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    confidence = float(critique.get("confidence") or 0.0)
    expires_at = _now_utc().replace(microsecond=0)
    expires_at = expires_at.fromtimestamp(
        time.time() + staging_ttl_s, tz=timezone.utc
    )

    approval_id = ""
    status = "staging"

    if not dry_run:
        try:
            from approval_manager import approval_manager
            req = approval_manager.submit_request(
                task_id=proposal_id,
                trace_id=f"trace_{uuid.uuid4().hex[:8]}",
                tool="register_semantic_rule",
                args={
                    "rule_id": rule_id,
                    "rule_type": rule["rule_type"],
                    "content": rule,
                    "source": "reflex-loop",
                    "critique_id": critique_id,
                },
                risk_level="L4",
                reason=(
                    f"Forge — {rule['rule_type']} proposé suite à "
                    f"{critique.get('pattern_count', 0)} occurrences de "
                    f"{critique.get('action')}/{critique.get('error_type')}"
                ),
                ttl_seconds=staging_ttl_s,
            )
            approval_id = str(getattr(req, "approval_id", "") or "")
            logger.info(
                "🔥 [Forge] Proposition envoyée en staging | proposal=%s | approval=%s",
                proposal_id, approval_id,
            )
        except Exception:
            logger.exception("Forge : échec soumission approval_manager")
            status = "submission_failed"

    _persist_proposal(
        proposal_id=proposal_id,
        proposal_type="rule",
        rule_type=rule["rule_type"],
        critique_id=critique_id,
        content=rule,
        confidence=confidence,
        dry_run=dry_run,
        expires_at=expires_at,
        approval_id=approval_id,
        status=status,
        extra={
            "critique_category": critique.get("category"),
            "critique_severity": critique.get("severity"),
            "critique_root_cause": critique.get("root_cause", "")[:200],
        },
    )
    _write_proposal_json(proposal_id, rule)

    _publish_event(
        action="forge_proposal_created",
        extra={
            "proposal_id": proposal_id,
            "rule_type": rule["rule_type"],
            "critique_id": critique_id,
            "dry_run": dry_run,
            "status": status,
        },
    )

    logger.info(
        "🔥 [Forge] %s | %s | rule=%s | conf=%.2f | dry_run=%s",
        proposal_id, rule["rule_type"], rule_id, confidence, dry_run,
    )

    return {
        "proposal_id": proposal_id,
        "status": status,
        "proposal_type": "rule",
        "rule_type": rule["rule_type"],
        "rule_id": rule_id,
        "confidence": confidence,
        "dry_run": dry_run,
        "approval_id": approval_id,
        "expires_at": expires_at.isoformat(),
    }


# ==============================================================================
# API PUBLIQUE — FORGE BATCH
# ==============================================================================
def forge_batch(
    max_proposals: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = True,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    staging_ttl_s: int = DEFAULT_STAGING_TTL_S,
) -> Dict[str, Any]:
    """Analyse les critiques non-forgées et crée jusqu'à N propositions."""
    _ensure_forge_schema()

    critiques = fetch_unforged_critiques(
        limit=max_proposals * 2,
        min_confidence=min_confidence,
    )

    logger.info(
        "🔥 [Forge] Batch démarré | %d critiques éligibles | max_proposals=%d | dry_run=%s",
        len(critiques), max_proposals, dry_run,
    )

    proposals: List[Dict[str, Any]] = []
    skipped = 0

    for crit in critiques:
        if len(proposals) >= max_proposals:
            break
        result = forge_from_critique(
            crit, dry_run=dry_run, staging_ttl_s=staging_ttl_s
        )
        if result is None:
            skipped += 1
        else:
            proposals.append(result)

    summary = {
        "analyzed": len(critiques),
        "proposed": len(proposals),
        "skipped": skipped,
        "dry_run": dry_run,
        "proposals": proposals,
    }

    logger.info(
        "🔥 [Forge] Batch terminé | analyzed=%d | proposed=%d | skipped=%d",
        summary["analyzed"], summary["proposed"], summary["skipped"],
    )
    return summary


# ==============================================================================
# LECTURE / STATS
# ==============================================================================
def list_proposals(
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Liste les propositions (toutes ou filtrées par statut)."""
    _ensure_forge_schema()
    conn = _get_conn()

    if status:
        query = """
            SELECT * FROM forge_proposals
            WHERE status = ?
            ORDER BY ts_utc DESC LIMIT ?
        """
        params: tuple = (status, int(limit))
    else:
        query = """
            SELECT * FROM forge_proposals
            ORDER BY ts_utc DESC LIMIT ?
        """
        params = (int(limit),)

    try:
        rows = conn.execute(query, params).fetchdf()
        return rows.to_dict(orient="records")
    except Exception:
        logger.exception("Forge : échec list_proposals")
        return []


def forge_stats() -> Dict[str, Any]:
    """Stats globales sur les propositions."""
    _ensure_forge_schema()
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'staging'  THEN 1 ELSE 0 END) AS staging,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN status = 'expired'  THEN 1 ELSE 0 END) AS expired
            FROM forge_proposals
        """).fetchone()
        if row is None:
            return {"total": 0, "staging": 0, "approved": 0, "rejected": 0, "expired": 0}
        return {
            "total": int(row[0] or 0),
            "staging": int(row[1] or 0),
            "approved": int(row[2] or 0),
            "rejected": int(row[3] or 0),
            "expired": int(row[4] or 0),
        }
    except Exception:
        logger.exception("Forge : échec forge_stats")
        return {"total": 0, "staging": 0, "approved": 0, "rejected": 0, "expired": 0}


# ==============================================================================
# TEST AUTONOME
# ==============================================================================
if __name__ == "__main__":
    import logging as _logging
    import os as _os

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    from services.episode_logger import configure, close_all

    TEST_DB = "./data/test_forge.duckdb"
    if _os.path.exists(TEST_DB):
        try:
            _os.remove(TEST_DB)
            print(f"🗑️  DB de test supprimée : {TEST_DB}")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer {TEST_DB} : {e}")

    configure(TEST_DB)

    # Injection de 2 critiques factices
    _ensure_forge_schema()
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
        ('crit_TEST_1', 'web_sync', 'error', 'TimeoutError', 6,
         'RESEARCH_FAIL', 'HIGH',
         'DDG timeout systématique', 'Router vers Mojeek si DDG timeout',
         0.92, '["web", "timeout"]',
         'nvidia', 'nemotron-ultra', 5000.0, now(), TRUE, ''),
        ('crit_TEST_2', 'create_dynamic_skill', 'error', 'SandboxRejection', 3,
         'CODE_SYNTAX', 'LOW',
         'Imports interdits détectés', 'Renforcer le prompt du générateur',
         0.90, '["skill", "sandbox"]',
         'nvidia', 'nemotron-ultra', 800.0, now(), TRUE, '')
    """)

    print("\n=== TEST 1 : fetch critiques non-forgées ===")
    critiques = fetch_unforged_critiques(limit=10, min_confidence=0.75)
    print(f"  → {len(critiques)} critiques éligibles")
    assert len(critiques) == 2, f"Attendu 2, reçu {len(critiques)}"
    print("✅ TEST 1 OK")

    print("\n=== TEST 2 : forge_from_critique (dry_run=True) ===")
    result = forge_from_critique(critiques[0], dry_run=True)
    assert result is not None, "Forge a renvoyé None"
    print(f"  → proposal_id : {result['proposal_id']}")
    print(f"  → rule_type   : {result['rule_type']}")
    print(f"  → rule_id     : {result['rule_id']}")
    print(f"  → dry_run     : {result['dry_run']}")
    assert result["dry_run"] is True
    assert result["rule_type"] == "fallback"
    print("✅ TEST 2 OK")

    print("\n=== TEST 3 : déduplication ===")
    result2 = forge_from_critique(critiques[0], dry_run=True)
    assert result2 is None, f"Attendu None (déduplication), reçu {result2}"
    print("  → Deuxième forge correctement skippée")
    print("✅ TEST 3 OK")

    print("\n=== TEST 4 : forge_batch (dry_run) ===")
    batch = forge_batch(max_proposals=5, dry_run=True)
    print(f"  → analyzed : {batch['analyzed']}")
    print(f"  → proposed : {batch['proposed']}")
    print(f"  → skipped  : {batch['skipped']}")
    assert batch["proposed"] == 1
    print("✅ TEST 4 OK")

    print("\n=== TEST 5 : forge_stats ===")
    stats = forge_stats()
    print(f"  → {stats}")
    assert stats["total"] == 2, f"Attendu 2, reçu {stats['total']}"
    assert stats["staging"] == 2
    print("✅ TEST 5 OK")

    print("\n=== TEST 6 : list_proposals ===")
    props = list_proposals(status="staging", limit=10)
    print(f"  → {len(props)} propositions en staging")
    assert len(props) == 2
    print("✅ TEST 6 OK")

    # ─── Fermeture propre (C6.1-bis) ───
    close_all()

    try:
        from event_bus_client import shutdown_event_bus_sync
        shutdown_event_bus_sync()
        print("🔌 EventBus fermé proprement.")
    except Exception as exc:
        print(f"⚠️  EventBus shutdown : {exc}")

    print("\n🎉 TOUS LES TESTS PASSENT — FORGE C6.1 VALIDÉE.\n")