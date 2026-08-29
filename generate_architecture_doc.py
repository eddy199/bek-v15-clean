"""
BEK-v15.2 HYBRID - Dynamic Architecture Document Generator
----------------------------------------------------------
Inspecte l'état réel du système (Hermes, SecurityGuard, Endpoints, Modèles)
et génère automatiquement la documentation d'architecture dans docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Résolution du chemin racine
WORKSPACE_DIR = Path(__file__).resolve().parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

DOCS_DIR = WORKSPACE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FILE = DOCS_DIR / "ARCHITECTURE.md"


def generate_architecture_markdown() -> str:
    """Génère la documentation Markdown à partir de l'état réel du code."""
    # Import tardif pour éviter les dépendances circulaires
    try:
        from hermes_core import hermes
        runtime = hermes.runtime_status()
        tools = runtime.get("tools", [])
    except Exception as exc:
        tools = []
        runtime = {"status": f"Error: {exc}", "security_guard_active": False}

    try:
        from security_guard import SecurityGuard
        guard_actions = sorted(SecurityGuard.ALLOWED_ACTIONS.keys())
    except Exception:
        guard_actions = []

    try:
        from app import get_all_nvidia_models
        nvidia_models = get_all_nvidia_models()
    except Exception:
        nvidia_models = []

    # Construction du document
    lines = [
        "# 🧬 Architecture Réelle du Système BEK-v15.2 Hybrid",
        f"> *Dernière synchronisation automatique : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        "",
        "## 1. Organigramme des Flux d'Exécution",
        "```text",
        "                         ┌──────────────────────────┐",
        "                         │      WEB / MOBILE UI     │",
        "                         │   Dashboard / Chat / CRM │",
        "                         └────────────┬─────────────┘",
        "                                      │",
        "                                      ▼",
        "                         ┌──────────────────────────┐",
        "                         │        app.py / API      │",
        "                         │   FastAPI / Flask Layer  │",
        "                         │ • Auth & Rate Limiting   │",
        "                         │ • Upload Security (ZIP)  │",
        "                         │ • SQL Security Gate      │",
        "                         └────────────┬─────────────┘",
        "                                      │",
        "                                      ▼",
        "                    ┌────────────────────────────────────┐",
        "                    │          🧠 BEK ORCHESTRATOR        │",
        "                    │  Intent → Planning → Execution     │",
        "                    └────────────────┬───────────────────┘",
        "                                     │",
        "                                      ▼",
        "                    ┌────────────────────────────────────┐",
        "                    │          HERMES CORE V2             │",
        "                    │ • Parallel Dispatcher (Threads)    │",
        "                    │ • GOAP Planner                     │",
        "                    │ • Risk Engine (L1 -> L5)           │",
        "                    │ • Task & Trace ID Management       │",
        "                    └───────────────┬────────────────────┘",
        "                                    │",
        "                     ┌──────────────┴──────────────┐",
        "                     ▼                             ▼",
        "            ┌─────────────────┐          ┌─────────────────┐",
        "            │ 🛡️ SecurityGuard │          │ 🧬 GOAP / Skills │",
        "            │ • HMAC-SHA256   │          │ • Registry      │",
        "            │ • Strict Allow  │          │ • Performance   │",
        "            │ • Risk L1 -> L5 │          │   Metrics (Neon)│",
        "            └────────┬────────┘          └────────┬────────┘",
        "                     │                            │",
        "                     └────────────┬───────────────┘",
        "                                  ▼",
        "                    ┌──────────────────────────────┐",
        "                    │       🔧 TOOL BUS / MCP       │",
        "                    │ • web_sync                   │",
        "                    │ • neon_audit                 │",
        "                    │ • default_llm                │",
        "                    │ • CRM tools / DB Mutations   │",
        "                    └──────────────┬───────────────┘",
        "                                   │",
        "             ┌─────────────────────┼─────────────────────┐",
        "             ▼                     ▼                     ▼",
        "      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐",
        "      │ NVIDIA NIM   │      │ Groq         │      │ Gemini /     │",
        "      │ (LLM Engine) │      │ AI Provider  │      │ OpenRouter   │",
        "      └──────────────┘      └──────────────┘      └──────────────┘",
        "             │",
        "             ▼",
        "      ┌─────────────────────────────────────────┐",
        "      │              💾 DATA LAYER               │",
        "      │ PostgreSQL / Neon (CRM & Traces)        │",
        "      │ Pinecone Vector Memory (Fallback SHA)   │",
        "      └─────────────────────────────────────────┘",
        "```",
        "",
        "## 2. État du Noyau Hermes & Outils Actifs",
        f"- **Statut d'exécution :** `{runtime.get('status', 'unknown')}`",
        f"- **SecurityGuard actif :** `{runtime.get('security_guard_active', False)}`",
        f"- **Nombre d'outils enregistrés :** `{len(tools)}`",
        "",
        "| Outil Hermes | Niveau de Risque | Description / Statut |",
        "| :--- | :---: | :--- |",
    ]

    if tools:
        for tool in tools:
            risk = tool.get("risk_level", "L1")
            approval = "Validation Humaine Requise" if risk in {"L3", "L4", "L5"} else "Exécution Automatique"
            lines.append(f"| `{tool.get('name')}` | **{risk}** | {approval} |")
    else:
        lines.append("| *Aucun outil chargé* | - | - |")

    lines.extend([
        "",
        "## 3. Politiques de Sécurité (SecurityGuard)",
        "- **Chiffrement & Signature :** HMAC-SHA256 obligatoire via `BEK_HSM_SECRET`",
        "- **Actions autorisées en liste blanche (*Allowlist*) :**",
    ])

    for action in guard_actions:
        lines.append(f"  * `{action}`")

    lines.extend([
        "",
        "## 4. Modèles NVIDIA NIM Intégrés",
    ])

    for model in nvidia_models:
        lines.append(f"- `{model}`")

    lines.extend([
        "",
        "## 5. Règles Opérationnelles Strictes",
        "1. **Zero Régression :** Tout nouveau composant doit s'interfacer avec le `SecurityGuard`.",
        "2. **Gestion des Risques :** Les actions de niveau L3, L4 et L5 sont bloquées par défaut (`REQUIRE_HUMAN`) tant qu'un manager d'approbation n'a pas validé la signature.",
        "3. **Isolation :** Aucun script direct `os.system` ou `eval` n'est autorisé en dehors du cadre sécurisé.",
        "",
    ])

    return "\n".join(lines)


def update_documentation_file() -> bool:
    """Écrit le fichier Markdown et retourne True si l'opération réussit."""
    try:
        content = generate_architecture_markdown()
        with open(TARGET_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"✅ Documentation d'architecture mise à jour avec succès : {TARGET_FILE}")
        return True
    except Exception as exc:
        print(f"❌ Erreur lors de la génération de la documentation : {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    update_documentation_file()
