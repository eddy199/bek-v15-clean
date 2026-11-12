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

> *Dernière synchronisation : 2026-11-10 12:55:21 UTC*
> *Version BEK : **19.15***
> *State hash : `0d0777eed88e`*
> *Boot phase : **complete***

═══════════════════════════════════════════════════════════════════════════════
## 🩺 DIAGNOSTIC ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

✅ **Aucun problème détecté** — Architecture saine.

### 🔌 API de diagnostic

| Endpoint | Description |
|---|---|
| `GET /api/architecture/status` | Statut complet + issues |
| `POST /api/refresh-architecture` | Régénérer ARCHITECTURE.md |

### 🔧 Outils Hermes enregistrés (73)

| Outil | Risque | Exécution |
|---|---|---|
| `default_llm` | **L1** | ✅ Auto |
| `neon_audit` | **L1** | ✅ Auto |
| `web_sync` | **L2** | ✅ Auto |
| `generate_image` | **L1** | ✅ Auto |
| `edit_image` | **L1** | ✅ Auto |
| `generate_video` | **L1** | ✅ Auto |
| `edit_video` | **L1** | ✅ Auto |
| `read_file` | **L1** | ✅ Auto |
| `read_file_map` | **L1** | ✅ Auto |
| `write_file` | **L1** | ✅ Auto |
| `append_file` | **L1** | ✅ Auto |
| `edit_file` | **L1** | ✅ Auto |
| `create_dir` | **L1** | ✅ Auto |
| `grep` | **L1** | ✅ Auto |
| `glob_files` | **L1** | ✅ Auto |
| `ls` | **L1** | ✅ Auto |
| `bash` | **L2** | ✅ Auto |
| `search_skills` | **L1** | ✅ Auto |
| `git_clone` | **L2** | ✅ Auto |
| `analyze_architecture` | **L1** | ✅ Auto |
| `security_scan_python` | **L1** | ✅ Auto |
| `orchestrate` | **L2** | ✅ Auto |
| `save_memory` | **L1** | ✅ Auto |
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
| `web_search` | **L2** | ✅ Auto |
| `web_search_docs` | **L2** | ✅ Auto |
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
| `codex_agent` | **L2** | ✅ Auto |
| `codex_editor` | **L3** | ⚠️ Humain requis |
| `codex_loop` | **L2** | ✅ Auto |
| `ga_get_best` | **L1** | ✅ Auto |
| `ga_record_result` | **L2** | ✅ Auto |
| `ga_evolve` | **L2** | ✅ Auto |
| `create_project` | **L2** | ✅ Auto |
| `list_projects` | **L1** | ✅ Auto |
| `project_status` | **L1** | ✅ Auto |
| `mcp_rea_analyze_binary` | **L2** | ✅ Auto |
| `mcp_rea_analyze_javascript` | **L2** | ✅ Auto |
| `mcp_python_analyze_file` | **L1** | ✅ Auto |
| `mcp_python_analyze_directory` | **L1** | ✅ Auto |
| `mcp_python_save_report` | **L1** | ✅ Auto |

### 🧠 Système nerveux (11 nerfs détectés)

- ✅ **Actifs :** 11
- ⛔ **Désactivés :** 0
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

- **Skills chargés :** 329
- **Alter Egos (6) :** atlas, belfort, mentor, nova, oracle, suntzu

### 🌐 Providers LLM disponibles (18)

- `groq`
- `apinex`
- `nvidia`
- `gemini`
- `openrouter`
- `mistral`
- `cohere`
- `aionlabs`
- `zhipu`
- `siliconflow`
- `huggingface`
- `ollama_cloud`
- `kimi`
- `aisa`
- `b_ai`
- `beatapi`
- `agnes`
- `local`

### ⚙️ Variables d'environnement BEK

| Variable | Valeur |
|---|---|
| `BEK_LAZY_LOAD` | `true` |
| `BEK_LAZY_LOAD_PLAYWRIGHT` | `true` |
| `BEK_LAZY_LOAD_CHROMADB` | `true` |
| `BEK_LAZY_LOAD_DUCKDB` | `true` |
| `BEK_DISABLE_CHROMADB` | `false` |
| `BEK_DISABLE_LANCEDB` | `(non défini)` |
| `BEK_DISABLE_DUCKDB_ANALYTICS` | `false` |
| `BEK_PROFILE` | `(non défini)` |

═══════════════════════════════════════════════════════════════════════════════
## 🗂️ CARTOGRAPHIE DES MODULES (scannée dynamiquement)
═══════════════════════════════════════════════════════════════════════════════

### Moteurs d'exécution (4)

- `core/execution_engine.py`
- `core/hermes_dag_adapter.py`
- `hermes_core.py`
- `worker_headless.py`

### Communication inter-agents (7)

- `event_bus.py`
- `event_bus_client.py`
- `mcp_gateway.py`
- `meta_cortex_grounding.py`
- `meta_cortex_swarm.py`
- `swarm_agent.py`
- `swarm_core.py`

### Mémoire (6)

- `benchmark_memory.py`
- `feedback_memory.py`
- `gen_memory.py`
- `hindsight_memory.py`
- `memory.py`
- `memory_coordinator.py`

