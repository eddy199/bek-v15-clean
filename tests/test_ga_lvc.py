import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from nerves.ga_nerves import get_ga_engine
from lvc_smart import smart_truncate, clean_boilerplate

print("--- [1] Initialisation du Moteur Génétique ---")
engine = get_ga_engine()
best_gene = engine.select_best_gene()
print(f"Gène actif (Prompt système) : {best_gene.gene_id} | Fitness : {best_gene.fitness:.2f}")

print("\n--- [2] Simulation d'une requête web polluée (Boilerplate) ---")
# On simule un texte récupéré sur un site web, plein de bruit (cookies, menus)
raw_text = """
Bienvenue sur notre site ! Ce site utilise des cookies pour améliorer votre expérience. 
Menu principal | Accueil | Contact | Blog | 
L'architecture de BEK repose sur 6 briques cognitives (REX, FLUX, MEM, LOOP, ECO, STAIR). 
Ces briques sont orchestrées par le BEK-CPU pour minimiser les coûts en tokens. 
En utilisant des abréviations LVC, on réduit la taille du prompt de 80%. 
Le système nerveux (12 nerfs) connecte ces briques aux outils Hermes (62 outils). 
Ne pas oublier d'accepter les cookies avant de continuer. 
"""
print(f"Texte brut (avant LVC) : {len(raw_text)} caractères.")
print(f"-> {raw_text[:80]}...")

print("\n--- [3] Action du BEK-LVC (Nettoyage + Troncature) ---")
# 1. Nettoyage du bruit (cookies, menus)
cleaned_text = clean_boilerplate(raw_text)
# 2. Troncature intelligente (le GA décide de la longueur max)
optimized_text = smart_truncate(cleaned_text, length=200)

print(f"Texte optimisé (après LVC) : {len(optimized_text)} caractères.")
print(f"-> {optimized_text}")

reduction = len(raw_text) - len(optimized_text)
pourcentage = (reduction / len(raw_text)) * 100
print(f"\n✅ BEK-LVC a supprimé {reduction} caractères inutiles ({pourcentage:.1f}% de réduction).")

print("\n--- [4] Feedback au GA (Apprentissage) ---")
# On simule que la réponse a été parfaite, donc on enregistre un succès.
# On estime les tokens utilisés (1 token = ~4 chars)
tokens_economises = reduction // 4
print(f"Tokens économisés : {tokens_economises}")

engine.calculate_fitness(best_gene, success=True, execution_time_ms=150, tokens_used=len(optimized_text)//4)
engine.evolve()

new_best = engine.select_best_gene()
print(f"Gène après feedback : {new_best.gene_id} | Fitness : {new_best.fitness:.2f}")

if new_best.fitness > best_gene.fitness:
    print("\n🎉 SUCCÈS : Le GA a enregistré l'économie de tokens et s'est amélioré !")
else:
    print("\n⚠️ Le GA a gardé le même gène (il était déjà optimal).")