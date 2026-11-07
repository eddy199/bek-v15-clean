# -*- coding: utf-8 -*-
"""
BEK-GA (BEK Genetic Algorithm) - v2 - 12 gènes stratégiques
Optimisé CPU & Low-RAM (4GB RAM)
★ FIX v2 :
  - Recharge exec_count / success_count (préserve l'historique fitness)
  - Population max 20 (au lieu de 6) → 12 gènes + marge d'évolution
  - Tournoi sur 3 parents (au lieu de 2) → vraie diversité génétique
  - Fitness normalisée 0-1 (au lieu du lissage buggé à 77)
"""

import json
import random
import time
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("bek.ga")


class NeuroneGene:
    """Représente un individu (configuration/prompt/skill) soumis à l'évolution."""

    def __init__(self, gene_id: str, prompt_template: str,
                 max_tokens: int = 512, temperature: float = 0.2):
        self.gene_id = gene_id
        self.prompt_template = prompt_template
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.fitness: float = 0.0
        self.exec_count: int = 0
        self.success_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene_id": self.gene_id,
            "prompt_template": self.prompt_template,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "fitness": round(self.fitness, 4),
            "success_rate": round(self.success_count / max(1, self.exec_count), 2),
            "exec_count": self.exec_count,
            "success_count": self.success_count,
        }

    @classmethod
    def from_dict(cls, item: Dict[str, Any]) -> "NeuroneGene":
        g = cls(
            gene_id=item["gene_id"],
            prompt_template=item["prompt_template"],
            max_tokens=item.get("max_tokens", 512),
            temperature=item.get("temperature", 0.2),
        )
        g.fitness = float(item.get("fitness", 0.0))
        g.exec_count = int(item.get("exec_count", 0))
        g.success_count = int(item.get("success_count", 0))
        return g


