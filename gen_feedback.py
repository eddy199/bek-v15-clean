# -*- coding: utf-8 -*-
"""Genere docs/FEEDBACK_SYSTEM.md"""
from pathlib import Path

DOCS = Path(__file__).resolve().parent / "docs"
DOCS.mkdir(exist_ok=True)

C = "# 🎓 SYSTÈME DE FEEDBACK UTILISATEUR BEK-v18\n\n"
C += "> L'utilisateur peut corriger l'agent, la correction est mémorisée\n"
C += "> dans Hindsight pour être appliquée automatiquement.\n\n"

C += "## 🎯 OBJECTIF\n\n"
C += "Scénario type :\n"
C += "1. Utilisateur : Quelle est ma couleur préférée ?\n"
C += "2. Agent (faux) : Rouge.\n"
C += "3. Utilisateur (feedback) : Non, c'est Bleu.\n"
C += "4. Hindsight stocke : CORRECTION : couleur préférée = Bleu.\n"
C += "5. Prochaine fois : agent répond Bleu.\n\n"

C += "## 🏗️ ARCHITECTURE\n\n"
C += "    Utilisateur (POST /api/feedback)\n"
C += "        ↓\n"
C += "    app.py — api_submit_feedback()\n"
C += "        ↓\n"
C += "    feedback_memory.py — submit_feedback_async()\n"
C += "        1. Écrit dans data/feedback_log.jsonl\n"
C += "        2. Subprocess isolé → Hindsight\n"
C += "        3. Si échec → data/pending_feedback.jsonl\n"
C += "        ↓\n"
C += "    HINDSIGHT (cloud structuré)\n\n"

C += "## 📁 FICHIERS\n\n"
C += "| Fichier | Rôle |\n"
C += "|---|---|\n"
C += "| feedback_memory.py | Coeur du système |\n"
C += "| app.py | Routes /api/feedback |\n"
C += "| data/feedback_log.jsonl | Journal permanent |\n"
C += "| data/pending_feedback.jsonl | Pending |\n\n"

C += "## 🔌 API PUBLIQUE\n\n"
C += "### submit_feedback() — sync\n\n"
C += "```python\n"
C += "from feedback_memory import submit_feedback\n"
C += "result = submit_feedback(\n"
C += "    user_query='Quelle est ma couleur ?',\n"
C += "    agent_response='Rouge',\n"
C += "    correction='Bleu',\n"
C += ")\n"
C += "```\n\n"

C += "### submit_feedback_async() — async\n\n"
C += "```python\n"
C += "from feedback_memory import submit_feedback_async\n"
C += "result = await submit_feedback_async(...)\n"
C += "```\n\n"

C += "### process_pending_feedbacks()\n\n"
C += "```python\n"
C += "from feedback_memory import process_pending_feedbacks\n"
C += "n = process_pending_feedbacks()\n"
C += "```\n\n"

C += "### list_feedbacks() / feedback_stats()\n\n"
C += "```python\n"
C += "from feedback_memory import list_feedbacks, feedback_stats\n"
C += "feedbacks = list_feedbacks(limit=50)\n"
C += "stats = feedback_stats()\n"
C += "```\n\n"

C += "## 🌐 ROUTES API\n\n"
C += "### POST /api/feedback\n\n"
C += "Body JSON :\n\n"
C += "```json\n"
C += '{\n'
C += '  "user_query": "...",\n'
C += '  "agent_response": "...",\n'
C += '  "correction": "...",\n'
C += '  "feedback_type": "correction",\n'
C += '  "rating": null\n'
C += '}\n'
C += "```\n\n"

C += "Réponse :\n\n"
C += "```json\n"
C += '{\n'
C += '  "status": "ok",\n'
C += '  "feedback_id": "fb_...",\n'
C += '  "stored_in_hindsight": true,\n'
C += '  "pending_retry": false,\n'
C += '  "timestamp": "..."\n'
C += '}\n'
C += "```\n\n"

C += "### GET /api/feedback\n\n"
C += "Liste les feedbacks + stats.\n\n"

C += "## ⚠️ LIMITATIONS\n\n"
C += "1. Bug Hindsight aretain() — contourné par subprocess isolé\n"
C += "2. Windows subprocess — fonction au niveau module obligatoire\n"
C += "3. Render Free — subprocess peut échouer, tout passe en pending\n"
C += "4. Warning Unclosed client session — cosmétique\n\n"

C += "## 🎯 ROADMAP\n\n"
C += "Court terme : bouton UI, interface admin, DELETE endpoint\n"
C += "Moyen terme : rating automatique, détection contradictions\n"
C += "Long terme : fine-tuning, curriculum learning\n\n"

C += "## 📚 RÉFÉRENCES\n\n"
C += "- feedback_memory.py\n"
C += "- hindsight_memory.py\n"
C += "- memory_coordinator.py\n"
C += "- docs/MEMORY_ARCHITECTURE.md\n\n"

C += "---\n\nVersion : 1.0\nDate : 2026-09-29\nAuteur : BEK Project\n"

target = DOCS / "FEEDBACK_SYSTEM.md"
target.write_text(C, encoding="utf-8")
print(f"OK : {target} ({len(C)} chars)")