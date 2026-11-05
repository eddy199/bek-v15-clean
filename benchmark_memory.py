# -*- coding: utf-8 -*-
"""
Benchmark du Memory Coordinator.
Mesure le temps de chaque sous-composant pour identifier le goulot d'étranglement.
"""

import sys
import os
import time
import statistics
import asyncio
from typing import List, Tuple

# Fix encodage Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(label: str, value):
    print(f"  {label:42s} : {value}")


def bench_component(name: str, func, iterations: int = 5) -> Tuple[float, float, float, List[float]]:
    """Benchmark générique d'un composant."""
    times = []
    errors = []
    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            result = func()
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)
        except Exception as e:
            errors.append(str(e))
            times.append(-1)
    return (
        statistics.mean(times) if times else 0,
        statistics.median(times) if times else 0,
        max(times) if times else 0,
        times,
    )


# ══════════════════════════════════════════════════════════════════
# SCENARIO 1 : Pinecone seul
# ══════════════════════════════════════════════════════════════════
def scenario_1_pinecone():
    print_header("SCENARIO 1 — PINECONE (recherche vectorielle cloud)")

    try:
        from memory import search_memory

        # Warmup
        try:
            search_memory("test", top_k=1)
        except Exception:
            pass

        mean, median, p95, times = bench_component(
            "Pinecone",
            lambda: search_memory("Quelle est la capitale de la France ?", top_k=3),
            iterations=5,
        )

        print_result("Moyenne", f"{mean:.0f}ms")
        print_result("Médiane", f"{median:.0f}ms")
        print_result("Max (P95)", f"{p95:.0f}ms")
        print_result("Toutes les mesures", [f"{t:.0f}ms" for t in times])
        print_result("STATUT", "✅ OK" if mean > 0 else "❌ ERREUR")

        return mean
    except Exception as e:
        print_result("STATUT", f"❌ ERREUR : {e}")
        return -1


# ══════════════════════════════════════════════════════════════════
# SCENARIO 2 : ChromaDB seul
# ══════════════════════════════════════════════════════════════════
def scenario_2_chromadb():
    print_header("SCENARIO 2 — CHROMADB (recherche vectorielle locale)")

    try:
        # ChromaDB est utilisé via memory.py, on va tester son chargement
        t0 = time.perf_counter()
        from memory import search_memory

        # Warmup
        try:
            search_memory("test", top_k=1)
        except Exception:
            pass

        # Test direct avec une requête simple
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            try:
                search_memory("test chromadb", top_k=3)
                times.append((time.perf_counter() - t0) * 1000)
            except Exception:
                times.append(-1)

        if times:
            mean = statistics.mean([t for t in times if t >= 0])
            print_result("Moyenne", f"{mean:.0f}ms")
            print_result("STATUT", "✅ OK" if mean > 0 else "❌ ERREUR")
            return mean
        else:
            print_result("STATUT", "❌ Aucune mesure")
            return -1
    except Exception as e:
        print_result("STATUT", f"❌ ERREUR : {e}")
        return -1


# ══════════════════════════════════════════════════════════════════
# SCENARIO 3 : Hindsight seul
# ══════════════════════════════════════════════════════════════════
def scenario_3_hindsight():
    print_header("SCENARIO 3 — HINDSIGHT (base temporelle vectorielle)")

    try:
        from hindsight_memory import hindsight_recall

        mean, median, p95, times = bench_component(
            "Hindsight",
            lambda: hindsight_recall("Quelle est la capitale de la France ?"),
            iterations=5,
        )

        print_result("Moyenne", f"{mean:.0f}ms")
        print_result("Médiane", f"{median:.0f}ms")
        print_result("Max (P95)", f"{p95:.0f}ms")
        print_result("Toutes les mesures", [f"{t:.0f}ms" for t in times])
        print_result("STATUT", "✅ OK" if mean > 0 else "❌ ERREUR")

        return mean
    except Exception as e:
        print_result("STATUT", f"❌ ERREUR : {e}")
        return -1


