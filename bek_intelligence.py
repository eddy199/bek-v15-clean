"""
================================================================================
BEK-v16 — INTELLIGENCE CORE (Couche Additive d'Auto-Correction & Routing)
================================================================================
- Aucune modification de provider_manager.py / skill_generator.py requise.
- 3 briques : SmartRouter (routage sémantique), AutoCorrectEngine (boucle
  d'auto-correction avec steering), SkillForge (génération de skills
  auto‑corrigée avec réinjection des erreurs).
- Hook GPT-6 Astra prêt si OPENAI_API_KEY est présent (optionnel).
================================================================================
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from provider_manager import provider_manager
from skill_generator import create_and_register_skill

logger = logging.getLogger("bek.intelligence")


# ════════════════════════════════════════════════════════════════════════════
# 1. SMART ROUTER — Classification + échelle d'escalade par type de tâche
# ════════════════════════════════════════════════════════════════════════════
class Task:
    CHAT, CODE, REASONING, VISION, LONG_DOC, CREATIVE = (
        "chat", "code", "reasoning", "vision", "long_doc", "creative"
    )

# Échelles d'escalade mises à jour avec Kimi K3, Kimi K3 Swarm, GLM 5.3 Flash et Qwen 3.8 Flash
ROUTE_LADDERS: Dict[str, List[Tuple[str, str]]] = {
    Task.CHAT: [
        ("kimi", "kimi-k3"),
        ("kimi", "kimi-k3-swarm"),
        ("b_ai", "glm-5.3-flash"),
        ("b_ai", "qwen3.8-flash"),
        ("groq", "llama-3.3-70b-versatile"),
        ("gemini", "gemini-3.8-flash"),
        ("mistral", "mistral-small-4"),
    ],
    Task.CODE: [
        ("kimi", "kimi-k3"),
        ("b_ai", "qwen3.8-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-3.8-flash"),
        ("ovh_anonymous", "ovh-qwen-3.5-397b"),
        ("nvidia", "openai/gpt-oss-120b"),
    ],
    Task.REASONING: [
        ("b_ai", "glm-5.3-flash"),
        ("kimi", "kimi-k3-swarm"),
        ("nvidia", "nvidia/nemotron-3-super-120b-a12b"),
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-3.6-flash"),
    ],
    Task.VISION: [
        ("nvidia", "meta/llama-3.2-90b-vision-instruct"),
        ("gemini", "gemini-3.6-flash"),
    ],
    Task.LONG_DOC: [
        ("gemini", "gemini-3.6-flash"),
        ("b_ai", "glm-5.3-flash"),
        ("nvidia", "nvidia/nemotron-3-super-120b-a12b"),
    ],
    Task.CREATIVE: [
        ("kimi", "kimi-k3"),
        ("mistral", "mistral-medium-3.5"),
        ("gemini", "gemini-3.6-flash"),
        ("cohere", "cohere-command-a"),
    ],
}

_ASTRA_LADDER: List[Tuple[str, str]] = [("openai", "gpt-6-astra")]


class SmartRouter:
    """Classifie la requête et retourne l'échelle de providers à essayer."""

    _CODE_RE = re.compile(r"\b(def |class |import |function|bug|erreur)\b", re.I)
    _VISION_RE = re.compile(r"\b(image|photo|capture|screenshot|vision)\b", re.I)
    _REASON_RE = re.compile(r"\b(raisonne|étape par étape|prouve|optimise)\b", re.I)
    _CREATIVE_RE = re.compile(r"\b(rédige|écrit|poème|script|article)\b", re.I)

    def classify(self, messages: List[Dict[str, Any]]) -> str:
        text = " ".join(
            str(m.get("content", "")) for m in messages[-3:]
            if isinstance(m.get("content"), str)
        )
        total_chars = len(text)

        if any(m.get("role") == "user" and isinstance(m.get("content"), list) for m in messages):
            return Task.VISION
        if self._VISION_RE.search(text):
            return Task.VISION
        if self._CODE_RE.search(text):
            return Task.CODE
        if total_chars > 12_000:
            return Task.LONG_DOC
        if self._REASON_RE.search(text):
            return Task.REASONING
        if self._CREATIVE_RE.search(text):
            return Task.CREATIVE
        return Task.CHAT

    def route(
        self,
        messages: List[Dict[str, Any]],
        force: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """Retourne l'échelle d'essai [(provider, model), …] sans doublons."""
        ladder = list(
            ROUTE_LADDERS.get(force or self.classify(messages),
                              ROUTE_LADDERS[Task.CHAT])
        )
        if provider_manager.get_api_key("OPENAI_API_KEY"):
            ladder = ladder + _ASTRA_LADDER

        seen, out = set(), []
        for p, m in ladder:
            if (p, m) not in seen and provider_manager.is_provider_available(p):
                seen.add((p, m))
                out.append((p, m))
        return out or ROUTE_LADDERS[Task.CHAT][:1]


# ════════════════════════════════════════════════════════════════════════════
# 2. AUTO‑CORRECT ENGINE — Boucle d'auto‑correction avec steering
# ════════════════════════════════════════════════════════════════════════════
class ResponseQuality:
    """Score qualité 0‑100 + diagnostic. Heuristiques, 0 token."""

    @staticmethod
    def _ngram_ratio(text: str, n: int = 4) -> float:
        words = text.split()
        if len(words) < n * 2:
            return 0.0
        grams = [" ".join(words[i:i + n]) for i in range(len(words) - n)]
        return 1.0 - len(set(grams)) / max(len(grams), 1)

    @classmethod
    def evaluate(cls, text: str, max_tokens: int) -> Tuple[int, List[str]]:
        issues: List[str] = []
        score = 100
        t = (text or "").strip()

        if len(t) < 20:
            issues.append("reponse_vide_ou_trop_courte")
            score -= 60
        rep = cls._ngram_ratio(t)
        if rep > 0.45:
            issues.append(f"repetition_boucle({rep:.0%})")
            score -= 45
        if t and t[-1] not in ".!?)}]`\"'" and len(t) > max_tokens * 3.5:
            issues.append("reponse_tronquee")
            score -= 35
        if re.search(r"\b(as an ai|je suis désolé, je ne peux pas)\b", t, re.I) and len(t) < 120:
            issues.append("refus_injustifie")
            score -= 50
        if re.search(r"Traceback \(most recent call last\)", t):
            issues.append("contient_traceback")
            score -= 25
        return max(score, 0), issues


class AutoCorrectEngine:
    """Exécute une requête avec auto‑correction : évalue la sortie,
    injecte un steering correctif et escalade le modèle si nécessaire."""

    def __init__(
        self,
        router: Optional[SmartRouter] = None,
        min_score: int = 70,
        max_rounds: int = 3,
        timeout: int = 30,
    ):
        self.router = router or SmartRouter()
        self.min_score = min_score
        self.max_rounds = max_rounds
        self.timeout = timeout

    def _run_once(
        self,
        messages: List[Dict[str, Any]],
        provider: str,
        model: str,
        max_tokens: int,
    ) -> Tuple[str, str, str]:
        text, prov, mod = "", provider, model
        start = time.time()
        for ev in provider_manager.execute_chat_stream(
            messages,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            temperature=0.6,
        ):
            if ev.get("chunk"):
                text += ev["chunk"]
            elif ev.get("done"):
                prov, mod = ev["provider"], ev["model"]
            elif ev.get("error"):
                raise RuntimeError(ev["error"])

        if time.time() - start > self.timeout:
            raise TimeoutError(f"Appel {provider}/{model} dépassé {self.timeout}s")
        return text, prov, mod

    def ask(
        self,
        messages: List[Dict[str, Any]],
        task_type: Optional[str] = None,
        max_tokens: int = 4096,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        def emit(ev: Dict[str, Any]) -> None:
            if on_event:
                on_event(ev)

        ladder = self.router.route(messages, force=task_type)
        history: List[Dict[str, Any]] = list(messages)
        best, best_score, last_issues = "", -1, []

        for rnd in range(self.max_rounds):
            prov, mod = ladder[min(rnd, len(ladder) - 1)]
            t0 = time.time()
            try:
                text, prov, mod = self._run_once(history, prov, mod, max_tokens)
            except Exception as exc:
                logger.warning("[AutoCorrect] %s/%s échec : %s", prov, mod, exc)
                emit({"retry": rnd + 1, "reason": str(exc)[:200]})
                continue

            score, issues = ResponseQuality.evaluate(text, max_tokens)
            latency = round(time.time() - t0, 2)
            emit({
                "round": rnd + 1,
                "provider": prov,
                "model": mod,
                "score": score,
                "latency": latency,
                "issues": issues,
                "chunk_stream": text if rnd == 0 else "",
            })

            if score > best_score:
                best, best_score = text, score
            if score >= self.min_score:
                return {
                    "status": "ok",
                    "text": text,
                    "score": score,
                    "provider": prov,
                    "model": mod,
                    "rounds": rnd + 1,
                    "latency": latency,
                }

            last_issues = issues
            diagnosis = "; ".join(issues) or "qualité insuffisante"
            history = history + [
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": (
                        f"[STEERING CORRECTIF] Ta réponse a été évaluée : "
                        f"{diagnosis}. Corrige intégralement en tenant compte de "
                        f"ce diagnostic. Ne commente pas le diagnostic, livre "
                        f"directement la réponse corrigée."
                    ),
                },
            ]

        return {
            "status": "corrected" if best else "failed",
            "text": best or "Désolé, échec après auto‑correction.",
            "score": max(best_score, 0),
            "issues": last_issues,
            "rounds": self.max_rounds,
        }


