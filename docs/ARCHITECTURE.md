# 🏛️ ARCHITECTURE BEK-v19 — Document Technique

> **Dernière mise à jour** : 2026-11-04
> **Version** : BEK Hybrid Agent v19
> **Auteur** : BEKKARA Mohamed — Oran, Algérie

---

## 🎯 Vue d'ensemble

BEK est un **agent IA hybride** qui unifie :

| Composant | Quantité | Rôle |
|---|---|---|
| **Nerfs** (système nerveux) | 12 modules | Connexion additive des briques |
| **Briques cognitives** (BEK-LVC) | 6 modules | Raisonnement, mémoire, anti-hallucination |
| **Outils Hermes** | 62 outils | Dispatcher d'actions (L1 → L5) |
| **Providers LLM** | 17 providers | Cascade de fallback automatique |
| **Skills** | 329 compétences | Sélection sémantique par SkillAgent |
| **Alter-egos** | 6 personas | atlas, belfort, mentor, nova, oracle, suntzu |
| **Routers FastAPI** | 6 + 42 sous-modules | API modulaire |
| **Services vision** | 15 modules | Images, vidéos, sous-titres, face swap |

---

## 🏗️ Architecture en couches

```text
+-------------------------------------------------------------+
|                    UTILISATEUR (Navigateur)                 |
+-----------------------------+-------------------------------+
                              | HTTP / SSE
+-----------------------------v-------------------------------+
|                      FastAPI (app.py)                       |
|  routers/ : chat, admin, files, memory, openai_compat       |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                  CERVEAU (core/brain.py)                    |
|  - SkillAgent (329 skills)                                  |
|  - BEK-REX (routing 5 tiers)                                |
|  - BEK-LVC (cache + compression)                            |
|  - Anti-Hallucination (Critic + Grounding)                  |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                  SYSTÈME NERVEUX (nerves/)                  |
|  12 nerfs additifs, activables par feature-flag             |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|               HERMES CORE (hermes_core.py)                  |
|  62 outils, dispatcher GOAP, niveaux L1->L5                 |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                  BRIQUES COGNITIVES (bek_core/)             |
|  BEK-REX, BEK-FLUX, BEK-MEM, BEK-LOOP, BEK-ECO, BEK-STAIR   |
+-------------------------------------------------------------+

```

## 🧠 Les 6 briques BEK-LVC (CPU Logique Virtuel)

| Brique | Module | Rôle |
|---|---|---|
| **BEK-REX** | `bek_core/rex/router.py` | Routage cognitif 5 tiers (LOCAL → FAST → DEEP → EXPERT → SPECIALIZED) |
| **BEK-FLUX** | `bek_core/flux/executor.py` | DAG engine dual-mode (thread I/O + process CPU, contournement GIL) |
| **BEK-MEM** | `bek_core/mem/matcher.py` | Mémoire associative par prototypes évolutifs (Jaccard, seuil 0.75) |
| **BEK-LOOP** | `bek_core/loop/recorder.py` | Apprentissage réflexif en boucle fermée (épisodes, patterns) |
| **BEK-ECO** | `bek_core/eco/optimizer.py` | Optimisation économique à 7 facteurs (cache, tokens, latence) |
| **BEK-STAIR** | `bek_core/stair/toc_builder.py` | Anti-hallucination par ToC (méthode IBM) |

Ces 6 briques sont orchestrées par `bek_core/cpu.py` (le CPU logique virtuel) qui permet de les appeler via une abréviation : `BekCPU.execute("BEK-REX", "route", query="...")`.

---

## 🧬 Les 12 nerfs (système nerveux additif)

