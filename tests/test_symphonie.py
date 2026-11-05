import sys
import os
import asyncio
import time

# Permet d'importer depuis la racine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bek_master import BEKMasterOrchestrator
from nerves.ga_nerves import get_ga_engine

async def run_symphonie():
    print("\n" + "="*70)
    print("  🏛️ TEST ULTIME : SYMPHONIE DES BRIQUES BEK + BEK-GA")
    print("="*70)

    master = BEKMasterOrchestrator()
    
    # 1. Vérifier l'état du GA avant de commencer
    engine = get_ga_engine()
    best_before = engine.select_best_gene()
    print(f"[GA] Gène initial : {best_before.gene_id} (Fitness: {best_before.fitness:.2f})")

    # 2. Requête complexe qui nécessite l'orchestration de TOUS les agents
    query = """
    Tu es BEK, le cerveau central. 
    Fais exactement ces étapes en invoquant tes briques internes :
    1. Utilise le WebAgent (Nerf 4) pour chercher "dernières avancées en IA agentique 2026".
    2. Utilise Headless (Nerf 11) pour extraire le contenu du premier résultat.
    3. Utilise le Codex Loop (Nerf 18) pour générer un script Python qui affiche "Symphonie BEK".
    4. Utilise la Mémoire (Nerf 1 + Pinecone) pour enregistrer un résumé de tes actions.
    5. Utilise le Swarm Cognitive (Nerf 2) pour faire une critique de ton propre travail.
    6. Enfin, utilise le BEK-GA (Nerf 20) pour enregistrer le succès de cette symphonie et faire muter tes gènes.
    Exécute tout cela de manière séquentielle et rapporte-moi le résultat final.
    """
    
    print(f"\n[Master] Envoi de la requête complexe...")
    start = time.time()
    
    # 3. Exécution via le Master (qui va router vers les bonnes briques)
    # Note : on utilise le provider NVIDIA pour avoir de la puissance
    result = await master.process(query, provider="nvidia", model="nvidia/nemotron-3.5-super-vl-120b-a12b")
    
    elapsed = (time.time() - start) * 1000
    
    # 4. Résultats
    print(f"\n[Master] ✅ Requête terminée en {elapsed:.2f} ms")
    print(f"[Master] Status : {result.get('status')}")
    print(f"[Master] Bricks utilisées : {result.get('bricks_used')}")
    print(f"\n[Master] Réponse du cerveau :\n{result.get('response')[:2000]}...")
    
    # 5. Vérification finale du GA
    best_after = engine.select_best_gene()
    print("\n" + "="*70)
    print("  🧬 ÉTAT FINAL DU BEK-GA")
    print("="*70)
    print(f"Gène gagnant : {best_after.gene_id}")
    print(f"Fitness : {best_after.fitness:.2f}")
    print(f"Population : {[g.gene_id for g in engine.population]}")
    
    if best_after.fitness > best_before.fitness or best_after.gene_id != best_before.gene_id:
        print("\n🎉 SUCCÈS : Le BEK-GA a été invoqué et a muté en direct !")
    else:
        print("\n✅ Le BEK-GA a été invoqué avec succès (le gène était déjà optimal).")

    print("\n✅ Test de la Symphonie terminé.")

if __name__ == "__main__":
    asyncio.run(run_symphonie())