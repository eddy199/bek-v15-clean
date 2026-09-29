# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Générateur d'architecture dynamique intelligent
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Générer docs/ARCHITECTURE.md avec un VRAI plan d'action
# 📄 Appelé au boot par app.py + disponible en CLI + appelable à chaud via API
# ------------------------------------------------------------------------------
# Version : 2.1
# Date : 2026-09-29
# ------------------------------------------------------------------------------
# v2.1 (2026-09-29) :
#   - Section "Mémoire" : Neon → Supabase + 3 nouveaux modules (Hindsight, Coordinator, Feedback)
#   - Section "BEK-LVC" : 5 → 6 briques (ajout BEK-STAIR)
#   - Section "Routage FastAPI" : chat.py v18.9 + streaming.py v1.3.3
#   - Ajout section "Mémoire long-terme" et "Apprentissage"
# ==============================================================================

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# ─── Résolution des chemins ───
WORKSPACE_DIR = Path(__file__).resolve().parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

DOCS_DIR = WORKSPACE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FILE = DOCS_DIR / "ARCHITECTURE.md"

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PLAN D'ACTION (statique, mode d'emploi pour le LLM)
# ══════════════════════════════════════════════════════════════════════════════

_PLAN_ACTION = """# 🏛️ ARCHITECTURE BEK-v18 — PLAN D'ACTION POUR LE LLM

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

Ces briques sont appelées AUTOMATIQUEMENT par le système après ton action.
Tu n'as PAS besoin de les appeler toi-même.

### BEK-REX (routing intelligent)
- Analyse ta requête
- Décide quel tier (TIER_0 → TIER_4)
- Route vers le bon outil

### BEK-STAIR (anti-hallucination)
- Valide tes réponses contre les sources réelles
- Détecte les URLs inventées
- Détecte les faits inventés

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
- Utilisé automatiquement dans `web_sync`

═══════════════════════════════════════════════════════════════════════════════
## ⚙️ RAPPEL DU FORMAT D'ACTION
═══════════════════════════════════════════════════════════════════════════════

Format EXCLUSIF :

- TOUJOURS fermer avec `[/ACTION]`
- INTERDIT d'utiliser des tokens spéciaux (`<|tool_call|>`, `<tool_call>`, etc.)
- UNE seule action par réponse
"""


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — COLLECTE DYNAMIQUE
# ══════════════════════════════════════════════════════════════════════════════

def _collect_hermes_tools() -> List[Dict[str, Any]]:
    try:
        from hermes_core import hermes
        runtime = hermes.runtime_status()
        return runtime.get("tools", [])
    except Exception as exc:
        logger.debug("[ArchiGen] Hermes tools indisponibles : %s", exc)
        return []


def _collect_nerfs() -> List[Dict[str, Any]]:
    nerfs: List[Dict[str, Any]] = []
    try:
        import nerves  # noqa: F401
        nerfs = [
            {"id": "Nerf 1", "name": "hermes_nerves", "role": "Outils Hermes réels"},
            {"id": "Nerf 2", "name": "cognitive_nerves", "role": "Swarm + Grounding"},
            {"id": "Nerf 3", "name": "event_bus_nerves", "role": "Pont Kafka ↔ Async"},
            {"id": "Nerf 4", "name": "web_agent_nerves", "role": "WebAgent tracé"},
            {"id": "Nerf 5", "name": "approval_nerves", "role": "Approbation L3+"},
            {"id": "Nerf 6", "name": "mcp_nerves", "role": "MCP ↔ Hermes"},
            {"id": "Nerf 7", "name": "router_nerves", "role": "SmartRouter sémantique"},
            {"id": "Nerf 8", "name": "skills_nerves", "role": "Skills chargés"},
            {"id": "Nerf 9", "name": "guardian_nerves", "role": "Guardian tracé"},
            {"id": "Nerf 10", "name": "crm_nerves", "role": "Sub-CRM → Hermes"},
            {"id": "Nerf 11-13", "name": "headless_nerves", "role": "Playwright → Hermes"},
            {"id": "Nerf 14-17", "name": "tmux_nerves", "role": "Tmux → Hermes"},
        ]
    except Exception as exc:
        logger.debug("[ArchiGen] Nerfs indisponibles : %s", exc)
    return nerfs


