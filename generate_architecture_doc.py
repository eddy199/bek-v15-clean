# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Générateur d'architecture dynamique ULTRA INTELLIGENT
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Générer docs/ARCHITECTURE.md avec un VRAI plan d'action
# 📄 Appelé au boot par app.py + disponible en CLI + appelable à chaud via API
# ------------------------------------------------------------------------------
# Version : 4.0
# Date : 2026-10-06
# ------------------------------------------------------------------------------
# v4.0 (2026-10-06) — DIAGNOSTIC & SIGNALEMENT :
#   - Détection automatique des PROBLÈMES d'architecture
#   - Classification par sévérité (info/warning/critical)
#   - Section "DIAGNOSTIC" dans ARCHITECTURE.md
#   - Exposition via API : get_cached_diagnostics()
#   - Signalement dans les logs (WARNING/ERROR si critique)
#   - State hash mis à jour avec issues
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Résolution des chemins ───
WORKSPACE_DIR = Path(__file__).resolve().parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

DOCS_DIR = WORKSPACE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FILE = DOCS_DIR / "ARCHITECTURE.md"
STATE_FILE = DOCS_DIR / ".archigen_state.json"

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# ★ v4.0 — STRUCTURES DE DIAGNOSTIC
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArchitectureIssue:
    """Représente un problème détecté dans l'architecture."""
    severity: str          # "critical" | "warning" | "info"
    category: str          # "nerf" | "lazy" | "memory" | "env" | "module" | "config"
    title: str             # Titre court
    detail: str            # Description détaillée
    fix_hint: str = ""     # Suggestion de correction
    source: str = ""       # Fichier/module concerné


# Cache global des diagnostics (pour l'API FastAPI)
_DIAGNOSTICS_CACHE: Dict[str, Any] = {
    "issues": [],
    "summary": {},
    "last_check": None,
    "state_hash": None,
}
_DIAGNOSTICS_LOCK = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# VERSION BEK (détectée dynamiquement)
# ══════════════════════════════════════════════════════════════════════════════