# ════════════════════════════════════════════════════════════════════════════
# 3. SKILL FORGE — Génération de skills auto‑corrigée (réinjection d'erreurs)
# ════════════════════════════════════════════════════════════════════════════
class SkillForge:
    """Génère un skill Python via LLM, teste son exécution, et en cas
    d'erreur réinjecte le traceback au LLM pour correction (max 3 cycles)."""

    def __init__(self, engine: Optional[AutoCorrectEngine] = None):
        self.engine = engine or AutoCorrectEngine()

    _PROMPT = (
        "Tu es le générateur de skills de l'agent BEK. Écris UN script Python "
        "complet pour la compétence demandée.\n"
        "RÈGLES STRICTES :\n"
        "- La fonction principale s'appelle `run(*args, **kwargs)`.\n"
        "- `run` retourne UN dict JSON‑sérialisable {{\"status\": ..., \"result\": ...}}.\n"
        "- Aucune dépendance hors stdlib (requests, json, re, os, hashlib ok).\n"
        "- Gère les exceptions internes : jamais de crash, toujours un dict d'erreur.\n"
        "- Réponds UNIQUEMENT avec le code, sans markdown ni explication.\n"
        "{feedback}\n"
        "Compétence demandée : {description}"
    )

    def _clean_code(self, raw: str) -> str:
        cleaned = re.sub(r"^```(?:python)?\s*|```$", "", raw, flags=re.M).strip()
        if "def run" in cleaned:
            cleaned = cleaned[cleaned.find("def run"):]
        return cleaned

    def forge(
        self,
        description: str,
        skill_name: Optional[str] = None,
        max_cycles: int = 3,
    ) -> Dict[str, Any]:
        name = skill_name or "skill_" + hashlib.md5(description.encode()).hexdigest()[:10]
        feedback, code = "", ""

        for cycle in range(1, max_cycles + 1):
            prompt = self._PROMPT.format(
                feedback=(
                    f"\n[ERREUR PRÉCÉDENTE À CORRIGER]\n{feedback}\n"
                    if feedback
                    else ""
                ),
                description=description,
            )
            res = self.engine.ask(
                [{"role": "user", "content": prompt}], task_type=Task.CODE
            )
            if res.get("status") == "failed":
                return {
                    "status": "failed",
                    "error": "Impossible de générer le code du skill (échec LLM).",
                    "cycles": cycle,
                }

            code = self._clean_code(res.get("text", ""))

            try:
                result = create_and_register_skill(name, code, description)
                if isinstance(result, dict) and (result.get("status") == "ok" or result.get("success")):
                    return {
                        "status": "ok",
                        "skill_name": name,
                        "code": code,
                        "cycles": cycle,
                        "result": result,
                    }
                feedback = result.get("error") if isinstance(result, dict) else str(result)
            except Exception as exc:
                feedback = str(exc)
                logger.warning("[SkillForge] Erreur cycle %s pour %s : %s", cycle, name, exc)

        return {
            "status": "failed",
            "error": f"Échec après {max_cycles} cycles. Dernière erreur : {feedback}",
            "code": code,
            "cycles": max_cycles,
        }


# ════════════════════════════════════════════════════════════════════════════
# 4. INSTANCIATION & FAÇADE EXPORTÉE
# ════════════════════════════════════════════════════════════════════════════
class BekIntelligence:
    """Façade unifiée pour app.py et les routes de BEK."""
    def __init__(self):
        self.router = SmartRouter()
        self.engine = AutoCorrectEngine(router=self.router)
        self.forge = SkillForge(engine=self.engine)

    def ask(self, *args, **kwargs):
        return self.engine.ask(*args, **kwargs)

    def route(self, *args, **kwargs):
        return self.router.route(*args, **kwargs)

    def create_skill(self, *args, **kwargs):
        return self.forge.forge(*args, **kwargs)


# Instances singleton disponibles à l'import
bek_intelligence = BekIntelligence()
smart_router = bek_intelligence.router
auto_correct_engine = bek_intelligence.engine
auto_engine = bek_intelligence.engine
skill_forge = bek_intelligence.forge