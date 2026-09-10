# 🧬 Architecture Réelle du Système BEK-v15.2 Hybrid
> *Dernière synchronisation automatique : 2026-09-10 17:43:50 UTC*

## 1. Organigramme des Flux d'Exécution
```text
                         ┌──────────────────────────┐
                         │      WEB / MOBILE UI     │
                         │   Dashboard / Chat / CRM │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │        app.py / API      │
                         │   FastAPI / Flask Layer  │
                         │ • Auth & Rate Limiting   │
                         │ • Upload Security (ZIP)  │
                         │ • SQL Security Gate      │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                    ┌────────────────────────────────────┐
                    │          🧠 BEK ORCHESTRATOR        │
                    │  Intent → Planning → Execution     │
                    └────────────────┬───────────────────┘
                                     │
                                      ▼
                    ┌────────────────────────────────────┐
                    │          HERMES CORE V2             │
                    │ • Parallel Dispatcher (Threads)    │
                    │ • GOAP Planner                     │
                    │ • Risk Engine (L1 -> L5)           │
                    │ • Task & Trace ID Management       │
                    └───────────────┬────────────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
            ┌─────────────────┐          ┌─────────────────┐
            │ 🛡️ SecurityGuard │          │ 🧬 GOAP / Skills │
            │ • HMAC-SHA256   │          │ • Registry      │
            │ • Strict Allow  │          │ • Performance   │
            │ • Risk L1 -> L5 │          │   Metrics (Neon)│
            └────────┬────────┘          └────────┬────────┘
                     │                            │
                     └────────────┬───────────────┘
                                  ▼
                    ┌──────────────────────────────┐
                    │       🔧 TOOL BUS / MCP       │
                    │ • web_sync                   │
                    │ • neon_audit                 │
                    │ • default_llm                │
                    │ • CRM tools / DB Mutations   │
                    └──────────────┬───────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             ▼                     ▼                     ▼
      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
      │ NVIDIA NIM   │      │ Groq         │      │ Gemini /     │
      │ (LLM Engine) │      │ AI Provider  │      │ OpenRouter   │
      └──────────────┘      └──────────────┘      └──────────────┘
             │
             ▼
      ┌─────────────────────────────────────────┐
      │              💾 DATA LAYER               │
      │ PostgreSQL / Neon (CRM & Traces)        │
      │ Pinecone Vector Memory (Fallback SHA)   │
      └─────────────────────────────────────────┘
```

## 2. État du Noyau Hermes & Outils Actifs
- **Statut d'exécution :** `operational`
- **SecurityGuard actif :** `True`
- **Nombre d'outils enregistrés :** `3`

| Outil Hermes | Niveau de Risque | Description / Statut |
| :--- | :---: | :--- |
| `default_llm` | **L1** | Exécution Automatique |
| `neon_audit` | **L1** | Exécution Automatique |
| `web_sync` | **L3** | Validation Humaine Requise |

## 3. Politiques de Sécurité (SecurityGuard)
- **Chiffrement & Signature :** HMAC-SHA256 obligatoire via `BEK_HSM_SECRET`
- **Actions autorisées en liste blanche (*Allowlist*) :**
  * `analyze_image`
  * `analyze_zip_content`
  * `create_contact`
  * `create_deal`
  * `create_dynamic_skill`
  * `create_file`
  * `create_task`
  * `create_zip`
  * `default_llm`
  * `delete_file`
  * `delete_from_memory`
  * `delete_memory`
  * `execute_background_task`
  * `execute_command`
  * `execute_tmux_headless`
  * `extract_zip`
  * `forget`
  * `generate_image`
  * `get_stats`
  * `kill_session`
  * `merge_and_edit_images`
  * `multi_agent_workflow`
  * `neon_audit`
  * `orchestrate`
  * `read_file`
  * `recall`
  * `remember`
  * `run_script`
  * `run_swarm_task`
  * `run_tests`
  * `save_file`
  * `save_memory`
  * `save_to_memory`
  * `search_contact`
  * `search_memory`
  * `start_background_task`
  * `stop_background_task`
  * `stop_session`
  * `stop_tmux_headless`
  * `update_contact`
  * `web_pipeline`
  * `web_search`
  * `web_sync`
  * `write_file`

## 4. Modèles NVIDIA NIM Intégrés

## 5. Règles Opérationnelles Strictes
1. **Zero Régression :** Tout nouveau composant doit s'interfacer avec le `SecurityGuard`.
2. **Gestion des Risques :** Les actions de niveau L3, L4 et L5 sont bloquées par défaut (`REQUIRE_HUMAN`) tant qu'un manager d'approbation n'a pas validé la signature.
3. **Isolation :** Aucun script direct `os.system` ou `eval` n'est autorisé en dehors du cadre sécurisé.
