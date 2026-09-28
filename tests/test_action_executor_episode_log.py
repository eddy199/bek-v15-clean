# -*- coding: utf-8 -*-
"""Vérifie que action_executor loggue bien chaque action dans episodic_log."""
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from services.action_executor import execute_agent_crm_tool
from services.episode_logger import count_episodes, fetch_recent_episodes, close_all


def main():
    print("\n=== TEST : 2 actions → 2 épisodes ===")
    before = count_episodes()
    print(f"Épisodes avant : {before}")

    # Action inconnue → status error
    execute_agent_crm_tool("action_qui_nexiste_pas", {"x": 1})
    # Skill malveillant → status error (sandbox)
    execute_agent_crm_tool(
        "create_dynamic_skill",
        {"skill_name": "evil_test", "code_content": "import subprocess"},
    )

    after = count_episodes()
    print(f"Épisodes après : {after}")
    assert after >= before + 2, f"Attendu +2, reçu {after - before}"
    print("✅ TEST OK")

    print("\n=== Vérification du contenu ===")
    eps = fetch_recent_episodes(hours=1, limit=5)
    for e in eps[:5]:
        print(f"  {e['action']:24s} | {e['status']:10s} | {e['latency_ms']:.1f}ms")

    close_all()
    print("\n🎉 TEST ACTION EXECUTOR EPISODE LOG OK.\n")


if __name__ == "__main__":
    main()