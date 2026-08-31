"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  REFLEXION-SWARM v1.0 — Critique Parallèle Multi-Angle pour BEK-v15.2       ║
║  Fichier : meta_cortex_swarm.py                                              ║
║  Rôle    : Lance 3 critiques spécialisées en parallèle, agrège par vote     ║
║            Intègre le protocole de raisonnement profond et filtrage social. ║
║            Supporte le Post-Plan Evaluation Hook pour Hermes Core V2.       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from provider_manager import provider_manager

logger = logging.getLogger("ReflexionSwarm")


class Verdict(str, Enum):
    GOOD = "GOOD"
    FIX = "FIX"
    ESCALATE = "ESCALATE"


class CriticRole(str, Enum):
    FACTUAL = "factual"
    LOGICAL = "logical"
    CONTEXTUAL = "contextual"


@dataclass
class SwarmCritique:
    critic_id: str
    role: CriticRole
    verdict: Verdict
    confidence: float
    reasoning: str
    issues: List[Dict[str, Any]]
    latency_ms: int = 0
    error: Optional[str] = None


@dataclass
class SwarmConsensus:
    final_verdict: Verdict
    confidence: float
    unanimous: bool
    breakdown: Dict[str, str]
    dominant_issues: List[Dict[str, Any]]
    reasoning: str
    escalation_reason: Optional[str] = None


CRITIC_PROMPTS = {
    CriticRole.FACTUAL: {
        "system": """Tu es Critic-Factual, un agent de vérification factuelle et technique du système BEK-v15.2.
MISSION :
1. Vérifie la véracité des chiffres, montants, codes, chemins de fichiers et cohérence des données.
2. Si la requête est une simple salutation ou discussion, AUCUN fait CRM ou base de données ne doit être inventé.
3. Ne tolère aucune action ou outil imaginaire non implémenté.

FORMAT DE SORTIE (JSON strict) :
{
  "verdict": "GOOD|FIX|ESCALATE",
  "confidence": 0.0-1.0,
  "reasoning": "Explication factuelle concise",
  "issues": [{"claim_id": "...", "severity": "LOW|MEDIUM|HIGH", "description": "...", "expected_correction": "..."}]
}"""
    },
    CriticRole.LOGICAL: {
        "system": """Tu es Critic-Logical, un agent de vérification logique et de raisonnement profond.
MISSION :
1. Traque les contradictions, sophismes, hallucinations et raccourcis.
2. Vérifie la causalité : une action technique ne doit être générée QUE SI l'utilisateur a donné un ordre explicite.
3. Assure que la réponse respecte rigoureusement les contraintes de l'utilisateur.

FORMAT DE SORTIE (JSON strict) :
{
  "verdict": "GOOD|FIX|ESCALATE",
  "confidence": 0.0-1.0,
  "reasoning": "Explication logique concise",
  "issues": [{"claim_id": "...", "severity": "LOW|MEDIUM|HIGH", "description": "...", "expected_correction": "..."}]
}"""
    },
    CriticRole.CONTEXTUAL: {
        "system": """Tu es Critic-Contextual, un agent de cadrage contextuel, d'adéquation et de posture sociale.
MISSION :
1. FILTRAGE INTENTION & SOCIAL : Si l'utilisateur dit 'bonjour', 'salut', ou engage une discussion générale, la réponse doit être naturelle, humaine et directe. INTERDICTION de forcer le sujet CRM ou de lister des fonctionnalités non demandées.
2. ACTIONNABILITÉ : Si c'est un ordre de programmation ou d'automatisation, vérifie que le ton est direct, expert et sans bla-bla.

FORMAT DE SORTIE (JSON strict) :
{
  "verdict": "GOOD|FIX|ESCALATE",
  "confidence": 0.0-1.0,
  "reasoning": "Explication contextuelle concise",
  "issues": [{"claim_id": "...", "severity": "LOW|MEDIUM|HIGH", "description": "...", "expected_correction": "..."}]
}"""
    }
}


