# 🚀 BEK-v15 Hybrid — Documentation & Architecture Globale

Référentiel technique et architectural complet de l'agent autonome multi-modèles **BEK-v15 Hybrid**, déployé en environnement de production cloud sur **Render**, avec mémoire hybride **Neon DB / Pinecone**, passerelle multi-fournisseurs (**NVIDIA NIM, Groq, OpenRouter, Gemini**), et maintien en éveil via **UptimeRobot**.

---

## 🏛️ 1. Diagramme d'Architecture Globale (Flux & Composants)

```
====================================================================================================
                                      UTILISATEUR & CLIENTS
                          [ Interface Web BEK-v15 Hybrid / API Clients ]
====================================================================================================
                                            │
                                            │ HTTPS / WSS / SSE (Port 443)
                                            ▼
+──────────────────────────+    +──────────────────────────────────────────────────────────────────+
|       UPTIMEROBOT        |───>|                     RENDER CLOUD PLATFORM                        |
|  (Keep-Alive 24h/24)     |    |              [ Reverse Proxy SSL & Ingress Router ]              |
|  Ping GET /api/connectors|    +─────────────────────────────────┬────────────────────────────────+
|  (Intervalle: 5 min)     |                                      │
+──────────────────────────+                                      │ Port 10000 (Internal)
                                                                  ▼
                                +──────────────────────────────────────────────────────────────────+
                                |                    SERVEUR D'APPLICATION WSGI                    |
                                |         Gunicorn 26.2.0 (2 Sync Workers --timeout 120)           |
                                +─────────────────────────────────┬────────────────────────────────+
                                                                  │
                                                                  ▼
                                +──────────────────────────────────────────────────────────────────+
                                |                      FLASK CORE APPLICATION                      |
                                |                             (app.py)                             |
                                +───┬─────────────────────────────┬────────────────────────────┬───+
                                    │                             │                            │
         ┌──────────────────────────┘                             │                            └──────────────────────────┐
         ▼                                                        ▼                                                       ▼
+─────────────────────────────────+             +──────────────────────────────────+            +─────────────────────────────────+
|     HERMES SECURITY ENGINE      |             |       AI INFERENCE ROUTER        |            |      HYBRID MEMORY ENGINE       |
+─────────────────────────────────+             +──────────────────────────────────+            +─────────────────────────────────+
| • BEK_HSM_SECRET (Hardware Sec) |             | • Primary: NVIDIA NIM            |            | • Neon PostgreSQL (Serverless)  |
| • BetterAuth / OAuth Validation |             |   - meta/llama-3.3-70b-instruct  |            |   - sync_log, state_entries     |
| • FLASK_SECRET_KEY Session Guard|             |   - meta/llama-3.2-11b-vision    |            |   - transactions & compensations|
| • CORS Origin & Token Guard     |             | • Fallbacks:                     |            | • Pinecone Vector Store         |
| • Sandboxed Execution Guard     |             |   - Groq (Mixtral / Llama ultra) |            |   - Index: bek-memory-v2        |
+────────────────┬────────────────+             |   - OpenRouter (Alpha 0x)        |            |   - Model: llama-text-embed-v2  |
                 │                              |   - Google Gemini API            |            |   - Metric: Cosine (1024 dim)   |
                 │                              +────────────────┬─────────────────+            +────────────────┬────────────────+
                 │                                               │                                               │
                 └───────────────────────────────────────────────┼───────────────────────────────────────────────┘
                                                                 │
                                                                 ▼
                                +──────────────────────────────────────────────────────────────────+
                                |                  SKILLS & PLUGINS ECOSYSTEM                      |
                                +──────────────────────────────────────────────────────────────────+
                                | • skills/rag_ia_ingenerie_archit.json (Ingénierie & Design)      |
                                | • plugins/ & tools/ (Web Sync, File Gen, Fast Math, Code Exec)   |
                                | • Context Loader, Swarm Core & Multi-Agent Dispatcher            |
                                +──────────────────────────────────────────────────────────────────+
```

---

## 📊 2. Référentiel Technique Détaillé des Composants

