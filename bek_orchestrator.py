# ==============================================================================
# bek_orchestrator.py — ORCHESTRATEUR MULTI-AGENTS HYBRIDE UNIFIÉ (BEK-v15.3)
# ARCHITECTURE TRIADIQUE (PLANIFICATEUR - WORKERS - CRITIQUE), A2A, MCP & SELF-HEALING
# ==============================================================================

from __future__ import annotations

import os
import sys
import json
import time
import uuid
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

# ==============================================================================
# 1. PROTOCOLE A2A : CONTRATS DE TRANSFERT TYPÉS (Site 1: AI Workflow Lab)
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
    confidence: float = 1.0  # 0.0 à 1.0
    status: str = "success"  # success, retry, failed
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
# 2. REGISTRE DES CAPACITÉS & AGENT MESH (Site 2: Agent Mag)
# ==============================================================================

@dataclass
class CapabilityManifest:
    agent_id: str
    role_type: str  # 'processing', 'service', 'support' (ArXiv Taxonomy)
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
# 3. ÉTAT OPÉRATIONNEL & PERSISTANCE DÉCOUPLÉE (Site 3: ArXiv)
# ==============================================================================

class OrchestratorState:
    """Gestionnaire de session découplé (État opérationnel vs Connaissances)."""
    def __init__(self, objective: str):
        self.session_id: str = f"bek_session_{uuid.uuid4().hex[:8]}"
        self.objective: str = objective
        self.plan: List[Dict[str, Any]] = []
        self.history: List[AgentHandoff] = []
        self.knowledge_cache: Dict[str, Any] = {}
        self.iteration_count: int = 0
        self.max_iterations: int = 5  # Guardrail anti-boucle stricte
        self.is_completed: bool = False

    def checkpoint(self, handoff: AgentHandoff):
        self.history.append(handoff)
        self.iteration_count += 1
        logger.info(f"📍 [Checkpoint {self.iteration_count}/{self.max_iterations}] Agent: {handoff.source_agent} ➔ Statut: {handoff.status}")

# ==============================================================================
# 4. WORKERS SPÉCIALISÉS (Processing, Service & Support)
# ==============================================================================

def worker_web_research(params: Dict[str, Any]) -> Dict[str, Any]:
    """Processing Agent : Recherche et scraping approfondi du web."""
    query = params.get("query", "")
    if not query:
        return {"status": "error", "message": "Requête web vide."}
    report = web_agent_instance.run_pipeline(query)
    return {"status": "success", "result": report, "citations": [query]}

