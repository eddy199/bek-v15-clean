# -*- coding: utf-8 -*-
"""Vérifie que le Critic fonctionne depuis un contexte async (C3)."""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


async def main():
    """Simule un appel Critic depuis FastAPI (event loop actif)."""
    from services.critic import Critic
    from services.episode_logger import configure, close_all

    configure("./data/test_critic_async.duckdb")

    critic = Critic(dry_run=True)

    pattern = {
        "signature": {
            "action": "web_sync",
            "status": "error",
            "error_type": "TimeoutError",
        },
        "count": 5,
        "avg_latency_ms": 5000.0,
        "min_latency_ms": 5000.0,
        "max_latency_ms": 5100.0,
        "sample_messages": ["Timeout DDG"],
        "sample_parameters": ["{'query': 'test'}"],
    }

    print("\n=== TEST : appel Critic depuis event loop actif ===")
    loop = asyncio.get_running_loop()
    print(f"Event loop actif : {loop is not None}")
    print(f"Thread : {loop}")

    # Appel direct (synchrone) depuis un contexte async — c'est ce qui
    # planterait SANS le fix C3 (RuntimeError: This event loop is already running).
    result = critic.analyze_pattern(pattern)

    print(f"\nStatus     : {result.get('status')}")
    print(f"Category   : {result.get('category')}")
    print(f"Severity   : {result.get('severity')}")
    print(f"Confidence : {result.get('confidence')}")
    print(f"Latency    : {result.get('latency_ms')} ms")

    assert result.get("status") == "success", \
        f"Le Critic a échoué en contexte async : {result}"
    print("\n✅ TEST OK — Critic fonctionne depuis event loop actif")

    close_all()
    print("\n🎉 C3 VALIDÉE.\n")


if __name__ == "__main__":
    asyncio.run(main())