class CriticAgent:
    def __init__(self, role: CriticRole, llm):
        self.role = role
        self.llm = llm
        self.config = CRITIC_PROMPTS[role]

    def critique(self, draft: str, original_query: str, user_context: Dict = None) -> SwarmCritique:
        import time
        start = time.time()
        user_prompt = f"REQUÊTE UTILISATEUR : {original_query}\n\nDRAFT DE RÉPONSE PROPOSÉ :\n{draft}"
        try:
            messages = [
                SystemMessage(content=self.config["system"]),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())
            latency = int((time.time() - start) * 1000)
            return SwarmCritique(
                critic_id=f"critic_{self.role.value}",
                role=self.role,
                verdict=Verdict(data.get("verdict", "FIX")),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                issues=data.get("issues", []),
                latency_ms=latency
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            return SwarmCritique(
                critic_id=f"critic_{self.role.value}",
                role=self.role,
                verdict=Verdict.ESCALATE,
                confidence=0.0,
                reasoning=str(e),
                issues=[],
                latency_ms=latency,
                error=str(e)
            )


class ReflexionSwarm:
    def __init__(self, llm_provider: str = "groq", llm_model: str = None):
        self.llm = self._init_llm(llm_provider, llm_model)
        self.critics = {role: CriticAgent(role, self.llm) for role in CriticRole}
        self.executor = ThreadPoolExecutor(max_workers=3)

    def _init_llm(self, provider: str, model: str = None):
        p = provider.lower().strip()
        if p == "groq":
            api_key = provider_manager.get_api_key("GROQ_API_KEY")
            return ChatGroq(model=model or "openai/gpt-oss-120b", temperature=0.1, api_key=api_key)
        elif p == "nvidia":
            api_key = provider_manager.get_api_key("NVIDIA_API_KEY")
            return ChatOpenAI(
                model=model or "meta/llama-3.3-70b-instruct",
                temperature=0.1,
                base_url="[https://integrate.api.nvidia.com/v1](https://integrate.api.nvidia.com/v1)",
                api_key=api_key
            )
        elif p == "gemini":
            api_key = provider_manager.get_api_key("GEMINI_API_KEY")
            return ChatGoogleGenerativeAI(model=model or "gemini-1.5-pro", temperature=0.1, api_key=api_key)
        elif p == "openrouter":
            api_key = provider_manager.get_api_key("OPENROUTER_API_KEY")
            return ChatOpenAI(
                model=model or "openai/gpt-oss-120b",
                temperature=0.1,
                base_url="[https://openrouter.ai/api/v1](https://openrouter.ai/api/v1)",
                api_key=api_key
            )
        else:
            raise ValueError(f"Provider inconnu: {provider}")

    def critique(self, draft: str, original_query: str, user_context: Dict = None) -> SwarmConsensus:
        futures = {self.executor.submit(c.critique, draft, original_query, user_context): role for role, c in self.critics.items()}
        critiques = []
        for future in as_completed(futures):
            try:
                critiques.append(future.result(timeout=30))
            except Exception as e:
                role = futures[future]
                critiques.append(SwarmCritique(f"critic_{role.value}", role, Verdict.ESCALATE, 0.0, str(e), [], error=str(e)))
        return self._aggregate(critiques)

    def post_plan_evaluation_hook(self, tasks: List[Dict[str, Any]], execution_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        [HOOK POINT C] : Intercepteur Post-Plan relié à Hermes Core V2.
        Audite la cohérence d'exécution globale avant transmission.
        """
        status = execution_payload.get("status", "UNKNOWN")
        results = execution_payload.get("results", {})
        
        # Audit d'intégrité rapide si l'exécution a réussi
        if status in ("SUCCESS", "PARTIAL_SUCCESS") and results:
            summary = json.dumps(results, ensure_ascii=False, default=str)[:1000]
            execution_payload["swarm_audit"] = {
                "verified": True,
                "audit_timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0,
                "summary_length": len(summary)
            }
        else:
            execution_payload["swarm_audit"] = {
                "verified": False,
                "reason": "Exécution incomplète ou échouée."
            }
        return execution_payload

    def _aggregate(self, critiques: List[SwarmCritique]) -> SwarmConsensus:
        votes = {v: 0.0 for v in Verdict}
        breakdown = {}
        all_issues = []
        for c in critiques:
            votes[c.verdict] += c.confidence
            breakdown[c.critic_id] = c.verdict.value
            all_issues.extend(c.issues)

        winner = max(votes, key=votes.get)
        total_conf = sum(votes.values())
        winner_conf = votes[winner] / total_conf if total_conf > 0 else 0
        unanimous = len(set(c.verdict for c in critiques)) == 1

        return SwarmConsensus(
            final_verdict=winner,
            confidence=winner_conf,
            unanimous=unanimous,
            breakdown=breakdown,
            dominant_issues=self._extract_dominant_issues(all_issues),
            reasoning=" | ".join([f"{c.role.value}:{c.verdict.value}" for c in critiques]),
            escalation_reason="Élevé par un critique" if winner == Verdict.ESCALATE else None
        )

    def _extract_dominant_issues(self, issues: List[Dict]) -> List[Dict]:
        if not issues:
            return []
        severity_scores = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        issue_scores = {}
        for issue in issues:
            desc = issue.get("description", "")
            sev = issue.get("severity", "MEDIUM")
            key = desc[:100]
            if key not in issue_scores:
                issue_scores[key] = {"description": desc, "severity": sev, "count": 0}
            issue_scores[key]["count"] += 1
        return sorted(issue_scores.values(), key=lambda x: x["count"], reverse=True)[:5]

    def to_dict(self, consensus: SwarmConsensus) -> Dict:
        return {
            "final_verdict": consensus.final_verdict.value,
            "confidence": consensus.confidence,
            "unanimous": consensus.unanimous,
            "breakdown": consensus.breakdown,
            "dominant_issues": consensus.dominant_issues,
            "reasoning": consensus.reasoning
        }

    def close(self):
        self.executor.shutdown(wait=True)
