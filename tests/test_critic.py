# -*- coding: utf-8 -*-
"""Test d'intégration du Critic avec provider_manager réel (nvidia)."""
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from services.critic import Critic
from services.episode_logger import configure, close_all


def main():
    configure("./data/test_critic_integration.duckdb")

    critic = Critic(dry_run=True)

    # Pattern synthétique issu du Reflex-Loop
    pattern = {
        "signature": {
            "action": "web_sync",
            "status": "error",
            "error_type": "TimeoutError",
        },
        "count": 12,
        "avg_latency_ms": 5025.0,
        "min_latency_ms": 5000.0,
        "max_latency_ms": 5100.0,
        "sample_messages": ["Timeout DDG", "DDG timeout après 5s"],
        "sample_parameters": ["{'query': 'actualités IA 2026'}"],
    }

    print("\n=== TEST : analyse pattern via LLM ===")
    result = critic.analyze_pattern(pattern)

    print(f"Status      : {result.get('status')}")
    print(f"Category    : {result.get('category')}")
    print(f"Severity    : {result.get('severity')}")
    print(f"Root cause  : {result.get('root_cause', '')[:120]}")
    print(f"Fix         : {result.get('fix_suggestion', '')[:120]}")
    print(f"Confidence  : {result.get('confidence')}")
    print(f"Latency     : {result.get('latency_ms')} ms")

    # --- Assertions ---
    assert result.get("status") == "success", \
        f"Critic devrait réussir, reçu : {result}"
    assert result.get("category") in (
        "RESEARCH_FAIL", "CODE_SYNTAX", "CODE_LOGIC",
        "TOOL_MISUSE", "PLANNER_LOOP", "HALLUCINATION",
    )
    assert result.get("severity") in ("LOW", "MEDIUM", "HIGH")
    assert result.get("confidence") is not None
    assert 0.0 <= float(result["confidence"]) <= 1.0
    assert result.get("dry_run") is True
    print("✅ TEST OK")

    close_all()
    print("\n🎉 TEST CRITIC INTÉGRATION OK.\n")


if __name__ == "__main__":
    main()