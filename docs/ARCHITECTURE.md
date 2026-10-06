# 🏛️ ARCHITECTURE BEK-v18 — PLAN D'ACTION POUR LE LLM

> Ce document n'est PAS un inventaire. C'est ton **mode d'emploi**.
> Il te dit **quand** utiliser **quelle brique** et **comment** raisonner.

═══════════════════════════════════════════════════════════════════════════════
## 🎯 RÈGLE ZÉRO — COMMENT RAISONNER
═══════════════════════════════════════════════════════════════════════════════

Avant de répondre, tu te poses TOUJOURS ces 4 questions dans cet ordre :

1. **La question est-elle conversationnelle ?** (bonjour, merci, comment vas-tu)
   → Réponds directement en 1 phrase. PAS d'action.

2. **La question demande-t-elle des informations fraîches ?** (news, actualités, prix, récent)
   → Utilise `[ACTION:web_sync]` OBLIGATOIREMENT.
   → INTERDIT de répondre depuis l'historique.

3. **La question demande-t-elle une création visuelle ?** (image, vidéo)
   → Utilise `[ACTION:generate_image]` ou `[ACTION:generate_video]`.

4. **La question est-elle complexe ?** (multi-étapes, analyse, plan)
   → Utilise `[ACTION:orchestrate]`.

═══════════════════════════════════════════════════════════════════════════════
## 📋 TABLE DE DÉCISION — QUEL OUTIL POUR QUOI
═══════════════════════════════════════════════════════════════════════════════

| Type de question | Outil à appeler | Exemple |
|---|---|---|
| Salutation / conversation | Aucun | "Bonjour", "Merci" |
| Actualité / news / prix | `web_sync` | "Cherche les news Bitcoin" |
| Recherche d'info fraîche | `web_sync` | "Quel est le prix de l'ETH ?" |
| Générer une image | `generate_image` | "Fais-moi un logo" |
| Générer une vidéo | `generate_video` | "Crée une vidéo de chat" |
| Étendre une vidéo | `extend_video` | "Prolonge la vidéo" |
| Scraper une URL précise | `headless_scrape` | "Scrape cette page" |
| Tâche multi-étapes | `orchestrate` | "Organise un voyage" |
| Écriture de fichier | `write_file` | "Écris dans config.json" |
| Commande shell | `execute_command` | "Liste les fichiers" |
| Question sur soi-même | `hindsight_query` | "Qui suis-je ?" |
| Rappeler un fait | `hindsight_recall` | "Quelle est ma couleur préférée ?" |

═══════════════════════════════════════════════════════════════════════════════
## 🚨 RÈGLES ABSOLUES (À RESPECTER SANS EXCEPTION)
═══════════════════════════════════════════════════════════════════════════════

### Règle 1 — Langue de la requête
- Utilisateur FR → requête `web_sync` en FRANÇAIS
- INTERDIT de traduire en anglais

### Règle 2 — Sources réelles uniquement
- INTERDIT de citer une source que tu n'as pas obtenue via un outil
- INTERDIT d'inventer des URLs

### Règle 3 — Fraîcheur des news
- Si l'utilisateur dit "cherche" / "news" / "actualité" / "actualise"
  → TOUJOURS appeler `web_sync`
  → INTERDIT de recycler une réponse précédente

### Règle 4 — Anti-hallucination
- Si les résultats sont insuffisants → dis-le honnêtement
- INTERDIT d'inventer des faits, chiffres, dates

### Règle 5 — Un seul outil par réponse
- Tu appelles UN seul outil
- Une fois le résultat obtenu, tu conclus

### Règle 6 — Mémoire long-terme
- Utilise `hindsight_query` pour les questions personnelles ("Qui suis-je ?")
- Utilise `hindsight_recall` pour retrouver un fait spécifique
- INTERDIT d'inventer un fait sur l'utilisateur