class BEKGeneticEngineCPU:
    """Moteur génétique léger adapté aux contraintes 4 Go RAM / CPU."""

    # ★ FIX v2 : 20 gènes max (au lieu de 6) pour accueillir les 12 + mutations
    MAX_POP_SIZE = 20
    MIN_POP_SIZE = 2

    def __init__(self, population_size: int = 12,
                 mutation_rate: float = 0.2,
                 db_path: str = "bek_ga_memory.json"):
        self.pop_size = max(self.MIN_POP_SIZE, min(population_size, self.MAX_POP_SIZE))
        self.mutation_rate = mutation_rate
        self.db_path = db_path
        self.generation = 1
        self.best_gene_id = "gene_architect_v1"
        self.population: List[NeuroneGene] = []
        self._load_or_init_population()

    # ══════════════════════════════════════════════════════════════════════════
    # CHARGEMENT / SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════
    def _load_or_init_population(self):
        """Charge la mémoire évolutive ou initialise la première génération."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # ★ FIX v2 : recharge exec_count + success_count
                    for item in data.get("population", []):
                        self.population.append(NeuroneGene.from_dict(item))
                    self.generation = int(data.get("generation", 1))
                    self.best_gene_id = data.get("best_gene_id", self.best_gene_id)
                logger.info(
                    f"[BEK-GA] Population chargée ({len(self.population)} gènes, "
                    f"génération {self.generation})."
                )
                return
            except Exception as e:
                logger.warning(f"[BEK-GA] Erreur chargement mémoire, réinitialisation: {e}")

        # Population de base (Génération 0) — 12 gènes
        self.population = [
            NeuroneGene("gene_architect_v1",
                        "Tu es un architecte logiciel senior. Structure ta réponse en : "
                        "1) analyse du besoin, 2) plan d'architecture, 3) implémentation JSON stricte.",
                        max_tokens=512, temperature=0.1),
            NeuroneGene("gene_coder_v1",
                        "Tu es un générateur de code pur. Produis UNIQUEMENT du JSON strict. "
                        "Aucun texte avant ou après. 1 fichier = 1 étape.",
                        max_tokens=384, temperature=0.05),
            NeuroneGene("gene_debugger_v1",
                        "Tu es un débuggeur expert. Analyse l'erreur, identifie la cause racine, "
                        "propose un correctif minimal via edit_file.",
                        max_tokens=384, temperature=0.15),
            NeuroneGene("gene_tester_v1",
                        "Tu es un testeur QA. Vérifie la syntaxe, lance les tests, "
                        "signale les échecs. Ne clôture avec done qu'après validation.",
                        max_tokens=320, temperature=0.1),
            NeuroneGene("gene_gamedev_v1",
                        "Tu es un game designer rétro. Applique : Game Feel, Juice, "
                        "Coyote Time, Jump Buffering, Object Pooling. 60 FPS stricts.",
                        max_tokens=512, temperature=0.2),
            NeuroneGene("gene_refactorer_v1",
                        "Tu es un refactorer. Découpe les God Files, élimine les doublons, "
                        "extrais les modules partagés. Ne casse aucune fonctionnalité.",
                        max_tokens=384, temperature=0.15),
            NeuroneGene("gene_documenter_v1",
                        "Tu es un documentaliste technique. Génère un README.md clair : "
                        "installation, usage, contrôles, architecture.",
                        max_tokens=320, temperature=0.3),
            NeuroneGene("gene_researcher_v1",
                        "Tu es un chercheur. Utilise web_search + headless_scrape pour "
                        "trouver les meilleures libs/assets. Vérifie avec cognitive_ground.",
                        max_tokens=448, temperature=0.25),
            NeuroneGene("gene_planner_v1",
                        "Tu es un planificateur granulaire. Génère un plan JSON où "
                        "1 étape = 1 fichier. Format args.steps.",
                        max_tokens=448, temperature=0.1),
            NeuroneGene("gene_security_v1",
                        "Tu es un auditeur sécurité. Utilise security_scan_python (Bandit) "
                        "et rea_analyze_* avant intégration.",
                        max_tokens=320, temperature=0.05),
            NeuroneGene("gene_optimizer_v1",
                        "Tu es un optimiseur de tokens. Compresse les réponses au strict "
                        "minimum. Utilise les alias LVC (w, e, b, r).",
                        max_tokens=192, temperature=0.0),
            NeuroneGene("gene_reviewer_v1",
                        "Tu es un code reviewer. Lis le fichier, critique la structure, "
                        "propose des améliorations concrètes via edit_file.",
                        max_tokens=384, temperature=0.2),
        ]
        self._save_population()
        logger.info(f"[BEK-GA] Population initialisée ({len(self.population)} gènes).")

    def _save_population(self):
        """Sauvegarde l'état des gènes sur disque."""
        try:
            # Met à jour le best_gene_id avant sauvegarde
            if self.population:
                best = max(self.population, key=lambda g: g.fitness)
                self.best_gene_id = best.gene_id
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({
                    "generation": self.generation,
                    "best_gene_id": self.best_gene_id,
                    "population": [g.to_dict() for g in self.population],
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[BEK-GA] Erreur sauvegarde: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # FITNESS
    # ══════════════════════════════════════════════════════════════════════════
    def calculate_fitness(self, gene: NeuroneGene, success: bool,
                          execution_time_ms: float, tokens_used: int) -> float:
        """
        ★ FIX v2 : Fitness normalisée 0-1 (au lieu du lissage buggé à 77).
        Formule :
          - base = 1.0 si succès, 0.0 sinon
          - pénalité temps : min(exec_s, 20) / 20 * 0.3  (max 0.3)
          - pénalité tokens : min(tokens, 10000) / 10000 * 0.2  (max 0.2)
          - fitness_instantanée = base - pénalités (clamp 0-1)
          - fitness_finale = 0.7 * ancienne + 0.3 * instantanée
        """
        gene.exec_count += 1
        if success:
            gene.success_count += 1

        base = 1.0 if success else 0.0
        time_penalty = min(execution_time_ms / 1000.0, 20.0) / 20.0 * 0.3
        token_penalty = min(tokens_used, 10000) / 10000.0 * 0.2

        instant_fitness = max(0.0, min(1.0, base - time_penalty - token_penalty))
        gene.fitness = round((gene.fitness * 0.7) + (instant_fitness * 0.3), 4)

        self._save_population()
        logger.debug(
            f"[BEK-GA] Fitness {gene.gene_id} : {gene.fitness:.4f} "
            f"(instantanée {instant_fitness:.4f})"
        )
        return gene.fitness

    # ══════════════════════════════════════════════════════════════════════════
    # SÉLECTION
    # ══════════════════════════════════════════════════════════════════════════
    def select_best_gene(self) -> NeuroneGene:
        """Sélectionne le meilleur individu (Élitisme)."""
        if not self.population:
            self._load_or_init_population()
        return max(self.population, key=lambda g: g.fitness)

    def _tournament_select(self, k: int = 3) -> NeuroneGene:
        """★ FIX v2 : Tournoi sur 3 parents (au lieu de 2) pour plus de diversité."""
        candidates = random.sample(self.population, min(k, len(self.population)))
        return max(candidates, key=lambda g: g.fitness)

    # ══════════════════════════════════════════════════════════════════════════
    # ÉVOLUTION
    # ══════════════════════════════════════════════════════════════════════════
    def evolve(self):
        """
        ★ FIX v2 : Boucle de mutation/croisement avec tournoi sur 3 parents.
        - Conserve les 3 meilleurs (élitisme renforcé)
        - Crossover par tournoi (3 parents)
        - Mutation contrôlée (5 patterns différents)
        - Nouvelle génération = population_size
        """
        if len(self.population) < 2:
            logger.warning("[BEK-GA] Population trop petite pour évoluer.")
            return

        sorted_pop = sorted(self.population, key=lambda g: g.fitness, reverse=True)

        # Élitisme : garde les 3 meilleurs
        new_pop = sorted_pop[:3]

        gen_counter = int(time.time()) % 10000

        # ★ FIX v2 : 5 patterns de mutation (au lieu de 3)
        mutation_patterns = [
            " Réponds sous forme d'action directe JSON.",
            " Valide chaque étape avant d'émettre le résultat.",
            " Réduis au strict minimum les mots explicatifs.",
            " Si erreur, utilise edit_file (jamais write_file complet).",
            " Découpe les fichiers > 3000 chars en append_file successifs.",
        ]

        while len(new_pop) < self.pop_size:
            # Tournoi sur 3 parents
            p1 = self._tournament_select(3)
            p2 = self._tournament_select(3)

            # Crossover : choix aléatoire du parent pour le prompt
            child_prompt = p1.prompt_template if random.random() > 0.5 else p2.prompt_template

            # Mutation contrôlée
            if random.random() < self.mutation_rate:
                child_prompt += random.choice(mutation_patterns)

            # Temperature interpolée + bruit
            child_temp = round(
                min(0.7, max(0.0,
                    (p1.temperature + p2.temperature) / 2.0
                    + random.uniform(-0.05, 0.05)
                )),
                2
            )

            child = NeuroneGene(
                gene_id=f"gene_mut_{gen_counter}_{len(new_pop)}",
                prompt_template=child_prompt,
                max_tokens=random.choice([192, 256, 320, 384, 448, 512]),
                temperature=child_temp,
            )
            new_pop.append(child)

        self.population = new_pop
        self.generation += 1
        self._save_population()
        logger.info(
            f"[BEK-GA] Évolution terminée → génération {self.generation} "
            f"({len(self.population)} gènes)."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════
    def get_population_stats(self) -> Dict[str, Any]:
        """Retourne les stats de la population (debug/dashboard)."""
        if not self.population:
            return {"size": 0, "generation": self.generation}
        fitnesses = [g.fitness for g in self.population]
        return {
            "size": len(self.population),
            "generation": self.generation,
            "best_gene_id": self.best_gene_id,
            "best_fitness": round(max(fitnesses), 4),
            "avg_fitness": round(sum(fitnesses) / len(fitnesses), 4),
            "worst_fitness": round(min(fitnesses), 4),
            "total_execs": sum(g.exec_count for g in self.population),
        }

    def list_genes(self) -> List[Dict[str, Any]]:
        """Retourne tous les gènes (debug/dashboard)."""
        return [g.to_dict() for g in self.population]