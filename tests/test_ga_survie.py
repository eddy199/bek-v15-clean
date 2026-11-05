import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nerves.ga_nerves import get_ga_engine

engine = get_ga_engine()
print("--- [STRESS TEST] Simulation de 10 échecs consécutifs ---")
initial_pop = [g.gene_id for g in engine.population]
print(f"Population initiale : {initial_pop}")

for i in range(10):
    # On fait échouer TOUS les gènes
    for gene in engine.population:
        engine.calculate_fitness(gene, success=False, execution_time_ms=1000, tokens_used=1000)
    engine.evolve()  # Le GA doit muter pour survivre

final_pop = [g.gene_id for g in engine.population]
print(f"Population finale   : {final_pop}")
mutations = sum(1 for g in final_pop if "mut" in g)
print(f"Nombre de mutations : {mutations}")

if len(set(final_pop) - set(initial_pop)) > 0:
    print("\n🎉 SUCCÈS : Le GA a muté pour survivre aux échecs répétés !")
else:
    print("\n⚠️ Le GA a gardé les mêmes gènes (l'élitisme a préservé les meilleurs).")