# 🧬 Architecture Cible — BEK v16 « Hybrid Standard »
> *Générée le 2026-09-10 — basée sur BEK v15.3 Hybrid. Principe fondateur : ZÉRO RÉGRESSION.*

---

## 0. Principes directeurs

1. **L'ADN ne bouge pas** — Hermes Core V3, GOAP Planner, SecurityGuard (HMAC, L1→L5), protocole HITL `[ACTION:]`, mémoire hybride triple-ancrage, fallback multi-provider : tous conservés à l'identique fonctionnel.
2. **La plomberie est réparée** — sécurité fichiers (anti path-traversal), authentification JWT, rate limiting. Ce sont des fuites à boucher, pas des changements d'architecture.
3. **Les portes standard s'ouvrent** — MCP réel, function calling natif, OpenTelemetry. Le monde vient se brancher chez vous ; votre architecture reste chez vous.
4. **Chaque phase est livrable seule** — rollback possible à tout moment, ancien code conservé tant que le nouveau n'est pas validé.

---

## 1. Vue d'ensemble

```text
                        ┌────────────────────────────┐
                        │   WEB / MOBILE / MCP       │
                        │  Dashboard · Chat · CRM    │
                        │  + Clients MCP externes    │
                        └─────────────┬──────────────┘
                                      ▼
                        ┌───────────────────────────────┐
                        │     FASTAPI — ROUTERS         │
                        │  chat · files · crm · memory  │
                        │       · admin · mcp           │
                        └─────────────┬─────────────────┘
                                      ▼
                     ┌────────────────────────────────────┐
                     │   🔐 MIDDLEWARE SÉCURITÉ V2        │
                     │ • Auth JWT/OAuth2 (routes sensib.) │
                     │ • Rate limiting (slowapi)          │
                     │ • PathGuard (anti-traversal)       │
                     └─────────────┬──────────────────────┘
                                   ▼
                     ┌────────────────────────────────────┐
                     │      🧠 BEK ORCHESTRATOR           │
                     │  Intent → GOAP Planning → Exec     │  ← ADN, inchangé
                     └─────────────┬──────────────────────┘
                                   ▼
                     ┌────────────────────────────────────┐
                     │        HERMES CORE V3              │
                     │ • GOAP Planner                     │  ← ADN, inchangé
                     │ • SecurityGuard HMAC (L1 → L5)     │  ← ADN, inchangé
                     │ • Dispatcher parallèle + TraceID   │  ← ADN, inchangé
                     └───────┬──────────────────┬─────────┘
                             ▼                  ▼
              ┌────────────────────┐ ┌──────────────────────┐
              │ 🛡️ SecurityGuard   │ │ 🧬 Skills Registry   │  ← ADN, inchangé
              └─────────┬──────────┘ └──────────┬───────────┘
                        ▼                       ▼
              ┌────────────────────────────────────────────┐
              │    🔧 TOOL BUS → MCP SERVER (réel)         │
              │  Vos outils Hermes, format standard MCP    │  ← NOUVEAU
              └──────────────────┬─────────────────────────┘
                                 ▼
        ┌───────────────────────────────────────────────┐
        │         🌐 LLM GATEWAY (votre cœur)            │
        │  provider_manager + FALLBACK_ORDER            │  ← ADN, inchangé
        │  • Function calling NATIF (chemin primaire)   │  ← NOUVEAU
        │  • Protocole [ACTION:] (fallback robustifié)  │  ← ADN, conservé
        │  • Adaptateur LiteLLM (optionnel)             │  ← OPTIONNEL
        └──────┬──────────────┬──────────────┬──────────┘
               ▼              ▼              ▼
        ┌───────────┐  ┌───────────┐  ┌────────────┐
        │   Groq    │  │NVIDIA NIM │  │Gemini etc. │
        └───────────┘  └───────────┘  └────────────┘
               │
               ▼
   ┌──────────────────────────────────────────────┐
   │         💾 DATA LAYER (inchangé)              │
   │  Neon PostgreSQL · Pinecone · ChromaDB       │
   └──────────────────────────────────────────────┘

   📡 OpenTelemetry : traces + métriques sur tous les flux  ← NOUVEAU
```

