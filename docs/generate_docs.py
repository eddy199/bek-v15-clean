# -*- coding: utf-8 -*-
"""
Générateur de documentation BEK-v18.
Crée les fichiers docs/MEMORY_ARCHITECTURE.md, docs/FEEDBACK_SYSTEM.md, docs/BEK_CPU.md
"""
from pathlib import Path

DOCS = Path(__file__).resolve().parent / "docs"
DOCS.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# FICHIER 1 — MEMORY_ARCHITECTURE.md
# ═══════════════════════════════════════════════════════════════════════════

MEMORY_ARCH = """# 🧠 ARCHITECTURE MÉMOIRE BEK-v18

> Ce document décrit les 4 couches mémoire de l'agent BEK et leur
> coordination via le Memory Coordinator.

## 📊 VUE D'ENSEMBLE

L'agent BEK dispose de 4 couches mémoire distinctes, chacune avec son rôle :

| # | Couche | Type | Rôle | Localisation |
|---|---|---|---|---|
| 1 | Pinecone | Cloud vectoriel | Mémoire sémantique principale | SaaS (US) |
| 2 | ChromaDB | Local vectoriel | Fallback local + cache offline | chroma_db/ |
| 3 | Supabase | Cloud PostgreSQL | États, CRM, transactions | SaaS (EU) |
| 4 | Hindsight | Cloud structuré | Entités, relations, causalité | SaaS (US) |

Le Memory Coordinator orchestre les 4 couches, détecte les conflits et
produit un contexte unifié pour le LLM.

Schéma :

    UTILISATEUR
        ↓
    routers/chat.py
        ↓ coordinate_memories_async()
    MEMORY COORDINATOR
        ├── Pinecone   (cloud vectoriel)
        ├── ChromaDB   (local vectoriel)
        ├── Hindsight  (structuré)
        └── Supabase   (relationnel)
        ↓
    Normalize → Detect Conflicts → Resolve → Fusion
        ↓
    [MÉMOIRE UNIFIÉE] → prompt système
        ↓
    LLM → Réponse ancrée
        ↓
    FINALLY : HINDSIGHT retain

## 1️⃣ PINECONE — MÉMOIRE VECTORIELLE CLOUD

Fichier : memory.py (fonctions search_memory, save_to_memory)

### Rôle
- Stocke des vecteurs (embeddings NVIDIA 1024 dims)
- Recherche par similarité sémantique
- Accessible depuis local ET Render

### Structure

    Index : bek-memory-v2
    Vector : 1024 dims (tronqué depuis NVIDIA 2048 dims)
    Metadata :
      - text : texte original
      - date : timestamp ISO
      - type : "conversation"

### API

```python
from memory import search_memory, save_to_memory

ctx = search_memory("Quelle est ma couleur ?", top_k=3)
save_to_memory(user_query, agent_response)