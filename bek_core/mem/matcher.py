# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-MEM Matcher
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-MEM-v1.0
# 📄 Doc : docs/brevets/BREVET_MEM.md
# 🎯 Rôle : Matching de prototypes par similarité
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.mem")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_MEM_DEFAULT_THRESHOLD = 0.85
BEK_MEM_DEFAULT_TOP_K = 3
BEK_MEM_STORAGE_FILE = "data/bek_mem_prototypes.json"


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekMemMatcher:
    """
    Matcher BEK-MEM.

    Trouve, stocke et met à jour les prototypes de résolution.
    Utilise un stockage JSON local (fallback si Pinecone absent).

    Usage :
        matcher = BekMemMatcher()
        
        # Chercher un prototype
        match = matcher.match("Cherche Bitcoin")
        
        # Stocker un nouveau prototype
        matcher.store("Cherche Bitcoin", "TIER_2", {"result": "..."})
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        threshold: float = BEK_MEM_DEFAULT_THRESHOLD,
    ):
        self.storage_path = Path(storage_path or BEK_MEM_STORAGE_FILE)
        self.threshold = threshold
        self._prototypes: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ──────────────────────────────────────────────────────────────────────────
    # CHARGEMENT / SAUVEGARDE
    # ──────────────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Charge les prototypes depuis le disque."""
        if not self.storage_path.exists():
            self._prototypes = {}
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._prototypes = data.get("prototypes", {})
            logger.info(
                "BekMem : %d prototypes chargés",
                len(self._prototypes),
            )
        except Exception as exc:
            logger.warning("BekMem : erreur chargement : %s", exc)
            self._prototypes = {}

    def _save(self) -> None:
        """Sauvegarde les prototypes sur le disque."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"prototypes": self._prototypes},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as exc:
            logger.error("BekMem : erreur sauvegarde : %s", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # MATCHING
    # ──────────────────────────────────────────────────────────────────────────

    def match(
        self,
        query: str,
        threshold: Optional[float] = None,
        top_k: int = BEK_MEM_DEFAULT_TOP_K,
    ) -> Optional[Dict[str, Any]]:
        """
        Trouve le prototype le plus proche de la requête.

        Args:
            query: La requête utilisateur
            threshold: Seuil de matching (défaut 0.85)
            top_k: Nombre de candidats à considérer

        Returns:
            dict du prototype ou None si aucun match
        """
        if not query or not query.strip():
            return None

        threshold = threshold or self.threshold
        query_lower = query.lower().strip()

        if not self._prototypes:
            return None

        # Scoring par similarité (simple : mots en commun)
        candidates = []
        query_words = set(query_lower.split())

        for proto_id, proto in self._prototypes.items():
            proto_query = proto.get("query", "").lower()
            proto_words = set(proto_query.split())

            if not proto_words:
                continue

            # Score Jaccard
            intersection = len(query_words & proto_words)
            union = len(query_words | proto_words)
            score = intersection / union if union > 0 else 0.0

            if score >= threshold:
                candidates.append({
                    "prototype_id": proto_id,
                    "score": round(score, 3),
                    "prototype": proto,
                })

        if not candidates:
            return None

        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]

        logger.info(
            "BekMem : match trouvé | score=%.2f | proto=%s",
            best["score"],
            best["prototype_id"],
        )

        return best

    # ──────────────────────────────────────────────────────────────────────────
    # STOCKAGE
    # ──────────────────────────────────────────────────────────────────────────

    def store(
        self,
        query: str,
        tier: str,
        result: Dict[str, Any],
    ) -> str:
        """
        Stocke un nouveau prototype.

        Args:
            query: La requête originale
            tier: Le tier utilisé
            result: Le résultat de la résolution

        Returns:
            str: prototype_id
        """
        # Générer un ID unique
        proto_hash = hashlib.md5(query.lower().encode()).hexdigest()[:12]
        proto_id = f"proto_{proto_hash}"

        # Créer ou mettre à jour
        if proto_id in self._prototypes:
            proto = self._prototypes[proto_id]
            proto["usage_count"] = proto.get("usage_count", 0) + 1
            proto["last_used"] = time.time()
        else:
            self._prototypes[proto_id] = {
                "prototype_id": proto_id,
                "query": query,
                "tier": tier,
                "methodology": tier,
                "usage_count": 1,
                "success_count": 0,
                "avg_time_ms": 0.0,
                "created_at": time.time(),
                "last_used": time.time(),
                "result_summary": str(result)[:200] if result else "",
            }
            logger.info("BekMem : nouveau prototype %s", proto_id)

        self._save()
        return proto_id

    # ──────────────────────────────────────────────────────────────────────────
    # MISE À JOUR
    # ──────────────────────────────────────────────────────────────────────────

    def update(
        self,
        prototype_id: str,
        success: bool,
        time_ms: float,
    ) -> bool:
        """
        Met à jour les statistiques d'un prototype.

        Args:
            prototype_id: ID du prototype
            success: True si la résolution a réussi
            time_ms: Temps d'exécution en ms

        Returns:
            bool: True si mis à jour
        """
        if prototype_id not in self._prototypes:
            return False

        proto = self._prototypes[prototype_id]

        # Moyenne mobile
        old_avg = proto.get("avg_time_ms", 0.0)
        old_count = proto.get("usage_count", 1)
        proto["avg_time_ms"] = (old_avg * old_count + time_ms) / (old_count + 1)

        if success:
            proto["success_count"] = proto.get("success_count", 0) + 1

        proto["last_used"] = time.time()

        self._save()
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def list_all(self) -> List[str]:
        """Liste tous les prototype_id."""
        return sorted(self._prototypes.keys())

    def count(self) -> int:
        """Nombre de prototypes stockés."""
        return len(self._prototypes)

    def get(self, prototype_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un prototype par son ID."""
        return self._prototypes.get(prototype_id)

    def clear(self) -> int:
        """Efface tous les prototypes. Retourne le nombre effacé."""
        count = len(self._prototypes)
        self._prototypes = {}
        self._save()
        return count


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_mem_match(
    query: str,
    threshold: float = BEK_MEM_DEFAULT_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """Fonction principale BEK-MEM : matching."""
    matcher = BekMemMatcher(threshold=threshold)
    return matcher.match(query, threshold=threshold)


def bek_mem_store(
    query: str,
    tier: str,
    result: Dict[str, Any],
) -> str:
    """Stocke un nouveau prototype."""
    matcher = BekMemMatcher()
    return matcher.store(query, tier, result)


def bek_mem_update(
    prototype_id: str,
    success: bool,
    time_ms: float,
) -> bool:
    """Met à jour un prototype."""
    matcher = BekMemMatcher()
    return matcher.update(prototype_id, success, time_ms)