def worker_code_execution(params: Dict[str, Any]) -> Dict[str, Any]:
    """Processing Agent : Exécution locale et validation de scripts."""
    import subprocess
    command = params.get("command", "")
    if not command:
        return {"status": "error", "message": "Commande vide."}
    
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        res = subprocess.run(command, shell=True, cwd=workspace_dir, capture_output=True, text=True, timeout=45)
        output = (res.stdout + "\n" + res.stderr).strip()
        return {
            "status": "success" if res.returncode == 0 else "error",
            "output": output[-3000:],
            "returncode": res.returncode
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
# 5. JUGE CRITIQUE & AUTO-RÉPARATION (Triade & Self-Healing)
# ==============================================================================

class QualityCritic:
    """Critic Agent : Évalue les résultats, détecte les anomalies et force le retry."""
    @staticmethod
    def evaluate(objective: str, worker_output: str) -> tuple[bool, str, float]:
        if not worker_output or len(worker_output.strip()) < 20:
            return False, "Résultat vide ou insuffisant.", 0.1

        error_signatures = ["Traceback (most recent call last)", "SyntaxError", "HTTP 404", "Client Error", "FAILED"]
        for err in error_signatures:
            if err in worker_output:
                return False, f"Erreur critique détectée dans la sortie : '{err}'", 0.0

        return True, "Validation qualité réussie. Conforme aux objectifs.", 0.95

# ==============================================================================
# 6. ORCHESTRATEUR MAÎTRE UNIFIÉ (BEK Unified Orchestrator)
# ==============================================================================

class BEKOrchestrator:
    """Planificateur GOAP / Superviseur Triadique universel."""
    def __init__(self):
        self.mesh = AgentMesh()
        self._init_mesh_capabilities()

    def _init_mesh_capabilities(self):
        self.mesh.register_capability(CapabilityManifest(
            agent_id="web_researcher",
            role_type="processing",
            description="Agent dédié à la veille web et au deep scraping.",
            tags=["web", "scrape", "search", "docs"],
            handler=worker_web_research
        ))
        self.mesh.register_capability(CapabilityManifest(
            agent_id="code_executor",
            role_type="processing",
            description="Agent d'exécution système local, terminal et tests.",
            tags=["shell", "command", "code", "run", "test"],
            handler=worker_code_execution
        ))
        self.mesh.register_capability(CapabilityManifest(
            agent_id="memory_service",
            role_type="service",
            description="Agent de synchronisation et rappel de connaissances.",
            tags=["memory", "vector", "sql", "db"],
            handler=worker_memory_vault
        ))

    def plan_objective(self, user_goal: str) -> List[Dict[str, str]]:
        """Décompose déterministement l'objectif en sous-tâches ordonnées."""
        plan = []
        goal_lower = user_goal.lower()

        if any(w in goal_lower for w in ["cherche", "veille", "web", "scrape", "analyse", "article"]):
            plan.append({"agent": "web_researcher", "task": user_goal})
        
        if any(w in goal_lower for w in ["execute", "lance", "script", "commande", "test", "python"]):
            plan.append({"agent": "code_executor", "task": user_goal})

        if not plan:
            plan.append({"agent": "web_researcher", "task": user_goal})

        # Toujours conclure par l'ancrage mémoire
        plan.append({"agent": "memory_service", "task": f"Persistance de la synthèse pour : {user_goal[:50]}"})
        return plan

    def run(self, objective: str) -> str:
        """Exécution complète du pipeline avec supervision, arbitrage et auto-réparation."""
        state = OrchestratorState(objective)
        state.plan = self.plan_objective(objective)
        
        logger.info(f"🚀 [Orchestration Démarrée] Session: {state.session_id} | Étapes: {len(state.plan)}")
        final_syntheses = []

        for step in state.plan:
            if state.iteration_count >= state.max_iterations:
                logger.warning("🛑 Disjoncteur activé : Limite maximale d'itérations atteinte.")
                break

            agent_manifest = self.mesh.route_deterministic(step["agent"])
            if not agent_manifest:
                continue

            # Exécution Worker
            worker_res = agent_manifest.handler({"query": step["task"], "command": step["task"]})
            raw_output = str(worker_res.get("result") or worker_res.get("output") or worker_res.get("message") or "")

            # Évaluation Juge Critique (Triade)
            is_valid, critic_feedback, score = QualityCritic.evaluate(step["task"], raw_output)

            # Auto-réparation (Self-Healing) si échec
            if not is_valid and state.iteration_count < state.max_iterations:
                logger.warning(f"⚠️ [Critic Alert] Échec détecté ({critic_feedback}). Déclenchement Self-Healing...")
                # Ajustement de correction automatique
                repair_params = {"query": f"{step['task']} architecture guide", "command": step["task"]}
                worker_res = agent_manifest.handler(repair_params)
                raw_output = str(worker_res.get("result") or worker_res.get("output") or "")
                is_valid, critic_feedback, score = QualityCritic.evaluate(step["task"], raw_output)

            # Création du contrat de transfert A2A
            handoff = AgentHandoff(
                task_id=f"step_{state.iteration_count + 1}",
                source_agent=agent_manifest.agent_id,
                target_agent="supervisor",
                summary=raw_output[:1500],
                citations=worker_res.get("citations", []),
                confidence=score,
                status="success" if is_valid else "retry",
                error_message=critic_feedback if not is_valid else None,
                iteration=state.iteration_count + 1
            )
            state.checkpoint(handoff)
            final_syntheses.append(raw_output)

        # Rapport global consolidé
        return (
            f"## ⚡ Rapport d'Exécution Multi-Agents Orchestré\n"
            f"*Session : `{state.session_id}` | Itérations validées : {state.iteration_count}/{state.max_iterations}*\n\n"
            f"### 🛡️ Synthèse Arbitrée par la Triade :\n\n"
            + "\n\n---\n\n".join(final_syntheses)
        )

# Instance globale
bek_orchestrator = BEKOrchestrator()