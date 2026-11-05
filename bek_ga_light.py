# -*- coding: utf-8 -*-
"""
BEK-GA (BEK Genetic Algorithm) - Version Optimisée CPU & Low-RAM (4GB RAM)
Gère l'évolution génétique des compétences (skills) et des prompts.
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
    def __init__(self, gene_id: str, prompt_template: str, max_tokens: int = 512, temperature: float = 0.2):
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
            "success_rate": round(self.success_count / max(1, self.exec_count), 2)
        }

class BEKGeneticEngineCPU:
    """Moteur génétique léger adapté aux contraintes 4 Go RAM / CPU."""
    def __init__(self, population_size: int = 4, mutation_rate: float = 0.2, db_path: str = "bek_ga_memory.json"):
        self.pop_size = max(2, min(population_size, 6))  # Borne stricte pour préserver le CPU
        self.mutation_rate = mutation_rate
        self.db_path = db_path
        self.population: List[NeuroneGene] = []
        self._load_or_init_population()

    def _load_or_init_population(self):
        """Charge la mémoire évolutive ou initialise la première génération."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("population", []):
                        gene = NeuroneGene(
                            gene_id=item["gene_id"],
                            prompt_template=item["prompt_template"],
                            max_tokens=item["max_tokens"],
                            temperature=item["temperature"]
                        )
                        gene.fitness = item.get("fitness", 0.0)
                        self.population.append(gene)
                logger.info(f"[BEK-GA] Population chargée ({len(self.population)} gènes).")
                return
            except Exception as e:
                logger.warning(f"[BEK-GA] Erreur chargement mémoire, réinitialisation: {e}")

        # Population de base (Génération 0)
        self.population = [
            NeuroneGene("gene_base_v1", "Exécute la tâche de manière concise et directe.", max_tokens=256, temperature=0.1),
            NeuroneGene("gene_analytic_v1", "Analyse étape par étape puis donne la solution JSON.", max_tokens=384, temperature=0.2),
            NeuroneGene("gene_fast_v1", "Format ultra-court sans explications inutiles.", max_tokens=192, temperature=0.0),
            NeuroneGene("gene_creative_v1", "Evalue plusieurs options et retiens la meilleure.", max_tokens=512, temperature=0.4),
        ]
        self._save_population()

    def _save_population(self):
        """Sauvegarde l'état des gènes sur disque."""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({"population": [g.to_dict() for g in self.population]}, f, indent=2)

    def calculate_fitness(self, gene: NeuroneGene, success: bool, execution_time_ms: float, tokens_used: int) -> float:
        """
        Calcul de Fitness optimisé pour CPU/RAM :
        Pondère la précision (succès) tout en sanctionnant l'usage abusif du CPU (temps) et de la RAM (tokens).
        """
        gene.exec_count += 1
        if success:
            gene.success_count += 1

        acc_score = 100.0 if success else 0.0
        # Pénalité de latence CPU (max 20s)
        time_penalty = min(execution_time_ms / 1000.0, 20.0) * 1.5
        # Pénalité de consommation de mémoire/tokens
        token_penalty = (tokens_used / 100.0) * 0.5

        fitness = acc_score - time_penalty - token_penalty
        gene.fitness = round((gene.fitness * 0.6) + (fitness * 0.4), 4)  # Lissage exponentiel
        self._save_population()
        return gene.fitness

    def select_best_gene(self) -> NeuroneGene:
        """Sélectionne le meilleur individu (Élitisme)."""
        return max(self.population, key=lambda g: g.fitness)

    def evolve(self):
        """Boucle de mutation et croisement génétique."""
        sorted_pop = sorted(self.population, key=lambda g: g.fitness, reverse=True)
        
        # Conserver les 2 meilleurs individus (Survivants)
        new_pop = [sorted_pop[0], sorted_pop[1]]

        # Générer de nouveaux individus par Croisement/Mutation
        gen_counter = int(time.time()) % 10000
        while len(new_pop) < self.pop_size:
            p1, p2 = sorted_pop[0], sorted_pop[1]
            child_prompt = p1.prompt_template if random.random() > 0.5 else p2.prompt_template
            
            # Mutation contrôlée
            if random.random() < self.mutation_rate:
                mutations = [
                    " Réponds sous forme d'action directe.",
                    " Valide chaque étape avant d'émettre le résultat.",
                    " Réduis au strict minimum les mots explicatifs."
                ]
                child_prompt += random.choice(mutations)

            child = NeuroneGene(
                gene_id=f"gene_mut_{gen_counter}_{len(new_pop)}",
                prompt_template=child_prompt,
                max_tokens=random.choice([192, 256, 384]),
                temperature=round(min(0.7, max(0.0, (p1.temperature + p2.temperature) / 2.0 + random.uniform(-0.05, 0.05))), 2)
            )
            new_pop.append(child)

        self.population = new_pop
        self._save_population()
        logger.info("[BEK-GA] Évolution terminée : Nouvelle génération prête.")