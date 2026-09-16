# ARCHITECTURE COMPLÈTE & CARTOGRAPHIE DES MODULES BEK-v16

Ce document recense l'ensemble des modules sources, moteurs d'exécution et briques cognitives actifs dans le projet.

## 1. Moteurs d'Exécution Asynchrones & Headless
- **`worker_headless.py` / `services/tasks.py` (Tmux & Headless Workers)** : Gestion des processus d'arrière-plan, exécution de tâches asynchrones, compatibilité Windows/Linux multi-OS via `psutil`.
- **`hermes_core.py` (Hermes V3 Engine)** : Moteur de planification GOAP (Goal-Oriented Action Planning), dispatcher d'outils, gestionnaire des niveaux de risque (L1 à L5) et hooks de pré-planification.

## 2. Protocoles d'Interopérabilité & Communication Inter-Agents
- **`event_bus.py` (A2A EventBus Kafka Mock)** : Pipeline d'ingestion et d'échange de messages asynchrones Agent-to-Agent (A2A).
- **`mcp_gateway.py` (Model Context Protocol Gateway)** : Passerelle d'outils standardisés MCP pour l'interopérabilité (Neon DB audit, etc.).
- **`meta_cortex_swarm.py` & `meta_cortex_sse_ui.py`** : Moteur de réflexion en essaim (Reflexion Swarm) et streaming SSE des étapes de réflexion.
- **`meta_cortex_grounding.py`** : Validation de l'ancrage factuel et contrôle qualité des sorties LLM.

## 3. Données, Mémoire & Matrice CRM
- **`memory.py`** : Triple ancrage vectoriel et persistant (Pinecone Cloud, ChromaDB local, compensation SQL `sync_log` sur Neon DB).
- **`sub_crm_engine.py` / `plugin_crm.py`** : Moteur de synchronisation multi-CRM et schéma Matrix Neon DB.
- **`services/db.py`** : Exécuteur SQL direct et sécurisé pour Neon DB.

## 4. Sécurité & Contrôle des Chemins
- **`core/security/path_guard.py` (`PathGuard`)** : Protection anti-traversal stricte confinant les accès aux répertoires autorisés (`uploads/`, `generated/`, racine).
- **`security_guard.py`** : Signature HMAC et vérification d'intégrité des payloads.
- **`bek_eval_guard.py`** : Garde d'évaluation des réponses et détection d'hallucinations.
- **`core/security/skill_sandbox.py`** : Analyseur de syntaxe abstraite (AST) pour valider et sécuriser le code des compétences générées dynamiquement avant leur injection.

## 5. Hub de Modèles & Compétences
- **`provider_manager.py`** : Hub universel multi-fournisseurs (Groq, Gemini, NVIDIA, Mistral, B.ai, etc.) avec cascade de fallback automatique.
- **`skill_generator.py` & `skill_registry.py`** : Registre dynamique et auto-génération de compétences Python à la volée.
- **`web_agent.py`** : Navigation, scraping et recherche web autonome.
- **`services/vision.py`** : Moteur multimodal de génération et analyse d'images.

## 6. Couche d'Intelligence Additive (BEK-Intelligence)
- **`bek_intelligence.py`** : Module intégrant un `SmartRouter` (routage sémantique dynamique), un `AutoCorrectEngine` (garde qualité et auto-correction), et `SkillForge` (génération de skills avec réinjection des erreurs au LLM).

## 7. Architecture Modulaire FastAPI (Batch 1-3)
- **`app.py`** : Point d'entrée bootstrap épuré (~100 lignes).
- **`routers/`** : `admin.py`, `chat.py`, `crm.py`, `files.py`, `memory.py`.
- **`services/`** : `action_executor.py`, `vision.py`, `tasks.py`, `db.py`.
- **`core/`** : `paths.py`, `utils.py`, `security/`.

---

## 8. Système Nerveux Additif (`nerves/`)

