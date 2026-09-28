# -*- coding: utf-8 -*-
"""Test de latence de update_task_state (fire-and-forget)."""
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


def main():
    from state_synchronizer import (
        update_task_state,
        shutdown_state_synchronizer,
    )

    print("\n=== TEST 1 : latence de 3 appels update_task_state ===")
    t0 = time.monotonic()
    update_task_state("test_task_1", "RUNNING", "corr_test", "payload test")
    update_task_state("test_task_1", "COMPLETED", "corr_test", "payload test")
    update_task_state("test_task_2", "RUNNING", "corr_test2", "payload test")
    elapsed_ms = (time.monotonic() - t0) * 1000

    print(f"\n→ 3 appels en {elapsed_ms:.2f} ms")
    print(f"  Attendu : < 50 ms (avant C2 : ~12000 ms)")
    assert elapsed_ms < 100, f"❌ Trop lent : {elapsed_ms:.2f}ms"
    print("✅ TEST 1 OK")

    # Attendre que les écritures en arrière-plan se terminent
    print("\n=== Attente 3s pour les écritures Neon en arrière-plan ===")
    time.sleep(3)

    shutdown_state_synchronizer(wait=True)
    print("\n🎉 TEST LATENCE STATE_SYNCHRONIZER VALIDÉ.\n")


if __name__ == "__main__":
    main()