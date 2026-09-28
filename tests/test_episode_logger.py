# -*- coding: utf-8 -*-
"""Test du EpisodeLogger avec la vraie DB (analytics.duckdb)."""
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from services.episode_logger import (
    log_episode,
    fetch_recent_episodes,
    count_episodes,
    close_all,
)


def main():
    print("\n=== TEST : 3 épisodes successifs ===")
    before = count_episodes()
    print(f"Épisodes avant : {before}")

    for i in range(3):
        log_episode(
            action="test_action",
            parameters={"i": i},
            status="success",
            message=f"test run {i}",
            latency_ms=10.0 + i,
        )

    after = count_episodes()
    print(f"Épisodes après : {after}")
    assert after >= before + 3, f"Attendu +3, reçu {after - before}"
    print("✅ TEST OK")

    print("\n=== TEST : fetch et vérification ===")
    eps = fetch_recent_episodes(hours=1, action_filter="test_action", limit=10)
    print(f"Épisodes 'test_action' récents : {len(eps)}")
    assert len(eps) >= 3
    print("✅ TEST OK")

    close_all()
    print("\n🎉 TEST EPISODE LOGGER OK.\n")


if __name__ == "__main__":
    main()