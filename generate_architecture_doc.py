# ==============================================================================
# BEK-v16 — Générateur de documentation d'architecture unifiée (Mis à jour)
# ==============================================================================
import os

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")
ARCH_FILE = os.path.join(DOCS_DIR, "ARCHITECTURE.md")

ARCHITECTURE_CONTENT = """# ARCHITECTURE COMPLÈTE & CARTOGRAPHIE DES MODULES BEK-v16

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
"""

def update_documentation_file():
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(ARCH_FILE, "w", encoding="utf-8") as f:
        f.write(ARCHITECTURE_CONTENT.strip())
    print(f"✅ Documentation d'architecture mise à jour avec succès : {ARCH_FILE}")

if __name__ == "__main__":
    update_documentation_file()