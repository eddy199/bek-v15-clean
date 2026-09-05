
# CONTEXTE PERMANENT DU PROJET BEK-v15 & CRM

## 1. Stack & Environnement
- OS : Linux Q4OS / Debian sur machine Acer
- Workspace principal : /media/moh/84B00E0BB00E0500/workspacekimi
- Répertoire CRM : /media/moh/84B00E0BB00E0500/crm-release
- Python Virtualenv : /home/moh/.venvs/kimi/bin/python3
- Base de données : Neon PostgreSQL (cloud) synchronisée via Bun & Prisma (`packages/db`)

## 2. Providers & Modèles Actifs
- NVIDIA API : Modèle principal `nvidia/llama-3.3-nemotron-super-49b-v1` et Vision `meta/llama-3.2-11b-vision-instruct`
- Groq API : Modèle rapide `llama-3.3-70b-versatile`
- OpenRouter & TokenRouter : Désactivés

## 3. Architecture Comp AI CRM (trycompai/crm)
- Framework d'agents persistants Vercel Eve avec 18 outils natifs et 4 skills Markdown.
- File d'attente PostgreSQL (`lib/tasks.ts`) avec `FOR UPDATE SKIP LOCKED`.
- Dispatcher connecté à l'agent BEK-v15 sur `http://127.0.0.1:8765`.