def _collect_bek_lvc() -> Dict[str, Any]:
    try:
        from bek_core import BekCPU
        briques = BekCPU.list() if hasattr(BekCPU, "list") else []
        return {"available": True, "briques": briques}
    except Exception as exc:
        logger.debug("[ArchiGen] BEK-LVC indisponible : %s", exc)
        return {"available": False, "briques": []}


def _collect_providers() -> List[str]:
    try:
        from provider_manager import provider_manager
        return list(provider_manager.PROVIDER_MODELS.keys())
    except Exception as exc:
        logger.debug("[ArchiGen] Providers indisponibles : %s", exc)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — GÉNÉRATION DU DOCUMENT
# ══════════════════════════════════════════════════════════════════════════════

def generate_architecture_markdown() -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    tools = _collect_hermes_tools()
    nerfs = _collect_nerfs()
    bek_lvc = _collect_bek_lvc()
    providers = _collect_providers()

    lines = [
        _PLAN_ACTION,
        "",
        "═══════════════════════════════════════════════════════════════════════════════",
        "## 📊 ÉTAT RÉEL DU SYSTÈME (généré automatiquement)",
        "═══════════════════════════════════════════════════════════════════════════════",
        "",
        f"> *Dernière synchronisation : {now_utc}*",
        "",
    ]

    # ─── Section outils Hermes ───
    lines.append(f"### 🔧 Outils Hermes enregistrés ({len(tools)})")
    lines.append("")
    if tools:
        lines.append("| Outil | Risque | Exécution |")
        lines.append("|---|---|---|")
        for tool in tools:
            name = tool.get("name", "?")
            risk = tool.get("risk_level", "L1")
            approval = "⚠️ Humain requis" if risk in {"L3", "L4", "L5"} else "✅ Auto"
            lines.append(f"| `{name}` | **{risk}** | {approval} |")
    else:
        lines.append("*Aucun outil chargé*")
    lines.append("")

    # ─── Section nerfs ───
    lines.append(f"### 🧠 Système nerveux ({len(nerfs)} nerfs)")
    lines.append("")
    if nerfs:
        lines.append("| Nerf | Module | Rôle |")
        lines.append("|---|---|---|")
        for nerve in nerfs:
            lines.append(f"| {nerve['id']} | `{nerve['name']}` | {nerve['role']} |")
    else:
        lines.append("*Aucun nerf chargé*")
    lines.append("")

    # ─── Section BEK-LVC ───
    lines.append("### 🏛️ BEK-LVC (6 briques)")
    lines.append("")
    if bek_lvc.get("available"):
        briques = bek_lvc.get("briques", [])
        lines.append("- **Statut :** ✅ Chargé")
        lines.append(f"- **Briques actives ({len(briques)}) :** {', '.join(briques) if briques else 'aucune'}")
    else:
        lines.append("- **Statut :** ❌ Non chargé")
    lines.append("")

    # ─── Section providers ───
    lines.append(f"### 🌐 Providers LLM disponibles ({len(providers)})")
    lines.append("")
    if providers:
        for p in providers[:20]:
            lines.append(f"- `{p}`")
        if len(providers) > 20:
            lines.append(f"- *... et {len(providers) - 20} autres*")
    else:
        lines.append("*Aucun provider*")
    lines.append("")

    # ─── Section architecture des modules ───
    lines.extend([
        "═══════════════════════════════════════════════════════════════════════════════",
        "## 🗂️ CARTOGRAPHIE DES MODULES",
        "═══════════════════════════════════════════════════════════════════════════════",
        "",
        "### Moteurs d'exécution",
        "- `worker_headless.py` — Workers Playwright headless",
        "- `hermes_core.py` — Planificateur GOAP + dispatcher",
        "- `core/execution_engine.py` — DAG Engine parallèle",
        "- `core/hermes_dag_adapter.py` — Adaptateur Hermes ↔ DAG",
        "",
        "### Communication inter-agents",
        "- `event_bus.py` — EventBus Redis Streams (sync)",
        "- `event_bus_client.py` — Client async unifié",
        "- `mcp_gateway.py` — Passerelle MCP",
        "- `meta_cortex_swarm.py` — Reflexion Swarm",
        "- `meta_cortex_grounding.py` — Ancrage factuel",
        "",
        "### Mémoire (4 couches coordonnées)",
        "- `memory.py` — Pinecone (cloud) + ChromaDB (local) + Supabase (relationnel)",
        "- `hindsight_memory.py` — Mémoire structurée long-terme (Hindsight)",
        "- `memory_coordinator.py` — Orchestrateur des 4 couches + résolution conflits",
        "- `feedback_memory.py` — Apprentissage par feedback utilisateur",
        "- `services/memory_service.py` — LanceDB + DuckDB (analytique local)",
        "",
        "### Sécurité",
        "- `security_guard.py` — HMAC + Allowlist + DLP",
        "- `core/security/path_guard.py` — Anti-traversal",
        "- `core/security/skill_sandbox.py` — AST validation",
        "- `bek_eval_guard.py` — Quality gate",
        "",
        "### Intelligence",
        "- `bek_intelligence.py` — SmartRouter + AutoCorrect + SkillForge",
        "- `web_agent.py` — WebAgent profond (Playwright + MinHash)",
        "- `services/vision/` — Multimodal (12 modules)",
        "- `services/reflex_loop.py` — Reflex-Loop (SQLite fallback)",
        "- `services/critic.py` — Critic LLM",
        "- `services/episode_logger.py` — Tracing (DuckDB ou SQLite)",
        "- `services/forge.py` — Forge (propositions d'amélioration)",
        "",
        "### Routage FastAPI",
        "- `routers/chat.py` — Chat orchestrateur (v18.9 — singleton event_bus)",
        "- `routers/chat_modules/` — 10 modules découpés :",
        "  - `config.py` — Constantes centralisées",
        "  - `prompts.py` — Prompt système (RÈGLE ZÉRO + 6 règles)",
        "  - `validation.py` — URLs stériles, traductions FR→EN",
        "  - `routing.py` — BEK-REX + BEK-ECO + BEK-MEM + BEK-LOOP",
        "  - `formatters.py` — Formatage résultats",
        "  - `actions.py` — Dispatcher unifié",
        "  - `scrape.py` — Auto-scrape BS4",
        "  - `stair.py` — Anti-hallucination ToC",
        "  - `streaming.py` — SSE v1.3.3 (4 leviers + Hindsight + garde-fous)",
        "- `routers/openai_compat.py` — Façade OpenAI-compatible",
        "- `routers/admin.py`, `routers/crm.py`, `routers/files.py`, `routers/memory.py`",
        "",
        "### CPU Logique Virtuel (`bek_core/`)",
        "- `bek_core/cpu.py` — BekCPU (point d'entrée)",
        "- `bek_core/registry.py` — BekRegistry",
        "- `bek_core/registry.json` — Catalogue des briques",
        "- `bek_core/translator.py` — BekTranslator",
        "- `bek_core/rex/` — BEK-REX (routing)",
        "- `bek_core/flux/` — BEK-FLUX (parallélisation)",
        "- `bek_core/mem/` — BEK-MEM (mémoire)",
        "- `bek_core/loop/` — BEK-LOOP (apprentissage)",
        "- `bek_core/eco/` — BEK-ECO (optimisation)",
        "- `bek_core/stair/` — BEK-STAIR (anti-hallucination)",
        "",
        "### Système nerveux (`nerves/`)",
        "- `nerves/event_bus_nerves.py` — Nerf 3 (pont Kafka↔Async, v18.7 anti-boucle)",
        "- `nerves/hermes_nerves.py` — Nerf 1 (8 outils Hermes réels)",
        "- `nerves/cognitive_nerves.py` — Nerf 2 (3 outils cognitifs)",
        "- `nerves/web_agent_nerves.py` — Nerf 4 (2 outils WebAgent)",
        "- `nerves/approval_nerves.py` — Nerf 5 (5 outils approbation)",
        "- `nerves/mcp_nerves.py` — Nerf 6 (3 outils MCP)",
        "- `nerves/router_nerves.py` — Nerf 7 (3 outils Router)",
        "- `nerves/skills_nerves.py` — Nerf 8 (5194 skills)",
        "- `nerves/guardian_nerves.py` — Nerf 9 (3 outils Guardian)",
        "- `nerves/crm_nerves.py` — Nerf 10 (5 outils CRM)",
        "- `nerves/headless_nerves.py` — Nerfs 11-13 (3 outils Playwright)",
        "- `nerves/tmux_nerves.py` — Nerfs 14-17 (4 outils Tmux)",
        "",
        "### Intégration OpenAI / DSH",
        "- `POST /v1/chat/completions` — Format OpenAI",
        "- `GET  /v1/models` — Liste des modèles",
        "- Permet à DSH, LangChain, Cursor de parler à BEK",
        "",
        "### Garde-fous streaming v1.3.3",
        "- `BEK_STREAM_TIMEOUT_SEC` — Timeout dur (défaut 300s)",
        "- `BEK_LOOP_DETECT_ENABLED` — Détection de répétition",
        "- `BEK_LOOP_WINDOW` — Fenêtre de détection (défaut 15)",
        "- `BEK_LOOP_THRESHOLD` — Seuil de déclenchement (défaut 4)",
        "- `BEK_MAX_REASONING_CHARS` — Limite de réflexion (défaut 6000)",
        "- **4 leviers d'accélération :** BEK-ECO cache, BEK-MEM prototypes, BEK-REX routing, BEK-LOOP feedback",
        "- **Hindsight retain** : mémorisation automatique des conversations",
        "",
        "### Routes API principales",
        "- `POST /api/chat` — Chat principal (orchestrateur v18.9)",
        "- `GET  /api/chat/debug` — Debug complet",
        "- `POST /api/feedback` — Soumettre un feedback utilisateur",
        "- `GET  /api/feedback` — Liste + stats des feedbacks",
        "- `GET  /api/hindsight/status` — État Hindsight",
        "- `GET  /api/hindsight/query` — Interroger Hindsight",
        "- `POST /api/admin/flush-redis` — Vider Redis Streams (v18.10)",
        "- `POST /api/refresh-architecture` — Régénérer ce document",
        "- `GET  /api/config` — Config providers + skills",
        "- `POST /api/skills/execute` — Exécuter un skill",
        "",
    ])

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ÉCRITURE FICHIER
# ══════════════════════════════════════════════════════════════════════════════

def update_documentation_file() -> bool:
    try:
        content = generate_architecture_markdown()
        with open(TARGET_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.info(
            "✅ [ArchiGen] Architecture mise à jour : %s (%d chars)",
            TARGET_FILE, len(content),
        )
        return True
    except Exception as exc:
        logger.error("[ArchiGen] Échec génération : %s", exc, exc_info=True)
        return False


def refresh_if_stale(max_age_seconds: int = 300) -> bool:
    try:
        if not TARGET_FILE.exists():
            return update_documentation_file()
        age = time.time() - TARGET_FILE.stat().st_mtime
        if age > max_age_seconds:
            logger.info("[ArchiGen] Fichier vieux de %.0fs → régénération", age)
            return update_documentation_file()
        return True
    except Exception as exc:
        logger.debug("[ArchiGen] refresh_if_stale échec : %s", exc)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = update_documentation_file()
    sys.exit(0 if success else 1)