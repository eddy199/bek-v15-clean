# ==============================================================================
# bek_orchestrator.py — ORCHESTRATEUR MULTI-AGENTS HYBRIDE UNIFIÉ (BEK-v15.3)
# ARCHITECTURE TRIADIQUE (PLANIFICATEUR - WORKERS - CRITIQUE), A2A, MCP & SELF-HEALING
# ------------------------------------------------------------------------------
# v19.51 (2026-11-05) : ★ BEK-GA intégré
#   - Récupération du prompt évolutif via ga_get_best
#   - Enregistrement du fitness après chaque run()
#   - Évolution automatique en cas d'échec
# ==============================================================================

from __future__ import annotations

import os
import re
import sys
import json
import time
import uuid
import shlex
import logging
import traceback
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone

# --- INTÉGRATIONS INTERNES BEK ---
from memory import search_memory, save_to_memory, get_db_connection
from web_agent import web_agent_instance

try:
    from provider_manager import provider_manager
except ImportError:
    provider_manager = None

try:
    from meta_cortex_swarm import ReflexionSwarm
except ImportError:
    ReflexionSwarm = None

logger = logging.getLogger("BEKOrchestrator")
logger.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════
# 🛡️ WHITELIST DE COMMANDES SHELL AUTORISÉES (v2)
# ══════════════════════════════════════════════════════════════════
_ALLOWED_SHELL_PREFIXES = (
    "ls", "dir", "pwd", "cd", "echo", "cat", "type",
    "python ", "python3 ", "pytest",
    "git status", "git log", "git diff", "git branch",
    "pip list", "pip show",
    "find ", "grep ", "wc ", "head ", "tail ",
)


def _is_safe_shell_command(command: str) -> bool:
    """Vérifie qu'une commande est dans la whitelist."""
    if not command or not command.strip():
        return False

    cmd = command.strip()

    if len(cmd) > 200:
        logger.warning("[Shell Guard] Commande trop longue (%d chars) — rejetée", len(cmd))
        return False

    natural_language_markers = (
        " the ", " from ", " for ", " and ", " with ", " articles ",
        " summarize ", " fetch ", " please ", " then ", " that ",
    )
    cmd_lower = cmd.lower()
    nl_hits = sum(1 for m in natural_language_markers if m in cmd_lower)
    if nl_hits >= 2:
        logger.warning("[Shell Guard] Phrase en langage naturel détectée — rejetée : %s", cmd[:80])
        return False

    for prefix in _ALLOWED_SHELL_PREFIXES:
        if cmd.startswith(prefix):
            return True

    logger.warning("[Shell Guard] Commande hors whitelist — rejetée : %s", cmd[:80])
    return False


# ==============================================================================
# 1. PROTOCOLE A2A : CONTRATS DE TRANSFERT TYPÉS
# ==============================================================================

@dataclass
class AgentHandoff:
    """Schéma de transfert inter-agents strict pour éliminer les hallucinations."""
    task_id: str
    source_agent: str
    target_agent: str
    summary: str
    data_payload: Dict[str, Any] = field(default_factory=dict)
    citations: List[str] = field(default_factory=list)
    confidence: float = 1.0
    status: str = "success"
    error_message: Optional[str] = None
    iteration: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_context_prompt(self) -> str:
        sections = [
            f"### [TRANSFERT A2A] Origine: {self.source_agent} ➔ Cible: {self.target_agent}",
            f"- **Statut :** {self.status.upper()} (Confiance: {self.confidence:.0%})",
            f"- **Synthèse :**\n{self.summary}",
        ]
        if self.citations:
            sections.append("- **Sources & Preuves :**\n" + "\n".join(f"  * {c}" for c in self.citations))
        if self.error_message:
            sections.append(f"- **Dernière Erreur Notée :** {self.error_message}")
        return "\n".join(sections)


# ==============================================================================
# 2. REGISTRE DES CAPACITÉS & AGENT MESH
# ==============================================================================

@dataclass
class CapabilityManifest:
    agent_id: str
    role_type: str
    description: str
    tags: List[str]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]


class AgentMesh:
    """Réseau de micro-agents déclaratifs avec routage déterministe."""
    def __init__(self):
        self.registry: Dict[str, CapabilityManifest] = {}

    def register_capability(self, manifest: CapabilityManifest):
        self.registry[manifest.agent_id] = manifest
        logger.info(f"⚡ [Mesh] Agent enregistré : {manifest.agent_id} ({manifest.role_type})")

    def route_deterministic(self, task_type: str) -> Optional[CapabilityManifest]:
        for manifest in self.registry.values():
            if task_type in manifest.tags or manifest.agent_id == task_type:
                return manifest
        return None


# ==============================================================================
# 3. ÉTAT OPÉRATIONNEL & PERSISTANCE DÉCOUPLÉE
# ==============================================================================

