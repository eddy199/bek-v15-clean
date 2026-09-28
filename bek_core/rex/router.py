# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-REX Router
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-REX-v1.0
# 📄 Doc : docs/brevets/BREVET_REX.md
# 🎯 Rôle : Implémentation du routing 5 tiers
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.1
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.rex")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_REX_TIERS = ["TIER_0", "TIER_1", "TIER_2", "TIER_3", "TIER_4"]

BEK_REX_DEFAULT_CONFIDENCE = 0.5

# Mots-clés par tier (v1.1 : enrichis)
BEK_REX_KEYWORDS = {
    "TIER_1": [
        # Questions factuelles simples
        "prix", "cours", "combien", "qui est", "quelle heure",
        "météo", "score", "résultat", "date", "quand",
        "où", "adresse", "téléphone", "email",
    ],
    "TIER_2": [
        # News et actualités
        "news", "actualité", "actualités", "dernières",
        "récent", "récente", "aujourd'hui", "hier",
        # Sujets fréquents
        "bitcoin", "crypto", "cryptomonnaie", "ethereum", "blockchain",
        "bourse", "finance", "marché", "économie",
        "ia", "intelligence artificielle",
        "tech", "technologie", "startup",
    ],
    "TIER_3": [
        # Analyses complexes
        "analyse", "rapport", "complet", "état de l'art",
        "veille", "étude", "recherche approfondie", "synthèse",
        "comparaison", "évaluation", "bilan", "perspective",
    ],
    "TIER_4": [
        # Recherche spécialisée
        "médecine", "médical", "droit", "juridique", "science",
        "philosophie", "biologie", "anthropologie", "religion",
        "académique", "scientifique", "recherche clinique",
        "thèse", "doctorat", "université", "publication",
    ],
}

