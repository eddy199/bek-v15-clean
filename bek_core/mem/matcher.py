# ==============================================================================
# BEK-v18 — BEK-MEM Matcher (v2.2 — Lazy Loading + JSON Safe)
# ★ v2.2 : Lazy loading confirmé + json.dumps() confirmé
# ==============================================================================
from __future__ import annotations

import hashlib, json, logging, time, difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False

logger = logging.getLogger("bek.core.mem")

BEK_MEM_DEFAULT_THRESHOLD = 0.75
BEK_MEM_DEFAULT_TOP_K = 3
BEK_MEM_STORAGE_FILE = "data/bek_mem_prototypes.json"
BEK_MEM_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

class BekMemMatcher:
    def __init__(self, storage_path: Optional[str] = None, threshold: float = BEK_MEM_DEFAULT_THRESHOLD):
        self.storage_path = Path(storage_path or BEK_MEM_STORAGE_FILE)
        self.threshold = threshold
        self._prototypes: Dict[str, Dict[str, Any]] = {}
        # ★ v2.2 : Lazy loading
        self._encoder = None
        self._encoder_loaded = False
        self._load()

    def _get_encoder(self):
        if self._encoder_loaded: return self._encoder
        self._encoder_loaded = True
        if not HAS_SEMANTIC:
            logger.warning("BekMem : sentence-transformers indisponible → mode hybride")
            return None
        try:
            logger.info("BekMem : chargement lazy du modèle %s", BEK_MEM_EMBEDDING_MODEL)
            self._encoder = SentenceTransformer(BEK_MEM_EMBEDDING_MODEL)
            return self._encoder
        except Exception as exc:
            logger.error("BekMem : échec chargement modèle : %s", exc)
            self._encoder = None
            return None

    def _load(self) -> None:
        if not self.storage_path.exists(): self._prototypes = {}; return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f: self._prototypes = json.load(f).get("prototypes", {})
            logger.info("BekMem : %d prototypes chargés", len(self._prototypes))
        except Exception as exc:
            logger.warning("BekMem : erreur chargement : %s", exc); self._prototypes = {}

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f: json.dump({"prototypes": self._prototypes}, f, indent=2, ensure_ascii=False)
        except Exception as exc: logger.error("BekMem : erreur sauvegarde : %s", exc)

    def _compute_score(self, query: str, proto_query: str, proto_embedding: Optional[List[float]]) -> float:
        encoder = self._get_encoder()
        if encoder is not None and proto_embedding:
            query_vec = encoder.encode(query); proto_vec = np.array(proto_embedding)
            norm = np.linalg.norm(query_vec) * np.linalg.norm(proto_vec)
            if norm == 0: return 0.0
            return float(np.dot(query_vec, proto_vec) / norm)
        query_lower, proto_lower = query.lower().strip(), proto_query.lower().strip()
        seq_ratio = difflib.SequenceMatcher(None, query_lower, proto_lower).ratio()
        q_words, p_words = set(query_lower.split()), set(proto_lower.split())
        union = len(q_words | p_words); jaccard = len(q_words & p_words) / union if union > 0 else 0.0
        return max(seq_ratio, jaccard)

    def match(self, query: str, threshold: Optional[float] = None, top_k: int = BEK_MEM_DEFAULT_TOP_K) -> Optional[Dict[str, Any]]:
        if not query or not query.strip() or not self._prototypes: return None
        threshold = threshold or self.threshold
        candidates = []
        for proto_id, proto in self._prototypes.items():
            proto_query = proto.get("query", "")
            if not proto_query: continue
            score = self._compute_score(query, proto_query, proto.get("embedding"))
            if score >= threshold: candidates.append({"prototype_id": proto_id, "score": round(score, 3), "prototype": proto})
        if not candidates: return None
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]

    def store(self, query: str, tier: str, result: Dict[str, Any]) -> str:
        proto_hash = hashlib.md5(query.lower().encode()).hexdigest()[:12]
        proto_id = f"proto_{proto_hash}"
        encoder = self._get_encoder()
        embedding = encoder.encode(query).tolist() if encoder else None
        # ★ FIX : json.dumps pour éviter les chaînes corrompues
        try: result_summary = json.dumps(result, ensure_ascii=False)[:200] if result else ""
        except Exception: result_summary = str(result)[:200] if result else ""

        if proto_id in self._prototypes:
            proto = self._prototypes[proto_id]
            proto["usage_count"] = proto.get("usage_count", 0) + 1; proto["last_used"] = time.time()
            if embedding: proto["embedding"] = embedding
        else:
            self._prototypes[proto_id] = {
                "prototype_id": proto_id, "query": query, "embedding": embedding,
                "tier": tier, "methodology": tier, "usage_count": 1, "success_count": 0,
                "avg_time_ms": 0.0, "created_at": time.time(), "last_used": time.time(),
                "result_summary": result_summary,
            }
        self._save(); return proto_id

    def update(self, prototype_id: str, success: bool, time_ms: float) -> bool:
        if prototype_id not in self._prototypes: return False
        proto = self._prototypes[prototype_id]
        old_avg = proto.get("avg_time_ms", 0.0); old_count = proto.get("usage_count", 1)
        proto["avg_time_ms"] = (old_avg * old_count + time_ms) / (old_count + 1)
        if success: proto["success_count"] = proto.get("success_count", 0) + 1
        proto["last_used"] = time.time(); self._save(); return True

    def list_all(self) -> List[str]: return sorted(self._prototypes.keys())
    def count(self) -> int: return len(self._prototypes)
    def get(self, prototype_id: str) -> Optional[Dict[str, Any]]: return self._prototypes.get(prototype_id)
    def clear(self) -> int:
        count = len(self._prototypes); self._prototypes = {}; self._save(); return count

def bek_mem_match(query: str, threshold: float = BEK_MEM_DEFAULT_THRESHOLD) -> Optional[Dict[str, Any]]: return BekMemMatcher(threshold=threshold).match(query, threshold=threshold)
def bek_mem_store(query: str, tier: str, result: Dict[str, Any]) -> str: return BekMemMatcher().store(query, tier, result)
def bek_mem_update(prototype_id: str, success: bool, time_ms: float) -> bool: return BekMemMatcher().update(prototype_id, success, time_ms)