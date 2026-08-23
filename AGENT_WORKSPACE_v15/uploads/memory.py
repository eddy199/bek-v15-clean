import os
import json
import hashlib
import time
import threading
from datetime import datetime
from pathlib import Path
import requests

from config import (
    SESSIONS_DIR, SKILLS_DIR, L2_PATH, CHROMA_DIR,
    PINECONE_API_KEY, PINECONE_INDEX_NAME, logger, MODELS
)

# ─── ChromaDB (local, optionnel) ─────────────────────────────────
chroma_collection = None
_chroma_available = False

try:
    import chromadb
    from chromadb.config import Settings
    chroma_client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )
    chroma_collection = chroma_client.get_or_create_collection(
        name="agent_l4_memory",
        metadata={"hnsw:space": "cosine"}
    )
    _chroma_available = True
    logger.info("[OK] ChromaDB initialisé.")
except Exception as e:
    logger.warning(f"ChromaDB indisponible: {e}")
    chroma_collection = None

# ─── Pinecone ────────────────────────────────────────────────────
pinecone_index = None
_pinecone_available = False

try:
    if PINECONE_API_KEY:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        pinecone_index = pc.Index(PINECONE_INDEX_NAME)
        _pinecone_available = True
        logger.info("[OK] Pinecone connecté.")
except Exception as e:
    logger.warning(f"Pinecone indisponible: {e}")
    pinecone_index = None

# ─── Sessions ────────────────────────────────────────────────────
_sessions_cache = {}
_sessions_lock = threading.Lock()

def get_session_id(flask_session=None):
    import secrets
    sid = secrets.token_hex(8)
    if flask_session and 'session_id' in flask_session:
        sid = flask_session['session_id']
    return sid

def load_session(sid):
    if sid in _sessions_cache:
        return _sessions_cache[sid]
    sp = SESSIONS_DIR / f"{sid}.json"
    if sp.exists():
        try:
            with open(sp, "r", encoding="utf-8") as f:
                data = json.load(f)
                _sessions_cache[sid] = data
                return data
        except Exception as e:
            logger.error(f"Erreur chargement session {sid}: {e}")
    _sessions_cache[sid] = {
        "created_at": datetime.now().isoformat(),
        "messages": [],
        "title": "Nouvelle conversation",
        "message_count": 0
    }
    return _sessions_cache[sid]