def _collect_bek_version() -> str:
    """Détecte la version BEK depuis app.py ou fallback."""
    try:
        app_py = WORKSPACE_DIR / "app.py"
        if app_py.exists():
            content = app_py.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'version\s*=\s*["\'](\d+\.\d+)["\']', content)
            if match:
                return match.group(1)
            match = re.search(r'# v(\d+\.\d+)', content)
            if match:
                return match.group(1)
    except Exception as exc:
        logger.debug("[ArchiGen] Version detection échec : %s", exc)
    return "18.14"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PLAN D'ACTION
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
"""


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — COLLECTE DYNAMIQUE
# ══════════════════════════════════════════════════════════════════════════════

def _collect_hermes_tools() -> List[Dict[str, Any]]:
    try:
        from hermes_core import hermes
        if hasattr(hermes, "runtime_status"):
            runtime = hermes.runtime_status()
            return runtime.get("tools", [])
        elif hasattr(hermes, "tools"):
            return [
                {"name": name, "risk_level": getattr(t, "risk_level", "L1")}
                for name, t in hermes.tools.items()
            ]
    except Exception as exc:
        logger.debug("[ArchiGen] Hermes tools indisponibles : %s", exc)
    return []


_NERF_MODULES = [
    ("Nerf 1",      "nerves.hermes_nerves",     "activate_hermes_nerves",     "Outils Hermes réels"),
    ("Nerf 2",      "nerves.cognitive_nerves",  "activate_cognitive_nerves",  "Swarm + Grounding"),
    ("Nerf 3",      "nerves.event_bus_nerves",  "activate_event_bus_nerves",  "Pont Kafka ↔ Async"),
    ("Nerf 4",      "nerves.web_agent_nerves",  "activate_web_agent_nerves",  "WebAgent tracé"),
    ("Nerf 5",      "nerves.approval_nerves",   "activate_approval_nerves",   "Approbation L3+"),
    ("Nerf 6",      "nerves.mcp_nerves",        "activate_mcp_nerves",        "MCP ↔ Hermes"),
    ("Nerf 7",      "nerves.router_nerves",     "activate_router_nerves",     "SmartRouter sémantique"),
    ("Nerf 8",      "nerves.skills_nerves",     "activate_skills_nerves",     "Skills chargés"),
    ("Nerf 9",      "nerves.guardian_nerves",   "activate_guardian_nerves",   "Guardian tracé"),
    ("Nerf 10",     "nerves.crm_nerves",        "activate_crm_nerves",        "Sub-CRM → Hermes"),
    ("Nerf 11-13",  "nerves.headless_nerves",   "activate_headless_nerves",   "Playwright → Hermes"),
    ("Nerf 14-17",  "nerves.tmux_nerves",       "activate_tmux_nerves",       "Tmux → Hermes"),
]


def _detect_nerf_status(module_name: str, func_name: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "unknown",
        "reason": "",
        "module_file": "",
    }
    try:
        file_path = WORKSPACE_DIR / module_name.replace(".", os.sep)
        if not file_path.with_suffix(".py").exists():
            result["status"] = "missing"
            result["reason"] = f"Fichier introuvable : {file_path}.py"
            return result
        result["module_file"] = str(file_path.relative_to(WORKSPACE_DIR))

        try:
            module = __import__(module_name, fromlist=[func_name])
        except ImportError as imp_err:
            result["status"] = "import_error"
            result["reason"] = str(imp_err)[:80]
            return result

        if hasattr(module, "_is_enabled"):
            try:
                enabled = module._is_enabled()
                if enabled:
                    result["status"] = "available"
                    result["reason"] = "Activé au boot"
                else:
                    result["status"] = "disabled"
                    result["reason"] = "Désactivé par feature-flag"
            except Exception as e:
                result["status"] = "unknown"
                result["reason"] = f"_is_enabled() échec : {str(e)[:60]}"
        else:
            result["status"] = "available"
            result["reason"] = "Pas de feature-flag"
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = str(exc)[:80]
    return result


def _collect_nerfs() -> List[Dict[str, Any]]:
    nerfs: List[Dict[str, Any]] = []
    for label, module_name, func_name, role in _NERF_MODULES:
        status = _detect_nerf_status(module_name, func_name)
        nerfs.append({
            "id": label,
            "name": module_name.split(".")[-1],
            "role": role,
            "status": status["status"],
            "reason": status["reason"],
        })
    return nerfs


def _collect_bek_lvc() -> Dict[str, Any]:
    try:
        from bek_core import BekCPU
        if hasattr(BekCPU, "list"):
            briques = BekCPU.list()
        else:
            registry_path = WORKSPACE_DIR / "bek_core" / "registry.json"
            if registry_path.exists():
                data = json.loads(registry_path.read_text(encoding="utf-8"))
                briques = list(data.get("briques", {}).keys())
            else:
                briques = []
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


def _collect_lazy_status() -> Dict[str, Dict[str, Any]]:
    lazy: Dict[str, Dict[str, Any]] = {}

    try:
        from worker_headless import _playwright_loaded
        lazy["playwright"] = {
            "status": "loaded" if _playwright_loaded else "lazy",
            "detail": "~200 MB économisés au boot" if not _playwright_loaded else "Chargé",
        }
    except Exception as exc:
        lazy["playwright"] = {"status": "unavailable", "detail": str(exc)[:60]}

    try:
        from memory import is_chromadb_loaded, is_chromadb_disabled
        if is_chromadb_disabled():
            lazy["chromadb"] = {"status": "disabled", "detail": "BEK_DISABLE_CHROMADB=true"}
        elif is_chromadb_loaded():
            lazy["chromadb"] = {"status": "loaded", "detail": "Chargé à la demande"}
        else:
            lazy["chromadb"] = {"status": "lazy", "detail": "~80 MB économisés au boot"}
    except Exception as exc:
        lazy["chromadb"] = {"status": "unavailable", "detail": str(exc)[:60]}

    try:
        from services.episode_logger import lazy_stats as el_stats
        stats = el_stats()
        lazy["duckdb_episode"] = {
            "status": stats.get("backend", "unknown"),
            "detail": f"Backend : {stats.get('backend', '?')}",
        }
    except Exception as exc:
        lazy["duckdb_episode"] = {"status": "unavailable", "detail": str(exc)[:60]}

    try:
        disable_lancedb = os.getenv("BEK_DISABLE_LANCEDB", "false").lower() in ("true", "1", "yes")
        lazy["lancedb"] = {
            "status": "disabled" if disable_lancedb else "lazy",
            "detail": "BEK_DISABLE_LANCEDB=true" if disable_lancedb else "Chargé à la demande",
        }
    except Exception as exc:
        lazy["lancedb"] = {"status": "unavailable", "detail": str(exc)[:60]}

    try:
        disable_duckdb = os.getenv("BEK_DISABLE_DUCKDB_ANALYTICS", "false").lower() in ("true", "1", "yes")
        lazy["duckdb_analytics"] = {
            "status": "disabled" if disable_duckdb else "lazy",
            "detail": "BEK_DISABLE_DUCKDB_ANALYTICS=true" if disable_duckdb else "Chargé à la demande",
        }
    except Exception as exc:
        lazy["duckdb_analytics"] = {"status": "unavailable", "detail": str(exc)[:60]}

    return lazy


def _collect_skills() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "skills_count": 0,
        "alter_egos": [],
        "alter_egos_count": 0,
    }
    try:
        from skill_registry import skill_registry
        skills = getattr(skill_registry, "skills", {}) or {}
        result["skills_count"] = len(skills)

        try:
            alter_egos = getattr(skill_registry, "alter_egos", {}) or {}
            result["alter_egos"] = list(alter_egos.keys())
            result["alter_egos_count"] = len(alter_egos)
        except Exception:
            pass
    except Exception as exc:
        logger.debug("[ArchiGen] Skills indisponibles : %s", exc)
    return result


def _collect_crm_status() -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": "unknown", "reason": ""}
    try:
        from nerves import crm_nerves
        if hasattr(crm_nerves, "_is_enabled"):
            if crm_nerves._is_enabled():
                result["status"] = "active"
                result["reason"] = "CRM activé"
            else:
                result["status"] = "disabled"
                result["reason"] = "BEK_ENABLE_CRM_NERVES=false"
    except Exception as exc:
        result["status"] = "unavailable"
        result["reason"] = str(exc)[:60]
    return result


def _collect_environment() -> Dict[str, str]:
    keys = [
        "BEK_LAZY_LOAD",
        "BEK_LAZY_LOAD_PLAYWRIGHT",
        "BEK_LAZY_LOAD_CHROMADB",
        "BEK_LAZY_LOAD_DUCKDB",
        "BEK_DISABLE_CHROMADB",
        "BEK_DISABLE_LANCEDB",
        "BEK_DISABLE_DUCKDB_ANALYTICS",
        "BEK_ENABLE_CRM_NERVES",
        "BEK_PROFILE",
    ]
    return {k: os.getenv(k, "(non défini)") for k in keys}


def _collect_modules() -> Dict[str, List[str]]:
    modules: Dict[str, List[str]] = {
        "Moteurs d'exécution": [],
        "Communication inter-agents": [],
        "Mémoire": [],
        "Sécurité": [],
        "Intelligence": [],
        "Routage FastAPI": [],
        "CPU Logique Virtuel": [],
        "Système nerveux": [],
        "Lazy Loading": [],
        "Autres modules racine": [],
    }

    exclude_dirs = {
        "venv", ".venv", "env", "ENV",
        "__pycache__", "node_modules", "data",
        "chroma_db", "generated", "uploads",
        ".git", ".idea", ".vscode",
        "skills", "backups", "docs",
    }

    try:
        for py_file in WORKSPACE_DIR.rglob("*.py"):
            parts = set(py_file.relative_to(WORKSPACE_DIR).parts[:-1])
            if parts & exclude_dirs:
                continue

            rel_path = str(py_file.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            parent = py_file.parent.name

            if "core/lazy" in rel_path:
                modules["Lazy Loading"].append(f"`{rel_path}`")
            elif rel_path.startswith("nerves/"):
                modules["Système nerveux"].append(f"`{rel_path}`")
            elif rel_path.startswith("bek_core/"):
                modules["CPU Logique Virtuel"].append(f"`{rel_path}`")
            elif rel_path.startswith("routers/"):
                modules["Routage FastAPI"].append(f"`{rel_path}`")
            elif rel_path.startswith("services/vision/"):
                modules["Intelligence"].append(f"`{rel_path}`")
            elif rel_path.startswith("services/"):
                modules["Intelligence"].append(f"`{rel_path}`")
            elif rel_path.startswith("core/security/"):
                modules["Sécurité"].append(f"`{rel_path}`")
            elif "memory" in rel_path.lower() or "hindsight" in rel_path.lower():
                modules["Mémoire"].append(f"`{rel_path}`")
            elif "event_bus" in rel_path or "mcp_gateway" in rel_path or "swarm" in rel_path or "grounding" in rel_path:
                modules["Communication inter-agents"].append(f"`{rel_path}`")
            elif "hermes" in rel_path or "worker_headless" in rel_path or "execution_engine" in rel_path or "dag_adapter" in rel_path:
                modules["Moteurs d'exécution"].append(f"`{rel_path}`")
            elif "security" in rel_path or "guard" in rel_path or "sandbox" in rel_path or "path_guard" in rel_path:
                modules["Sécurité"].append(f"`{rel_path}`")
            elif py_file.parent == WORKSPACE_DIR:
                modules["Autres modules racine"].append(f"`{rel_path}`")

        for key in modules:
            modules[key].sort()
    except Exception as exc:
        logger.debug("[ArchiGen] Scan modules échec : %s", exc)

    return modules


# ══════════════════════════════════════════════════════════════════════════════
# ★ v4.0 — SECTION 2.5 : DÉTECTION DE PROBLÈMES (DIAGNOSTIC)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_issues(
    nerfs: List[Dict[str, Any]],
    lazy_status: Dict[str, Dict[str, Any]],
    crm_status: Dict[str, Any],
    providers: List[str],
    tools: List[Dict[str, Any]],
    bek_lvc: Dict[str, Any],
) -> List[ArchitectureIssue]:
    """
    Détecte tous les problèmes d'architecture.

    Returns:
        Liste d'ArchitectureIssue, triée par sévérité.
    """
    issues: List[ArchitectureIssue] = []

    # ─── 1. Nerfs manquants ou en erreur ───
    for n in nerfs:
        if n["status"] == "missing":
            issues.append(ArchitectureIssue(
                severity="critical",
                category="nerf",
                title=f"{n['id']} manquant",
                detail=f"Le fichier du module `{n['name']}` est introuvable.",
                fix_hint=f"Vérifier que le fichier `nerves/{n['name']}.py` existe.",
                source=n["name"],
            ))
        elif n["status"] == "import_error":
            issues.append(ArchitectureIssue(
                severity="critical",
                category="nerf",
                title=f"{n['id']} : erreur d'import",
                detail=n.get("reason", "ImportError"),
                fix_hint=f"Vérifier les dépendances de `{n['name']}`.",
                source=n["name"],
            ))
        elif n["status"] == "error":
            issues.append(ArchitectureIssue(
                severity="warning",
                category="nerf",
                title=f"{n['id']} : erreur de détection",
                detail=n.get("reason", "Erreur inconnue"),
                fix_hint="Vérifier la structure du module.",
                source=n["name"],
            ))

    # ─── 2. Lazy components problématiques ───
    for comp_name, info in lazy_status.items():
        status = info.get("status", "unknown")
        if status == "unavailable":
            issues.append(ArchitectureIssue(
                severity="warning",
                category="lazy",
                title=f"Lazy '{comp_name}' indisponible",
                detail=info.get("detail", "Module non détecté"),
                fix_hint=f"Vérifier que `{comp_name}` est installé et importable.",
                source=comp_name,
            ))

    # ─── 3. CRM désactivé (info) ───
    if crm_status.get("status") == "disabled":
        issues.append(ArchitectureIssue(
            severity="info",
            category="config",
            title="CRM désactivé",
            detail="Le Nerf 10 (CRM) est désactivé — comportement attendu.",
            fix_hint="Pour réactiver : `BEK_ENABLE_CRM_NERVES=true`.",
            source="crm_nerves",
        ))

    # ─── 4. Providers manquants ───
    if len(providers) == 0:
        issues.append(ArchitectureIssue(
            severity="critical",
            category="config",
            title="Aucun provider LLM",
            detail="Aucun provider LLM n'est détecté.",
            fix_hint="Vérifier `provider_manager.py` et les clés API.",
            source="provider_manager",
        ))
    elif len(providers) < 5:
        issues.append(ArchitectureIssue(
            severity="warning",
            category="config",
            title=f"Peu de providers LLM ({len(providers)})",
            detail=f"Seulement {len(providers)} providers détectés.",
            fix_hint="Vérifier les clés API dans `env.txt`.",
            source="provider_manager",
        ))

    # ─── 5. Outils Hermes manquants ───
    if len(tools) == 0:
        issues.append(ArchitectureIssue(
            severity="critical",
            category="config",
            title="Aucun outil Hermes",
            detail="Hermes n'est pas initialisé ou aucun outil n'est enregistré.",
            fix_hint="Vérifier l'import de `hermes_core`.",
            source="hermes_core",
        ))
    elif len(tools) < 20:
        issues.append(ArchitectureIssue(
            severity="warning",
            category="config",
            title=f"Peu d'outils Hermes ({len(tools)})",
            detail=f"Seulement {len(tools)} outils enregistrés (attendu : 40+).",
            fix_hint="Vérifier l'activation des nerfs.",
            source="hermes_core",
        ))

    # ─── 6. BEK-LVC non chargé ───
    if not bek_lvc.get("available"):
        issues.append(ArchitectureIssue(
            severity="critical",
            category="config",
            title="BEK-LVC non chargé",
            detail="Les 6 briques cognitives BEK-LVC ne sont pas accessibles.",
            fix_hint="Vérifier `bek_core/` et `BEK-LVC.md`.",
            source="bek_core",
        ))

    # ─── 7. Variables d'environnement manquantes ───
    env = _collect_environment()
    critical_env = ["BEK_LAZY_LOAD"]
    for key in critical_env:
        if env.get(key) == "(non défini)":
            issues.append(ArchitectureIssue(
                severity="info",
                category="env",
                title=f"Variable {key} non définie",
                detail=f"La variable `{key}` n'est pas définie (valeur par défaut utilisée).",
                fix_hint=f"Ajouter `{key}=true` dans `env.txt`.",
                source="env.txt",
            ))

    # ─── 8. Fichiers critiques manquants ───
    critical_files = [
        ("app.py", "critical"),
        ("hermes_core.py", "critical"),
        ("memory.py", "critical"),
        ("web_agent.py", "critical"),
        ("core/lazy.py", "warning"),
        ("generate_architecture_doc.py", "info"),
    ]
    for rel_path, sev in critical_files:
        full_path = WORKSPACE_DIR / rel_path
        if not full_path.exists():
            issues.append(ArchitectureIssue(
                severity=sev,
                category="module",
                title=f"Fichier manquant : {rel_path}",
                detail=f"Le fichier `{rel_path}` est introuvable.",
                fix_hint=f"Vérifier que `{rel_path}` existe à la racine du projet.",
                source=rel_path,
            ))

    # ─── Tri par sévérité (critical > warning > info) ───
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    return issues


def _log_issues(issues: List[ArchitectureIssue]) -> None:
    """Log les problèmes détectés avec le niveau approprié."""
    if not issues:
        logger.info("✅ [ArchiGen] Aucun problème d'architecture détecté")
        return

    # Compter par sévérité
    counts = {"critical": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1

    summary = (
        f"⚠️ [ArchiGen] {len(issues)} problème(s) détecté(s) : "
        f"{counts['critical']} critique(s), "
        f"{counts['warning']} avertissement(s), "
        f"{counts['info']} info(s)"
    )

    if counts["critical"] > 0:
        logger.error(summary)
    elif counts["warning"] > 0:
        logger.warning(summary)
    else:
        logger.info(summary)

    # Log les critiques et warnings
    for issue in issues:
        if issue.severity == "critical":
            logger.error(
                "[ArchiGen] 🔴 [%s] %s — %s | Fix: %s",
                issue.category, issue.title, issue.detail, issue.fix_hint,
            )
        elif issue.severity == "warning":
            logger.warning(
                "[ArchiGen] 🟠 [%s] %s — %s | Fix: %s",
                issue.category, issue.title, issue.detail, issue.fix_hint,
            )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — STATE HASH
# ══════════════════════════════════════════════════════════════════════════════

def _compute_state_hash(state: Dict[str, Any]) -> str:
    try:
        serialized = json.dumps(state, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:12]
    except Exception as exc:
        logger.debug("[ArchiGen] Hash échec : %s", exc)
        return "unknown"


def _load_previous_state() -> Optional[str]:
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return data.get("state_hash")
    except Exception:
        pass
    return None


def _save_state_hash(state_hash: str, issues_count: int = 0) -> None:
    try:
        STATE_FILE.write_text(
            json.dumps({
                "state_hash": state_hash,
                "issues_count": issues_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("[ArchiGen] Save state échec : %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — GÉNÉRATION DU DOCUMENT
# ══════════════════════════════════════════════════════════════════════════════

def generate_architecture_markdown() -> Tuple[str, List[ArchitectureIssue]]:
    """
    Génère le contenu Markdown complet.

    Returns:
        (markdown_content, list_of_issues)
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # ─── Collecte ───
    bek_version = _collect_bek_version()
    tools = _collect_hermes_tools()
    nerfs = _collect_nerfs()
    bek_lvc = _collect_bek_lvc()
    providers = _collect_providers()
    lazy_status = _collect_lazy_status()
    skills_info = _collect_skills()
    crm_status = _collect_crm_status()
    environment = _collect_environment()
    modules_tree = _collect_modules()

    # ─── Diagnostic ───
    issues = _detect_issues(
        nerfs=nerfs,
        lazy_status=lazy_status,
        crm_status=crm_status,
        providers=providers,
        tools=tools,
        bek_lvc=bek_lvc,
    )
    _log_issues(issues)

    # ─── Hash ───
    state = {
        "version": bek_version,
        "tools": [t.get("name") for t in tools],
        "nerfs": [(n["id"], n["status"]) for n in nerfs],
        "briques": bek_lvc.get("briques", []),
        "providers": providers,
        "lazy": {k: v.get("status") for k, v in lazy_status.items()},
        "skills": skills_info.get("skills_count", 0),
        "alter_egos": skills_info.get("alter_egos", []),
        "crm": crm_status.get("status"),
        "issues": [(i.severity, i.title) for i in issues],
    }
    state_hash = _compute_state_hash(state)

    # ─── Construction du markdown ───
    lines = [
        _PLAN_ACTION,
        "",
        "═══════════════════════════════════════════════════════════════════════════════",
        "## 📊 ÉTAT RÉEL DU SYSTÈME (généré automatiquement)",
        "═══════════════════════════════════════════════════════════════════════════════",
        "",
        f"> *Dernière synchronisation : {now_utc}*",
        f"> *Version BEK : **{bek_version}***",
        f"> *State hash : `{state_hash}`*",
        "",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # ★ v4.0 — SECTION DIAGNOSTIC (en premier pour visibilité)
    # ═══════════════════════════════════════════════════════════════════════════
    lines.append("═══════════════════════════════════════════════════════════════════════════════")
    lines.append("## 🩺 DIAGNOSTIC ARCHITECTURE")
    lines.append("═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")

    counts = {"critical": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1

    if not issues:
        lines.append("✅ **Aucun problème détecté** — Architecture saine.")
    else:
        # Résumé
        lines.append(f"⚠️ **{len(issues)} problème(s) détecté(s) :**")
        lines.append("")
        lines.append(f"- 🔴 **Critiques :** {counts['critical']}")
        lines.append(f"- 🟠 **Avertissements :** {counts['warning']}")
        lines.append(f"- 🔵 **Informations :** {counts['info']}")
        lines.append("")

        # Détails par sévérité
        for severity, icon, label in [
            ("critical", "🔴", "CRITIQUE"),
            ("warning", "🟠", "AVERTISSEMENT"),
            ("info", "🔵", "INFO"),
        ]:
            sev_issues = [i for i in issues if i.severity == severity]
            if not sev_issues:
                continue
            lines.append(f"### {icon} {label} ({len(sev_issues)})")
            lines.append("")
            lines.append("| Catégorie | Problème | Détail | Correction |")
            lines.append("|---|---|---|---|")
            for issue in sev_issues:
                lines.append(
                    f"| `{issue.category}` | **{issue.title}** | "
                    f"{issue.detail} | {issue.fix_hint or '—'} |"
                )
            lines.append("")

    lines.append("")
    lines.append("### 🔌 API de diagnostic")
    lines.append("")
    lines.append("| Endpoint | Description |")
    lines.append("|---|---|")
    lines.append("| `GET /api/architecture/status` | Statut complet + issues |")
    lines.append("| `POST /api/refresh-architecture` | Régénérer ARCHITECTURE.md |")
    lines.append("")

    # ─── Outils Hermes ───
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
        lines.append("*Aucun outil chargé (Hermes non initialisé)*")
    lines.append("")

    # ─── Nerfs ───
    active_nerfs = [n for n in nerfs if n["status"] == "available"]
    disabled_nerfs = [n for n in nerfs if n["status"] == "disabled"]
    missing_nerfs = [n for n in nerfs if n["status"] in ("missing", "import_error", "error")]

    lines.append(f"### 🧠 Système nerveux ({len(nerfs)} nerfs détectés)")
    lines.append("")
    lines.append(f"- ✅ **Actifs :** {len(active_nerfs)}")
    lines.append(f"- ⛔ **Désactivés :** {len(disabled_nerfs)}")
    lines.append(f"- ❌ **Manquants/erreurs :** {len(missing_nerfs)}")
    lines.append("")
    lines.append("| Nerf | Module | Rôle | Statut |")
    lines.append("|---|---|---|---|")
    for nerve in nerfs:
        status_icon = {
            "available": "✅",
            "disabled": "⛔",
            "missing": "❌",
            "import_error": "⚠️",
            "error": "⚠️",
            "unknown": "❓",
        }.get(nerve["status"], "❓")
        lines.append(
            f"| {nerve['id']} | `{nerve['name']}` | {nerve['role']} | "
            f"{status_icon} {nerve['status']} |"
        )
    lines.append("")

    # ─── Lazy Loading ───
    lines.append("### ★ Lazy Loading Status (v18.13)")
    lines.append("")
    lines.append("| Composant | Statut | Détail |")
    lines.append("|---|---|---|")
    for comp, info in lazy_status.items():
        status = info.get("status", "unknown")
        icon = {
            "lazy": "💤",
            "loaded": "✅",
            "disabled": "⛔",
            "unavailable": "❌",
            "duckdb": "✅",
            "sqlite": "⚠️",
        }.get(status, "❓")
        lines.append(f"| `{comp}` | {icon} **{status}** | {info.get('detail', '')} |")
    lines.append("")

    # ─── BEK-LVC ───
    lines.append("### 🏛️ BEK-LVC (6 briques cognitives)")
    lines.append("")
    if bek_lvc.get("available"):
        briques = bek_lvc.get("briques", [])
        lines.append(f"- **Statut :** ✅ Chargé")
        lines.append(f"- **Briques actives ({len(briques)}) :** {', '.join(briques) if briques else 'aucune'}")
    else:
        lines.append("- **Statut :** ❌ Non chargé")
    lines.append("")

    # ─── Skills & Alter Egos ───
    lines.append("### 🎭 Skills & Alter Egos")
    lines.append("")
    lines.append(f"- **Skills chargés :** {skills_info.get('skills_count', 0)}")
    alter_egos = skills_info.get("alter_egos", [])
    if alter_egos:
        lines.append(f"- **Alter Egos ({len(alter_egos)}) :** {', '.join(alter_egos)}")
    else:
        lines.append("- **Alter Egos :** aucun")
    lines.append("")

    # ─── CRM ───
    lines.append("### 🛠️ CRM Status (Nerf 10)")
    lines.append("")
    crm_icon = {"active": "✅", "disabled": "⛔", "unavailable": "❌"}.get(crm_status.get("status"), "❓")
    lines.append(f"- **Statut :** {crm_icon} **{crm_status.get('status', 'unknown')}**")
    lines.append(f"- **Raison :** {crm_status.get('reason', '')}")
    lines.append("")

    # ─── Providers ───
    lines.append(f"### 🌐 Providers LLM disponibles ({len(providers)})")
    lines.append("")
    if providers:
        for p in providers:
            lines.append(f"- `{p}`")
    else:
        lines.append("*Aucun provider*")
    lines.append("")

    # ─── Env ───
    lines.append("### ⚙️ Variables d'environnement BEK")
    lines.append("")
    lines.append("| Variable | Valeur |")
    lines.append("|---|---|")
    for k, v in environment.items():
        lines.append(f"| `{k}` | `{v}` |")
    lines.append("")

    # ─── Modules ───
    lines.append("═══════════════════════════════════════════════════════════════════════════════")
    lines.append("## 🗂️ CARTOGRAPHIE DES MODULES (scannée dynamiquement)")
    lines.append("═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")

    for category, files in modules_tree.items():
        if not files:
            continue
        lines.append(f"### {category} ({len(files)})")
        lines.append("")
        for f in files[:50]:
            lines.append(f"- {f}")
        if len(files) > 50:
            lines.append(f"- *... et {len(files) - 50} autres*")
        lines.append("")

    # ─── Routes API ───
    lines.append("═══════════════════════════════════════════════════════════════════════════════")
    lines.append("## 🛣️ ROUTES API PRINCIPALES")
    lines.append("═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("| Méthode | Route | Description |")
    lines.append("|---|---|---|")
    lines.append("| `POST` | `/api/chat` | Chat principal (orchestrateur) |")
    lines.append("| `GET`  | `/api/chat/debug` | Debug complet |")
    lines.append("| `GET`  | `/api/config` | Config providers + skills |")
    lines.append("| `GET`  | `/api/architecture/status` | **★ Diagnostic architecture** |")
    lines.append("| `POST` | `/api/refresh-architecture` | **★ Régénérer ce document** |")
    lines.append("| `POST` | `/api/feedback` | Soumettre un feedback |")
    lines.append("| `GET`  | `/api/feedback` | Liste + stats des feedbacks |")
    lines.append("| `GET`  | `/api/hindsight/status` | État Hindsight |")
    lines.append("| `GET`  | `/api/hindsight/query` | Interroger Hindsight |")
    lines.append("| `POST` | `/api/admin/flush-redis` | Vider Redis Streams |")
    lines.append("| `POST` | `/api/skills/execute` | Exécuter un skill |")
    lines.append("| `GET`  | `/health/worker` | Health check worker |")
    lines.append("| `GET`  | `/health/memory` | **★ Health check mémoire + lazy** |")
    lines.append("| `POST` | `/v1/chat/completions` | Façade OpenAI-compatible |")
    lines.append("| `GET`  | `/v1/models` | Liste des modèles OpenAI-compat |")
    lines.append("")

    return "\n".join(lines), issues


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — ÉCRITURE FICHIER
# ══════════════════════════════════════════════════════════════════════════════

def update_documentation_file(force: bool = False) -> bool:
    """
    Met à jour le fichier ARCHITECTURE.md + cache les diagnostics.

    Args:
        force: Si True, force la régénération même si rien n'a changé.

    Returns:
        True si succès, False si erreur.
    """
    try:
        # ─── Collecte rapide pour hash ───
        state = {
            "version": _collect_bek_version(),
            "tools": [t.get("name") for t in _collect_hermes_tools()],
            "nerfs": [(n["id"], n["status"]) for n in _collect_nerfs()],
            "briques": _collect_bek_lvc().get("briques", []),
            "providers": _collect_providers(),
            "lazy": {k: v.get("status") for k, v in _collect_lazy_status().items()},
            "skills": _collect_skills().get("skills_count", 0),
            "crm": _collect_crm_status().get("status"),
        }
        current_hash = _compute_state_hash(state)
        previous_hash = _load_previous_state()

        # ─── Skip si inchangé ───
        if not force and previous_hash == current_hash and TARGET_FILE.exists():
            logger.debug("[ArchiGen] State inchangé, pas de régénération")
            return True

        # ─── Générer ───
        content, issues = generate_architecture_markdown()

        # ─── Écrire ───
        with open(TARGET_FILE, "w", encoding="utf-8") as fh:
            fh.write(content)

        # ─── Cache diagnostics (pour API) ───
        with _DIAGNOSTICS_LOCK:
            _DIAGNOSTICS_CACHE["issues"] = [asdict(i) for i in issues]
            _DIAGNOSTICS_CACHE["summary"] = {
                "total": len(issues),
                "critical": sum(1 for i in issues if i.severity == "critical"),
                "warning": sum(1 for i in issues if i.severity == "warning"),
                "info": sum(1 for i in issues if i.severity == "info"),
                "healthy": len(issues) == 0,
            }
            _DIAGNOSTICS_CACHE["last_check"] = datetime.now(timezone.utc).isoformat()
            _DIAGNOSTICS_CACHE["state_hash"] = current_hash

        # ─── Sauvegarder hash ───
        _save_state_hash(current_hash, issues_count=len(issues))

        logger.info(
            "✅ [ArchiGen] Architecture mise à jour : %s (%d chars) | "
            "hash=%s | issues=%d",
            TARGET_FILE, len(content), current_hash, len(issues),
        )
        return True

    except Exception as exc:
        logger.error("[ArchiGen] Échec génération : %s", exc, exc_info=True)
        return False


def refresh_if_stale(max_age_seconds: int = 300) -> bool:
    try:
        if not TARGET_FILE.exists():
            return update_documentation_file(force=True)
        age = time.time() - TARGET_FILE.stat().st_mtime
        if age > max_age_seconds:
            logger.info("[ArchiGen] Fichier vieux de %.0fs → régénération", age)
            return update_documentation_file(force=True)
        return True
    except Exception as exc:
        logger.debug("[ArchiGen] refresh_if_stale échec : %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# ★ v4.0 — SECTION 6 : API PUBLIQUE POUR FASTAPI
# ══════════════════════════════════════════════════════════════════════════════

def get_cached_diagnostics() -> Dict[str, Any]:
    """
    Retourne les diagnostics en cache (pour FastAPI).

    Returns:
        Dict avec issues, summary, last_check, state_hash.
    """
    with _DIAGNOSTICS_LOCK:
        return {
            "issues": list(_DIAGNOSTICS_CACHE.get("issues", [])),
            "summary": dict(_DIAGNOSTICS_CACHE.get("summary", {})),
            "last_check": _DIAGNOSTICS_CACHE.get("last_check"),
            "state_hash": _DIAGNOSTICS_CACHE.get("state_hash"),
        }


def get_architecture_status() -> Dict[str, Any]:
    """
    Retourne un statut complet de l'architecture (pour FastAPI).

    Contient :
      - version
      - diagnostics (issues)
      - status (healthy / degraded / broken)
      - counts (nerfs, tools, providers)
    """
    diag = get_cached_diagnostics()
    summary = diag.get("summary", {})

    # Déterminer le statut global
    if summary.get("critical", 0) > 0:
        status = "broken"
    elif summary.get("warning", 0) > 0:
        status = "degraded"
    else:
        status = "healthy"

    # Collecter quelques stats rapides
    try:
        tools = _collect_hermes_tools()
        nerfs = _collect_nerfs()
        providers = _collect_providers()
    except Exception:
        tools, nerfs, providers = [], [], []

    return {
        "status": status,
        "version": _collect_bek_version(),
        "state_hash": diag.get("state_hash"),
        "last_check": diag.get("last_check"),
        "summary": summary,
        "counts": {
            "tools": len(tools),
            "nerfs": len(nerfs),
            "nerfs_active": sum(1 for n in nerfs if n["status"] == "available"),
            "providers": len(providers),
        },
        "issues": diag.get("issues", []),
    }


def force_refresh() -> Dict[str, Any]:
    """Force une régénération et retourne le statut."""
    update_documentation_file(force=True)
    return get_architecture_status()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — WATCHER
# ══════════════════════════════════════════════════════════════════════════════

_watcher_thread: Optional[threading.Thread] = None
_watcher_stop_event = threading.Event()


def _watcher_loop(interval_sec: int = 60) -> None:
    logger.info("[ArchiGen] Watcher démarré (interval=%ds)", interval_sec)
    while not _watcher_stop_event.is_set():
        try:
            update_documentation_file(force=False)
        except Exception as exc:
            logger.debug("[ArchiGen] Watcher erreur : %s", exc)
        _watcher_stop_event.wait(timeout=interval_sec)
    logger.info("[ArchiGen] Watcher arrêté")


def start_watcher(interval_sec: int = 60) -> bool:
    global _watcher_thread
    if _watcher_thread is not None and _watcher_thread.is_alive():
        return False
    _watcher_stop_event.clear()
    _watcher_thread = threading.Thread(
        target=_watcher_loop,
        args=(interval_sec,),
        daemon=True,
        name="ArchiGen-Watcher",
    )
    _watcher_thread.start()
    logger.info("[ArchiGen] Watcher démarré en arrière-plan")
    return True


def stop_watcher() -> None:
    global _watcher_thread
    _watcher_stop_event.set()
    if _watcher_thread is not None:
        _watcher_thread.join(timeout=5)
        _watcher_thread = None


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="BEK Architecture Generator v4.0 — Ultra dynamique + Diagnostic",
    )
    parser.add_argument("--force", "-f", action="store_true", help="Force la régénération")
    parser.add_argument("--watch", "-w", action="store_true", help="Démarre le watcher")
    parser.add_argument("--interval", "-i", type=int, default=60, help="Intervalle watcher")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logs détaillés")
    parser.add_argument("--diagnostic", "-d", action="store_true", help="Affiche uniquement le diagnostic")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    # Mode diagnostic uniquement
    if args.diagnostic:
        status = force_refresh()
        print(json.dumps(status, indent=2, ensure_ascii=False, default=str))
        return 0 if status.get("status") != "broken" else 1

    # Génération
    success = update_documentation_file(force=args.force)
    if not success:
        print("❌ Échec de la génération")
        return 1

    print(f"✅ ARCHITECTURE.md généré : {TARGET_FILE}")

    # Afficher un résumé des issues
    diag = get_cached_diagnostics()
    summary = diag.get("summary", {})
    if summary.get("total", 0) > 0:
        print(f"\n⚠️ {summary['total']} problème(s) détecté(s) :")
        print(f"   🔴 Critiques : {summary.get('critical', 0)}")
        print(f"   🟠 Avertissements : {summary.get('warning', 0)}")
        print(f"   🔵 Informations : {summary.get('info', 0)}")

        for issue in diag.get("issues", [])[:5]:
            icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}.get(issue["severity"], "❓")
            print(f"   {icon} {issue['title']}")
    else:
        print("\n✅ Aucun problème détecté")

    # Mode watch
    if args.watch:
        print(f"\n👁️ Démarrage du watcher (interval={args.interval}s)")
        start_watcher(interval_sec=args.interval)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Arrêt du watcher")
            stop_watcher()

    return 0


if __name__ == "__main__":
    sys.exit(main())