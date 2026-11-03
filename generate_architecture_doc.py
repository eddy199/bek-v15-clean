# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Générateur d'architecture dynamique ULTRA INTELLIGENT
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Générer docs/ARCHITECTURE.md avec un VRAI plan d'action
# 📄 Appelé au boot par app.py + disponible en CLI + appelable à chaud via API
# ------------------------------------------------------------------------------
# Version : 4.4
# Date : 2026-10-30
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

WORKSPACE_DIR = Path(__file__).resolve().parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

DOCS_DIR = WORKSPACE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FILE = DOCS_DIR / "ARCHITECTURE.md"
STATE_FILE = DOCS_DIR / ".archigen_state.json"

logger = logging.getLogger("BEKApp")

@dataclass
class ArchitectureIssue:
    severity: str
    category: str
    title: str
    detail: str
    fix_hint: str = ""
    source: str = ""

_DIAGNOSTICS_CACHE: Dict[str, Any] = {
    "issues": [],
    "summary": {},
    "last_check": None,
    "state_hash": None,
}
_DIAGNOSTICS_LOCK = threading.Lock()

def _is_boot_early() -> bool:
    try:
        if "nerves.hermes_nerves" not in sys.modules:
            return True
        hermes_nerves = sys.modules["nerves.hermes_nerves"]
        if hasattr(hermes_nerves, "_ACTIVATED") and hermes_nerves._ACTIVATED:
            return False
        if hasattr(hermes_nerves, "activated") and hermes_nerves.activated:
            return False
        try:
            from hermes_core import hermes
            if hasattr(hermes, "tools"):
                nb_tools = len(hermes.tools)
                return nb_tools < 20
        except Exception:
            pass
        return True
    except Exception:
        return True

def _collect_bek_version() -> str:
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
    # ★ Désactivé — CRM retiré de l'architecture
    # ("Nerf 10",   "nerves.crm_nerves",        "activate_crm_nerves",        "Sub-CRM → Hermes"),
    ("Nerf 11-13",  "nerves.headless_nerves",   "activate_headless_nerves",   "Playwright → Hermes"),
    ("Nerf 14-17",  "nerves.tmux_nerves",       "activate_tmux_nerves",       "Tmux → Hermes"),
]

_NERF_ENV_MAPPING = {
    "nerves.hermes_nerves":     "BEK_ENABLE_HERMES_NERVES",
    "nerves.cognitive_nerves":  "BEK_ENABLE_COGNITIVE_NERVES",
    "nerves.event_bus_nerves":  "BEK_ENABLE_EVENT_BUS_NERVES",
    "nerves.web_agent_nerves":  "BEK_ENABLE_WEB_AGENT_NERVES",
    "nerves.approval_nerves":   "BEK_ENABLE_APPROVAL_NERVES",
    "nerves.mcp_nerves":        "BEK_ENABLE_MCP_NERVES",
    "nerves.router_nerves":     "BEK_ENABLE_ROUTER_NERVES",
    "nerves.skills_nerves":     "BEK_ENABLE_SKILLS_NERVES",
    "nerves.guardian_nerves":   "BEK_ENABLE_GUARDIAN_NERVES",
    "nerves.headless_nerves":   "BEK_ENABLE_HEADLESS_NERVES",
    "nerves.tmux_nerves":       "BEK_ENABLE_TMUX_NERVES",
}

