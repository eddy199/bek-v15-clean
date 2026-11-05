# 🧠 ARCHITECTURE MÉMOIRE BEK-v18

## 📊 VUE D'ENSEMBLE

4 couches mémoire :

| # | Couche | Type | Rôle |
|---|---|---|---|
| 1 | Pinecone | Cloud vectoriel | Mémoire sémantique |
| 2 | ChromaDB | Local vectoriel | Fallback local |
| 3 | Supabase | Cloud PostgreSQL | États, CRM |
| 4 | Hindsight | Cloud structuré | Entités, relations |

Le Memory Coordinator orchestre les 4 couches et détecte les conflits.

## 1. PINECONE

Fichier : memory.py
- Stocke vecteurs NVIDIA 1024 dims
- Index : bek-memory-v2
- API : search_memory(), save_to_memory()

## 2. CHROMADB

Fichier : memory.py
- Fallback local (chroma_db/)
- Collection : bek_memory_local
- Distance : cosine

## 3. SUPABASE

Tables : sync_log, bek_task_states, matrix_sub_crms, companies, contacts

## 4. HINDSIGHT

Fichier : hindsight_memory.py
- retain(content) : stocke un fait
- recall(query) : rappelle
- reflect(query) : synthèse
- status() : état
- close() : ferme

## MEMORY COORDINATOR

Fichier : memory_coordinator.py
Fonction : coordinate_memories_async(query)

Règles de priorité :
1. Hindsight gagne
2. Plus récent gagne
3. Confidence élevée gagne

Poids : hindsight=1.0, pinecone=0.7, chromadb=0.5, supabase=0.9

## RÉFÉRENCES

- memory.py
- hindsight_memory.py
- memory_coordinator.py
- feedback_memory.py
- docs/FEEDBACK_SYSTEM.md

---

Version : 1.0
Date : 2026-09-29
Auteur : BEK Project