Couche **additive, non-invasive** qui relie les briques existantes de BEK **sans les modifier**.
Chaque nerf est :
- **activé/désactivé** par un feature-flag (`BEK_ENABLE_*_NERVES`, défaut `true`),
- **idempotent** (appel multiple sans effet de bord),
- **isolé** (échec d'un nerf n'empêche pas les autres de fonctionner),
- **traçable** (publication d'événements A2A via le pont unifié du Nerf 3).

### 8.1 Cartographie des 12 modules `nerves/`

| Nerf | Module | Rôle | Outils Hermes | Bridges |
|---|---|---|---|---|
| **1** | `hermes_nerves.py` | Remplace les stubs Hermes par les vrais handlers | 8 outils (`web_sync`, `orchestrate`, `neon_audit`, `generate_image`, `edit_image`, `generate_video`, `edit_video`, `headless_scrape`) | — |
| **2** | `cognitive_nerves.py` | Cortex cognitif : Swarm critique + Grounding SQL | `cognitive_critique`, `cognitive_ground`, `cognitive_full_check` | `run_critique_swarm`, `run_grounding`, `run_cognitive_pipeline` |
| **3** | `event_bus_nerves.py` | Pont bidirectionnel EventBusKafka ↔ EventBusClient | — | `publish_event_unified`, `get_event_bus_bridge` |
| **4** | `web_agent_nerves.py` | WebAgent tracé sur EventBus unifié | `web_agent_traced`, `web_agent_scrape` | `pipeline_and_trace`, `scrape_and_trace` |
| **5** | `approval_nerves.py` | Interception L3+ → ApprovalManager (monkey-patch réversible) | `approval_submit`, `approval_list`, `approval_get`, `approval_approve`, `approval_reject` | `submit_for_human_approval` |
| **6** | `mcp_nerves.py` | Sync bidirectionnelle MCP Gateway ↔ Hermes | `mcp_list_tools`, `mcp_execute`, `mcp_register` | `register_mcp_tool_into_hermes`, `sync_hermes_tools_to_mcp` |
| **7** | `router_nerves.py` | SmartRouter sémantique réel (7 types de tâches) | `router_route`, `router_task_type`, `router_providers` | `route_semantic`, `detect_task_type` |
| **8** | `skills_nerves.py` | Charge le SkillRegistry au boot | — | — |
| **9** | `guardian_nerves.py` | Guardian tracé sur EventBus unifié | `guardian_status`, `guardian_audit_log`, `guardian_trigger_audit` | `notify_guardian_audit_start/done/error` |
| **10** | `crm_nerves.py` | Sub-CRM Engine branché à Hermes (5 outils) | `sub_crm_spawn`, `sub_crm_list`, `sub_crm_get`, `sub_crm_opportunities`, `sub_crm_stats` | `spawn_sub_crm_with_worker` |
| **11-13** | `headless_nerves.py` | Playwright branché (search, render, leads) | `headless_search`, `headless_extract_leads`, `headless_render` | `headless_scrape_for_web_agent` |
| **14-17** | `tmux_nerves.py` | Tâches de fond multi-OS + bridges Guardian/Sub-CRM | `tmux_start_task`, `tmux_stop_task`, `tmux_list_tasks`, `tmux_task_status` | `tmux_start_for_guardian`, `tmux_start_for_sub_crm` |

### 8.2 Modules utilitaires internes

- **`_async_utils.py`** : `run_async_safely(coro, timeout=60)` — exécution sûre d'une coroutine, quel que soit le contexte (thread ou event loop actif). Utilisé par `headless_nerves.py` et `hermes_nerves.py`.
- **`_health.py`** : `get_all_nerves_status()` + `get_nerves_summary()` — health check complet du système nerveux (voir section 9).

### 8.3 Ordre d'activation (dans `app.py`)

L'ordre est **critique** : le pont EventBus (Nerf 3) doit être activé en premier car il est la fondation pour tous les nerfs tracés.
