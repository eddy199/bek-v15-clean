# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-STAIR ToC Builder (Semantic & LLM-Judge Ready)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-STAIR-v1.0
# 📄 Doc : docs/brevets/BREVET_STAIR.md
# 🎯 Rôle : Construire le ToC et valider les hallucinations (Fuzzy + Judge)
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 2.0 (Refactored)
# Date : 2026-09-28
# ==============================================================================

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.core.stair")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_STAIR_VERSION = "2.0.0"
BEK_STAIR_MAX_FACTS_PER_PAGE = 5
BEK_STAIR_MIN_FACT_LENGTH = 40
BEK_STAIR_MAX_FACT_LENGTH = 200

# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekStairToC:
    """
    Constructeur et Validateur ToC BEK-STAIR.
    """

    def build(self, pages: List[Dict[str, Any]], query: str) -> str:
        """Construit le ToC à partir des pages scrapées (Inchangé, déjà très bon)."""
        if not pages:
            return ""

        lines = [
            "═══════════════════════════════════════════════════════════════════",
            "🎯 TABLE OF CONTENTS (ToC) — SOURCES AUTORISÉES",
            "═══════════════════════════════════════════════════════════════════",
            f"**Sujet :** {query}",
            f"**Nombre de sources :** {len(pages)}",
            "**Tu DOIS répondre UNIQUEMENT en te basant sur les sources ci-dessous.**",
            "**Tu NE PEUX PAS inventer de faits, dates, chiffres ou URLs.**",
            "───────────────────────────────────────────────────────────────────",
        ]

        for i, page in enumerate(pages, 1):
            title = (page.get("title") or f"Source {i}")[:120]
            url = page.get("url", "")
            content = page.get("content", "")

            lines.append(f"📄 **[S{i}]** {title}")
            lines.append(f"    URL : {url}")

            if content:
                facts = self._extract_key_facts(content)
                for fact in facts:
                    lines.append(f"      • {fact}")
            lines.append("")

        lines.extend([
            "═══════════════════════════════════════════════════════════════════",
            "⚠️ **RÈGLES ABSOLUES :**",
            "1. Cite tes sources avec le format **[S1]**, **[S2]**, etc.",
            "2. Si l'information n'est PAS dans le ToC ci-dessus → dis honnêtement :",
            "   « Cette information ne figure pas dans les sources disponibles. »",
            "3. N'invente JAMAIS de nouvelles URLs, dates, chiffres ou noms.",
            "═══════════════════════════════════════════════════════════════════",
        ])

        return "\n".join(lines)

    def _extract_key_facts(self, content: str, max_facts: int = BEK_STAIR_MAX_FACTS_PER_PAGE) -> List[str]:
        if not content:
            return []
        sentences = re.split(r'[.!?]\s+', content)
        facts = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= BEK_STAIR_MIN_FACT_LENGTH:
                facts.append(sentence[:BEK_STAIR_MAX_FACT_LENGTH])
            if len(facts) >= max_facts:
                break
        return facts

    def _normalize_url(self, url: str) -> str:
        """Normalise une URL pour éviter les faux positifs (ex: HTTP vs HTTPS, www)."""
        parsed = urlparse(url.lower())
        netloc = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}"

    def validate(
        self,
        llm_response: str,
        toc_context: str,
        pages: List[Dict[str, Any]],
        llm_judge_hook: Optional[Callable[[str, str], bool]] = None
    ) -> Dict[str, Any]:
        """
        Valide la réponse du LLM contre le ToC.
        Utilise un hook LLM si fourni (BEK-MUX), sinon fallback sur de l'analyse lexicale robuste.
        """
        result = {
            "valid": True,
            "hallucinations": [],
            "score": 1.0,
        }

        if not llm_response:
            return result

        # ─── 1. Validation des URLs (Robustesse accrue) ───
        cited_urls = re.findall(r'https?://[^\s\)\]\>"\']+', llm_response)
        valid_normalized_urls = {self._normalize_url(page.get("url", "")) for page in pages if page.get("url")}
        
        invalid_urls = []
        for cited in cited_urls:
            norm_cited = self._normalize_url(cited)
            # Vérifier si l'URL citée fait partie du domaine/chemin d'une source autorisée
            if not any(norm_cited.startswith(valid_u) or valid_u.startswith(norm_cited) for valid_u in valid_normalized_urls):
                invalid_urls.append(cited)

        if invalid_urls:
            result["valid"] = False
            result["score"] -= 0.3 * min(len(invalid_urls), 3)
            result["hallucinations"].append({
                "type": "invalid_urls",
                "detail": f"URLs inventées ou modifiées : {invalid_urls[:3]}",
                "urls": invalid_urls,
            })

        # ─── 2. Validation Factuelle (LLM-as-a-Judge ou Regex Fallback) ───
        if llm_judge_hook:
            # Mode Avancé : On demande au MUX d'évaluer la fidélité
            is_faithful = llm_judge_hook(llm_response, toc_context)
            if not is_faithful:
                result["valid"] = False
                result["score"] -= 0.5
                result["hallucinations"].append({
                    "type": "semantic_hallucination",
                    "detail": "Le modèle Juge a détecté des faits non supportés par le ToC.",
                })
        else:
            # Mode Fallback : Détection lexicale des affirmations non sourcées
            # Recherche la présence de balises de sources [S1] si des entités sont nommées
            has_sources_citations = re.search(r'\[S\d+\]', llm_response)
            if not has_sources_citations and len(pages) > 0 and len(llm_response) > 150:
                # Si le texte est long et qu'il y a des pages, l'absence de [Sx] est suspecte
                result["score"] -= 0.2
                result["hallucinations"].append({
                    "type": "missing_citations",
                    "detail": "La réponse affirme des faits sans utiliser la taxonomie [S1], [S2] requise.",
                })

        # ─── 3. Finalisation du Score ───
        result["score"] = max(0.0, result["score"])
        if result["score"] < 0.5:
            result["valid"] = False

        if not result["valid"]:
            logger.warning("BekStair : Validation échouée | score=%.2f | Hallucinations : %s", result["score"], result["hallucinations"])

        return result

# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_stair_build_toc(pages: List[Dict[str, Any]], query: str) -> str:
    toc = BekStairToC()
    return toc.build(pages, query)

def bek_stair_validate(
    llm_response: str, 
    toc_context: str, 
    pages: List[Dict[str, Any]], 
    llm_judge_hook: Optional[Callable[[str, str], bool]] = None
) -> Dict[str, Any]:
    toc = BekStairToC()
    return toc.validate(llm_response, toc_context, pages, llm_judge_hook)