# Salutations (TIER_0)
BEK_REX_GREETINGS = {
    "bonjour", "bonsoir", "salut", "hello", "hi", "coucou",
    "ça va", "comment ça va", "merci", "au revoir", "bye",
}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekRexRouter:
    """
    Routeur cognitif BEK-REX.

    Détecte la complexité d'une requête et la route vers le tier optimal.

    Tiers :
        - TIER_0 : LOCAL       (salutations, conversations)
        - TIER_1 : FAST        (questions factuelles simples)
        - TIER_2 : DEEP        (news, analyses moyennes)
        - TIER_3 : EXPERT      (analyses complexes)
        - TIER_4 : SPECIALIZED (recherche spécialisée)

    Usage :
        router = BekRexRouter()
        result = router.route("Cherche les news sur le Bitcoin")
        # → {"tier": "TIER_2", "confidence": 0.75, ...}
    """

    def __init__(self):
        self.default_confidence = BEK_REX_DEFAULT_CONFIDENCE

    # ──────────────────────────────────────────────────────────────────────────
    # ROUTING
    # ──────────────────────────────────────────────────────────────────────────

    def route(
        self,
        query: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Route une requête vers le tier optimal.

        Args:
            query: La requête utilisateur
            options: Options (force_tier, max_tier, min_confidence)

        Returns:
            dict: {
                "tier": "TIER_X",
                "confidence": 0.0-1.0,
                "scores": {...},
                "reasoning": "...",
                "query": "..."
            }
        """
        options = options or {}
        force_tier = options.get("force_tier")
        max_tier = options.get("max_tier", "TIER_4")
        min_confidence = options.get("min_confidence", 0.0)

        if not query or not query.strip():
            return self._result("TIER_0", 1.0, "Requête vide", query)

        # Forçage manuel
        if force_tier and force_tier in BEK_REX_TIERS:
            return self._result(force_tier, 1.0, "Tier forcé manuellement", query)

        query_lower = query.lower().strip()

        # 1. Salutations → TIER_0
        if self._is_greeting(query_lower):
            return self._result("TIER_0", 0.95, "Salutation détectée", query)

        # 2. Requête très courte (1-2 mots) → TIER_0
        if len(query_lower.split()) <= 2:
            return self._result("TIER_0", 0.80, "Requête très courte", query)

        # 3. Scoring par tier
        scores = self._score_all_tiers(query_lower)

        # 4. Filtrer par max_tier
        max_idx = BEK_REX_TIERS.index(max_tier)
        allowed_tiers = BEK_REX_TIERS[:max_idx + 1]
        scores = {t: s for t, s in scores.items() if t in allowed_tiers}

        # 5. Choisir le meilleur (v1.1 : prend le meilleur même si bas)
        sorted_tiers = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_tier, best_score = sorted_tiers[0]

        # 6. Calcul de la confiance
        # Confiance = score normalisé + bonus si match clair
        if best_score >= 0.5:
            confidence = min(1.0, 0.6 + best_score * 0.4)
        elif best_score > 0.0:
            # Match partiel
            confidence = 0.5 + best_score * 0.3
        else:
            # Aucun match → TIER_3 par défaut (prudence)
            best_tier = "TIER_3"
            best_score = 0.3
            confidence = 0.5

        # Si min_confidence forcé, respecter
        if min_confidence > 0 and confidence < min_confidence:
            # Escalader d'un cran
            best_tier = self.escalate(best_tier)
            confidence = min_confidence

        reasoning = self._build_reasoning(best_tier, scores, query_lower)

        return self._result(best_tier, confidence, reasoning, query, scores)

    def _score_all_tiers(self, query_lower: str) -> Dict[str, float]:
        """Score la requête pour chaque tier."""
        scores = {
            "TIER_0": 0.0,
            "TIER_1": 0.0,
            "TIER_2": 0.0,
            "TIER_3": 0.0,
            "TIER_4": 0.0,
        }

        # Scoring par mots-clés
        for tier, keywords in BEK_REX_KEYWORDS.items():
            for kw in keywords:
                # Match exact (v1.3 : plus agressif)
                if kw in query_lower:
                    scores[tier] += 0.40  # était 0.30
                    # Bonus si en début de requête
                    if query_lower.startswith(kw):
                        scores[tier] += 0.15
                    # Bonus si mot entier (limites de mot)
                    if re.search(rf"\b{re.escape(kw)}\b", query_lower):
                        scores[tier] += 0.15

                # v1.2 : match racine (singulier/pluriel)
                # ex: "analyse" matche "analyses", "médical" matche "médicaux"
                elif kw.endswith(("e", "s", "l", "x")) and kw[:-1] in query_lower:
                    scores[tier] += 0.20
                # ex: "analyse" matche "analyser", "analysé"
                elif len(kw) > 5 and kw[:-1] in query_lower:
                    scores[tier] += 0.15

                # Scoring par longueur (requêtes longues = plus complexe)
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

        # v1.4 : PRIORITÉ par ordre de tier (le plus élevé gagne)
        # Si TIER_4 a un mot-clé fort détecté, il gagne
        if scores["TIER_4"] >= 0.40:
            scores["TIER_4"] = 1.0
            scores["TIER_3"] = min(scores["TIER_3"], 0.6)
            scores["TIER_2"] = min(scores["TIER_2"], 0.5)
            scores["TIER_1"] = min(scores["TIER_1"], 0.4)
        # Sinon si TIER_3 a un mot-clé fort détecté, il gagne
        elif scores["TIER_3"] >= 0.40:
            scores["TIER_3"] = 1.0
            scores["TIER_2"] = min(scores["TIER_2"], 0.7)
            scores["TIER_1"] = min(scores["TIER_1"], 0.5)

        # v1.4 : normaliser à 1.0 max pour comparaison
        # Mais préserver les boosts de TIER_3/TIER_4
        for tier in scores:
            scores[tier] = round(min(1.0, scores[tier]), 3)

        return scores

    def _is_greeting(self, query_lower: str) -> bool:
        """Détecte une salutation."""
        for greeting in BEK_REX_GREETINGS:
            if greeting in query_lower:
                return True
        return False

    def _build_reasoning(
        self,
        tier: str,
        scores: Dict[str, float],
        query_lower: str,
    ) -> str:
        """Construit une explication du routing."""
        parts = [f"Tier choisi : {tier}"]

        # Mots-clés détectés
        if tier in BEK_REX_KEYWORDS:
            detected = [
                kw for kw in BEK_REX_KEYWORDS[tier]
                if kw in query_lower
            ]
            if detected:
                parts.append(f"Mots-clés : {', '.join(detected[:3])}")

        # Complexité
        word_count = len(query_lower.split())
        parts.append(f"Longueur : {word_count} mots")

        # Score
        parts.append(f"Score : {scores.get(tier, 0.0):.2f}")

        return " | ".join(parts)

    def _result(
        self,
        tier: str,
        confidence: float,
        reasoning: str,
        query: str,
        scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Construit le résultat de routing."""
        return {
            "tier": tier,
            "confidence": round(confidence, 3),
            "scores": scores or {},
            "reasoning": reasoning,
            "query": query,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def list_tiers(self) -> List[str]:
        """Liste les 5 tiers disponibles."""
        return BEK_REX_TIERS.copy()

    def escalate(self, current_tier: str) -> str:
        """
        Retourne le tier supérieur (escalade).

        Args:
            current_tier: Tier actuel

        Returns:
            Tier supérieur, ou le même si déjà au max
        """
        if current_tier not in BEK_REX_TIERS:
            return "TIER_3"
        idx = BEK_REX_TIERS.index(current_tier)
        if idx >= len(BEK_REX_TIERS) - 1:
            return current_tier
        return BEK_REX_TIERS[idx + 1]


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_rex_route(
    query: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fonction principale BEK-REX.

    API publique du brevet BEK-REX-v1.0.
    """
    router = BekRexRouter()
    return router.route(query, options)


def bek_rex_list_tiers() -> List[str]:
    """Liste les tiers disponibles."""
    return BEK_REX_TIERS.copy()