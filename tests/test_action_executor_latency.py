# -*- coding: utf-8 -*-
"""Mesure la latence réelle d'une action après C2."""
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


def main():
    from services.action_executor import execute_agent_crm_tool

    print("\n=== TEST : latence action inconnue (aucun effet de bord) ===")

    # Warmup : premier appel = cold start Python + imports
    _ = execute_agent_crm_tool("warmup_action", {})

    # Mesure réelle
    t0 = time.monotonic()
    res = execute_agent_crm_tool("action_qui_nexiste_pas", {})
    elapsed_ms = (time.monotonic() - t0) * 1000

    print(f"\n→ Latence : {elapsed_ms:.2f} ms")
    print(f"→ Status  : {res.get('status')}")
    print(f"→ Message : {res.get('message', '')[:100]}")
    print(f"\n  Avant C2 : ~4400 ms")
    print(f"  Après C2 : attendu < 500 ms")

    assert elapsed_ms < 1000, f"❌ Toujours trop lent : {elapsed_ms:.2f}ms"
    print("\n✅ Gain confirmé — action non bloquée par Neon\n")


if __name__ == "__main__":
    main()