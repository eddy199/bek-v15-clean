# -*- coding: utf-8 -*-
"""
BEK-GA (BEK Genetic Algorithm) - v3 - Persistance Supabase
Optimisé CPU & Low-RAM (4GB RAM)
★ v3 (2026-11-08) :
  - Persistance sur Supabase (table bek_ga_population + bek_ga_meta)
  - Fallback sur fichier JSON local si Supabase indisponible
  - Sauvegarde asynchrone non-bloquante pour ne pas ralentir le chat
"""
from __future__ import annotations

import json
import random
import time
import os
import logging
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger("bek.ga")

# ══════════════════════════════════════════════════════════════════════════════
# CLIENT SUPABASE (lazy init + singleton)
# ══════════════════════════════════════════════════════════════════════════════
_supabase_client = None
_supabase_lock = threading.Lock()
_supabase_disabled = False


def _get_supabase():
    """Retourne le client Supabase (singleton). None si indisponible."""
    global _supabase_client, _supabase_disabled
    if _supabase_disabled:
        return None
    if _supabase_client is not None:
        return _supabase_client

    with _supabase_lock:
        if _supabase_client is not None:
            return _supabase_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            logger.info("[BEK-GA] Supabase non configuré (SUPABASE_URL/KEY manquants) → fallback JSON local")
            _supabase_disabled = True
            return None

        try:
            from supabase import create_client
            _supabase_client = create_client(url, key)
            logger.info("[BEK-GA] ✅ Client Supabase initialisé")
            return _supabase_client
        except ImportError:
            logger.warning("[BEK-GA] Package 'supabase' non installé → fallback JSON. Fais: pip install supabase")
            _supabase_disabled = True
            return None
        except Exception as exc:
            logger.error("[BEK-GA] Échec init Supabase : %s → fallback JSON", exc)
            _supabase_disabled = True
            return None


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

    def to_supabase_row(self) -> Dict[str, Any]:
        """Format pour l'upsert Supabase."""
        return {
            "gene_id": self.gene_id,
            "prompt_template": self.prompt_template,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "fitness": round(self.fitness, 4),
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

    @classmethod
    def from_supabase_row(cls, row: Dict[str, Any]) -> "NeuroneGene":
        return cls.from_dict(row)


class BEKGeneticEngineCPU:
    """Moteur génétique avec persistance Supabase (fallback JSON)."""

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
    # CHARGEMENT
    # ══════════════════════════════════════════════════════════════════════════
    def _load_or_init_population(self):
        """Charge depuis Supabase, sinon JSON, sinon population par défaut."""
        if self._load_from_supabase():
            return
        if self._load_from_json():
            self._save_to_supabase()
            return
        self._init_default_population()
        self._save_population()
        logger.info(f"[BEK-GA] Population initialisée ({len(self.population)} gènes).")

    def _load_from_supabase(self) -> bool:
        client = _get_supabase()
        if client is None:
            return False
        try:
            res = client.table("bek_ga_population").select("*").execute()
            rows = res.data or []
            if not rows:
                logger.info("[BEK-GA] Table Supabase vide → chargement JSON ou init")
                return False
            self.population = [NeuroneGene.from_supabase_row(r) for r in rows]
            meta_res = client.table("bek_ga_meta").select("*").eq("id", 1).execute()
            if meta_res.data:
                meta = meta_res.data[0]
                self.generation = int(meta.get("generation", 1))
                self.best_gene_id = meta.get("best_gene_id") or self.best_gene_id
            logger.info(
                f"[BEK-GA] ✅ Population chargée depuis Supabase "
                f"({len(self.population)} gènes, génération {self.generation})."
            )
            return True
        except Exception as exc:
            logger.warning("[BEK-GA] Échec chargement Supabase : %s → fallback JSON", exc)
            return False

    def _load_from_json(self) -> bool:
        if not os.path.exists(self.db_path):
            return False
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("population", []):
                self.population.append(NeuroneGene.from_dict(item))
            self.generation = int(data.get("generation", 1))
            self.best_gene_id = data.get("best_gene_id", self.best_gene_id)
            logger.info(
                f"[BEK-GA] Population chargée depuis JSON local "
                f"({len(self.population)} gènes, génération {self.generation})."
            )
            return True
        except Exception as exc:
            logger.warning(f"[BEK-GA] Erreur chargement JSON : {exc}")
            return False

    def _init_default_population(self):
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

    # ══════════════════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════
    def _save_population(self):
        if self.population:
            best = max(self.population, key=lambda g: g.fitness)
            self.best_gene_id = best.gene_id
        self._save_to_supabase()
        self._save_to_json()

    def _save_to_supabase(self) -> bool:
        client = _get_supabase()
        if client is None:
            return False
        try:
            rows = [g.to_supabase_row() for g in self.population]
            if rows:
                client.table("bek_ga_population").upsert(
                    rows, on_conflict="gene_id"
                ).execute()
            client.table("bek_ga_meta").upsert(
                {
                    "id": 1,
                    "generation": self.generation,
                    "best_gene_id": self.best_gene_id,
                },
                on_conflict="id",
            ).execute()
            logger.debug(
                f"[BEK-GA] 💾 Supabase synchronisé "
                f"({len(rows)} gènes, génération {self.generation})."
            )
            return True
        except Exception as exc:
            logger.warning("[BEK-GA] Échec sauvegarde Supabase : %s", exc)
            return False

    def _save_to_json(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({
                    "generation": self.generation,
                    "best_gene_id": self.best_gene_id,
                    "population": [g.to_dict() for g in self.population],
                }, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"[BEK-GA] Erreur sauvegarde JSON : {exc}")

    def _save_population_async(self):
        def _worker():
            try:
                self._save_population()
            except Exception as exc:
                logger.debug("[BEK-GA] Erreur sauvegarde async : %s", exc)
        threading.Thread(target=_worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # FITNESS
    # ══════════════════════════════════════════════════════════════════════════
    def calculate_fitness(self, gene: NeuroneGene, success: bool,
                          execution_time_ms: float, tokens_used: int) -> float:
        gene.exec_count += 1
        if success:
            gene.success_count += 1
        base = 1.0 if success else 0.0
        time_penalty = min(execution_time_ms / 1000.0, 20.0) / 20.0 * 0.3
        token_penalty = min(tokens_used, 10000) / 10000.0 * 0.2
        instant_fitness = max(0.0, min(1.0, base - time_penalty - token_penalty))
        gene.fitness = round((gene.fitness * 0.7) + (instant_fitness * 0.3), 4)
        self._save_population_async()
        logger.debug(
            f"[BEK-GA] Fitness {gene.gene_id} : {gene.fitness:.4f} "
            f"(instantanée {instant_fitness:.4f})"
        )
        return gene.fitness

    # ══════════════════════════════════════════════════════════════════════════
    # SÉLECTION & ÉVOLUTION
    # ══════════════════════════════════════════════════════════════════════════
    def select_best_gene(self) -> NeuroneGene:
        if not self.population:
            self._load_or_init_population()
        return max(self.population, key=lambda g: g.fitness)

    def _tournament_select(self, k: int = 3) -> NeuroneGene:
        candidates = random.sample(self.population, min(k, len(self.population)))
        return max(candidates, key=lambda g: g.fitness)

    def evolve(self):
        if len(self.population) < 2:
            logger.warning("[BEK-GA] Population trop petite pour évoluer.")
            return
        sorted_pop = sorted(self.population, key=lambda g: g.fitness, reverse=True)
        new_pop = sorted_pop[:3]
        gen_counter = int(time.time()) % 10000
        mutation_patterns = [
            " Réponds sous forme d'action directe JSON.",
            " Valide chaque étape avant d'émettre le résultat.",
            " Réduis au strict minimum les mots explicatifs.",
            " Si erreur, utilise edit_file (jamais write_file complet).",
            " Découpe les fichiers > 3000 chars en append_file successifs.",
        ]
        while len(new_pop) < self.pop_size:
            p1 = self._tournament_select(3)
            p2 = self._tournament_select(3)
            child_prompt = p1.prompt_template if random.random() > 0.5 else p2.prompt_template
            if random.random() < self.mutation_rate:
                child_prompt += random.choice(mutation_patterns)
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
            "supabase_connected": _get_supabase() is not None,
        }

    def list_genes(self) -> List[Dict[str, Any]]:
        return [g.to_dict() for g in self.population]