═══════════════════════════════════════════════════════════════════════════════
## 🧠 BRIQUES COGNITIVES DISPONIBLES (utilisées AUTOMATIQUEMENT)
═══════════════════════════════════════════════════════════════════════════════

### BEK-REX (routing intelligent)
- Analyse ta requête
- Décide quel tier (TIER_0 → TIER_4)
- Route vers le bon outil

### BEK-STAIR (anti-hallucination)
- Valide tes réponses contre les sources réelles
- Détecte les URLs inventées

### BEK-LVC (6 briques cognitives)
- **BEK-REX** : routage intelligent (5 tiers)
- **BEK-FLUX** : parallélisation DAG
- **BEK-MEM** : mémoire par prototypes
- **BEK-LOOP** : apprentissage continu
- **BEK-ECO** : économie de calcul (cache)
- **BEK-STAIR** : anti-hallucination ToC

### Critic (Nerf 2)
- Analyse la cohérence de ta réponse
- Peut te demander de reformuler

### Grounding (Nerf 2)
- Vérifie les faits cités
- Valide l'ancrage dans les sources

### ReflexionSwarm
- Débat multi-agents sur les sujets complexes

═══════════════════════════════════════════════════════════════════════════════
## ⚙️ RAPPEL DU FORMAT D'ACTION
═══════════════════════════════════════════════════════════════════════════════

Format EXCLUSIF :
- TOUJOURS fermer avec `[/ACTION]`
- INTERDIT d'utiliser des tokens spéciaux
- UNE seule action par réponse


═══════════════════════════════════════════════════════════════════════════════
## 📊 ÉTAT RÉEL DU SYSTÈME (généré automatiquement)
═══════════════════════════════════════════════════════════════════════════════

> *Dernière synchronisation : 2026-10-06 23:35:22 UTC*
> *Version BEK : **18.14***
> *State hash : `b6f5416e5c7b`*
> *Boot phase : **complete***

═══════════════════════════════════════════════════════════════════════════════
## 🩺 DIAGNOSTIC ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

⚠️ **1 problème(s) détecté(s) :**

- 🔴 **Critiques :** 0
- 🟠 **Avertissements :** 0
- 🔵 **Informations :** 1

### 🔵 INFO (1)

| Catégorie | Problème | Détail | Correction |
|---|---|---|---|
| `config` | **CRM désactivé** | Le Nerf 10 (CRM) est désactivé — comportement attendu. | Pour réactiver : `BEK_ENABLE_CRM_NERVES=true`. |


### 🔌 API de diagnostic

| Endpoint | Description |
|---|---|
| `GET /api/architecture/status` | Statut complet + issues |
| `POST /api/refresh-architecture` | Régénérer ARCHITECTURE.md |

### 🔧 Outils Hermes enregistrés (42)