---

## 2. Arborescence cible

```text
bek-v16/
├── app.py                     # Bootstrap UNIQUEMENT (~100 lignes)
├── core/
│   ├── config.py              # Pydantic Settings (env vars, clés)
│   ├── security/
│   │   ├── guard.py           # SecurityGuard Hermes — ADN, déplacé tel quel
│   │   ├── auth.py            # JWT/OAuth2 + scopes                [NOUVEAU]
│   │   ├── path_guard.py      # Anti path-traversal                 [NOUVEAU]
│   │   └── rate_limit.py      # Rate limiting slowapi               [NOUVEAU]
│   ├── hermes/                # Hermes Core V3 (GOAP, dispatcher)  — ADN
│   ├── memory/                # Mémoire hybride                    — ADN
│   └── events/                # EventBus A2A + correlation IDs     — ADN
├── routers/
│   ├── chat.py                # /api/chat (SSE, HITL v2)
│   ├── files.py               # upload/download/delete (via PathGuard)
│   ├── crm.py                 # CRUD + SQL admin (auth requis)
│   ├── memory.py              # /api/memory
│   ├── admin.py               # health, config, tasks, sync
│   └── mcp.py                 # endpoints MCP (phase 4)
├── services/
│   ├── action_executor.py     # execute_agent_crm_tool extrait + testé
│   ├── action_extractor.py    # Function calling natif + fallback [ACTION:] robuste
│   ├── llm_gateway.py         # provider_manager (ADN) + adaptateur LiteLLM optionnel
│   ├── vision.py              # Analyse/génération/fusion d'images
│   └── tasks.py               # Tâches de fond multi-OS (psutil)   — ADN
├── mcp/
│   └── server.py              # Serveur MCP réel exposant les outils Hermes
├── skills/ · plugins/ · uploads/ · generated/ · docs/
├── tests/
│   ├── test_path_guard.py
│   ├── test_action_executor.py
│   └── test_action_extractor.py
└── ARCHITECTURE.md
```

---

## 3. Couche par couche — décisions