class OrchestratorState:
    """Gestionnaire de session découplé."""
    def __init__(self, objective: str):
        self.session_id: str = f"bek_session_{uuid.uuid4().hex[:8]}"
        self.objective: str = objective
        self.plan: List[Dict[str, Any]] = []
        self.history: List[AgentHandoff] = []
        self.knowledge_cache: Dict[str, Any] = {}
        self.iteration_count: int = 0
        self.max_iterations: int = 5
        self.is_completed: bool = False

    def checkpoint(self, handoff: AgentHandoff):
        self.history.append(handoff)
        self.iteration_count += 1
        logger.info(
            f"📍 [Checkpoint {self.iteration_count}/{self.max_iterations}] "
            f"Agent: {handoff.source_agent} ➔ Statut: {handoff.status}"
        )


# ==============================================================================
# 4. WORKERS SPÉCIALISÉS
# ==============================================================================

def worker_web_research(params: Dict[str, Any]) -> Dict[str, Any]:
    """Processing Agent : Recherche et scraping approfondi du web."""
    query = params.get("query", "")
    if not query:
        return {"status": "error", "message": "Requête web vide."}
    report = web_agent_instance.run_pipeline(query)
    return {"status": "success", "result": report, "citations": [query]}


def worker_code_execution(params: Dict[str, Any]) -> Dict[str, Any]:
    """Processing Agent : Exécution locale sécurisée (v2)."""
    import subprocess

    command = params.get("command", "").strip()
    if not command:
        return {"status": "error", "message": "Commande vide."}

    if not _is_safe_shell_command(command):
        logger.warning("[code_executor] Commande rejetée par sécurité : %s", command[:80])
        return {
            "status": "error",
            "message": "Commande rejetée par sécurité (hors whitelist).",
            "returncode": -1,
        }

    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        res = subprocess.run(command, shell=True, cwd=workspace_dir,
                             capture_output=True, text=True, timeout=45)
        output = (res.stdout + "\n" + res.stderr).strip()
        return {
            "status": "success" if res.returncode == 0 else "error",
            "output": output[-3000:],
            "returncode": res.returncode,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "returncode": -1}


def worker_memory_vault(params: Dict[str, Any]) -> Dict[str, Any]:
    """Service Agent : Interaction directe avec la mémoire vectorielle et SQL."""
    action = params.get("action", "search")
    query = params.get("query", "")
    content = params.get("content", "")

    if action == "save" and content:
        save_to_memory(content)
        return {"status": "success", "message": "Information ancrée dans Pinecone/ChromaDB."}
    elif action == "search" and query:
        mem_data = search_memory(query, top_k=3)
        return {"status": "success", "data": mem_data}
    return {"status": "error", "message": "Paramètres mémoire invalides."}


# ==============================================================================
# 5. JUGE CRITIQUE & AUTO-RÉPARATION
# ==============================================================================

class QualityCritic:
    """Critic Agent : Évalue les résultats, détecte les anomalies."""
    @staticmethod
    def evaluate(objective: str, worker_output: str) -> tuple:
        if not worker_output or len(worker_output.strip()) < 20:
            return False, "Résultat vide ou insuffisant.", 0.1

        error_signatures = [
            "Traceback (most recent call last)",
            "SyntaxError", "HTTP 404", "Client Error", "FAILED",
        ]
        for err in error_signatures:
            if err in worker_output:
                return False, f"Erreur critique détectée : '{err}'", 0.0

        return True, "Validation qualité réussie.", 0.95


# ==============================================================================
# 6. ORCHESTRATEUR MAÎTRE UNIFIÉ (v2)
# ==============================================================================

_WEB_TASK_KEYWORDS = (
    "cherche", "recherche", "trouve", "veille",
    "web", "scrape", "article", "news", "actualité",
    "fetch", "find", "search", "summarize", "résume",
    "https", "http", "url", "site",
)

_SHELL_TASK_KEYWORDS = (
    "execute la commande", "lance la commande", "exécute la commande",
    "run command", "shell command", "$ ", "cmd>",
)