| Outil | Risque | Exécution |
|---|---|---|
| `default_llm` | **L1** | ✅ Auto |
| `neon_audit` | **L1** | ✅ Auto |
| `web_sync` | **L2** | ✅ Auto |
| `generate_image` | **L1** | ✅ Auto |
| `edit_image` | **L1** | ✅ Auto |
| `generate_video` | **L1** | ✅ Auto |
| `edit_video` | **L1** | ✅ Auto |
| `orchestrate` | **L2** | ✅ Auto |
| `extend_video` | **L1** | ✅ Auto |
| `extend_video_multiple` | **L1** | ✅ Auto |
| `generate_subtitles` | **L1** | ✅ Auto |
| `burn_subtitles` | **L1** | ✅ Auto |
| `hindsight_query` | **L1** | ✅ Auto |
| `hindsight_recall` | **L1** | ✅ Auto |
| `submit_feedback` | **L1** | ✅ Auto |
| `headless_scrape` | **L2** | ✅ Auto |
| `headless_search` | **L2** | ✅ Auto |
| `headless_extract_leads` | **L2** | ✅ Auto |
| `headless_render` | **L2** | ✅ Auto |
| `tmux_start_task` | **L3** | ⚠️ Humain requis |
| `tmux_stop_task` | **L3** | ⚠️ Humain requis |
| `tmux_list_tasks` | **L1** | ✅ Auto |
| `tmux_task_status` | **L1** | ✅ Auto |
| `web_agent_traced` | **L3** | ⚠️ Humain requis |
| `web_agent_scrape` | **L2** | ✅ Auto |
| `guardian_status` | **L1** | ✅ Auto |
| `guardian_audit_log` | **L1** | ✅ Auto |
| `guardian_trigger_audit` | **L2** | ✅ Auto |
| `approval_submit` | **L1** | ✅ Auto |
| `approval_list` | **L1** | ✅ Auto |
| `approval_get` | **L1** | ✅ Auto |
| `approval_approve` | **L2** | ✅ Auto |
| `approval_reject` | **L2** | ✅ Auto |
| `mcp_list_tools` | **L1** | ✅ Auto |
| `mcp_execute` | **L2** | ✅ Auto |
| `mcp_register` | **L2** | ✅ Auto |
| `cognitive_critique` | **L2** | ✅ Auto |
| `cognitive_ground` | **L2** | ✅ Auto |
| `cognitive_full_check` | **L2** | ✅ Auto |
| `router_route` | **L1** | ✅ Auto |
| `router_task_type` | **L1** | ✅ Auto |
| `router_providers` | **L1** | ✅ Auto |

### 🧠 Système nerveux (12 nerfs détectés)

- ✅ **Actifs :** 11
- ⛔ **Désactivés :** 1
- ❌ **Manquants/erreurs :** 0

| Nerf | Module | Rôle | Statut |
|---|---|---|---|
| Nerf 1 | `hermes_nerves` | Outils Hermes réels | ✅ available |
| Nerf 2 | `cognitive_nerves` | Swarm + Grounding | ✅ available |
| Nerf 3 | `event_bus_nerves` | Pont Kafka ↔ Async | ✅ available |
| Nerf 4 | `web_agent_nerves` | WebAgent tracé | ✅ available |
| Nerf 5 | `approval_nerves` | Approbation L3+ | ✅ available |
| Nerf 6 | `mcp_nerves` | MCP ↔ Hermes | ✅ available |
| Nerf 7 | `router_nerves` | SmartRouter sémantique | ✅ available |
| Nerf 8 | `skills_nerves` | Skills chargés | ✅ available |
| Nerf 9 | `guardian_nerves` | Guardian tracé | ✅ available |
| Nerf 10 | `crm_nerves` | Sub-CRM → Hermes | ⛔ disabled |
| Nerf 11-13 | `headless_nerves` | Playwright → Hermes | ✅ available |
| Nerf 14-17 | `tmux_nerves` | Tmux → Hermes | ✅ available |

### ★ Lazy Loading Status (v18.13)

| Composant | Statut | Détail |
|---|---|---|
| `playwright` | 💤 **lazy** | ~200 MB économisés au boot |
| `chromadb` | 💤 **lazy** | ~80 MB économisés au boot |
| `duckdb_episode` | ✅ **duckdb** | Backend : duckdb |
| `lancedb` | 💤 **lazy** | Chargé à la demande |
| `duckdb_analytics` | 💤 **lazy** | Chargé à la demande |

### 🏛️ BEK-LVC (6 briques cognitives)

- **Statut :** ✅ Chargé
- **Briques actives (6) :** BEK-ECO, BEK-FLUX, BEK-LOOP, BEK-MEM, BEK-REX, BEK-STAIR

### 🎭 Skills & Alter Egos

- **Skills chargés :** 0
- **Alter Egos (1) :** suntzu

### 🛠️ CRM Status (Nerf 10)

- **Statut :** ⛔ **disabled**
- **Raison :** BEK_ENABLE_CRM_NERVES=false

### 🌐 Providers LLM disponibles (18)