| Nerf | Module | Rôle | Outils | Statut |
|---|---|---|---|---|
| **1** | `hermes_nerves.py` | Remplace les stubs Hermes par les vrais handlers | 9 outils | ✅ Actif |
| **2** | `cognitive_nerves.py` | Cortex cognitif (Swarm critique + Grounding) | 3 outils | ✅ Actif |
| **3** | `event_bus_nerves.py` | Pont EventBusKafka ↔ EventBusClient | — (bridge) | ✅ Actif |
| **4** | `web_agent_nerves.py` | WebAgent tracé sur EventBus unifié | 4 outils | ✅ Actif |
| **5** | `approval_nerves.py` | Interception L3+ → ApprovalManager | 5 outils | ✅ Actif |
| **6** | `mcp_nerves.py` | Sync bidirectionnelle MCP Gateway ↔ Hermes | 3 + 5 outils | ✅ Actif |
| **7** | `router_nerves.py` | SmartRouter sémantique (7 types de tâches) | 3 outils | ✅ Actif |
| **8** | `skills_nerves.py` | Charge le SkillRegistry au boot (329 skills) | — | ✅ Actif |
| **9** | `guardian_nerves.py` | Guardian tracé sur EventBus unifié | 3 outils | ✅ Actif |
| **11-13** | `headless_nerves.py` | Playwright branché (search, leads, render) | 3 outils | ✅ Actif |
| **14-17** | `tmux_nerves.py` | Tâches de fond multi-OS (Tmux/Wimux) | 4 outils | ✅ Actif |
| **18** | `coder_nerves.py` | Codex + 11 code_tools | 3 + 11 outils | ✅ Actif |
| **19** | `project_creator_nerves.py` | Création de projets autonomes | 3 outils | ✅ Actif |

> ⚠️ **Note** : Le Nerf 10 (CRM) a été **supprimé de l'architecture**. Le fichier `nerves/crm_nerves.py` et `plugins/plugin_crm.py` ont été retirés.

### Modules utilitaires internes

- **`_async_utils.py`** : `run_async_safely(coro, timeout=60)` — exécution sûre d'une coroutine quel que soit le contexte (thread ou event loop actif).
- **`_health.py`** : `get_all_nerves_status()` + `get_nerves_summary()` — health check complet du système nerveux.

---

## 🛠️ Les 62 outils Hermes (par catégorie)

### Outils par défaut (7)
`default_llm`, `neon_audit`, `web_sync`, `generate_image`, `edit_image`, `generate_video`, `edit_video`

### Outils fichiers (11)
`read_file`, `read_file_map`, `write_file`, `append_file`, `edit_file`, `create_dir`, `grep`, `glob_files`, `ls`, `bash`, `search_skills`

### Outils mémoire (5)
`save_memory`, `hindsight_query`, `hindsight_recall`, `submit_feedback`, `orchestrate`

### Outils vidéo avancés (4)
`extend_video`, `extend_video_multiple`, `generate_subtitles`, `burn_subtitles`

### Outils headless (4)
`headless_scrape`, `headless_search`, `headless_extract_leads`, `headless_render`

### Outils tmux (4)
`tmux_start_task`, `tmux_stop_task`, `tmux_list_tasks`, `tmux_task_status`

### Outils web agent (4)
`web_agent_traced`, `web_agent_scrape`, `web_search`, `web_search_docs`

### Outils guardian (3)
`guardian_status`, `guardian_audit_log`, `guardian_trigger_audit`

### Outils MCP (3)
`mcp_list_tools`, `mcp_execute`, `mcp_register`

### Outils cognitifs (3)
`cognitive_critique`, `cognitive_ground`, `cognitive_full_check`

### Outils router (3)
`router_route`, `router_task_type`, `router_providers`

### Outils Codex (3)
`codex_agent`, `codex_editor`, `codex_loop`

### Outils projet (3)
`create_project`, `list_projects`, `project_status`

### Outils MCP importés (5)
`mcp_rea_analyze_binary`, `mcp_rea_analyze_javascript`, `mcp_python_analyze_file`, `mcp_python_analyze_directory`, `mcp_python_save_report`

---

## 🌐 Les 17 providers LLM (cascade de fallback)

