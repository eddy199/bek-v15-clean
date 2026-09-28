# -*- coding: utf-8 -*-
"""Test Reflex-Loop v1 sur données réelles d'episodic_log."""
import json
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from services.reflex_loop import ReflexLoop
from services.episode_logger import (
    log_episode, close_all, count_episodes,
)


def main():
    print("\n=== TEST : Reflex-Loop sur DB réelle ===")
    before = count_episodes()
    print(f"Épisodes en base : {before}")

    # Injecte 5 épisodes récurrents pour être sûr d'avoir un pattern
    for i in range(5):
        log_episode(
            action="test_reflex_action",
            parameters={"i": i},
            status="error",
            message="erreur récurrente de test",
            error_type="TestError",
            latency_ms=250.0,
        )

    loop = ReflexLoop(hours=1, min_occurrences=3, top_n=10)
    report = loop.run_cycle(hours=1)

    print("\nRapport généré :")
    print(json.dumps(report["summary"], indent=2))

    patterns = [
        p for p in report["top_patterns"]
        if p["signature"]["action"] == "test_reflex_action"
    ]
    assert len(patterns) == 1, "Pattern attendu non trouvé"
    assert patterns[0]["count"] >= 5
    print(f"\n✅ Pattern trouvé : count={patterns[0]['count']}")

    # Vérifie que le fichier est écrit
    path = loop.reports_dir / f"{report['report_id']}.json"
    assert path.exists()
    print(f"✅ Rapport sur disque : {path}")

    close_all()
    print("\n🎉 TEST REFLEX LOOP OK.\n")


if __name__ == "__main__":
    main()