- `kimi`
- `aisa`
- `b_ai`
- `kilo_anonymous`
- `ovh_anonymous`
- `llm7_anonymous`
- `groq`
- `nvidia`
- `gemini`
- `agnes`
- `openrouter`
- `mistral`
- `cohere`
- `aionlabs`
- `zhipu`
- `siliconflow`
- `huggingface`
- `ollama_cloud`

### ⚙️ Variables d'environnement BEK

| Variable | Valeur |
|---|---|
| `BEK_LAZY_LOAD` | `true` |
| `BEK_LAZY_LOAD_PLAYWRIGHT` | `true` |
| `BEK_LAZY_LOAD_CHROMADB` | `true` |
| `BEK_LAZY_LOAD_DUCKDB` | `true` |
| `BEK_DISABLE_CHROMADB` | `false` |
| `BEK_DISABLE_LANCEDB` | `false` |
| `BEK_DISABLE_DUCKDB_ANALYTICS` | `false` |
| `BEK_ENABLE_CRM_NERVES` | `false` |
| `BEK_PROFILE` | `(non défini)` |

═══════════════════════════════════════════════════════════════════════════════
## 🗂️ CARTOGRAPHIE DES MODULES (scannée dynamiquement)
═══════════════════════════════════════════════════════════════════════════════

### Moteurs d'exécution (7)

- `backup/hermes_core.py`
- `backup/worker_headless.py`
- `core/execution_engine.py`
- `core/hermes_dag_adapter.py`
- `hermes_core.py`
- `tests/test_hermes_dag.py`
- `worker_headless.py`

### Communication inter-agents (12)

- `backup/event_bus.py`
- `backup/meta_cortex_grounding.py`
- `backup/meta_cortex_swarm.py`
- `backup/swarm_agent.py`
- `backup/swarm_core.py`
- `event_bus.py`
- `event_bus_client.py`
- `mcp_gateway.py`
- `meta_cortex_grounding.py`
- `meta_cortex_swarm.py`
- `swarm_agent.py`
- `swarm_core.py`

### Mémoire (6)

- `backup/memory.py`
- `feedback_memory.py`
- `gen_memory.py`
- `hindsight_memory.py`
- `memory.py`
- `memory_coordinator.py`

### Sécurité (6)

- `backup/security_guard.py`
- `bek_eval_guard.py`
- `core/security/path_guard.py`
- `core/security/skill_sandbox.py`
- `security_guard.py`
- `tests/test_action_executor_sandbox.py`

### Intelligence (25)

- `services/action_executor.py`
- `services/critic.py`
- `services/critic_prompt.py`
- `services/db.py`
- `services/episode_logger.py`
- `services/forge.py`
- `services/huggingface_service.py`
- `services/memory_service.py`
- `services/prompt_optimizer.py`
- `services/reflex_loop.py`
- `services/tasks.py`
- `services/vision/__init__.py`
- `services/vision/agnes_client.py`
- `services/vision/constants.py`
- `services/vision/face_swap.py`
- `services/vision/ffmpeg_utils.py`
- `services/vision/huggingface_client.py`
- `services/vision/image_analysis.py`
- `services/vision/image_generation.py`
- `services/vision/pollinations_client.py`
- `services/vision/veo_client.py`
- `services/vision/video_concat.py`
- `services/vision/video_extension.py`
- `services/vision/video_generation.py`
- `services/vision/whisper_client.py`

### Routage FastAPI (16)

- `routers/admin.py`
- `routers/chat.py`
- `routers/chat_modules/__init__.py`
- `routers/chat_modules/actions.py`
- `routers/chat_modules/config.py`
- `routers/chat_modules/formatters.py`
- `routers/chat_modules/prompts.py`
- `routers/chat_modules/routing.py`
- `routers/chat_modules/scrape.py`
- `routers/chat_modules/stair.py`
- `routers/chat_modules/streaming.py`
- `routers/chat_modules/validation.py`
- `routers/crm.py`
- `routers/files.py`
- `routers/memory.py`
- `routers/openai_compat.py`

