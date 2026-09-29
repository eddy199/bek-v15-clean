# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-MEM Matcher (Optimisation Sémantique)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-MEM-v1.0
# 📄 Doc : docs/brevets/BREVET_MEM.md
# 🎯 Rôle : Matching de prototypes par similarité sémantique (Cosinus)
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 2.0 (Refactored)
# Date : 2026-09-28
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import time
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

# Support optionnel pour les embeddings sémantiques réels (rapide et local)
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False

logger = logging.getLogger("bek.core.mem")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_MEM_DEFAULT_THRESHOLD = 0.75  # Rabaissé de 0.85 à 0.75 pour le sémantique
BEK_MEM_DEFAULT_TOP_K = 3
BEK_MEM_STORAGE_FILE = "data/bek_mem_prototypes.json"
BEK_MEM_EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Modèle ultra-léger (~80MB)


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekMemMatcher:
    """
    Matcher BEK-MEM Sémantique.

    Trouve, stocke et met à jour les prototypes de résolution.
    Utilise la similarité Cosinus sur des vecteurs sémantiques si disponible,
    sinon utilise une approche hybride (Jaccard + Ratcliff/Obershelp).
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        threshold: float = BEK_MEM_DEFAULT_THRESHOLD,
    ):
        self.storage_path = Path(storage_path or BEK_MEM_STORAGE_FILE)
        self.threshold = threshold
        self._prototypes: Dict[str, Dict[str, Any]] = {}
        
        # Initialisation du modèle d'embedding (Lazy loading)
        self.encoder = None
        if HAS_SEMANTIC:
            logger.info("BekMem : Moteur d'embeddings sémantiques activé.")
            self.encoder = SentenceTransformer(BEK_MEM_EMBEDDING_MODEL)
        else:
            logger.warning("BekMem : Mode sémantique inactif. Installez 'sentence-transformers'. Mode hybride activé.")

        self._load()

    # ──────────────────────────────────────────────────────────────────────────
    # CHARGEMENT / SAUVEGARDE
    # ──────────────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._prototypes = {}
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._prototypes = data.get("prototypes", {})
            logger.info("BekMem : %d prototypes chargés", len(self._prototypes))
        except Exception as exc:
            logger.warning("BekMem : erreur chargement : %s", exc)
            self._prototypes = {}

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"prototypes": self._prototypes}, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("BekMem : erreur sauvegarde : %s", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # MATCHING SÉMANTIQUE
    # ──────────────────────────────────────────────────────────────────────────

    def _compute_score(self, query: str, proto_query: str, proto_embedding: Optional[List[float]]) -> float:
        """Calcule le score de similarité entre 0.0 et 1.0."""
        
        # 1. Mode Sémantique Vectoriel (Cosine Similarity)
        if self.encoder is not None and proto_embedding:
            query_vec = self.encoder.encode(query)
            proto_vec = np.array(proto_embedding)
            # Distance Cosinus
            cosine_sim = np.dot(query_vec, proto_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(proto_vec))
            return float(cosine_sim)
        
        # 2. Mode Fallback Hybride (Si pas de PyTorch/Embeddings)
        query_lower = query.lower().strip()
        proto_lower = proto_query.lower().strip()
        
        # Similarité de séquence (Ratcliff/Obershelp)
        seq_ratio = difflib.SequenceMatcher(None, query_lower, proto_lower).ratio()
        
        # Jaccard
        q_words = set(query_lower.split())
        p_words = set(proto_lower.split())
        union = len(q_words | p_words)
        jaccard = len(q_words & p_words) / union if union > 0 else 0.0
        
        # On prend le meilleur des deux scores
        return max(seq_ratio, jaccard)

    def match(
        self,
        query: str,
        threshold: Optional[float] = None,
        top_k: int = BEK_MEM_DEFAULT_TOP_K,
    ) -> Optional[Dict[str, Any]]:
        if not query or not query.strip() or not self._prototypes:
            return None

        threshold = threshold or self.threshold
        candidates = []

        for proto_id, proto in self._prototypes.items():
            proto_query = proto.get("query", "")
            if not proto_query:
                continue

            score = self._compute_score(query, proto_query, proto.get("embedding"))

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

        logger.info("BekMem : match trouvé | score=%.2f | proto=%s", best["score"], best["prototype_id"])
        return best

    # ──────────────────────────────────────────────────────────────────────────
    # STOCKAGE
    # ──────────────────────────────────────────────────────────────────────────

    def store(self, query: str, tier: str, result: Dict[str, Any]) -> str:
        proto_hash = hashlib.md5(query.lower().encode()).hexdigest()[:12]
        proto_id = f"proto_{proto_hash}"

        # Générer l'embedding au moment du stockage
        embedding = self.encoder.encode(query).tolist() if self.encoder else None

        if proto_id in self._prototypes:
            proto = self._prototypes[proto_id]
            proto["usage_count"] = proto.get("usage_count", 0) + 1
            proto["last_used"] = time.time()
            if embedding:
                proto["embedding"] = embedding
        else:
            self._prototypes[proto_id] = {
                "prototype_id": proto_id,
                "query": query,
                "embedding": embedding,
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
    # MISE À JOUR ET HELPERS (Inchangés)
    # ──────────────────────────────────────────────────────────────────────────

    def update(self, prototype_id: str, success: bool, time_ms: float) -> bool:
        if prototype_id not in self._prototypes:
            return False

        proto = self._prototypes[prototype_id]
        old_avg = proto.get("avg_time_ms", 0.0)
        old_count = proto.get("usage_count", 1)
        proto["avg_time_ms"] = (old_avg * old_count + time_ms) / (old_count + 1)

        if success:
            proto["success_count"] = proto.get("success_count", 0) + 1

        proto["last_used"] = time.time()
        self._save()
        return True

    def list_all(self) -> List[str]:
        return sorted(self._prototypes.keys())

    def count(self) -> int:
        return len(self._prototypes)

    def get(self, prototype_id: str) -> Optional[Dict[str, Any]]:
        return self._prototypes.get(prototype_id)

    def clear(self) -> int:
        count = len(self._prototypes)
        self._prototypes = {}
        self._save()
        return count


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_mem_match(query: str, threshold: float = BEK_MEM_DEFAULT_THRESHOLD) -> Optional[Dict[str, Any]]:
    matcher = BekMemMatcher(threshold=threshold)
    return matcher.match(query, threshold=threshold)

def bek_mem_store(query: str, tier: str, result: Dict[str, Any]) -> str:
    matcher = BekMemMatcher()
    return matcher.store(query, tier, result)

def bek_mem_update(prototype_id: str, success: bool, time_ms: float) -> bool:
    matcher = BekMemMatcher()
    return matcher.update(prototype_id, success, time_ms)