class BEKOrchestrator:
    """Planificateur GOAP / Superviseur Triadique universel (v2 + BEK-GA)."""

    def __init__(self):
        self.mesh = AgentMesh()
        self._init_mesh_capabilities()

    # ─── BEK-GA : Récupération du prompt évolutif ───
    def _get_ga_prompt(self) -> str:
        """Demande au moteur génétique le meilleur prompt évolutif."""
        try:
            from nerves.ga_nerves import get_ga_engine
            best = get_ga_engine().select_best_gene()
            logger.debug("[BEK-GA] Gène actif : %s (fitness=%s)", best.gene_id, best.fitness)
            return best.prompt_template
        except Exception:
            return "Exécute la tâche de manière concise et directe."

    # ─── BEK-GA : Enregistrement du fitness ───
    def _record_ga_fitness(self, objective: str, result: str, elapsed_ms: float):
        """Enregistre le fitness du gène actif dans le moteur génétique."""
        try:
            from nerves.ga_nerves import get_ga_engine
            engine = get_ga_engine()
            best_gene = engine.select_best_gene()
            tokens_est = len(str(objective)) // 4 + len(str(result)) // 4
            success = bool(result and len(str(result)) > 20)
            engine.calculate_fitness(best_gene, success, elapsed_ms, tokens_est)
            if not success:
                engine.evolve()
                logger.info("[BEK-GA] ⚡ Évolution déclenchée (échec orchestrateur)")
        except Exception as ga_exc:
            logger.debug("[BEK-GA] Enregistrement fitness ignoré : %s", ga_exc)

    def _init_mesh_capabilities(self):
        self.mesh.register_capability(CapabilityManifest(
            agent_id="web_researcher", role_type="processing",
            description="Agent dédié à la veille web et au deep scraping.",
            tags=["web", "scrape", "search", "docs"],
            handler=worker_web_research,
        ))
        self.mesh.register_capability(CapabilityManifest(
            agent_id="code_executor", role_type="processing",
            description="Agent d'exécution système local, terminal et tests.",
            tags=["shell", "command", "code", "run", "test"],
            handler=worker_code_execution,
        ))
        self.mesh.register_capability(CapabilityManifest(
            agent_id="memory_service", role_type="service",
            description="Agent de synchronisation et rappel de connaissances.",
            tags=["memory", "vector", "sql", "db"],
            handler=worker_memory_vault,
        ))

    def plan_objective(self, user_goal: str) -> List[Dict[str, str]]:
        plan = []
        goal_lower = user_goal.lower()

        is_web_task = any(w in goal_lower for w in _WEB_TASK_KEYWORDS)
        is_shell_task = any(w in goal_lower for w in _SHELL_TASK_KEYWORDS)

        if is_web_task:
            plan.append({"agent": "web_researcher", "task": user_goal})

        if is_shell_task and not is_web_task:
            plan.append({"agent": "code_executor", "task": user_goal})

        if not plan:
            plan.append({"agent": "web_researcher", "task": user_goal})

        plan.append({
            "agent": "memory_service",
            "task": f"Persistance de la synthèse pour : {user_goal[:50]}",
        })
        return plan

    def run(self, objective: str) -> str:
        """Exécution complète du pipeline avec supervision, auto-réparation et BEK-GA."""
        start_time = time.time()

        # ★ BEK-GA : Récupération du prompt évolutif
        ga_prompt = self._get_ga_prompt()
        logger.info("[BEK-GA] Prompt actif : %s...", ga_prompt[:80])

        state = OrchestratorState(objective)
        state.plan = self.plan_objective(objective)

        logger.info(
            f"🚀 [Orchestration Démarrée] Session: {state.session_id} | "
            f"Étapes: {len(state.plan)}"
        )
        final_syntheses = []

        for step in state.plan:
            if state.iteration_count >= state.max_iterations:
                logger.warning("🛑 Disjoncteur activé : Limite maximale d'itérations atteinte.")
                break

            agent_manifest = self.mesh.route_deterministic(step["agent"])
            if not agent_manifest:
                continue

            if agent_manifest.agent_id == "web_researcher":
                handler_params = {"query": step["task"]}
            elif agent_manifest.agent_id == "code_executor":
                handler_params = {"command": step["task"]}
            elif agent_manifest.agent_id == "memory_service":
                handler_params = {"action": "save", "content": step["task"]}
            else:
                handler_params = {"query": step["task"]}

            worker_res = agent_manifest.handler(handler_params)
            raw_output = str(
                worker_res.get("result") or worker_res.get("output")
                or worker_res.get("message") or ""
            )

            is_valid, critic_feedback, score = QualityCritic.evaluate(step["task"], raw_output)

            if not is_valid and state.iteration_count < state.max_iterations:
                logger.warning(f"⚠️ [Critic Alert] Échec ({critic_feedback}). Self-Healing...")
                if agent_manifest.agent_id == "web_researcher":
                    repair_params = {"query": f"{step['task']} guide"}
                else:
                    repair_params = handler_params
                worker_res = agent_manifest.handler(repair_params)
                raw_output = str(worker_res.get("result") or worker_res.get("output") or "")
                is_valid, critic_feedback, score = QualityCritic.evaluate(step["task"], raw_output)

            handoff = AgentHandoff(
                task_id=f"step_{state.iteration_count + 1}",
                source_agent=agent_manifest.agent_id,
                target_agent="supervisor",
                summary=raw_output[:1500],
                citations=worker_res.get("citations", []),
                confidence=score,
                status="success" if is_valid else "retry",
                error_message=critic_feedback if not is_valid else None,
                iteration=state.iteration_count + 1,
            )
            state.checkpoint(handoff)
            final_syntheses.append(raw_output)

        final_result = (
            f"## ⚡ Rapport d'Exécution Multi-Agents Orchestré\n"
            f"*Session : `{state.session_id}` | "
            f"Itérations validées : {state.iteration_count}/{state.max_iterations}*\n\n"
            f"### 🛡️ Synthèse Arbitrée par la Triade :\n\n"
            + "\n\n---\n\n".join(final_syntheses)
        )

        # ★ BEK-GA : Enregistrement du fitness
        elapsed_ms = (time.time() - start_time) * 1000
        self._record_ga_fitness(objective, final_result, elapsed_ms)

        return final_result


# Instance globale
bek_orchestrator = BEKOrchestrator()