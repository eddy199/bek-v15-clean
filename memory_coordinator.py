# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v19 — MEMORY COORDINATOR (v1.4 — Async-Safe + Tri pertinence)
# ------------------------------------------------------------------------------
# v1.4 (2026-10-30) — Fix :
#   - Fonction coordinate_memories_async unique et robuste (plus de doublon)
#   - Ajout de asyncio.wait_for pour éviter les blocages infinis
#   - Tri par pertinence dans _build_unified_context (limite 10 faits)
#   - Timeout conservé à 15s
# ==============================================================================

from __future__ import annotations

import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.memory_coordinator")


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryFact:
    text: str
    source: str
    confidence: float = 0.5
    timestamp: Optional[datetime] = None
    entities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def age_seconds(self) -> float:
        if not self.timestamp:
            return float("inf")
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()


@dataclass
class Conflict:
    entity: str
    facts: List[MemoryFact]
    reason: str


@dataclass
class UnifiedMemory:
    context: str
    facts: List[MemoryFact]
    conflicts: List[Conflict]
    sources_used: List[str]
    elapsed_ms: float


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

SOURCE_WEIGHTS = {
    "hindsight":  1.0,
    "pinecone":   0.7,
    "chromadb":   0.5,
    "supabase":   0.9,
}

NEGATION_WORDS = {
    "ne", "pas", "jamais", "aucun", "aucune", "rien", "plus",
    "no", "not", "never", "none", "nothing",
}

# ★ Timeout global par source
FETCH_TIMEOUT = 15.0

SIMILARITY_DUPLICATE_THRESHOLD = 0.92
SIMILARITY_CONTRADICTION_THRESHOLD = 0.70
MIN_LENGTH_RATIO = 0.7
MIN_COMMON_WORDS = 4


# ══════════════════════════════════════════════════════════════════════════════
# FETCH
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_pinecone(query: str) -> List[MemoryFact]:
    try:
        from memory import search_memory
        raw = search_memory(query, top_k=5)
        if not raw:
            return []
        facts = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("- "):
                line = line[2:].strip()
            if line:
                facts.append(MemoryFact(
                    text=line,
                    source="pinecone",
                    confidence=SOURCE_WEIGHTS["pinecone"],
                ))
        return facts
    except Exception as exc:
        logger.debug("[Coordinator] Pinecone échec : %s", exc)
        return []


def _fetch_chromadb(query: str) -> List[MemoryFact]:
    try:
        from memory import get_chroma_collection, get_embedding
        coll = get_chroma_collection()
        if coll is None:
            return []
        vec = get_embedding(query, input_type="query")
        if not vec:
            return []
        res = coll.query(query_embeddings=[vec], n_results=5)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        facts = []
        for doc, meta in zip(docs, metas):
            if not doc:
                continue
            ts = None
            if isinstance(meta, dict) and meta.get("date"):
                try:
                    ts = datetime.fromisoformat(meta["date"].replace("Z", "+00:00"))
                except Exception:
                    pass
            facts.append(MemoryFact(
                text=doc,
                source="chromadb",
                confidence=SOURCE_WEIGHTS["chromadb"],
                timestamp=ts,
            ))
        return facts
    except Exception as exc:
        logger.debug("[Coordinator] ChromaDB échec : %s", exc)
        return []


async def _fetch_hindsight_async(query: str) -> List[MemoryFact]:
    try:
        from hindsight_memory import hindsight_recall_async
        raw = await hindsight_recall_async(query)
        if not raw:
            return []
        facts = []
        for r in raw:
            text = r.get("text", "").strip()
            if not text:
                continue
            score = r.get("score", 0.0) or 0.0
            confidence = max(score, 0.8) if score > 0 else SOURCE_WEIGHTS["hindsight"]
            facts.append(MemoryFact(
                text=text,
                source="hindsight",
                confidence=confidence,
            ))
        return facts
    except Exception as exc:
        logger.debug("[Coordinator] Hindsight async échec : %s", exc)
        return []


def _fetch_supabase(query: str) -> List[MemoryFact]:
    try:
        from memory import get_db_connection
        conn = get_db_connection()
        if not conn:
            return []
        cur = conn.cursor()
        facts = []

        try:
            cur.execute("""
                SELECT task_id, state, updated_at
                FROM bek_task_states
                WHERE state ILIKE %s
                ORDER BY updated_at DESC
                LIMIT 3;
            """, (f"%{query}%",))
            for task_id, state, updated_at in cur.fetchall():
                ts = updated_at if isinstance(updated_at, datetime) else None
                facts.append(MemoryFact(
                    text=f"Tâche {task_id} [{state}]",
                    source="supabase",
                    confidence=SOURCE_WEIGHTS["supabase"],
                    timestamp=ts,
                ))
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        if not facts:
            try:
                cur.execute("""
                    SELECT id, content, updated_at
                    FROM sync_log
                    WHERE content ILIKE %s
                    ORDER BY updated_at DESC
                    LIMIT 3;
                """, (f"%{query}%",))
                for rid, content, updated_at in cur.fetchall():
                    ts = updated_at if isinstance(updated_at, datetime) else None
                    facts.append(MemoryFact(
                        text=f"[sync {rid[:8]}] {content[:200]}",
                        source="supabase",
                        confidence=SOURCE_WEIGHTS["supabase"],
                        timestamp=ts,
                    ))
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

        cur.close()
        conn.close()
        return facts
    except Exception as exc:
        logger.debug("[Coordinator] Supabase échec : %s", exc)
        return []


