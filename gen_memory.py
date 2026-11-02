# -*- coding: utf-8 -*-
"""Genere docs/MEMORY_ARCHITECTURE.md"""
from pathlib import Path

DOCS = Path(__file__).resolve().parent / "docs"
DOCS.mkdir(exist_ok=True)

CONTENU = "# 🧠 ARCHITECTURE MÉMOIRE BEK-v18\n\n"
CONTENU += "## 📊 VUE D'ENSEMBLE\n\n"
CONTENU += "4 couches mémoire :\n\n"
CONTENU += "| # | Couche | Type | Rôle |\n"
CONTENU += "|---|---|---|---|\n"
CONTENU += "| 1 | Pinecone | Cloud vectoriel | Mémoire sémantique |\n"
CONTENU += "| 2 | ChromaDB | Local vectoriel | Fallback local |\n"
CONTENU += "| 3 | Supabase | Cloud PostgreSQL | États, CRM |\n"
CONTENU += "| 4 | Hindsight | Cloud structuré | Entités, relations |\n\n"
CONTENU += "Le Memory Coordinator orchestre les 4 couches et détecte les conflits.\n\n"

CONTENU += "## 1. PINECONE\n\n"
CONTENU += "Fichier : memory.py\n"
CONTENU += "- Stocke vecteurs NVIDIA 1024 dims\n"
CONTENU += "- Index : bek-memory-v2\n"
CONTENU += "- API : search_memory(), save_to_memory()\n\n"

CONTENU += "## 2. CHROMADB\n\n"
CONTENU += "Fichier : memory.py\n"
CONTENU += "- Fallback local (chroma_db/)\n"
CONTENU += "- Collection : bek_memory_local\n"
CONTENU += "- Distance : cosine\n\n"

CONTENU += "## 3. SUPABASE\n\n"
CONTENU += "Tables : sync_log, bek_task_states, matrix_sub_crms, companies, contacts\n\n"

CONTENU += "## 4. HINDSIGHT\n\n"
CONTENU += "Fichier : hindsight_memory.py\n"
CONTENU += "- retain(content) : stocke un fait\n"
CONTENU += "- recall(query) : rappelle\n"
CONTENU += "- reflect(query) : synthèse\n"
CONTENU += "- status() : état\n"
CONTENU += "- close() : ferme\n\n"

CONTENU += "## MEMORY COORDINATOR\n\n"
CONTENU += "Fichier : memory_coordinator.py\n"
CONTENU += "Fonction : coordinate_memories_async(query)\n\n"
CONTENU += "Règles de priorité :\n"
CONTENU += "1. Hindsight gagne\n"
CONTENU += "2. Plus récent gagne\n"
CONTENU += "3. Confidence élevée gagne\n\n"
CONTENU += "Poids : hindsight=1.0, pinecone=0.7, chromadb=0.5, supabase=0.9\n\n"

CONTENU += "## RÉFÉRENCES\n\n"
CONTENU += "- memory.py\n"
CONTENU += "- hindsight_memory.py\n"
CONTENU += "- memory_coordinator.py\n"
CONTENU += "- feedback_memory.py\n"
CONTENU += "- docs/FEEDBACK_SYSTEM.md\n\n"

CONTENU += "---\n\nVersion : 1.0\nDate : 2026-09-29\nAuteur : BEK Project\n"

target = DOCS / "MEMORY_ARCHITECTURE.md"
target.write_text(CONTENU, encoding="utf-8")
print(f"OK : {target} ({len(CONTENU)} chars)")