`groq`, `nvidia`, `gemini`, `openrouter`, `mistral`, `cohere`, `aionlabs`, `zhipu`, `siliconflow`, `huggingface`, `ollama_cloud`, `kimi`, `aisa`, `b_ai`, `beatapi`, `agnes`, `local`

Chaque provider est géré par `provider_manager.py` avec :
- Circuit breaker
- Protection TPM (tokens par minute)
- Cascade de fallback automatique

---

## 🎭 Skills & Alter-Egos

- **329 skills** dans `skills/` (dossiers avec `SKILL.md` + fichiers `.py` éventuels)
- **6 alter-egos** : `atlas`, `belfort`, `mentor`, `nova`, `oracle`, `suntzu`
- **SkillAgent** (`skill_agent.py`) : sélectionne les skills pertinentes par catégorie (CODE, SECURITY, DATA, AGENT)
- **SkillRegistry** (`skill_registry.py`) : registre central (métadonnées, alter-egos)
- **SkillRunner** (`skill_runner.py`) : scan et chargement des skills

---

## 🔐 Sécurité (4 couches)

| Couche | Module | Rôle |
|---|---|---|
| **PathGuard** | `core/security/path_guard.py` | Anti-traversal, confinement aux répertoires autorisés |
| **Validateur AST** | `core/security/skill_sandbox.py` | Analyse statique du code des skills (blacklist + whitelist) |
| **Sandbox d'exécution** | `bek_core/security/skill_sandbox.py` | Isolation sous-processus + limites RAM/CPU (non branché, en attente) |
| **SecurityGuard** | `security_guard.py` | Signature HMAC-SHA256, niveaux L1→L5, détection d'injections |

---

## 🛣️ Routes API principales

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/chat` | Chat principal (orchestrateur SSE) |
| `POST` | `/api/brain/chat` | Chat avec routage Brain |
| `GET` | `/api/config` | Config providers + skills |
| `GET` | `/api/files` | Liste des fichiers de session |
| `POST` | `/api/upload` | Upload de fichiers |
| `GET` | `/api/memory` | État de la mémoire vectorielle |
| `GET` | `/api/connectors` | État des connecteurs |
| `GET` | `/api/reflex/stats` | Stats Reflex Loop |
| `GET` | `/api/reflex/history` | Historique des propositions |
| `POST` | `/api/reflex/run-cycle` | Lance un cycle Reflex |
| `GET` | `/api/architecture/status` | Diagnostic architecture |
| `POST` | `/api/refresh-architecture` | Régénère `docs/ARCHITECTURE.md` |
| `GET` | `/health/worker` | Health check worker |
| `GET` | `/health/memory` | Health check mémoire + lazy loading |
| `POST` | `/v1/chat/completions` | Façade OpenAI-compatible |
| `GET` | `/v1/models` | Liste des modèles OpenAI-compat |

---

## 📊 État du système (dernière exécution)

- **Version** : 19.11
- **Nerfs actifs** : 11/12 (le CRM est supprimé)
- **Outils Hermes** : 62
- **Skills chargés** : 329
- **Alter-egos** : 6
- **Providers LLM** : 17
- **Issues ArchiGen** : 0

---

## 📚 Documentation complémentaire

- `docs/ARCHITECTURE.md` — Diagnostic auto-généré par ArchiGen (mis à jour à chaque boot)
- `docs/ADDING_A_BRICK.md` — Comment ajouter une brique
- `docs/BEK_LVC.md` — Référentiel du CPU logique virtuel
- `docs/brevets/` — 16 brevets (REX, FLUX, MEM, LOOP, ECO, STAIR, MCP, etc.)
- `docs/programming/` — Conventions de code

---

## 📜 Licence

AGPL-3.0 — voir `LICENSE`

---

> **Note** : ce document est maintenu manuellement. La version auto-générée est dans `docs/ARCHITECTURE.md`.