def _detect_nerf_status(module_name: str, func_name: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "unknown",
        "reason": "",
        "module_file": "",
    }

    try:
        file_path = WORKSPACE_DIR / module_name.replace(".", os.sep)
        py_file = file_path.with_suffix(".py")
        
        env_var = _NERF_ENV_MAPPING.get(module_name)
        default_value = "false" if "CRM" in (env_var or "") else "true"
        env_value = os.getenv(env_var, default_value).lower() if env_var else "true"
        is_disabled = env_value not in ("true", "1", "yes", "on")
        
        if not py_file.exists():
            if is_disabled:
                result["status"] = "disabled"
                result["reason"] = f"Fichier absent + {env_var}=false (normal)"
            else:
                result["status"] = "missing"
                result["reason"] = f"Fichier introuvable : {py_file.name}"
            return result
            
        result["module_file"] = str(py_file.relative_to(WORKSPACE_DIR))

        if env_var is None:
            result["status"] = "available"
            result["reason"] = "Pas de feature-flag"
            return result

        if is_disabled:
            result["status"] = "disabled"
            result["reason"] = f"{env_var}={env_value}"
        else:
            result["status"] = "available"
            result["reason"] = f"{env_var}={env_value}"

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
        from services.episode_logger import _detect_backend
        backend = _detect_backend()
        lazy["duckdb_episode"] = {
            "status": backend,
            "detail": f"Backend : {backend}",
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


def _collect_environment() -> Dict[str, str]:
    keys = [
        "BEK_LAZY_LOAD",
        "BEK_LAZY_LOAD_PLAYWRIGHT",
        "BEK_LAZY_LOAD_CHROMADB",
        "BEK_LAZY_LOAD_DUCKDB",
        "BEK_DISABLE_CHROMADB",
        "BEK_DISABLE_LANCEDB",
        "BEK_DISABLE_DUCKDB_ANALYTICS",
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
        "bek-v15-clean",
    }

    try:
        for root, dirs, files in os.walk(WORKSPACE_DIR, topdown=True):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                py_file = Path(root) / filename
                try:
                    rel_path = str(py_file.relative_to(WORKSPACE_DIR)).replace("\\", "/")
                except ValueError:
                    continue

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
                elif any(k in rel_path for k in ("event_bus", "mcp_gateway", "swarm", "grounding")):
                    modules["Communication inter-agents"].append(f"`{rel_path}`")
                elif any(k in rel_path for k in ("hermes", "worker_headless", "execution_engine", "dag_adapter")):
                    modules["Moteurs d'exécution"].append(f"`{rel_path}`")
                elif any(k in rel_path for k in ("security", "guard", "sandbox", "path_guard")):
                    modules["Sécurité"].append(f"`{rel_path}`")
                elif py_file.parent == WORKSPACE_DIR:
                    modules["Autres modules racine"].append(f"`{rel_path}`")

        for key in modules:
            modules[key].sort()
    except Exception as exc:
        logger.debug("[ArchiGen] Scan modules échec : %s", exc)

    return modules

def _detect_issues(
    nerfs: List[Dict[str, Any]],
    lazy_status: Dict[str, Dict[str, Any]],
    providers: List[str],
    tools: List[Dict[str, Any]],
    bek_lvc: Dict[str, Any],
) -> List[ArchitectureIssue]:

    issues: List[ArchitectureIssue] = []

    boot_early = _is_boot_early()
    if boot_early:
        logger.debug("[ArchiGen] Boot précoce détecté → warnings 'peu d'outils' ignorés")

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

    if len(providers) == 0:
        issues.append(ArchitectureIssue(
            severity="critical",
            category="config",
            title="Aucun provider LLM",
            detail="Aucun provider LLM n'est détecté.",
            fix_hint="Vérifier `provider_manager.py` et les clés API.",
            source="provider_manager",
        ))
    elif len(providers) < 5 and not boot_early:
        issues.append(ArchitectureIssue(
            severity="warning",
            category="config",
            title=f"Peu de providers LLM ({len(providers)})",
            detail=f"Seulement {len(providers)} providers détectés.",
            fix_hint="Vérifier les clés API dans `env.txt`.",
            source="provider_manager",
        ))

    if len(tools) == 0:
        issues.append(ArchitectureIssue(
            severity="critical",
            category="config",
            title="Aucun outil Hermes",
            detail="Hermes n'est pas initialisé ou aucun outil n'est enregistré.",
            fix_hint="Vérifier l'import de `hermes_core`.",
            source="hermes_core",
        ))
    elif len(tools) < 20 and not boot_early:
        issues.append(ArchitectureIssue(
            severity="warning",
            category="config",
            title=f"Peu d'outils Hermes ({len(tools)})",
            detail=f"Seulement {len(tools)} outils enregistrés (attendu : 40+).",
            fix_hint="Vérifier l'activation des nerfs.",
            source="hermes_core",
        ))

    if not bek_lvc.get("available"):
        issues.append(ArchitectureIssue(
            severity="critical",
            category="config",
            title="BEK-LVC non chargé",
            detail="Les 6 briques cognitives BEK-LVC ne sont pas accessibles.",
            fix_hint="Vérifier `bek_core/` et `BEK-LVC.md`.",
            source="bek_core",
        ))

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

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    return issues

def _log_issues(issues: List[ArchitectureIssue]) -> None:
    if not issues:
        logger.info("✅ [ArchiGen] Aucun problème d'architecture détecté")
        return

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

def generate_architecture_markdown() -> Tuple[str, List[ArchitectureIssue]]:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    bek_version = _collect_bek_version()
    tools = _collect_hermes_tools()
    nerfs = _collect_nerfs()
    bek_lvc = _collect_bek_lvc()
    providers = _collect_providers()
    lazy_status = _collect_lazy_status()
    skills_info = _collect_skills()
    environment = _collect_environment()
    modules_tree = _collect_modules()

    boot_early = _is_boot_early()
    boot_phase = "early" if boot_early else "complete"

    issues = _detect_issues(
        nerfs=nerfs,
        lazy_status=lazy_status,
        providers=providers,
        tools=tools,
        bek_lvc=bek_lvc,
    )
    _log_issues(issues)

    state = {
        "version": bek_version,
        "tools": [t.get("name") for t in tools],
        "nerfs": [(n["id"], n["status"]) for n in nerfs],
        "briques": bek_lvc.get("briques", []),
        "providers": providers,
        "lazy": {k: v.get("status") for k, v in lazy_status.items()},
        "skills": skills_info.get("skills_count", 0),
        "alter_egos": skills_info.get("alter_egos", []),
        "issues": [(i.severity, i.title) for i in issues],
        "boot_phase": boot_phase,
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
        f"> *Boot phase : **{boot_phase}***",
        "",
    ]

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
        lines.append(f"⚠️ **{len(issues)} problème(s) détecté(s) :**")
        lines.append("")
        lines.append(f"- 🔴 **Critiques :** {counts['critical']}")
        lines.append(f"- 🟠 **Avertissements :** {counts['warning']}")
        lines.append(f"- 🔵 **Informations :** {counts['info']}")
        lines.append("")

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

    lines.append("### 🏛️ BEK-LVC (6 briques cognitives)")
    lines.append("")
    if bek_lvc.get("available"):
        briques = bek_lvc.get("briques", [])
        lines.append(f"- **Statut :** ✅ Chargé")
        lines.append(f"- **Briques actives ({len(briques)}) :** {', '.join(briques) if briques else 'aucune'}")
    else:
        lines.append("- **Statut :** ❌ Non chargé")
    lines.append("")
    lines.append("### 🎭 Skills & Alter Egos")
    lines.append("")
    lines.append(f"- **Skills chargés :** {skills_info.get('skills_count', 0)}")
    alter_egos = skills_info.get("alter_egos", [])
    if alter_egos:
        lines.append(f"- **Alter Egos ({len(alter_egos)}) :** {', '.join(alter_egos)}")
    else:
        lines.append("- **Alter Egos :** aucun")
    lines.append("")

    lines.append(f"### 🌐 Providers LLM disponibles ({len(providers)})")
    lines.append("")
    if providers:
        for p in providers:
            lines.append(f"- `{p}`")
    else:
        lines.append("*Aucun provider*")
    lines.append("")

    lines.append("### ⚙️ Variables d'environnement BEK")
    lines.append("")
    lines.append("| Variable | Valeur |")
    lines.append("|---|---|")
    for k, v in environment.items():
        lines.append(f"| `{k}` | `{v}` |")
    lines.append("")

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


def update_documentation_file(force: bool = False) -> bool:
    """
    Génère et écrit ARCHITECTURE.md.
    Si force=False (boot), skip si le state n'a pas changé.
    """
    import time as _time
    t0 = _time.monotonic()

    try:
        # ─── Collecte RAPIDE pour hash ───
        state = {
            "version": _collect_bek_version(),
            "tools": [t.get("name") for t in _collect_hermes_tools()],
            "nerfs": [(n["id"], n["status"]) for n in _collect_nerfs()],
            "briques": _collect_bek_lvc().get("briques", []),
            "providers": _collect_providers(),
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

        elapsed = (_time.monotonic() - t0) * 1000
        logger.info(
            "✅ [ArchiGen] Architecture mise à jour : %s (%d chars) | "
            "hash=%s | issues=%d | %.0fms",
            TARGET_FILE, len(content), current_hash, len(issues), elapsed,
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


def get_cached_diagnostics() -> Dict[str, Any]:
    """Retourne les diagnostics en cache (pour FastAPI)."""
    with _DIAGNOSTICS_LOCK:
        return {
            "issues": list(_DIAGNOSTICS_CACHE.get("issues", [])),
            "summary": dict(_DIAGNOSTICS_CACHE.get("summary", {})),
            "last_check": _DIAGNOSTICS_CACHE.get("last_check"),
            "state_hash": _DIAGNOSTICS_CACHE.get("state_hash"),
        }


def get_architecture_status() -> Dict[str, Any]:
    """Retourne un statut complet de l'architecture (pour FastAPI)."""
    diag = get_cached_diagnostics()
    summary = diag.get("summary", {})

    if summary.get("critical", 0) > 0:
        status = "broken"
    elif summary.get("warning", 0) > 0:
        status = "degraded"
    else:
        status = "healthy"

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
        "boot_phase": "early" if _is_boot_early() else "complete",
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


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="BEK Architecture Generator v4.4 — Ultra dynamique + Diagnostic",
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

    if args.diagnostic:
        status = force_refresh()
        print(json.dumps(status, indent=2, ensure_ascii=False, default=str))
        return 0 if status.get("status") != "broken" else 1

    success = update_documentation_file(force=args.force)
    if not success:
        print("❌ Échec de la génération")
        return 1

    print(f"✅ ARCHITECTURE.md généré : {TARGET_FILE}")

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
       