### CPU Logique Virtuel (18)

- `bek_core/__init__.py`
- `bek_core/cpu.py`
- `bek_core/eco/__init__.py`
- `bek_core/eco/optimizer.py`
- `bek_core/flux/__init__.py`
- `bek_core/flux/executor.py`
- `bek_core/loop/__init__.py`
- `bek_core/loop/recorder.py`
- `bek_core/mem/__init__.py`
- `bek_core/mem/matcher.py`
- `bek_core/registry.py`
- `bek_core/rex/__init__.py`
- `bek_core/rex/router.py`
- `bek_core/security/__init__.py`
- `bek_core/security/skill_sandbox.py`
- `bek_core/stair/__init__.py`
- `bek_core/stair/toc_builder.py`
- `bek_core/translator.py`

### Système nerveux (15)

- `nerves/__init__.py`
- `nerves/_async_utils.py`
- `nerves/_health.py`
- `nerves/approval_nerves.py`
- `nerves/cognitive_nerves.py`
- `nerves/crm_nerves.py`
- `nerves/event_bus_nerves.py`
- `nerves/guardian_nerves.py`
- `nerves/headless_nerves.py`
- `nerves/hermes_nerves.py`
- `nerves/mcp_nerves.py`
- `nerves/router_nerves.py`
- `nerves/skills_nerves.py`
- `nerves/tmux_nerves.py`
- `nerves/web_agent_nerves.py`

### Lazy Loading (1)

- `core/lazy.py`

### Autres modules racine (38)

- `ai_service.py`
- `app.py`
- `approval_manager.py`
- `bek_intelligence.py`
- `bek_master.py`
- `bek_model_hub.py`
- `bek_orchestrator.py`
- `bek_routing_config.py`
- `bek_simulate.py`
- `config.py`
- `context_loader.py`
- `demo.py`
- `env_loader.py`
- `fast_math.py`
- `file_gen.py`
- `find_connector_files.py`
- `gen_cpu.py`
- `gen_feedback.py`
- `generate_architecture_doc.py`
- `google_search.py`
- `list_models.py`
- `meta_cortex_sse_ui.py`
- `plugins.py`
- `port_scanner.py`
- `provider_manager.py`
- `reconciliation_job.py`
- `run_enhance_architecture.py`
- `run_hf_diagnose.py`
- `run_tests.py`
- `save_project_context.py`
- `skill_generator.py`
- `skill_registry.py`
- `skill_runner.py`
- `skills.py`
- `state_synchronizer.py`
- `sub_crm_engine.py`
- `sync_manager.py`
- `web_agent.py`

═══════════════════════════════════════════════════════════════════════════════
## 🛣️ ROUTES API PRINCIPALES
═══════════════════════════════════════════════════════════════════════════════

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/chat` | Chat principal (orchestrateur) |
| `GET`  | `/api/chat/debug` | Debug complet |
| `GET`  | `/api/config` | Config providers + skills |
| `GET`  | `/api/architecture/status` | **★ Diagnostic architecture** |
| `POST` | `/api/refresh-architecture` | **★ Régénérer ce document** |
| `POST` | `/api/feedback` | Soumettre un feedback |
| `GET`  | `/api/feedback` | Liste + stats des feedbacks |
| `GET`  | `/api/hindsight/status` | État Hindsight |
| `GET`  | `/api/hindsight/query` | Interroger Hindsight |
| `POST` | `/api/admin/flush-redis` | Vider Redis Streams |
| `POST` | `/api/skills/execute` | Exécuter un skill |
| `GET`  | `/health/worker` | Health check worker |
| `GET`  | `/health/memory` | **★ Health check mémoire + lazy** |
| `POST` | `/v1/chat/completions` | Façade OpenAI-compatible |
| `GET`  | `/v1/models` | Liste des modèles OpenAI-compat |
