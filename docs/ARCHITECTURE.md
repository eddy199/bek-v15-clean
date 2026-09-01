# 🧬 Architecture Réelle du Système BEK-v15.2 Hybrid
> *Dernière synchronisation automatique : 2026-09-01 04:03:59 UTC*

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
  * `create_contact`
  * `create_deal`
  * `create_task`
  * `default_llm`
  * `get_stats`
  * `neon_audit`
  * `search_contact`
  * `update_contact`
  * `web_sync`

## 4. Modèles NVIDIA NIM Intégrés

## 5. Règles Opérationnelles Strictes
1. **Zero Régression :** Tout nouveau composant doit s'interfacer avec le `SecurityGuard`.
2. **Gestion des Risques :** Les actions de niveau L3, L4 et L5 sont bloquées par défaut (`REQUIRE_HUMAN`) tant qu'un manager d'approbation n'a pas validé la signature.
3. **Isolation :** Aucun script direct `os.system` ou `eval` n'est autorisé en dehors du cadre sécurisé.