async def fetch_all_memories_async(query: str) -> Dict[str, List[MemoryFact]]:
    results: Dict[str, List[MemoryFact]] = {
        "pinecone": [],
        "chromadb": [],
        "hindsight": [],
        "supabase": [],
    }

    try:
        results["hindsight"] = await _fetch_hindsight_async(query)
    except Exception as exc:
        logger.debug("[Coordinator] Hindsight async échec : %s", exc)

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            loop.run_in_executor(executor, _fetch_pinecone, query): "pinecone",
            loop.run_in_executor(executor, _fetch_chromadb, query): "chromadb",
            loop.run_in_executor(executor, _fetch_supabase, query): "supabase",
        }
        # On attend chaque future avec un timeout individuel
        for fut, src in futures.items():
            try:
                results[src] = await asyncio.wait_for(fut, timeout=FETCH_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("[Coordinator] %s timeout (%ss)", src, FETCH_TIMEOUT)
            except Exception as exc:
                logger.debug("[Coordinator] %s échec : %s", src, exc)

    return results


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZE
# ══════════════════════════════════════════════════════════════════════════════

_ENTITY_PATTERN = re.compile(
    r'\b([A-Z][a-zà-ÿ]{2,}(?:\s+[A-Z][a-zà-ÿ]{2,})?)\b'
)


def _extract_entities(text: str) -> List[str]:
    if not text:
        return []
    matches = _ENTITY_PATTERN.findall(text)
    stopwords = {"Le", "La", "Les", "Un", "Une", "Des", "Ce", "Cet", "Cette", "Extrait"}
    return [m for m in matches if m not in stopwords][:5]


def _normalize(facts: List[MemoryFact]) -> List[MemoryFact]:
    for fact in facts:
        if not fact.entities:
            fact.entities = _extract_entities(fact.text)
    return facts


# ══════════════════════════════════════════════════════════════════════════════
# DETECT CONFLICTS
# ══════════════════════════════════════════════════════════════════════════════

def _has_negation(text: str) -> bool:
    words = set(re.findall(r'\b\w+\b', text.lower()))
    return bool(words & NEGATION_WORDS)


def _similarity(text1: str, text2: str) -> float:
    def _significant_words(text: str) -> set:
        words = re.findall(r'\b[a-zà-ÿ]{5,}\b', text.lower())
        stops = {
            "cette", "celui", "celle", "ceux", "elles", "nous", "vous",
            "avec", "dans", "pour", "sans", "sous", "chez", "vers",
            "plus", "moins", "tres", "bien", "tout", "tous", "toutes",
            "faire", "peut", "doit", "voir", "donc", "ainsi", "aussi",
            "mais", "car", "quand", "comme", "alors", "aussi",
            "extrait", "source", "comparatif", "quatre",
        }
        return {w for w in words if w not in stops}

    w1 = _significant_words(text1)
    w2 = _significant_words(text2)

    common = w1 & w2
    if len(common) < MIN_COMMON_WORDS:
        return 0.0

    union = w1 | w2
    if not union:
        return 0.0
    return len(common) / len(union)


def detect_conflicts(facts: List[MemoryFact]) -> List[Conflict]:
    conflicts: List[Conflict] = []
    seen_pairs = set()

    for i, f1 in enumerate(facts):
        for j, f2 in enumerate(facts):
            if i >= j:
                continue
            pair = (i, j)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            len_ratio = min(len(f1.text), len(f2.text)) / max(len(f1.text), len(f2.text), 1)
            if len_ratio < MIN_LENGTH_RATIO:
                continue

            sim = _similarity(f1.text, f2.text)

            if sim > SIMILARITY_DUPLICATE_THRESHOLD:
                conflicts.append(Conflict(
                    entity=",".join(f1.entities[:2] or ["?"]),
                    facts=[f1, f2],
                    reason="duplicate",
                ))
                continue

            common_entities = set(f1.entities) & set(f2.entities)
            if common_entities and sim > SIMILARITY_CONTRADICTION_THRESHOLD:
                neg1 = _has_negation(f1.text)
                neg2 = _has_negation(f2.text)
                if neg1 != neg2:
                    conflicts.append(Conflict(
                        entity=list(common_entities)[0],
                        facts=[f1, f2],
                        reason="contradiction",
                    ))

    return conflicts


# ══════════════════════════════════════════════════════════════════════════════
# RESOLVE
# ══════════════════════════════════════════════════════════════════════════════

def resolve_conflict(conflict: Conflict) -> MemoryFact:
    facts = conflict.facts
    hindsight_facts = [f for f in facts if f.source == "hindsight"]
    if hindsight_facts:
        return max(hindsight_facts, key=lambda f: f.confidence)
    dated = [f for f in facts if f.timestamp]
    if dated:
        return min(dated, key=lambda f: f.age_seconds())
    return max(facts, key=lambda f: f.confidence)


def resolve_all_conflicts(
    facts: List[MemoryFact],
    conflicts: List[Conflict],
) -> List[MemoryFact]:
    to_remove = set()
    for conflict in conflicts:
        winner = resolve_conflict(conflict)
        for f in conflict.facts:
            if f is not winner:
                to_remove.add(id(f))
    result = [f for f in facts if id(f) not in to_remove]
    logger.info(
        "[Coordinator] %d conflits résolus, %d faits retenus sur %d",
        len(conflicts), len(result), len(facts),
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# FUSION (tri pertinence + limite)
# ══════════════════════════════════════════════════════════════════════════════

def _build_unified_context(facts: List[MemoryFact], max_chars: int = 2000) -> str:
    if not facts:
        return ""

    def _score_relevance(f: MemoryFact) -> float:
        score = f.confidence
        text_lower = f.text.lower()
        if any(k in text_lower for k in ["mohamed", "bek-v19", "prénom", "projet", "je m'appelle"]):
            score += 3.0
        if any(k in text_lower for k in ["http", "url :", "extrait :", "user-agent", "source "]):
            score -= 1.0
        return score

    facts_sorted = sorted(facts, key=_score_relevance, reverse=True)[:10]

    lines = []
    total = 0
    for fact in facts_sorted:
        source_tag = {
            "hindsight": "🧠",
            "pinecone": "📊",
            "chromadb": "💾",
            "supabase": "🗄️",
        }.get(fact.source, "•")

        line = f"{source_tag} [{fact.source}] {fact.text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE (v1.4 — async-safe)
# ══════════════════════════════════════════════════════════════════════════════

async def coordinate_memories_async(query: str, max_chars: int = 2000) -> UnifiedMemory:
    """
    Version ASYNC — utilisée par FastAPI / uvicorn.
    Ne crée JAMAIS de nouvelle boucle, s'intègre à celle qui existe.
    """
    t0 = time.monotonic()

    if not query or not query.strip():
        return UnifiedMemory("", [], [], [], 0.0)

    try:
        raw_by_source = await asyncio.wait_for(
            fetch_all_memories_async(query),
            timeout=FETCH_TIMEOUT + 5,  # marge de sécurité globale
        )
    except asyncio.TimeoutError:
        logger.warning("[Coordinator] ⏱️ Timeout global (%ss)", FETCH_TIMEOUT + 5)
        return UnifiedMemory("", [], [], [], (time.monotonic() - t0) * 1000)

    all_facts: List[MemoryFact] = []
    sources_used = []
    for source, facts in raw_by_source.items():
        if facts:
            all_facts.extend(facts)
            sources_used.append(source)

    logger.info(
        "[Coordinator] Fetch : %d faits (%s)",
        len(all_facts),
        ", ".join(f"{s}={len(f)}" for s, f in raw_by_source.items()),
    )

    if not all_facts:
        return UnifiedMemory("", [], [], [], (time.monotonic() - t0) * 1000)

    all_facts = _normalize(all_facts)

    conflicts = detect_conflicts(all_facts)
    if conflicts:
        logger.info(
            "[Coordinator] %d conflits détectés (raisons: %s)",
            len(conflicts),
            {c.reason for c in conflicts},
        )

    resolved_facts = resolve_all_conflicts(all_facts, conflicts)
    context = _build_unified_context(resolved_facts, max_chars=max_chars)

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "[Coordinator] Terminé en %.0fms | %d faits | %d conflits | sources=%s",
        elapsed_ms, len(resolved_facts), len(conflicts), sources_used,
    )

    return UnifiedMemory(
        context=context,
        facts=resolved_facts,
        conflicts=conflicts,
        sources_used=sources_used,
        elapsed_ms=elapsed_ms,
    )


def coordinate_memories(query: str, max_chars: int = 2000) -> UnifiedMemory:
    """
    Version SYNC — pour scripts standalone.
    Détecte la présence d'une boucle et s'y adapte.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Aucune boucle active → on peut en créer une
        return asyncio.run(coordinate_memories_async(query, max_chars))

    # Une boucle tourne déjà → on utilise un thread séparé
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            lambda: asyncio.run(coordinate_memories_async(query, max_chars))
        )
        try:
            return future.result(timeout=FETCH_TIMEOUT + 10)
        except concurrent.futures.TimeoutError:
            logger.warning("[Coordinator] Timeout en mode sync-threaded")
            return UnifiedMemory("", [], [], [], 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# TEST DIRECT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    print("\n=== TEST Coordinator v1.4 ===\n")
    result = coordinate_memories("Qui est Eddy ?")
    print(f"Sources : {result.sources_used}")
    print(f"Faits : {len(result.facts)}")
    print(f"Conflits : {len(result.conflicts)}")
    print(f"Temps : {result.elapsed_ms:.0f}ms")
    print(f"\nContexte :\n{result.context[:500]}")
    print("\n✅ Tests terminés.\n")