def save_session(sid, data):
    with _sessions_lock:
        try:
            with open(SESSIONS_DIR / f"{sid}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _sessions_cache[sid] = data
        except Exception as e:
            logger.error(f"Erreur sauvegarde session {sid}: {e}")

def append_message(sid, role, content):
    sess = load_session(sid)
    sess["messages"].append({"role": role, "content": content})
    sess["message_count"] = len(sess["messages"])
    if role == "user" and sess["message_count"] <= 2:
        sess["title"] = content[:50] + "..." if len(content) > 50 else content
    save_session(sid, sess)

def list_sessions():
    sessions = []
    for fp in SESSIONS_DIR.glob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append({
                "id": fp.stem,
                "title": data.get("title", "Nouvelle conversation"),
                "created_at": data.get("created_at", ""),
                "message_count": data.get("message_count", 0),
            })
        except Exception:
            pass
    return sorted(sessions, key=lambda s: s["created_at"], reverse=True)

# ─── L2 (Mémoire disque) ─────────────────────────────────────────
def l2_load():
    if not L2_PATH.exists():
        return {"sessions": [], "skills_created": [], "faits": []}
    try:
        with open(L2_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"sessions": [], "skills_created": [], "faits": []}

def l2_save(d):
    try:
        with open(L2_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"L2 save fail: {e}")

def l2_log(text):
    d = l2_load()
    d["faits"].append({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "txt": text})
    d["faits"] = d["faits"][-1000:]
    l2_save(d)

def l2_skill_created(name):
    d = l2_load()
    d["skills_created"].append({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "skill": name})
    l2_save(d)

# ─── Embeddings via NVIDIA (avec fallback local robuste) ─────────
EMBEDDING_DIMENSION = 1024
_embedding_cache = {}
_embedding_cache_lock = threading.Lock()
_MAX_CACHE_SIZE = 200

def _make_local_embedding(text):
    """Fallback 100% offline — génère un vecteur déterministe depuis le hash du texte."""
    h = hashlib.sha256(text.encode()).digest()
    vec = [float(b) / 255.0 for b in h]
    while len(vec) < EMBEDDING_DIMENSION:
        vec.extend(vec)
    return vec[:EMBEDDING_DIMENSION]

def get_embedding(text, input_type="query"):
    """Génère un vecteur d'embedding via l'API NVIDIA ou fallback local. Cache LRU intégré."""
    cache_key = hashlib.md5(f"{text}:{input_type}".encode()).hexdigest()
    with _embedding_cache_lock:
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

    nv = MODELS.get("nvidia")
    if nv and nv.get("key"):
        try:
            url = nv["base_url"].rstrip("/") + "/embeddings"
            headers = {
                "Authorization": f"Bearer {nv['key']}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": text[:8000],
                "model": "nvidia/nv-embedqa-e5-v5",
                "encoding_format": "float",
                "input_type": input_type,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=8)
            if res.status_code == 200:
                vec = res.json()["data"][0]["embedding"]
                with _embedding_cache_lock:
                    if len(_embedding_cache) >= _MAX_CACHE_SIZE:
                        oldest = next(iter(_embedding_cache))
                        del _embedding_cache[oldest]
                    _embedding_cache[cache_key] = vec
                return vec
            logger.warning(f"Embedding API: HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"Embedding API échec, fallback local: {e}")

    vec = _make_local_embedding(text)
    with _embedding_cache_lock:
        if len(_embedding_cache) >= _MAX_CACHE_SIZE:
            oldest = next(iter(_embedding_cache))
            del _embedding_cache[oldest]
        _embedding_cache[cache_key] = vec
    return vec

# ─── L4 (Mémoire vectorielle) ────────────────────────────────────

def l4_insert(text, tags=None):
    if not text or not text.strip():
        return
    doc_id = hashlib.md5(f"{text}{time.time_ns()}".encode()).hexdigest()[:16]

    # Chroma — avec try/except isolé pour ne pas bloquer Pinecone
    if _chroma_available and chroma_collection:
        try:
            chroma_collection.add(
                documents=[text],
                metadatas=[{"tags": ",".join(tags or []), "ts": datetime.now().isoformat()}],
                ids=[doc_id]
            )
        except Exception as e:
            logger.error(f"Chroma insert fail: {e}")

    # Pinecone — avec try/except isolé
    if _pinecone_available and pinecone_index:
        try:
            vector = get_embedding(text, input_type="passage")
            pinecone_index.upsert(vectors=[{
                "id": doc_id,
                "values": vector,
                "metadata": {
                    "text": text,
                    "tags": ",".join(tags or []),
                    "ts": datetime.now().isoformat()
                }
            }])
            logger.info(f"Insert Pinecone réussi pour doc_id: {doc_id}")
        except Exception as e:
            logger.error(f"Pinecone insert fail: {e}")

    l2_log(f"[Mémoire] {text[:80]}")


def l4_search(query, top=3):
    results = []

    # Chroma — avec try/except isolé
    if _chroma_available and chroma_collection:
        try:
            res = chroma_collection.query(
                query_texts=[query],
                n_results=top,
                include=["documents", "metadatas", "distances"]
            )
            if res and res.get("documents"):
                for i, doc in enumerate(res["documents"][0]):
                    meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                    dist = res["distances"][0][i] if res.get("distances") else 0
                    results.append({
                        "text": doc,
                        "source": "chroma",
                        "tags": meta.get("tags", ""),
                        "score": round(1 - min(dist, 1.0), 3)
                    })
        except Exception as e:
            logger.error(f"Chroma search fail: {e}")

    # Pinecone — avec try/except isolé
    if _pinecone_available and pinecone_index:
        try:
            vector = get_embedding(query, input_type="query")
            res = pinecone_index.query(vector=vector, top_k=top, include_metadata=True)
            for m in (res.get("matches") or []):
                meta = m.get("metadata") or {}
                results.append({
                    "text": meta.get("text", ""),
                    "source": "pinecone",
                    "tags": meta.get("tags", ""),
                    "score": round(m.get("score", 0), 3)
                })
        except Exception as e:
            logger.error(f"Pinecone search fail: {e}")

    # Dédoublonnage
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x.get("score", 0), reverse=True):
        key = r.get("text", "")[:100]
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:top]


def add_memory(text, tags=None):
    l4_insert(text, tags)
    return {"ok": True}


def search_memory(query, top=3):
    return l4_search(query, top=top)


def memory_stats():
    stats = {
        "chroma": _chroma_available,
        "pinecone": _pinecone_available
    }
    if _pinecone_available and pinecone_index:
        try:
            stats["dimension"] = pinecone_index.describe_index_stats().get("dimension")
        except Exception:
            pass
    return stats


# ─── Skills (validation) ─────────────────────────────────────────
from jsonschema import validate, ValidationError

SKILL_SCHEMA = {
    "type": "object",
    "required": ["name", "command"],
    "additionalProperties": True,
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "code": {"type": "string"},
        "command": {"type": "string"},
        "category": {"type": "string"},
        "tags": {"type": "array"},
        "version": {"type": "string"}
    }
}

def validate_skill(data):
    try:
        validate(instance=data, schema=SKILL_SCHEMA)
        return True
    except ValidationError as e:
        logger.error(f"Skill invalide: {e.message}")
        return False

def read_skill_content(name):
    for p in [SKILLS_DIR / f"{name}.json", SKILLS_DIR / name / "SKILL.md"]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if validate_skill(data):
                        return data
            except:
                pass
    return {"error": f"Skill '{name}' introuvable ou invalide"}
