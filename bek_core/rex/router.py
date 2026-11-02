# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-REX Router
# ------------------------------------------------------------------------------
# v1.3 (2026-10-24) : FIX surcoût sémantique (densité relative au lieu de =1.0)
# ==============================================================================
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.rex")

BEK_REX_TIERS = ["TIER_0", "TIER_1", "TIER_2", "TIER_3", "TIER_4"]
BEK_REX_DEFAULT_CONFIDENCE = 0.5

BEK_REX_KEYWORDS = {
    "TIER_1": ["prix", "cours", "combien", "qui est", "quelle heure", "météo", "score", "résultat", "date", "quand", "où", "adresse", "téléphone", "email"],
    "TIER_2": ["news", "actualité", "actualités", "dernières", "récent", "récente", "aujourd'hui", "hier", "bitcoin", "crypto", "cryptomonnaie", "ethereum", "blockchain", "bourse", "finance", "marché", "économie", "ia", "intelligence artificielle", "tech", "technologie", "startup"],
    "TIER_3": ["analyse", "rapport", "complet", "état de l'art", "veille", "étude", "recherche approfondie", "synthèse", "comparaison", "évaluation", "bilan", "perspective"],
    "TIER_4": ["médecine", "médical", "droit", "juridique", "science", "philosophie", "biologie", "anthropologie", "religion", "académique", "scientifique", "recherche clinique", "thèse", "doctorat", "université", "publication"],
}

BEK_REX_GREETINGS = {"bonjour", "bonsoir", "salut", "hello", "hi", "coucou", "ça va", "comment ça va", "merci", "au revoir", "bye"}

class BekRexRouter:
    def __init__(self):
        self.default_confidence = BEK_REX_DEFAULT_CONFIDENCE

    def route(self, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = options or {}
        force_tier = options.get("force_tier")
        max_tier = options.get("max_tier", "TIER_4")
        min_confidence = options.get("min_confidence", 0.0)

        if max_tier not in BEK_REX_TIERS:
            logger.warning("[rex] max_tier invalide '%s', fallback sur TIER_4", max_tier)
            max_tier = "TIER_4"

        if not query or not query.strip(): return self._result("TIER_0", 1.0, "Requête vide", query)
        if force_tier and force_tier in BEK_REX_TIERS: return self._result(force_tier, 1.0, "Tier forcé manuellement", query)

        query_lower = query.lower().strip()
        if self._is_greeting(query_lower): return self._result("TIER_0", 0.95, "Salutation détectée", query)
        if len(query_lower.split()) <= 2: return self._result("TIER_0", 0.80, "Requête très courte", query)

        scores = self._score_all_tiers(query_lower)
        max_idx = BEK_REX_TIERS.index(max_tier)
        allowed_tiers = BEK_REX_TIERS[:max_idx + 1]
        scores = {t: s for t, s in scores.items() if t in allowed_tiers}

        sorted_tiers = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_tier, best_score = sorted_tiers[0]

        if best_score >= 0.5: confidence = min(1.0, 0.6 + best_score * 0.4)
        elif best_score > 0.0: confidence = 0.5 + best_score * 0.3
        else:
            best_tier = "TIER_3"
            best_score = 0.3
            confidence = 0.5

        if min_confidence > 0 and confidence < min_confidence:
            best_tier = self.escalate(best_tier)
            confidence = min_confidence

        reasoning = self._build_reasoning(best_tier, scores, query_lower)
        return self._result(best_tier, confidence, reasoning, query, scores)

    def _score_all_tiers(self, query_lower: str) -> Dict[str, float]:
        scores = {t: 0.0 for t in BEK_REX_TIERS}

        for tier, keywords in BEK_REX_KEYWORDS.items():
            for kw in keywords:
                if kw in query_lower:
                    scores[tier] += 0.40
                    if query_lower.startswith(kw): scores[tier] += 0.15
                    if re.search(rf"\b{re.escape(kw)}\b", query_lower): scores[tier] += 0.15
                elif kw.endswith(("e", "s", "l", "x")) and kw[:-1] in query_lower:
                    scores[tier] += 0.20
                elif len(kw) > 5 and kw[:-1] in query_lower:
                    scores[tier] += 0.15

        word_count = len(query_lower.split())
        if word_count > 15:
            scores["TIER_3"] += 0.35
            scores["TIER_4"] += 0.30
        elif word_count > 10:
            scores["TIER_3"] += 0.25
            scores["TIER_4"] += 0.15
        elif word_count > 8:
            scores["TIER_2"] += 0.20
            scores["TIER_3"] += 0.15
        elif word_count > 4:
            scores["TIER_1"] += 0.10
            scores["TIER_2"] += 0.10

        # ★ FIX v1.3 : Densité sémantique (ratio mots-clés / mots totaux) au lieu de l'écrasement
        word_count = max(1, word_count)
        for tier in ["TIER_2", "TIER_3", "TIER_4"]:
            if scores[tier] > 0:
                density = scores[tier] / word_count
                # On mélange le score brut et la densité (50/50)
                scores[tier] = min(1.0, scores[tier] * 0.5 + density * 0.5)

        for tier in scores:
            scores[tier] = round(min(1.0, scores[tier]), 3)

        return scores

    def _is_greeting(self, query_lower: str) -> bool:
        words = query_lower.split()
        if len(words) > 4: return False
        for greeting in BEK_REX_GREETINGS:
            if query_lower == greeting or query_lower.startswith(greeting + " "):
                return True
        return False

    def _build_reasoning(self, tier: str, scores: Dict[str, float], query_lower: str) -> str:
        parts = [f"Tier choisi : {tier}"]
        if tier in BEK_REX_KEYWORDS:
            detected = [kw for kw in BEK_REX_KEYWORDS[tier] if kw in query_lower]
            if detected: parts.append(f"Mots-clés : {', '.join(detected[:3])}")
        parts.append(f"Longueur : {len(query_lower.split())} mots")
        parts.append(f"Score : {scores.get(tier, 0.0):.2f}")
        return " | ".join(parts)

    def _result(self, tier: str, confidence: float, reasoning: str, query: str, scores: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        return {"tier": tier, "confidence": round(confidence, 3), "scores": scores or {}, "reasoning": reasoning, "query": query}

    def list_tiers(self) -> List[str]: return BEK_REX_TIERS.copy()

    def escalate(self, current_tier: str) -> str:
        if current_tier not in BEK_REX_TIERS: return "TIER_3"
        idx = BEK_REX_TIERS.index(current_tier)
        if idx >= len(BEK_REX_TIERS) - 1: return current_tier
        return BEK_REX_TIERS[idx + 1]

def bek_rex_route(query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    router = BekRexRouter()
    return router.route(query, options)

def bek_rex_list_tiers() -> List[str]: return BEK_REX_TIERS.copy()