# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Critic LLM (Étape 8)
# ------------------------------------------------------------------------------
# Analyse chaque pattern en erreur détecté par le Reflex-Loop en appelant
# un LLM (via provider_manager) et en produisant un diagnostic structuré.
#
# Sortie :
#   - Ligne dans la table DuckDB `reflection_log`
#   - Fichier JSON dans `data/critiques/`
#   - Événement sur EventBus unifié (topic skills-index) — Étape 8c
#
# Mode par défaut : DRY-RUN
#   Le Critic analyse et écrit, mais ne déclenche AUCUNE action corrective.
#   Il sert uniquement à l'observation et à l'alimentation de la Forge.
#
# v2 (2026-09-22) — C3 :
#   - Appel LLM enveloppé dans run_async_safely (nerves/_async_utils.py)
#     → fonctionne depuis un script, FastAPI, ou tout contexte async
#   - Signature de analyze_pattern INCHANGÉE (toujours synchrone)
#   - Fallback bloquant si nerves/_async_utils indisponible
#   - Zéro régression sur le comportement précédent
# ==============================================================================
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.critic_prompt import (
    CATEGORIES,
    SEVERITIES,
    build_critic_messages,
)
from services.episode_logger import _get_conn  # connexion DuckDB thread-local

logger = logging.getLogger("bek.critic")


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_PROVIDER = "nvidia"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_TOKENS = 800
DEFAULT_TEMPERATURE = 0.2   # basse = moins d'hallucination

CRITIQUES_DIR = "./data/critiques"


# ==============================================================================
# TABLE reflection_log (créée au premier usage)
# ==============================================================================
_SCHEMA_READY = False


def _ensure_reflection_schema() -> None:
    """Crée la table reflection_log si elle n'existe pas."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    try:
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
            CREATE INDEX IF NOT EXISTS idx_reflection_category
            ON reflection_log(category, ts_utc);
        """)
        _SCHEMA_READY = True
        logger.debug("Critic : schéma reflection_log prêt")
    except Exception as exc:
        logger.exception("Critic : échec création schema reflection_log : %s", exc)


# ==============================================================================
# APPEL LLM VIA provider_manager — ENVELOPPÉ DANS run_async_safely (C3)
# ==============================================================================
def _call_llm_blocking(messages: List[Dict[str, Any]]) -> str:
    """
    Appel LLM synchrone, à exécuter dans un thread isolé via run_async_safely.
    Retourne la réponse brute accumulée (str).
    Lève une exception en cas d'erreur provider.
    """
    from provider_manager import provider_manager

    raw_response = ""
    for item in provider_manager.execute_chat_stream(
        messages=messages,
        provider=DEFAULT_PROVIDER,
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    ):
        if "error" in item:
            raise RuntimeError(f"Provider error: {item['error']}")
        if "chunk" in item:
            raw_response += item["chunk"]
    return raw_response


async def _call_llm_async(messages: List[Dict[str, Any]]) -> str:
    """Coroutine wrapper pour run_async_safely."""
    import asyncio
    # Exécute l'appel bloquant dans un thread séparé pour ne pas bloquer
    # l'event loop du thread principal (si présent).
    return await asyncio.to_thread(_call_llm_blocking, messages)


def _call_llm_safe(messages: List[Dict[str, Any]]) -> Optional[str]:
    """
    Point d'entrée robuste : fonctionne depuis script, FastAPI, ou contexte async.

    Utilise run_async_safely() du module nerves/_async_utils.py :
      - Aucun event loop actif → asyncio.run
      - Event loop déjà actif → ThreadPoolExecutor isolé

    Retourne None en cas d'échec (l'appelant gère le fallback).
    """
    try:
        from nerves._async_utils import run_async_safely
    except ImportError:
        # Fallback : pas de nerves/_async_utils → appel bloquant direct
        logger.warning(
            "Critic : nerves/_async_utils indisponible, appel LLM bloquant."
        )
        try:
            return _call_llm_blocking(messages)
        except Exception as exc:
            logger.error("Critic : erreur LLM (fallback bloquant) : %s", exc)
            return None

    try:
        result = run_async_safely(_call_llm_async(messages))
        return result
    except Exception as exc:
        logger.error("Critic : erreur LLM via run_async_safely : %s", exc)
        return None


# ==============================================================================
# PARSE ROBUSTE DE LA RÉPONSE LLM
# ==============================================================================
def _parse_critic_response(raw: str) -> Optional[Dict[str, Any]]:
    """
    Parse la réponse du LLM.
    Tolère : espaces, ```json ... ```, texte avant/après le JSON.
    """
    if not raw:
        return None

    text = raw.strip()

    # Enlever les fences ```json ... ```
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
        else:
            text = text.replace("```json", "").replace("```", "").strip()

    # Trouver le premier { ... } équilibré
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1]

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            fixed = candidate.replace("\n", " ").replace("\r", " ")
            data = json.loads(fixed)
        except Exception:
            return None

    if not isinstance(data, dict):
        return None

    # Validation stricte des champs
    category = str(data.get("category", "")).strip().upper()
    severity = str(data.get("severity", "")).strip().upper()

    if category not in CATEGORIES:
        category = "HALLUCINATION"
    if severity not in SEVERITIES:
        severity = "MEDIUM"

    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    root_cause = str(data.get("root_cause", "")).strip()[:500]
    fix_suggestion = str(data.get("fix_suggestion", "")).strip()[:800]

    tags_raw = data.get("tags", [])
    if isinstance(tags_raw, list):
        tags = [str(t)[:40] for t in tags_raw[:8]]
    else:
        tags = []

    return {
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "fix_suggestion": fix_suggestion,
        "confidence": confidence,
        "tags": tags,
    }


