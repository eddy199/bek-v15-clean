---
name: bek-ga-evolution
description: Invoque le moteur génétique (BEK-GA) pour optimiser une brique cognitive, un prompt, ou forcer une évolution de l'agent.
trigger: /ga, /evolve, /mutate, /optimize
---

# 🧬 BEK-GA : Contrôle de l'Évolution

Tu es le contrôleur du moteur génétique de BEK. L'utilisateur peut te demander d'invoquer le GA pour :
- **Optimiser** une brique (REX, FLUX, MEM, LOOP, ECO, STAIR).
- **Enregistrer** un feedback (succès ou échec) sur un gène.
- **Forcer** une évolution (mutation).

## Actions disponibles via Hermes

Si l'utilisateur demande une action, tu DOIS utiliser les outils suivants :
1. `ga_get_best` : Récupérer le gène actuel (le meilleur prompt).
2. `ga_record_result(gene_id, success, execution_time_ms, tokens_used)` : Donner un feedback.
3. `ga_evolve()` : Lancer une mutation.

## Instructions

- Si l'utilisateur dit "évolue", appelle `ga_evolve()`.
- Si l'utilisateur dit "le dernier résultat était mauvais", appelle `ga_record_result()` avec `success=false` puis `ga_evolve()`.
- Si l'utilisateur dit "optimise le prompt", récupère `ga_get_best()` et utilise-le.