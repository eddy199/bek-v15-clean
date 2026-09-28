# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Test Reflex-Loop v2 (Reflex + Critic intégré)
# ------------------------------------------------------------------------------
# Vérifie le pipeline complet : injection → mining → critique → rapport.
# Utilise une DB de test isolée (nettoyée à chaque run).
# ==============================================================================
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


# ==============================================================================
# CONFIG DB DE TEST ISOLÉE
# ==============================================================================
TEST_DB = "./data/test_reflex_full.duckdb"


def _reset_test_db():
    """Supprime la DB de test pour repartir à zéro."""
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
            print(f"🗑️  DB de test supprimée : {TEST_DB}")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer {TEST_DB} : {e}")


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    # Étape 1 : DB fraîche
    _reset_test_db()

    from services.episode_logger import (
        configure,
        close_all,
        log_episode,
        count_episodes,
    )

    configure(TEST_DB)

    print("\n=== PREP : injection de 15 épisodes synthétiques ===")
    before = count_episodes()
    assert before == 0, f"DB devrait être vide, reçu {before}"

    # Pattern A : web_sync timeout x 6 (SERA critiqué — RESEARCH_FAIL attendu)
    for i in range(6):
        log_episode(
            action="web_sync",
            parameters={"query": f"test_timeout_{i}"},
            status="error",
            message="Timeout DDG",
            error_type="TimeoutError",
            latency_ms=5000.0 + i * 10,
        )

    # Pattern B : web_sync success x 4 (NE sera PAS critiqué)
    for i in range(4):
        log_episode(
            action="web_sync",
            parameters={"query": f"ok_{i}"},
            status="success",
            message="3 résultats",
            latency_ms=120.0 + i * 5,
        )

    # Pattern C : create_dynamic_skill sandbox x 3 (SERA critiqué — CODE_SYNTAX attendu)
    for i in range(3):
        log_episode(
            action="create_dynamic_skill",
            parameters={"skill_name": f"evil_{i}"},
            status="error",
            message="Sandbox AST refus",
            error_type="SandboxRejection",
            latency_ms=8.0,
        )

    # Pattern D : action unique (ne doit PAS apparaître dans les top significatifs)
    log_episode(
        action="rare_action",
        parameters={},
        status="error",
        message="one shot",
        error_type="OneShot",
        latency_ms=42.0,
    )

    after = count_episodes()
    print(f"→ Épisodes injectés : {after - before}")
    assert after - before == 14, f"Attendu 14, reçu {after - before}"
    print("✅ PREP OK")

    # ==========================================================================
    # TEST 1 : cycle SANS Critic (mode observation pure)
    # ==========================================================================
    print("\n=== TEST 1 : cycle sans Critic ===")
    from services.reflex_loop import ReflexLoop

    loop = ReflexLoop(hours=1, min_occurrences=3, top_n=20)
    report = loop.run_cycle(hours=1)

    assert report["summary"]["total_episodes"] >= 14
    assert report["critic"]["enabled"] is False, \
        f"Critic devrait être désactivé, reçu : {report['critic']}"
    assert report["critiques"] == [], "Pas de critiques attendues"

    # Vérifier les top patterns
    pattern_actions = [
        p["signature"]["action"] for p in report["top_patterns"]
    ]
    assert "web_sync" in pattern_actions
    assert "create_dynamic_skill" in pattern_actions
    assert "rare_action" not in pattern_actions, \
        "rare_action (count=1) ne devrait pas être significative"

    print(f"  → Patterns significatifs : {len(report['top_patterns'])}")
    for p in report["top_patterns"]:
        sig = p["signature"]
        print(
            f"    • {sig['action']:24s} | {sig['status']:8s} | "
            f"{sig.get('error_type') or '-':18s} | count={p['count']}"
        )
    print("✅ TEST 1 OK (pas d'appel LLM)")

    # ==========================================================================
    # TEST 2 : cycle AVEC Critic (mode complet — appels LLM réels)
    # ==========================================================================
    print("\n=== TEST 2 : cycle avec Critic (2 patterns max) ===")
    print("  ⏱️  Ce test peut prendre 30-60s (appels LLM réels)")

    report2 = loop.run_cycle(
        hours=1,
        with_critic=True,
        critic_max_patterns=2,
    )

    assert report2["critic"]["enabled"] is True
    assert report2["critic"]["analyzed"] >= 1, \
        f"Au moins 1 pattern doit être analysé : {report2['critic']}"
    assert report2["critic"]["analyzed"] <= 2

    print(f"\n  → Critic meta : {report2['critic']}")
    for c in report2["critiques"]:
        if c.get("status") == "success":
            print(
                f"    ⚖️  {c['category']:18s} | {c['severity']:6s} | "
                f"conf={c['confidence']:.2f} | {c['latency_ms']:.0f}ms"
            )
            print(f"       Cause : {c['root_cause'][:100]}")
        else:
            print(f"    ❌  {c.get('status')} : {c.get('error', '')[:100]}")

    # Au moins une critique a réussi
    successes = [c for c in report2["critiques"] if c.get("status") == "success"]
    assert len(successes) >= 1, \
        f"Au moins 1 critique doit réussir, reçu : {report2['critiques']}"

    # Vérifier que les catégories sont valides
    from services.critic_prompt import CATEGORIES, SEVERITIES
    for c in successes:
        assert c["category"] in CATEGORIES, \
            f"Catégorie invalide : {c['category']}"
        assert c["severity"] in SEVERITIES, \
            f"Sévérité invalide : {c['severity']}"

    print("✅ TEST 2 OK")

    # ==========================================================================
    # TEST 3 : rapport JSON sur disque avec section critiques
    # ==========================================================================
    print("\n=== TEST 3 : rapport JSON écrit avec section critiques ===")
    report_path = loop.reports_dir / f"{report2['report_id']}.json"
    assert report_path.exists(), f"Rapport absent : {report_path}"

    with open(report_path, "r", encoding="utf-8") as f:
        reloaded = json.load(f)

    assert "critic" in reloaded
    assert "critiques" in reloaded
    assert reloaded["report_id"] == report2["report_id"]

    print(f"  → Rapport : {report_path}")
    print(f"  → Taille  : {report_path.stat().st_size} bytes")
    print("✅ TEST 3 OK")

    # ==========================================================================
    # TEST 4 : table reflection_log en DuckDB
    # ==========================================================================
    print("\n=== TEST 4 : table reflection_log alimentée ===")
    from services.episode_logger import _get_conn

    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) FROM reflection_log"
    ).fetchone()
    count = int(row[0]) if row else 0

    print(f"  → {count} ligne(s) dans reflection_log")
    assert count >= 1, "Au moins 1 ligne reflection_log attendue"
    print("✅ TEST 4 OK")

    # ==========================================================================
    # Nettoyage
    # ==========================================================================
    close_all()
    print("\n🎉 C5 VALIDÉE — Reflex-Loop v2 + Critic fonctionnels.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ÉCHEC : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)