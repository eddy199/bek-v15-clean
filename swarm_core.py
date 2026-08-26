"""
BEK-v15 Swarm-Core Architecture (LangGraph + Blackboard)
Intégré avec Neon DB pour le CRM et support multi-providers dynamiques (Groq, Nvidia NIM, Gemini, OpenRouter).
"""
import asyncio
import os
import json
import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

# ==========================================
# DIRECTIVES GLOBALES INFAILLIBLES
# ==========================================
BEK_GOLDEN_RULES = """
=== RÈGLES D'OR DE L'ARCHITECTE (ZÉRO RÉGRESSION) ===
1. INTERDICTION DE CASSER L'EXISTANT : Toutes les fonctionnalités actuelles (UI, providers, agents web/mémoire, CRM) doivent rester 100% intactes. Ne jamais supprimer du code sans accord explicite.
2. MÉTHODE CHIRURGICALE OBLIGATOIRE : Ne jamais réécrire un fichier de zéro. Travailler uniquement sur l'ancien code.
3. CODES COMPLETS : Toujours restituer le fichier complet sans utiliser de raccourcis.
4. VALIDATION ITÉRATIVE : Avancer étape par étape.
======================================================
"""

# ═══════════════════════════════════════════════════════════════
# 1. MODÈLES DE DONNÉES — Blackboard & State
# ═══════════════════════════════════════════════════════════════
class AgentRole(Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    ANALYST = "analyst"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"

@dataclass
class AgentTask:
    id: str
    role: AgentRole
    prompt: str
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)
    result: Optional[str] = None
    status: str = "pending"

class SwarmState(TypedDict):
    messages: Annotated[List[Any], operator.add]
    tasks: Annotated[List[AgentTask], operator.add]
    blackboard: Annotated[Dict[str, Any], operator.or_]
    iteration: int
    max_iterations: int
    token_budget: int
    tokens_used: int
    final_output: Optional[str]
    swarm_active: bool

# ═══════════════════════════════════════════════════════════════
# 2. WORKER POOL & FACTORY MULTI-PROVIDER
# ═══════════════════════════════════════════════════════════════
class AgentFactory:
    ROLE_PROMPTS = {
        AgentRole.RESEARCHER: "Tu es un agent de recherche. Explore en profondeur et retourne des faits vérifiables.",
        AgentRole.CODER: "Tu es un agent développeur senior. Écris du code production-ready et des requêtes SQL sécurisées.",
        AgentRole.ANALYST: "Tu es un analyste de données CRM. Identifie les patterns et la structure des tables.",
        AgentRole.CRITIC: "Tu es un agent critique. Vérifie la qualité et signale les erreurs potentielles.",
        AgentRole.SYNTHESIZER: "Tu es un agent synthétiseur. Fusionne les contributions en un livrable final clair."
    }

    def __init__(self, api_key: str, provider: str = "groq", model_name: str = "openai/gpt-oss-120b"):
        # Sélection dynamique de l'endpoint et de la clé selon le provider présent dans env.txt
        if provider == "nvidia":
            base_url = "https://integrate.api.nvidia.com/v1"
            # Si une clé spécifique au modèle est définie dans l'environnement, on l'utilise
            env_key_candidate = model_name.replace("/", "_").replace("-", "_").upper()
            resolved_key = os.environ.get(model_name, api_key)
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            resolved_key = os.environ.get("GEMINI_API_KEY", api_key)
        elif provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
            resolved_key = os.environ.get("OPENROUTER_API_KEY", api_key)
        else:  # Groq par défaut
            base_url = "https://api.groq.com/openai/v1"
            resolved_key = os.environ.get("GROQ_API_KEY", api_key)

        self.llm = ChatOpenAI(
            base_url=base_url,
            api_key=resolved_key if resolved_key else api_key,
            model=model_name,
            temperature=0.2
        )

    async def spawn(self, task: AgentTask, blackboard: Dict) -> AgentTask:
        system_prompt = self.ROLE_PROMPTS.get(task.role, "Tu es un agent IA utile.")
        messages = [
            SystemMessage(content=f"{BEK_GOLDEN_RULES}\n\n{system_prompt}"),
            HumanMessage(content=f"TÂCHE : {task.prompt}\n\nRéponds directement avec ton livrable.")
        ]
        try:
            response = await self.llm.ainvoke(messages)
            task.result = response.content
            task.status = "done"
        except Exception as e:
            task.result = f"Erreur agent {task.role.value}: {str(e)}"
            task.status = "failed"
        return task

