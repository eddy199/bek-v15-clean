# 🎓 SYSTÈME DE FEEDBACK UTILISATEUR BEK-v18

> L'utilisateur peut corriger l'agent, la correction est mémorisée
> dans Hindsight pour être appliquée automatiquement.

## 🎯 OBJECTIF

Scénario type :
1. Utilisateur : Quelle est ma couleur préférée ?
2. Agent (faux) : Rouge.
3. Utilisateur (feedback) : Non, c'est Bleu.
4. Hindsight stocke : CORRECTION : couleur préférée = Bleu.
5. Prochaine fois : agent répond Bleu.

## 🏗️ ARCHITECTURE

    Utilisateur (POST /api/feedback)
        ↓
    app.py — api_submit_feedback()
        ↓
    feedback_memory.py — submit_feedback_async()
        1. Écrit dans data/feedback_log.jsonl
        2. Subprocess isolé → Hindsight
        3. Si échec → data/pending_feedback.jsonl
        ↓
    HINDSIGHT (cloud structuré)

## 📁 FICHIERS

| Fichier | Rôle |
|---|---|
| feedback_memory.py | Coeur du système |
| app.py | Routes /api/feedback |
| data/feedback_log.jsonl | Journal permanent |
| data/pending_feedback.jsonl | Pending |

## 🔌 API PUBLIQUE

### submit_feedback() — sync

```python
from feedback_memory import submit_feedback
result = submit_feedback(
    user_query='Quelle est ma couleur ?',
    agent_response='Rouge',
    correction='Bleu',
)
```

### submit_feedback_async() — async

```python
from feedback_memory import submit_feedback_async
result = await submit_feedback_async(...)
```

### process_pending_feedbacks()

```python
from feedback_memory import process_pending_feedbacks
n = process_pending_feedbacks()
```

### list_feedbacks() / feedback_stats()

```python
from feedback_memory import list_feedbacks, feedback_stats
feedbacks = list_feedbacks(limit=50)
stats = feedback_stats()
```

## 🌐 ROUTES API

### POST /api/feedback

Body JSON :

```json
{
  "user_query": "...",
  "agent_response": "...",
  "correction": "...",
  "feedback_type": "correction",
  "rating": null
}
```

Réponse :

```json
{
  "status": "ok",
  "feedback_id": "fb_...",
  "stored_in_hindsight": true,
  "pending_retry": false,
  "timestamp": "..."
}
```

### GET /api/feedback

Liste les feedbacks + stats.

## ⚠️ LIMITATIONS

1. Bug Hindsight aretain() — contourné par subprocess isolé
2. Windows subprocess — fonction au niveau module obligatoire
3. Render Free — subprocess peut échouer, tout passe en pending
4. Warning Unclosed client session — cosmétique

## 🎯 ROADMAP

Court terme : bouton UI, interface admin, DELETE endpoint
Moyen terme : rating automatique, détection contradictions
Long terme : fine-tuning, curriculum learning

## 📚 RÉFÉRENCES

- feedback_memory.py
- hindsight_memory.py
- memory_coordinator.py
- docs/MEMORY_ARCHITECTURE.md

---

Version : 1.0
Date : 2026-09-29
Auteur : BEK Project