# ══════════════════════════════════════════════════════════════════
# SCENARIO 4 : Supabase / Neon (PostgreSQL)
# ══════════════════════════════════════════════════════════════════
def scenario_4_supabase():
    print_header("SCENARIO 4 — SUPABASE / NEON (PostgreSQL)")

    try:
        from memory import get_db_connection

        def _test_db():
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return cur.fetchone()
            finally:
                conn.close()

        mean, median, p95, times = bench_component(
            "Supabase",
            _test_db,
            iterations=5,
        )

        print_result("Moyenne", f"{mean:.0f}ms")
        print_result("Médiane", f"{median:.0f}ms")
        print_result("Max (P95)", f"{p95:.0f}ms")
        print_result("Toutes les mesures", [f"{t:.0f}ms" for t in times])
        print_result("STATUT", "✅ OK" if mean > 0 else "❌ ERREUR")

        return mean
    except Exception as e:
        print_result("STATUT", f"❌ ERREUR : {e}")
        return -1


# ══════════════════════════════════════════════════════════════════
# SCENARIO 5 : Coordinator complet
# ══════════════════════════════════════════════════════════════════
def scenario_5_coordinator():
    print_header("SCENARIO 5 — COORDINATOR COMPLET (les 3 sources en parallèle)")

    try:
        from memory_coordinator import coordinate_memories_async

        async def _run_coordinator():
            return await coordinate_memories_async("Quelle est la capitale de la France ?")

        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            try:
                asyncio.run(_run_coordinator())
                elapsed = (time.perf_counter() - t0) * 1000
                times.append(elapsed)
                print_result(f"  Run {len(times)}", f"{elapsed:.0f}ms")
            except Exception as e:
                print_result(f"  Run {len(times)+1}", f"❌ {e}")
                times.append(-1)

        if times:
            valid = [t for t in times if t >= 0]
            if valid:
                mean = statistics.mean(valid)
                print_result("Moyenne", f"{mean:.0f}ms")
                print_result("STATUT", "✅ OK" if mean < 5000 else f"⚠️ LENT ({mean:.0f}ms)")
                return mean
        print_result("STATUT", "❌ Aucune mesure")
        return -1
    except Exception as e:
        print_result("STATUT", f"❌ ERREUR : {e}")
        return -1


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  BENCHMARK MEMORY COORDINATOR — Identification du goulot")
    print("=" * 70)

    results = {}

    results["Pinecone"] = scenario_1_pinecone()
    results["ChromaDB"] = scenario_2_chromadb()
    results["Hindsight"] = scenario_3_hindsight()
    results["Supabase"] = scenario_4_supabase()
    results["Coordinator (total)"] = scenario_5_coordinator()

    # ─── RÉSUMÉ ───
    print("\n" + "=" * 70)
    print("  RÉSUMÉ FINAL — TEMPS PAR COMPOSANT")
    print("=" * 70)

    for name, time_ms in sorted(results.items(), key=lambda x: x[1] if x[1] > 0 else 99999):
        if time_ms < 0:
            print(f"  ❌ {name:30s} : ERREUR")
        elif time_ms < 100:
            print(f"  ✅ {name:30s} : {time_ms:.0f}ms (rapide)")
        elif time_ms < 1000:
            print(f"  ⚠️  {name:30s} : {time_ms:.0f}ms (acceptable)")
        elif time_ms < 5000:
            print(f"  🟠 {name:30s} : {time_ms:.0f}ms (LENT)")
        else:
            print(f"  🔴 {name:30s} : {time_ms:.0f}ms (TRÈS LENT - GOULOT)")

    # Identifier le goulot
    slowest = max(results.items(), key=lambda x: x[1] if x[1] > 0 else 0)
    print("\n" + "=" * 70)
    if slowest[1] > 1000:
        print(f"  🎯 GOULOT D'ÉTRANGLEMENT : {slowest[0]} ({slowest[1]:.0f}ms)")
        print(f"  💡 Recommandation : réduire le timeout ou paralléliser")
    else:
        print(f"  ✅ Tous les composants sont rapides (<1s)")
    print("=" * 70)
    print()