# ==============================================================================
# CRITIC
# ==============================================================================
class Critic:
    """
    Analyse les patterns en erreur via provider_manager.

    Usage :
        critic = Critic()
        result = critic.analyze_pattern(pattern)
    """

    def __init__(
        self,
        provider: str = DEFAULT_PROVIDER,
        model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        dry_run: bool = True,
        critiques_dir: str = CRITIQUES_DIR,
    ) -> None:
        self.provider = provider
        self.model = model
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.dry_run = dry_run
        self.critiques_dir = Path(critiques_dir)
        self.critiques_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # API PRINCIPALE
    # --------------------------------------------------------------------------
    def analyze_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse un pattern et retourne un dict structuré.

        Le dict contient toujours :
            - critique_id, status ("success" | "error" | "parse_failed" | ...)
            - category, severity, root_cause, fix_suggestion, confidence, tags (si success)
            - error (si échec)
        """
        _ensure_reflection_schema()

        critique_id = f"crit_{uuid.uuid4().hex[:16]}"
        sig = pattern.get("signature", {}) or {}
        action = sig.get("action", "unknown")
        status = sig.get("status", "unknown")
        error_type = sig.get("error_type") or ""

        logger.info(
            "🧠 [Critic] Analyse pattern | action=%s status=%s error=%s count=%s",
            action, status, error_type or "(none)", pattern.get("count", 0),
        )

        # --- Construction des messages ---
        try:
            messages = build_critic_messages(pattern)
        except Exception as exc:
            logger.exception("Critic : échec build messages")
            return self._record_failure(
                critique_id, pattern, "build_messages_error", str(exc)
            )

        # --- Appel LLM via run_async_safely (C3) ---
        t0 = time.monotonic()
        raw_response = _call_llm_safe(messages)
        latency_ms = (time.monotonic() - t0) * 1000.0

        if raw_response is None:
            return self._record_failure(
                critique_id, pattern, "llm_call_error",
                "Appel LLM échoué (voir logs)",
                provider=self.provider, model=self.model,
                latency_ms=latency_ms,
            )

        # --- Parse robuste ---
        parsed = _parse_critic_response(raw_response)
        if parsed is None:
            logger.warning(
                "Critic : échec parse réponse LLM | raw_len=%d", len(raw_response)
            )
            return self._record_failure(
                critique_id, pattern, "parse_failed",
                raw_response[:500],
                provider=self.provider, model=self.model,
                latency_ms=latency_ms,
            )

        # --- Enregistrement succès ---
        critique = {
            "critique_id": critique_id,
            "status": "success",
            "pattern_signature": sig,
            "pattern_count": pattern.get("count", 0),
            "category": parsed["category"],
            "severity": parsed["severity"],
            "root_cause": parsed["root_cause"],
            "fix_suggestion": parsed["fix_suggestion"],
            "confidence": parsed["confidence"],
            "tags": parsed["tags"],
            "provider": self.provider,
            "model": self.model,
            "latency_ms": round(latency_ms, 2),
            "dry_run": self.dry_run,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
        }

        self._persist_success(critique, raw_response, pattern)
        self._write_json(critique)

        logger.info(
            "✅ [Critic] %s | %s | confidence=%.2f | %.0fms | %s",
            parsed["category"], parsed["severity"],
            parsed["confidence"], latency_ms,
            parsed["root_cause"][:80],
        )

        return critique

    # --------------------------------------------------------------------------
    # PERSISTANCE
    # --------------------------------------------------------------------------
    def _persist_success(
        self,
        critique: Dict[str, Any],
        raw_response: str,
        pattern: Dict[str, Any],
    ) -> None:
        _ensure_reflection_schema()
        try:
            conn = _get_conn()
            sig = critique.get("pattern_signature", {}) or {}
            conn.execute(
                """
                INSERT INTO reflection_log (
                    critique_id, pattern_sig, action, status, error_type,
                    pattern_count, category, severity, root_cause, fix_suggestion,
                    confidence, tags, provider, model, latency_ms, ts_utc,
                    dry_run, raw_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    critique["critique_id"],
                    json.dumps(sig, ensure_ascii=False),
                    sig.get("action", "unknown"),
                    sig.get("status", "unknown"),
                    sig.get("error_type") or "",
                    int(critique.get("pattern_count", 0)),
                    critique["category"],
                    critique["severity"],
                    critique["root_cause"],
                    critique["fix_suggestion"],
                    float(critique["confidence"]),
                    json.dumps(critique.get("tags", []), ensure_ascii=False),
                    critique["provider"],
                    critique["model"],
                    float(critique["latency_ms"]),
                    datetime.now(timezone.utc),
                    bool(critique["dry_run"]),
                    (raw_response or "")[:2000],
                ),
            )
        except Exception:
            logger.exception("Critic : échec insertion reflection_log")

    def _write_json(self, critique: Dict[str, Any]) -> Path:
        filename = f"{critique['critique_id']}.json"
        path = self.critiques_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(critique, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            logger.exception("Critic : échec écriture JSON")
        return path

    def _record_failure(
        self,
        critique_id: str,
        pattern: Dict[str, Any],
        error_kind: str,
        error_msg: str,
        provider: str = "",
        model: str = "",
        latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        sig = pattern.get("signature", {}) or {}
        return {
            "critique_id": critique_id,
            "status": error_kind,
            "pattern_signature": sig,
            "pattern_count": pattern.get("count", 0),
            "category": None,
            "severity": None,
            "root_cause": f"[{error_kind}] {error_msg[:200]}",
            "fix_suggestion": None,
            "confidence": 0.0,
            "tags": [],
            "provider": provider,
            "model": model,
            "latency_ms": round(latency_ms, 2),
            "dry_run": self.dry_run,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "error": error_msg[:500],
        }

    # --------------------------------------------------------------------------
    # BATCH
    # --------------------------------------------------------------------------
    def analyze_patterns(
        self,
        patterns: List[Dict[str, Any]],
        only_errors: bool = True,
        max_patterns: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Analyse une liste de patterns (filtrés sur erreur par défaut).
        """
        selected: List[Dict[str, Any]] = []

        for p in patterns:
            sig = p.get("signature", {}) or {}
            if only_errors and sig.get("status") != "error":
                continue
            selected.append(p)
            if len(selected) >= max_patterns:
                break

        logger.info(
            "🧠 [Critic] Batch : %d patterns à analyser (sur %d fournis)",
            len(selected), len(patterns),
        )

        results = []
        for p in selected:
            r = self.analyze_pattern(p)
            results.append(r)
        return results


# ==============================================================================
# TEST AUTONOME (mock LLM, pas d'appel réseau)
# ==============================================================================
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    # --- Utilise une DB isolée ---
    from services.episode_logger import configure, close_all
    configure("./data/test_critic.duckdb")

    print("\n=== TEST 1 : parse — JSON valide ===")
    raw = '{"category": "RESEARCH_FAIL", "severity": "HIGH", "root_cause": "DDG timeout", "fix_suggestion": "Fallback Mojeek", "confidence": 0.85, "tags": ["web"]}'
    parsed = _parse_critic_response(raw)
    assert parsed is not None
    assert parsed["category"] == "RESEARCH_FAIL"
    assert parsed["severity"] == "HIGH"
    assert parsed["confidence"] == 0.85
    print(f"  → {parsed}")
    print("✅ TEST 1 OK")

    print("\n=== TEST 2 : parse — JSON dans un fence ```json ``` ===")
    raw = '```json\n{"category": "CODE_SYNTAX", "severity": "LOW", "root_cause": "subprocess import", "fix_suggestion": "hardening prompt", "confidence": 0.9, "tags": []}\n```'
    parsed = _parse_critic_response(raw)
    assert parsed["category"] == "CODE_SYNTAX"
    print("✅ TEST 2 OK")

    print("\n=== TEST 3 : parse — catégorie invalide → fallback HALLUCINATION ===")
    raw = '{"category": "WHATEVER", "severity": "BOGUS", "root_cause": "x", "fix_suggestion": "y", "confidence": 2.0}'
    parsed = _parse_critic_response(raw)
    assert parsed["category"] == "HALLUCINATION"
    assert parsed["severity"] == "MEDIUM"
    assert parsed["confidence"] == 1.0  # clampé
    print("✅ TEST 3 OK")

    print("\n=== TEST 4 : parse — texte avant/après le JSON ===")
    raw = "Voici mon analyse : {\"category\": \"TOOL_MISUSE\", \"severity\": \"MEDIUM\", \"root_cause\": \"arg manquant\", \"fix_suggestion\": \"valider args\", \"confidence\": 0.7} Fin."
    parsed = _parse_critic_response(raw)
    assert parsed["category"] == "TOOL_MISUSE"
    print("✅ TEST 4 OK")

    print("\n=== TEST 5 : parse — réponse vide → None ===")
    assert _parse_critic_response("") is None
    assert _parse_critic_response("pas de json ici") is None
    print("✅ TEST 5 OK")

    print("\n=== TEST 6 : schema reflection_log créé ===")
    _ensure_reflection_schema()
    from services.episode_logger import _get_conn
    conn = _get_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='reflection_log'"
    ).fetchone()
    assert row is not None, "reflection_log non créée"
    print("✅ TEST 6 OK")

    close_all()
    print("\n🎉 TOUS LES TESTS PASSENT — CRITIC V2 VALIDÉ (parse + schema).\n")