| Composant v15.3 | v16 | Décision |
|---|---|---|
| SecurityGuard (HMAC, L1→L5, allowlist) | Déplacé dans `core/security/`, code inchangé | 🧬 ADN |
| GOAP Planner Hermes | Inchangé | 🧬 ADN |
| Dispatcher parallèle + TraceID | Inchangé | 🧬 ADN |
| Protocole HITL `[ACTION:]` | **Conservé** + extracteur robuste (JSON repair) + function calling en primaire | 🧬 ADN renforcé |
| Mémoire hybride (Pinecone+Chroma+Neon) | Inchangée | 🧬 ADN |
| `provider_manager` + `FALLBACK_ORDER` | Conservé + adaptateur LiteLLM optionnel | 🧬 ADN |
| Tâches de fond multi-OS (psutil) | Inchangées, isolées dans `services/tasks.py` | 🧬 ADN |
| `app.py` monolithique (~1000 lignes) | Split `routers/` + `services/` + `core/` | 🔧 Refactoring |
| Opérations fichiers (`read/write/delete`) | `PathGuard` : `basename()` + `resolve()` + `relative_to()` | 🔴 Sécurité |
| `/api/crm/execute`, actions L3+ | Auth JWT/OAuth2 + scopes obligatoires | 🔴 Sécurité |
| Rate limiting (promis dans l'archi, absent du code) | Middleware slowapi actif | 🔴 Sécurité |
| Gateway MCP (mock) | Serveur MCP réel (SDK officiel) exposant Hermes tools | 🚪 Standard |
| Task states maison (Neon) | Conservés + OpenTelemetry en parallèle | 🚪 Observabilité |
| EventBus Kafka (mock fallback) | Conservé tel quel | — |

---

## 4. Flux d'exécution des actions — HITL v2

```text
Réponse LLM
    │
    ├─► (1) TOOL CALLS NATIFS (structured outputs)                 ← nouveau, primaire
    │         └─► JSON garanti par le provider → validation Pydantic
    │              └─► L1/L2 → exécution immédiate
    │              └─► L3+  → bannière HITL utilisateur → accord/refus
    │
    └─► (2) FALLBACK : protocole [ACTION:] (votre invention)      ← conservé, robustifié
              └─► extracteur : regex + JSON repair (json5 → ast → repair)
                   └─► même pipeline L1/L2/L3+ ci-dessus

Résultat → injection contexte → [EXECUTED_ACTION:] / [REFUSED_ACTION:]
           → BEK Eval Guard → réponse finale streamée (SSE)
```

**Garantie** : un LLM qui malforme son JSON ne casse plus jamais le pipeline.

---

## 5. Les 3 réparations de plomberie (code prêt)

**5.1 `core/security/path_guard.py`**
```python
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

def safe_path(filename: str, *allowed_dirs: Path) -> Path:
    """Lève ValueError si le chemin sort des dossiers autorisés."""
    candidate = (WORKSPACE / Path(filename).name).resolve()
    allowed = [WORKSPACE.resolve(), *[d.resolve() for d in allowed_dirs]]
    if not any(candidate.is_relative_to(a) for a in allowed):
        raise ValueError(f"Accès refusé hors workspace : {filename}")
    return candidate
```
→ Remplace **tous** les `os.path.join(WORKSPACE_DIR, filename)` de `read_file`, `write_file`, `delete_file`, ZIP.

**5.2 `core/security/auth.py`** — FastAPI `OAuth2PasswordBearer` + scopes (`crm:write`, `actions:execute`, `admin`). Appliqué sur `/api/crm/execute`, actions L3+, delete, upload.

**5.3 `core/security/rate_limit.py`** — `slowapi` en middleware global : 30 req/min par IP sur `/api/chat`, 10 req/min sur upload.

---

## 6. Feuille de route — 4 phases, zéro régression

| Phase | Durée | Contenu | Critère de sortie |
|---|---|---|---|
| **1 — Plomberie** | Semaine 1 | path_guard, auth JWT, rate limiting. **Aucun changement de comportement.** | Path traversal impossible (testé), endpoints sensibles protégés |
| **2 — Refactoring** | Semaines 2-3 | Split `app.py` → routers/services/core, schémas Pydantic, tests pytest. Ancien `app.py` conservé en `app_legacy.py`. | Couverture > 60 % sur `services/`, parité comportementale vérifiée |
| **3 — Actions robustes** | Semaines 4-6 | Function calling primaire + extracteur `[ACTION:]` robuste, BEK Eval Guard branché, OpenTelemetry initialisé | Taux d'actions malformées ≈ 0, traces visibles |
| **4 — Portes** (optionnel) | Mois 2 | Serveur MCP réel, adaptateur LiteLLM, évaluation A2A SDK, POC pgvector | Vos outils utilisables depuis un client MCP externe |

**KPIs suivis** : taux d'actions malformées, latence p95 `/api/chat`, couverture de tests, incidents sécurité.

---

## 7. Explicitement EXCLU (pour l'instant)

- ❌ Réécriture sous LangGraph / Temporal — évalués en phase 4 seulement, jamais imposés
- ❌ Abandon de Pinecone/Chroma pour pgvector — POC uniquement
- ❌ Abandon du protocole `[ACTION:]` — il devient le fallback officiel
- ❌ Abandon de `provider_manager` — LiteLLM est un adaptateur, pas un remplacement

*Votre appartement garde ses murs. On ajoute des prises standard et on bouche les fuites.*
