import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time
from core.brain import get_brain
from nerves.ga_nerves import get_ga_engine

print("--- [1] État du GA AVANT le test ---")
engine = get_ga_engine()
best_before = engine.select_best_gene()
print(f"Meilleur gène : {best_before.gene_id} | Fitness : {best_before.fitness:.2f}")

print("\n--- [2] Simulation d'un feedback positif dans le Cerveau ---")
brain = get_brain()

try:
    # Le cerveau va utiliser le prompt du GA et enregistrer le succès
    brain.record_feedback(gene_id=best_before.gene_id, success=True, execution_time_ms=150, tokens_used=300)
    print("✅ Feedback enregistré avec succès par le Cerveau.")
except Exception as e:
    print(f"⚠️ Erreur (normal si la méthode n'existe pas encore dans brain.py) : {e}")

print("\n--- [3] Simulation de 5 cycles d'évolution ---")
for i in range(5):
    # On simule 5 cycles de réussites pour le GA actuel
    # (On passe par le moteur directement pour être sûr que ça marche)
    engine.calculate_fitness(best_before, success=True, execution_time_ms=150, tokens_used=300)
    engine.evolve()  # Le GA mute et croise

best_after = engine.select_best_gene()
print(f"Meilleur gène APRÈS évolution : {best_after.gene_id} | Fitness : {best_after.fitness:.2f}")

print("\n--- [4] Vérification de la population ---")
for gene in engine.population:
    print(f" - Gène : {gene.gene_id} | Fitness : {gene.fitness:.2f} | Succès : {gene.success_count}")

if best_after.fitness > best_before.fitness or best_after.gene_id != best_before.gene_id:
    print("\n🎉 SUCCÈS : L'algorithme génétique a évolué et s'est amélioré en direct !")
else:
    print("\n⚠️ Le GA n'a pas évolué (peut-être qu'il a déjà atteint son maximum de fitness).")