| Bloc Architectural | Composant / Service | Rôle & Responsabilité | Protocole / Port | Endpoint / Target |
| :--- | :--- | :--- | :--- | :--- |
| **Ingress & Routing** | Render Web Service | Point d'entrée sécurisé, terminaison SSL/TLS | HTTPS (443) | `https://bek-v15-clean.onrender.com` |
| **Supervision 24/7** | UptimeRobot Monitor | Maintien en éveil continu (anti-spin down de 15 min) | HTTP GET (5 min) | `GET /api/connectors` |
| **Runtime WSGI** | Gunicorn 26.2.0 | Gestion des processus applicatifs et concurrence | HTTP (10000) | `gunicorn app:app --workers 2 --timeout 120` |
| **Framework Backend** | Flask (Python 3.11+) | Orchestration, routes REST, streaming SSE | Interne | `app.py`, `meta_cortex_sse_ui.py` |
| **Base Relationnelle** | Neon DB (PostgreSQL) | Persistance des états, sessions et tables de compensation | PostgreSQL Wire | `DATABASE_URL?sslmode=require` |
| **Index Vectoriel** | Pinecone Serverless | Mémoire sémantique à long terme et pipeline RAG | HTTPS API | Index: `bek-memory-v2` |
| **Moteur IA Principal** | NVIDIA NIM API | Modèle central de raisonnement et de génération | REST API | `meta/llama-3.3-70b-instruct` |
| **Moteurs Secours** | Groq / OpenRouter / Gemini | Fournisseurs secondaires à basculement automatique | REST API | `GROQ_API_KEY`, `GEMINI_API_KEY`, etc. |
| **Sécurité & Auth** | Hermes & BetterAuth | Chiffrement HSM, validation des jetons et CORS | Interne | `BEK_HSM_SECRET`, `FLASK_SECRET_KEY` |
| **Base de Compétences**| RAG Knowledge Engine | Base de règles et compétences d'architecture logicielle| JSON / Vectoriel | `skills/rag_ia_ingenerie_archit.json` |

---

## 🔄 3. Cycle de Vie d'une Requête (Pipeline RAG & Inférence)

1. **Réception & Filtrage :** Le client envoie une invite via l'interface `BEK-v15 Hybrid` vers `/api/chat`.
2. **Contrôle Sécurité :** Le middleware `Hermes Security` valide les sessions, jetons et origines autorisées.
3. **Récupération Contexte & Mémoire (RAG) :**
   * Recherche de similarité vectorielle dans **Pinecone (`bek-memory-v2`)**.
   * Extraction de l'état système et de l'historique transactionnel dans **Neon DB**.
   * Injection des modules de compétences actifs (`skills/rag_ia_ingenerie_archit.json`).
4. **Routage & Inférence :** L'invite enrichie est transmise au fournisseur d'inférence prioritaire (**NVIDIA NIM - Llama 3.3 70B**).
5. **Streaming & Sauvegarde :** La réponse est diffusée en direct par SSE (*Server-Sent Events*) à l'utilisateur, puis l'échange est persisté simultanément dans Neon DB et Pinecone.

---

## 🔐 4. Matrice des Variables d'Environnement (Render)

```env
# ── BASE DE DONNÉES & MÉMOIRE HYBRIDE
DATABASE_URL=postgresql://<user>:<password>@<host>.neon.tech/neondb?sslmode=require
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=bek-memory-v2

# ── FOURNISSEURS DE MODÈLES D'IA (LLMs)
NVIDIA_API_KEY=nvapi-...
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=Sk-or-v1-...
GEMINI_API_KEY=AQ....

# ── SÉCURITÉ, AUTHENTIFICATION & SESSIONS
FLASK_SECRET_KEY=<secret_hash_64>
BEK_HSM_SECRET=<secret_hash_64>
BETTER_AUTH_SECRET=<secret_hash_64>
AUTH_BYPASS=true
ALLOWED_SIGN_IN=admin@local.host

# ── INTÉGRATIONS CLOUD & CONTRÔLE DE VERSION
GITHUB_USERNAME=eddy199
GITHUB_TOKEN=ghp_...
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_SUBDOMAIN=...
```

---

## 🛠️ 5. Endpoints de Diagnostic et Supervision

* **`GET /api/connectors`** : Rapport de santé en temps réel de PostgreSQL Neon, Pinecone et des LLMs.
* **`GET /api/memory`** : Diagnostic complet des tables relationnelles et des vecteurs mémoire.
* **`POST /api/chat`** : Point d'entrée de dialogue avec streaming SSE et exécution d'outils.