# ═══════════════════════════════════════════════════════════════
# 3. SUPERVISEUR LANGGRAPH
# ═══════════════════════════════════════════════════════════════
class SwarmSupervisor:
    def __init__(self, api_key: str, provider: str = "groq", model_name: str = "openai/gpt-oss-120b"):
        # Initialisation du LLM Superviseur avec le bon provider
        if provider == "nvidia":
            base_url = "https://integrate.api.nvidia.com/v1"
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        elif provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = "https://api.groq.com/openai/v1"

        self.llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model_name,
            temperature=0.1
        )
        self.factory = AgentFactory(api_key, provider, model_name)
        self.max_parallel = 3

    async def plan(self, state: SwarmState) -> SwarmState:
        if state["iteration"] > 0:
            return state

        user_request = state["messages"][-1].content if state["messages"] else ""
        planning_prompt = f"""Tu es l'orchestrateur d'un swarm d'agents IA pour le CRM BEK-v15.
Décompose cette requête en sous-tâches spécialisées.

REQUÊTE : {user_request}

Réponds UNIQUEMENT au format JSON :
{{
  "tasks": [
    {{
      "id": "task_1",
      "role": "analyst",
      "prompt": "description",
      "priority": 1,
      "dependencies": []
    }}
  ],
  "strategy": "stratégie"
}}"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"{BEK_GOLDEN_RULES}\n\nTu réponds uniquement en JSON valide."),
                HumanMessage(content=planning_prompt)
            ])
            plan = json.loads(response.content)
            tasks = [AgentTask(
                id=t["id"],
                role=AgentRole(t["role"]),
                prompt=t["prompt"],
                priority=t.get("priority", 1),
                dependencies=t.get("dependencies", [])
            ) for t in plan["tasks"]]
            state["tasks"] = tasks
            state["blackboard"]["strategy"] = plan.get("strategy", "")
            state["blackboard"]["completed_tasks"] = []
        except Exception:
            state["tasks"] = [AgentTask(
                id="task_1",
                role=AgentRole.SYNTHESIZER,
                prompt=user_request,
                priority=1
            )]

        state["iteration"] = 1
        state["swarm_active"] = True
        return state

    async def execute_swarm(self, state: SwarmState) -> SwarmState:
        tasks = state["tasks"]
        blackboard = state["blackboard"]

        ready_tasks = [
            t for t in tasks 
            if t.status == "pending" and all(
                dep in [ct["id"] for ct in blackboard.get("completed_tasks", [])]
                for dep in t.dependencies
            )
        ]

        if not ready_tasks:
            return state

        batch = ready_tasks[:self.max_parallel]
        results = await asyncio.gather(*[
            self.factory.spawn(task, blackboard) 
            for task in batch
        ], return_exceptions=True)

        for task in results:
            if isinstance(task, Exception):
                continue
            if task.status == "done":
                state["blackboard"]["completed_tasks"].append({
                    "id": task.id,
                    "role": task.role.value,
                    "result": task.result
                })
                for t in state["tasks"]:
                    if t.id == task.id:
                        t.status = "done"
                        t.result = task.result

        return state

    async def judge_termination(self, state: SwarmState) -> SwarmState:
        all_done = all(t.status == "done" for t in state["tasks"])
        max_iter_reached = state["iteration"] >= state["max_iterations"]

        if all_done or max_iter_reached:
            state["swarm_active"] = False
            if all_done:
                completed = state["blackboard"].get("completed_tasks", [])
                synthesis_content = "\n".join([f"[{c['role']}] {c['result']}" for c in completed])
                state["final_output"] = f"<thought>\nL'essaim a coordonné les agents avec succès via le provider configuré.\n</thought>\n\n### 🐝 Rapport de l'Essaim Swarm\n\n{synthesis_content}"

        state["iteration"] += 1
        return state

    def should_continue(self, state: SwarmState) -> str:
        return "swarm" if state["swarm_active"] else "end"

# ═══════════════════════════════════════════════════════════════
# 4. ASSEMBLAGE DU GRAPHE
# ═══════════════════════════════════════════════════════════════
def build_swarm_graph(api_key: str, provider: str, model: str):
    supervisor = SwarmSupervisor(api_key, provider, model)
    workflow = StateGraph(SwarmState)

    workflow.add_node("planner", supervisor.plan)
    workflow.add_node("swarm_execute", supervisor.execute_swarm)
    workflow.add_node("judge", supervisor.judge_termination)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "swarm_execute")
    workflow.add_edge("swarm_execute", "judge")
    workflow.add_conditional_edges("judge", supervisor.should_continue, {"swarm": "swarm_execute", "end": END})

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# ═══════════════════════════════════════════════════════════════
# 5. EXÉCUTION SYNCHRONE / BRIDGE POUR FLASK
# ═══════════════════════════════════════════════════════════════
async def run_bek_swarm_sync(user_query: str, api_key: str, provider: str = "groq", model: str = "openai/gpt-oss-120b") -> str:
    graph = build_swarm_graph(api_key, provider, model)
    initial_state: SwarmState = {
        "messages": [HumanMessage(content=user_query)],
        "tasks": [],
        "blackboard": {
            "observations": [],
            "completed_tasks": []
        },
        "iteration": 0,
        "max_iterations": 5,
        "token_budget": 100000,
        "tokens_used": 0,
        "final_output": None,
        "swarm_active": False
    }
    config = {"configurable": {"thread_id": f"bek_swarm_{id(user_query)}"}}
    
    final_res = "Essaim initialisé."
    async for event in graph.astream(initial_state, config):
        if "judge" in event:
            state = event["judge"]
            if state.get("final_output"):
                final_res = state["final_output"]
                break
    return final_res
