# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-STAIR ToC Builder
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-STAIR-v1.0
# 📄 Doc : docs/brevets/BREVET_STAIR.md
# 🎯 Rôle : Construire et valider le ToC (Table of Contents)
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.2
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.stair")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_STAIR_VERSION = "1.2.0"
BEK_STAIR_MAX_FACTS_PER_PAGE = 5
BEK_STAIR_MIN_FACT_LENGTH = 40
BEK_STAIR_MAX_FACT_LENGTH = 200


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekStairToC:
    """
    Constructeur de ToC BEK-STAIR.

    Transforme une liste de pages scrapées en un ToC hiérarchique.
    Le LLM doit répondre UNIQUEMENT dans ce ToC.

    Usage :
        toc = BekStairToC()
        context = toc.build(pages=pages, query="Cherche Bitcoin")
        validation = toc.validate(llm_response, context, pages)
    """

    def build(
        self,
        pages: List[Dict[str, Any]],
        query: str,
    ) -> str:
        """
        Construit le ToC à partir des pages scrapées.

        Args:
            pages: Liste de pages {title, url, content}
            query: La requête utilisateur

        Returns:
            str: ToC formaté pour injection dans le prompt
        """
        if not pages:
            return ""

        lines = [
            "",
            "═══════════════════════════════════════════════════════════════════",
            "🎯 TABLE OF CONTENTS (ToC) — SOURCES AUTORISÉES",
            "═══════════════════════════════════════════════════════════════════",
            "",
            f"**Sujet :** {query}",
            "",
            f"**Nombre de sources :** {len(pages)}",
            "",
            "**Tu DOIS répondre UNIQUEMENT en te basant sur les sources ci-dessous.**",
            "**Tu NE PEUX PAS inventer de faits, dates, chiffres ou URLs.**",
            "",
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
            "",
            "⚠️ **RÈGLES ABSOLUES :**",
            "",
            "1. Cite tes sources avec le format **[S1]**, **[S2]**, etc.",
            "2. Si l'information n'est PAS dans le ToC ci-dessus → **dis honnêtement** :",
            "   « Cette information ne figure pas dans les sources disponibles. »",
            "3. N'invente JAMAIS de :",
            "   - Nouvelles URLs",
            "   - Nouvelles dates",
            "   - Nouveaux chiffres",
            "   - Nouveaux noms (entreprises, personnes, journaux)",
            f"4. Ta réponse doit être **100% traçable** aux sources [S1]-[S{len(pages)}].",
            "",
            "═══════════════════════════════════════════════════════════════════",
            "",
        ])

        return "\n".join(lines)

    def _extract_key_facts(
        self,
        content: str,
        max_facts: int = BEK_STAIR_MAX_FACTS_PER_PAGE,
    ) -> List[str]:
        """Extrait les faits clés d'un contenu."""
        if not content:
            return []

        # Découper en phrases
        sentences = re.split(r'[.!?]\s+', content)

        facts = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= BEK_STAIR_MIN_FACT_LENGTH:
                fact = sentence[:BEK_STAIR_MAX_FACT_LENGTH]
                facts.append(fact)
            if len(facts) >= max_facts:
                break

        return facts

    def validate(
        self,
        llm_response: str,
        toc_context: str,
        pages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Valide la réponse du LLM contre le ToC.

        Détecte :
            - URLs citées qui n'existent PAS dans les sources
            - Noms de sources non présents dans le ToC

        Args:
            llm_response: La réponse du LLM
            toc_context: Le ToC construit
            pages: Les pages sources

        Returns:
            dict: {
                "valid": bool,
                "hallucinations": [...],
                "score": float
            }
        """
        result = {
            "valid": True,
            "hallucinations": [],
            "score": 1.0,
        }

        if not llm_response:
            return result

        # ─── 1. Extraire les URLs citées ───
        url_pattern = r'https?://[^\s\)\]\>"\']+'
        cited_urls = re.findall(url_pattern, llm_response)

        # ─── 2. Extraire les URLs du ToC et des pages ───
        toc_urls = set(re.findall(r'URL : (https?://[^\s\)\]\>"\']+)', toc_context))
        for page in pages:
            page_url = page.get("url", "")
            if page_url:
                toc_urls.add(page_url)
                toc_urls.add(page_url.rstrip("/"))

        # ─── 3. Comparer les URLs ───
        invalid_urls = []
        for cited in cited_urls:
            cited_clean = cited.rstrip(".,;:")
            is_valid = any(
                cited_clean in toc_url or toc_url in cited_clean
                for toc_url in toc_urls
            )
            if not is_valid:
                invalid_urls.append(cited_clean)

        if invalid_urls:
            result["valid"] = False
            result["hallucinations"].append({
                "type": "invalid_urls",
                "detail": f"URLs non présentes dans le ToC : {invalid_urls[:3]}",
                "urls": invalid_urls,
            })
            result["score"] -= 0.3 * min(len(invalid_urls), 3)

        # ─── 4. Détecter les mentions de sources non vérifiables ───
        # v1.2 : regex améliorée (case-insensitive, apostrophes multiples)
        # ─── 4. Détecter les mentions de sources non vérifiables ───
        # v1.3 : regex stricte
        # - Préfixes en variantes minuscule/majuscule explicites
        # - Capture limitée à 1-2 mots
        # - SANS re.IGNORECASE (pour que [A-Z] reste une vraie majuscule)
        source_pattern = (
            r'(?:[Ss]elon|[Dd][\'’]après|[Ss]ource\s*:\s*|[Cc]ite\s+|'
            r'[Rr]apporte\s+|[Ll][\'’]analyse\s+de\s+|'
            r'[Aa]nalyse\s+de\s+|[Pp]ropos\s+de\s+)'
            r'([A-Z][a-zA-ZÀ-ÿ]+(?:\s+[A-Z][a-zA-ZÀ-ÿ]+)?)'
        )
        source_mentions = re.findall(source_pattern, llm_response)
            

        # Filtrer : ne pas compter les simples mots communs
        _IGNORE_WORDS = {
            "le", "la", "les", "un", "une", "des", "du", "de",
            "et", "ou", "mais", "car", "donc", "or", "ni",
            "cette", "son", "sa", "ses", "leur", "leurs",
            "the", "a", "an", "and", "or", "but", "this", "that",
        }

        for mention in source_mentions:
            mention_lower = mention.lower().strip()

            # Ignorer les mots trop courts ou communs
            if len(mention) < 3 or mention_lower in _IGNORE_WORDS:
                continue

            # Vérifier si le nom est dans le ToC
            if mention_lower not in toc_context.lower():
                result["hallucinations"].append({
                    "type": "invalid_source_mention",
                    "detail": f"Source mentionnée non présente : '{mention}'",
                })
                result["score"] -= 0.1

        # ─── 5. Score final ───
        result["score"] = max(0.0, result["score"])

        # v1.2 : rejet strict si source inventée détectée
        if any(h["type"] == "invalid_source_mention" for h in result["hallucinations"]):
            result["valid"] = False
            result["score"] = min(result["score"], 0.4)  # Forcer sous 0.5

        if result["score"] < 0.5:
            result["valid"] = False

        if not result["valid"]:
            logger.warning(
                "BekStair : hallucinations détectées | score=%.2f | %d cas",
                result["score"],
                len(result["hallucinations"]),
            )

        return result


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_stair_build_toc(
    pages: List[Dict[str, Any]],
    query: str,
) -> str:
    """Construit un ToC à partir des pages."""
    toc = BekStairToC()
    return toc.build(pages, query)


def bek_stair_validate(
    llm_response: str,
    toc_context: str,
    pages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Valide une réponse LLM contre le ToC."""
    toc = BekStairToC()
    return toc.validate(llm_response, toc_context, pages)