### Sécurité (5)

- `bek_eval_guard.py`
- `core/security/path_guard.py`
- `core/security/skill_sandbox.py`
- `security_guard.py`
- `tests/test_bek_skills/test_skill_sandbox.py`

### Intelligence (26)

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
- `services/vision/b_ai_client.py`
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

### Routage FastAPI (47)

- `routers/admin.py`
- `routers/chat.py`
- `routers/chat_modules/__init__.py`
- `routers/chat_modules/actions/__init__.py`
- `routers/chat_modules/actions/aliases.py`
- `routers/chat_modules/actions/cleaning.py`
- `routers/chat_modules/actions/core.py`
- `routers/chat_modules/actions/extraction.py`
- `routers/chat_modules/actions/guards.py`
- `routers/chat_modules/actions/regex.py`
- `routers/chat_modules/actions/summary.py`
- `routers/chat_modules/chat/__init__.py`
- `routers/chat_modules/chat/constants.py`
- `routers/chat_modules/chat/core.py`
- `routers/chat_modules/chat/debug.py`
- `routers/chat_modules/chat/files.py`
- `routers/chat_modules/chat/helpers.py`
- `routers/chat_modules/chat/memory.py`
- `routers/chat_modules/chat/slash.py`
- `routers/chat_modules/config.py`
- `routers/chat_modules/formatters.py`
- `routers/chat_modules/prompts/__init__.py`
- `routers/chat_modules/prompts/action_format.py`
- `routers/chat_modules/prompts/anti_hallucination.py`
- `routers/chat_modules/prompts/core.py`
- `routers/chat_modules/prompts/decision_table.py`
- `routers/chat_modules/prompts/identity.py`
- `routers/chat_modules/prompts/image.py`
- `routers/chat_modules/prompts/lang.py`
- `routers/chat_modules/prompts/memory.py`
- `routers/chat_modules/prompts/orchestration.py`
- `routers/chat_modules/prompts/video.py`
- `routers/chat_modules/prompts/web.py`
- `routers/chat_modules/routing.py`
- `routers/chat_modules/scrape.py`
- `routers/chat_modules/stair.py`
- `routers/chat_modules/streaming/__init__.py`
- `routers/chat_modules/streaming/constants.py`
- `routers/chat_modules/streaming/core.py`
- `routers/chat_modules/streaming/guards.py`
- `routers/chat_modules/streaming/loop_detect.py`
- `routers/chat_modules/streaming/parsing.py`
- `routers/chat_modules/streaming/truncation.py`
- `routers/chat_modules/validation.py`
- `routers/files.py`
- `routers/memory.py`
- `routers/openai_compat.py`

### CPU Logique Virtuel (19)

- `bek_core/__init__.py`
- `bek_core/cpu.py`
- `bek_core/eco/__init__.py`
- `bek_core/eco/optimizer.py`
- `bek_core/flux/__init__.py`
- `bek_core/flux/executor.py`
- `bek_core/genes/gene_manager.py`
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

### Système nerveux (17)

- `nerves/__init__.py`
- `nerves/_async_utils.py`
- `nerves/_health.py`
- `nerves/approval_nerves.py`
- `nerves/coder_nerves.py`
- `nerves/cognitive_nerves.py`
- `nerves/event_bus_nerves.py`
- `nerves/ga_nerves.py`
- `nerves/guardian_nerves.py`
- `nerves/headless_nerves.py`
- `nerves/hermes_nerves.py`
- `nerves/mcp_nerves.py`
- `nerves/project_creator_nerves.py`
- `nerves/router_nerves.py`
- `nerves/skills_nerves.py`
- `nerves/tmux_nerves.py`
- `nerves/web_agent_nerves.py`

### Lazy Loading (1)

- `core/lazy.py`

### Autres modules racine (44)

- `ai_service.py`
- `app.py`
- `approval_manager.py`
- `bek_ga_light.py`
- `bek_intelligence.py`
- `bek_master.py`
- `bek_orchestrator.py`
- `bek_routing_config.py`
- `bek_simulate.py`
- `benchmark_ga.py`
- `build_skill_index.py`
- `codex_py_2e1751.py`
- `codex_py_cbdca4.py`
- `context_loader.py`
- `env_loader.py`
- `fast_math.py`
- `file_gen.py`
- `find_connector_files.py`
- `gen_cpu.py`
- `gen_feedback.py`
- `generate_architecture_doc.py`
- `generer_readme.py`
- `google_search.py`
- `list_models.py`
- `lvc_smart.py`
- `meta_cortex_sse_ui.py`
- `plugins.py`
- `port_scanner.py`
- `probe_agnes.py`
- `provider_manager.py`
- `python_analyzer_mcp.py`
- `python_bridge.py`
- `rea_agents_bridge.py`
- `reconciliation_job.py`
- `run_enhance_architecture.py`
- `run_hf_diagnose.py`
- `save_project_context.py`
- `skill_agent.py`
- `skill_generator.py`
- `skill_registry.py`
- `skill_runner.py`
- `state_synchronizer.py`
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
