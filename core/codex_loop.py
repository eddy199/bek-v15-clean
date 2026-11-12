# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v19 — CODEX LOOP (v7.29 — Respect Strict du Provider + Fix ReflexLoop)
# ★ FIX v7.29 : 
#   - Suppression du fallback forcé sur Groq (fallback_chain) quand l'utilisateur 
#     a explicitement choisi un provider (ex: Gemini).
#   - Correction de _fetch_lessons_from_memory pour lire correctement la mémoire.
# ==============================================================================
from __future__ import annotations

import json
import logging
import re
import time
from bek_core.genes.gene_manager import gene_manager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.code_tools import (
    read_file, read_file_map, edit_file, write_file, append_file,
    create_dir, bash, grep, ls, glob_files
)

try:
    from bek_core import BekCPU
    BEK_CPU_AVAILABLE = True
except ImportError:
    BEK_CPU_AVAILABLE = False

logger = logging.getLogger("bek.core.codex_loop")

# ==============================================================================
# MESURE BEK-LVC
# ==============================================================================
_LVC_STATS: Dict[str, int] = {
    "calls": 0, "in_tok": 0, "out_tok": 0, "lvc_calls": 0, "retries": 0,
}

def _reset_lvc_stats() -> None:
    _LVC_STATS.update({"calls": 0, "in_tok": 0, "out_tok": 0, "lvc_calls": 0, "retries": 0})

def _log_lvc_stats(label: str) -> None:
    logger.info(
        "[Codex Loop] 📊 %s — cumul: %d appels | in≈%d tok | out≈%d tok | LVC→native:%d | retries:%d",
        label, _LVC_STATS["calls"], _LVC_STATS["in_tok"], _LVC_STATS["out_tok"],
        _LVC_STATS["lvc_calls"], _LVC_STATS["retries"],
    )

def _log_facture(label: str) -> None:
    """★ FACTURE LVC : log systématique (PLAN, STEP, AUTO)."""
    in_tok = _LVC_STATS["in_tok"]
    lvc_calls = _LVC_STATS["lvc_calls"]
    if in_tok > 0:
        base_tok = int(in_tok * 1.35)
        lvc_savings = lvc_calls * 250
        total_savings = (base_tok - in_tok) + lvc_savings
        pct = int((total_savings / max(1, base_tok)) * 100) if base_tok else 0
        logger.info(
            "[💰 FACTURE] %s : %d tokens (in) | LVC appels : %d | Économie : -%d tokens (-%d%%)",
            label, in_tok, lvc_calls, total_savings, pct,
        )

def _auto_summary(history: List[Dict[str, Any]], raw_summary: Optional[str]) -> str:
    if raw_summary and str(raw_summary).strip():
        return str(raw_summary).strip()
    if not history:
        return "Aucune action."
    tools_used = [h.get("tool", "?") for h in history]
    unique_tools = ", ".join(sorted(set(tools_used)))
    return f"{len(history)} action(s) : {unique_tools}"

def _compress_tool_result(tool: str, res_dict: Dict[str, Any]) -> str:
    status = res_dict.get("status", "ok")

    if status == "error":
        return f"❌ {tool} ERR: {str(res_dict.get('message', 'Erreur'))[:80]}"

    path = res_dict.get("path", "")
    chars = res_dict.get("chars") or res_dict.get("total_size") or 0
    syntax = res_dict.get("syntax_check", "")

    if path or chars:
        parts = [f"✅ {tool}:"]
        if path: parts.append(path)
        if chars: parts.append(f"({chars}c)")
        if syntax: parts.append(f"[{syntax}]")
        return " ".join(parts)

    results = res_dict.get("results") or res_dict.get("data") or res_dict.get("links")
    if isinstance(results, list) and results:
        compressed = []
        for r in results[:3]:
            if isinstance(r, dict):
                title = str(r.get("title", r.get("name", "Sans titre")))[:40]
                url = str(r.get("url", r.get("link", "")))[:60]
                snippet = str(r.get("snippet", r.get("content", "")))[:100]
                compressed.append(f"- {title} ({url}) : {snippet}")
            else:
                compressed.append(str(r)[:100])
        return f"✅ {tool} (Top {len(compressed)}):\n" + "\n".join(compressed)

    if "text" in res_dict:
        return f"✅ {tool}:\n{str(res_dict['text'])[:1000]}..."

    return f"✅ {tool}: " + str(res_dict.get("message", "OK"))[:60]

def _parse_pytest_output(stdout: str, stderr: str) -> str:
    output = (stdout or "") + (stderr or "")
    if "passed" in output and "failed" not in output and "error" not in output:
        return "✅ TESTS PASSED"

    match = re.search(r"(FAILED .*?)(?:\n|$)", output)
    if match:
        fail_line = match.group(1).strip()
        line_match = re.search(r"test_calculator.py:(\d+)", output)
        line_info = f" (L.{line_match.group(1)})" if line_match else ""

        assert_match = re.search(r"(TypeError|AssertionError|ValueError):?(.*?)(?:\n|$)", output)
        if assert_match:
            return f"❌ TEST FAILED: {fail_line}{line_info} - {assert_match.group(1)} {assert_match.group(2).strip()[:50]}"
        return f"❌ TEST FAILED: {fail_line}{line_info}"

    return f"❌ TEST ERROR: {output[:120]}..."

def _load_relevant_skills_lvc(goal: str, budget: Dict[str, int]) -> str:
    skills_dir = Path(__file__).resolve().parent.parent / "skills"
    if not skills_dir.exists():
        return ""

    goal_lower = (goal or "").lower()
    domain_priority = []
    if any(k in goal_lower for k in ["python", "script", "api", "backend"]):
        domain_priority = ["python", "backend", "software-engineering"]
    elif any(k in goal_lower for k in ["godot", "gdscript", "unity", "unreal"]):
        domain_priority = ["game-development", "godot", "gdscript", "gamedev"]

    foundational = ["architecture", "debugging", "software-engineering"]
    candidates = []
    banned_files = {"license", "readme.md", "third_party_notices.md"}

    for f in skills_dir.rglob("*"):
        if not f.is_file() or f.name.startswith(".") or f.name.lower() in banned_files:
            continue
        if f.suffix.lower() not in (".md", ".txt"):
            continue

        rel_str = str(f.relative_to(skills_dir)).lower().replace("\\", "/")
        score = 0
        if any(k in rel_str for k in foundational): score += 8
        for i, domain in enumerate(domain_priority):
            if domain in rel_str: score += 10 - i
            break

        if score > 0:
            candidates.append((score, f))

    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:budget["skills_count"]]

    lvc_map = {
        "write_file": "w", "append_file": "a", "read_file": "r", "read_file_map": "rm",
        "edit_file": "e", "create_dir": "d", "grep": "g", "glob_files": "f", "bash": "b"
    }

    text = ""
    total_chars = 0

    for _score, f in candidates:
        if total_chars >= budget["total_skill_chars"]:
            break

        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            content = re.sub(r"```[a-zA-Z]*\n?", "", content)
            content = re.sub(r"^#+\s+", "", content, flags=re.MULTILINE)
            content = re.sub(r"^\s*[-*]\s+", "", content, flags=re.MULTILINE)
            content = re.sub(r"[*_]{1,3}", "", content)
            content = re.sub(r"\n{2,}", "\n", content)
            content = re.sub(r" {2,}", " ", content).strip()

            for native, code in lvc_map.items():
                content = content.replace(native, code)

            max_len = budget["skill_chars"]
            if len(content) > max_len:
                content = content[:max_len] + "..."

            text += f"\n[SKILL: {f.stem}]\n{content}\n"
            total_chars += len(content)

        except Exception:
            pass

    if text:
        logger.info("[Codex Loop] 📚 LVC-Skills chargés : %d chars (~%d tokens)", len(text), len(text)//3)
    return text

# ★ FIX ReflexLoop — lecture des leçons gravées en mémoire
def _fetch_lessons_from_memory(goal: str) -> str:
    """Interroge la mémoire vectorielle pour récupérer les erreurs passées liées à cet objectif."""
    try:
        from memory import search_memory
        # ★ FIX : On utilise le bon paramètre attendu par search_memory
        results = search_memory(f"[LECON CODEX] {goal}", top_k=3)
        if results:
            logger.info("[Codex Loop] 🧠 Leçons passées trouvées en mémoire (ReflexLoop)")
            return f"\n\n=== LEÇONS DU PASSÉ (REFLEX LOOP) ===\n{results}\nÉvite de refaire ces erreurs.\n"
    except Exception as e:
        logger.warning(f"[Codex Loop] Impossible de lire la mémoire: {e}") # Passé en warning pour que tu le vois
    return ""

# ==============================================================================
# CONSTANTES
# ==============================================================================
LOCAL_TOOLS = {
    "read_file": read_file, "read_file_map": read_file_map, "edit_file": edit_file, "write_file": write_file,
    "append_file": append_file, "create_dir": create_dir, "bash": bash,
    "grep": grep, "ls": ls, "glob_files": glob_files,
}

EXTERNAL_ALLOWED_TOOLS = {
    "headless_render", "web_search", "web_search_docs", "headless_search",
    "headless_scrape", "web_agent_scrape", "web_agent_traced",
    "guardian_status", "guardian_audit_log", "cognitive_critique",
    "cognitive_ground", "search_skills", "mcp_list_tools", "mcp_execute",
}

BEK_TO_HERMES = {
    "w": "write_file", "a": "append_file", "r": "read_file", "rm": "read_file_map",
    "e": "edit_file", "d": "create_dir", "g": "grep", "f": "glob_files",
    "ls": "ls", "b": "bash", "sw": "web_search", "hs": "headless_scrape",
    "bek-fs.write": "write_file", "bek-fs.append": "append_file", "bek-fs.read": "read_file",
    "bek-sh.run": "bash", "bek-search.web": "web_search",
}
BEK_LVC_TOOLS = set(BEK_TO_HERMES.keys())

TERMINAL_ACTIONS = {"done", "none", "finish", "complete", "terminate", "end", "d1"}

MAX_TOKENS_LLM = 8192
MAX_ACTIONS_PER_STEP = 5
MAX_RESULT_CHARS = 4000
MAX_INVALID_JSON_STREAK = 6

PATH_ALIASES = ("path", "file", "filename", "target_file", "name", "f")
CONTENT_ALIASES = ("content", "text", "data", "code", "body", "value", "c")
OLD_ALIASES = ("old_string", "old_str", "search", "find", "o")
NEW_ALIASES = ("new_string", "new_str", "replace", "replacement", "n")

TOOL_ARG_SCHEMA: Dict[str, Tuple[Tuple[str, Tuple[str, ...]], ...]] = {
    "write_file": (("path", PATH_ALIASES), ("content", CONTENT_ALIASES)),
    "append_file": (("path", PATH_ALIASES), ("content", CONTENT_ALIASES)),
    "edit_file": (("path", PATH_ALIASES), ("old_string", OLD_ALIASES), ("new_string", NEW_ALIASES)),
    "create_dir": (("path", PATH_ALIASES),),
    "read_file": (("path", PATH_ALIASES),),
    "read_file_map": (("path", PATH_ALIASES),),
    "ls": (), "grep": (("pattern", ("pattern", "query", "regex", "search", "p")),),
    "glob_files": (("pattern", ("pattern", "query", "glob", "p")),),
    "bash": (("cmd", ("cmd", "command", "shell", "script", "c")),),
    "w": (("path", PATH_ALIASES), ("content", CONTENT_ALIASES)),
    "a": (("path", PATH_ALIASES), ("content", CONTENT_ALIASES)),
    "e": (("path", PATH_ALIASES), ("old_string", OLD_ALIASES), ("new_string", NEW_ALIASES)),
    "d": (("path", PATH_ALIASES),),
    "r": (("path", PATH_ALIASES),),
    "rm": (("path", PATH_ALIASES),),
    "g": (("pattern", ("pattern", "query", "regex", "search", "p")),),
    "f": (("pattern", ("pattern", "query", "glob", "p")),),
    "b": (("cmd", ("cmd", "command", "shell", "script", "c")),),
    "sw": (("query", ("query", "search", "text", "prompt", "q")),),
    "hs": (("url", ("url", "link", "target", "u")),),
    "bek-fs.write": (("path", PATH_ALIASES), ("content", CONTENT_ALIASES)),
    "bek-fs.append": (("path", PATH_ALIASES), ("content", CONTENT_ALIASES)),
    "bek-fs.read": (("path", PATH_ALIASES),),
    "bek-sh.run": (("cmd", ("cmd", "command", "shell", "script", "c")),),
    "bek-search.web": (("query", ("query", "search", "text", "prompt", "q")),),
}

PLAN_SYSTEM_PROMPT = """Tu es BEK Codex, un Agent de Développement Autonome Senior.

=== MODE PLAN (WORKFLOW CLAUDE CODE / CODEX) ===
Tu dois générer un plan ULTRA-GRANULAIRE pour construire le projet.
RÈGLE ABSOLUE : 1 ÉTAPE = 1 FICHIER (ou 1 action très simple).
Ne regroupe JAMAIS plusieurs fichiers dans une seule étape.

=== FORMAT DE RÉPONSE STRICT ===
Tu dois répondre UNIQUEMENT avec ce JSON (pas de Markdown, pas de texte avant/après) :

{"thought":"Planification du projet","tool":"plan","args":{"steps":[
  {"step":1,"action":"d","file":"bek_workspace/projet/src","description":"Créer le dossier src/"},
  {"step":2,"action":"w","file":"bek_workspace/projet/src/__init__.py","description":"Créer __init__.py vide"},
  {"step":3,"action":"w","file":"bek_workspace/projet/src/config.py","description":"Créer config.py"},
  {"step":4,"action":"w","file":"bek_workspace/projet/src/player.py","description":"Créer player.py"},
  {"step":5,"action":"w","file":"bek_workspace/projet/src/enemy.py","description":"Créer enemy.py"},
  {"step":6,"action":"w","file":"bek_workspace/projet/src/boss.py","description":"Créer boss.py"},
  {"step":7,"action":"w","file":"bek_workspace/projet/main.py","description":"Créer main.py"},
  {"step":8,"action":"w","file":"bek_workspace/projet/README.md","description":"Créer le README"}
]}}

RÈGLES ABSOLUES :
- La clé "steps" DOIT contenir une LISTE d'objets JSON.
- Chaque objet DOIT avoir "step" (numéro), "action" (d=create_dir, w=write_file), "file" (chemin), "description".
- Ne mets AUCUN fichier en dehors de "steps".
- Ne mets AUCUN texte avant ou après le JSON.
"""

BASE_SYSTEM_PROMPT = """Tu es BEK Codex. Agent autonome.

=== RÈGLES CRITIQUES ===
1. Tu réponds UNIQUEMENT en JSON strict. JAMAIS de Markdown.
2. Format : {"thought":"1 phrase","tool":"nom_outil","args":{...}}
3. Tu exécutes UNE SEULE action à la fois.
4. Quand tu as fini l'étape en cours, tu réponds {"thought":"Étape terminée","tool":"done","args":{}}
5. Si tu as un doute, tu clôtures avec "done" et tu passes à l'étape suivante.

=== OUTILS ===
w=write_file a=append_file r=read_file rm=read_file_map e=edit_file
d=create_dir g=grep f=glob_files ls=ls b=bash sw=web_search hs=headless_scrape

=== INTERDICTIONS ===
- Pas de "cd", "mkdir -p", "grep", "ls" via bash.
- Pas de commandes destructrices.
- NE LANCE JAMAIS pytest sur un jeu.
"""

# ==============================================================================
# ★ NOUVEAU : résolution du provider/model — RESPECTE le choix utilisateur
# ==============================================================================
_DEFAULT_PROVIDER = "nvidia"
_DEFAULT_PLAN_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
_DEFAULT_STEP_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"

def _resolve_target(provider: Optional[str], model: Optional[str]) -> Tuple[str, str]:
    prov = provider or _DEFAULT_PROVIDER
    mdl = model or _DEFAULT_PLAN_MODEL
    if model and not provider:
        if "/" in model:
            prov = model.split("/", 1)[0]
        else:
            prov = _DEFAULT_PROVIDER
    return prov, mdl

# ==============================================================================
# BUDGET PAR PROVIDER (Memory Shield inclus)
# ==============================================================================
def _budget(provider: Optional[str]) -> Dict[str, int]:
    p = (provider or "").lower()
    if p in ("groq", "ovh_anonymous", "llm7_anonymous", "beatapi", "kilo_anonymous"):
        return {
            "skills_count": 2, "skill_chars": 2000, "total_skill_chars": 4000,
            "memory_chars": 0,
            "max_tokens_llm": 1024,
            "max_history_messages": 4,
            "request_tpm_limit": 6000 if p == "groq" else 16000,
        }
    return {
        "skills_count": 2, "skill_chars": 3000, "total_skill_chars": 6000,
        "memory_chars": 150,
        "max_tokens_llm": MAX_TOKENS_LLM,
        "max_history_messages": 20, "request_tpm_limit": 200000,
    }

def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3) if isinstance(text, str) else 0

def _estimate_request_tokens(messages: List[Dict[str, Any]]) -> int:
    return sum(_estimate_tokens(m.get("content", "")) for m in messages)

# ==============================================================================
# PARSING
# ==============================================================================
def _extract_json(text: str) -> dict:
    if not isinstance(text, str): return {}
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if block:
        try:
            parsed = json.loads(block.group(1))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    return {}

def _normalize_args(tool: str, args: Any) -> Dict[str, Any]:
    if not isinstance(args, dict): return {}
    schema = TOOL_ARG_SCHEMA.get(tool, ())
    normalized = {}
    for canonical, aliases in schema:
        for alias in aliases:
            value = args.get(alias)
            if isinstance(value, str) and value.strip():
                normalized[canonical] = value
                break
            if value is not None and not isinstance(value, str):
                normalized[canonical] = value
                break
    for key, value in args.items():
        if key not in normalized:
            normalized.setdefault(key, value)
    return normalized

def _missing_required(tool: str, args: Dict[str, Any]) -> List[str]:
    return [
        canonical for canonical, _aliases in TOOL_ARG_SCHEMA.get(tool, ())
        if args.get(canonical) is None
        or (isinstance(args.get(canonical), str) and not args.get(canonical).strip())
    ]

def _extract_plan_steps(parsed: dict) -> List[Dict[str, Any]]:
    if not isinstance(parsed, dict):
        return []
    args = parsed.get("args", {})
    if isinstance(args, dict):
        for key in ("steps", "plan", "etapes", "actions", "taches"):
            steps = args.get(key)
            if isinstance(steps, list) and len(steps) > 0:
                return [s for s in steps if isinstance(s, dict)]
    for key in ("steps", "plan", "etapes", "actions", "taches"):
        steps = parsed.get(key)
        if isinstance(steps, list) and len(steps) > 0:
            return [s for s in steps if isinstance(s, dict)]
    return []

# ==============================================================================
# ★ NOUVEAU v7.25 : détection du type d'erreur JSON pour feedback ciblé
# ==============================================================================
def _diagnose_json_failure(raw: str) -> str:
    if not raw or not raw.strip():
        return (
            "ERR JSON: Ta réponse est VIDE. Tu DOIS répondre avec un JSON. "
            'Exemple : {"thought":"...","tool":"write_file","args":{"path":"...","content":"..."}}'
        )

    text = raw.strip()
    lower = text.lower()

    if text.startswith("#") or "```markdown" in lower or "```md" in lower:
        return (
            "ERR JSON: Tu as écrit du MARKDOWN au lieu de JSON. "
            "INTERDIT. Pour écrire un fichier Markdown (README), tu DOIS utiliser write_file : "
            '{"thought":"écrire README","tool":"write_file","args":{"path":"...","content":"# Titre\\n..."}} '
            "Le contenu Markdown va DANS args.content, PAS dans ta réponse brute."
        )

    if (text.startswith("import ") or text.startswith("def ") or text.startswith("class ") 
        or text.startswith("function ") or text.startswith("const ") or text.startswith("<!DOCTYPE")
        or text.startswith("extends ") or text.startswith("func ") or text.startswith("var ")):
        lang = "Python"
        if "def " in text[:200] or "import " in text[:200]: lang = "Python"
        elif "extends " in text[:200] or "func " in text[:200]: lang = "GDScript (Godot)"
        elif "function " in text[:200] or "const " in text[:200]: lang = "JavaScript"
        
        return (
            f"ERR JSON: Tu as écrit du CODE {lang} brut au lieu de JSON. "
            "INTERDIT. Pour écrire du code dans un fichier, tu DOIS utiliser write_file : "
            '{"thought":"écrire fichier","tool":"write_file","args":{"path":"...","content":"<ton code ici>"}} '
            "Le code va DANS args.content (avec des \\n pour les retours à la ligne)."
        )

    if not text.startswith("{") and ("je vais" in lower or "voici" in lower or "je peux" in lower or "pour " in lower[:50]):
        return (
            "ERR JSON: Tu as répondu en TEXTE NATUREL au lieu de JSON. "
            "INTERDIT. Tu dois UNIQUEMENT produire un objet JSON. "
            'Exemple : {"thought":"...","tool":"create_dir","args":{"path":"..."}}'
        )

    if text.startswith("{") and not text.rstrip().endswith("}"):
        return (
            "ERR JSON: Ton JSON est TRONQUÉ (il ne se termine pas par }). "
            "Réduis la taille du content (max 3000 chars par write_file). "
            "Si le fichier est trop gros, découpe-le en plusieurs write_file/append_file. "
            'Format : {"thought":"...","tool":"write_file","args":{"path":"...","content":"..."}}'
        )

    if text.startswith("{"):
        return (
            "ERR JSON: Ton JSON est mal formé ou il manque 'tool'/'args'. "
            'Format EXACT requis : {"thought":"1 phrase","tool":"nom_outil","args":{"param":"valeur"}} '
            "Vérifie les guillemets et les accolades."
        )

    return (
        "ERR JSON: Format invalide. Tu DOIS répondre UNIQUEMENT avec un objet JSON valide. "
        'Exemple : {"thought":"...","tool":"write_file","args":{"path":"...","content":"..."}} '
        "Aucun texte avant ou après le JSON."
    )

def _validate_syntax(file_path: str, content: str) -> Tuple[bool, str]:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".py":
        try:
            import ast
            ast.parse(content)
            return True, "Syntaxe Python validée"
        except SyntaxError as e:
            return False, f"SYNTAX ERROR ligne {e.lineno}: {e.msg}"

    elif ext == ".gd":
        stripped = content.strip()
        if not stripped:
            return True, "Fichier GDScript vide"
        first_lines = stripped.split("\n")[:5]
        has_extends = any(l.strip().startswith(("extends ", "class_name ")) for l in first_lines)
        if not has_extends:
            return False, "GDScript invalide : le fichier doit commencer par 'extends' ou 'class_name'"
        open_braces = content.count("{")
        close_braces = content.count("}")
        open_parens = content.count("(")
        close_parens = content.count(")")
        if open_braces != close_braces:
            return False, f"GDScript invalide : accolades déséquilibrées ({open_braces} vs {close_braces})"
        if open_parens != close_parens:
            return False, f"GDScript invalide : parenthèses déséquilibrées ({open_parens} vs {close_parens})"
        return True, "Syntaxe GDScript validée (basique)"

    elif ext == ".tscn":
        stripped = content.strip()
        if not stripped:
            return False, "Fichier .tscn vide"
        if not (stripped.startswith("[gd_scene") or stripped.startswith("[gd_resource")):
            return False, "Fichier .tscn invalide : doit commencer par [gd_scene ...] ou [gd_resource ...]"
        open_brackets = content.count("[")
        close_brackets = content.count("]")
        if open_brackets != close_brackets:
            return False, f"Fichier .tscn invalide : crochets déséquilibrés"
        return True, "Syntaxe .tscn validée (basique)"

    elif ext == ".json":
        try:
            json.loads(content)
            return True, "Syntaxe JSON validée"
        except json.JSONDecodeError as e:
            return False, f"JSON invalide : {e.msg}"

    return True, ""

# ==============================================================================
# APPEL LLM
# ==============================================================================
def _call_llm_safe(messages: List[Dict[str, Any]], provider: str, model: str,
                   max_tokens: Optional[int] = None,
                   fallback_chain: Optional[List[Tuple[str, str]]] = None
                   ) -> Tuple[Optional[str], Optional[str]]:
    try:
        from provider_manager import provider_manager
    except ImportError:
        return None, "provider_manager introuvable"

    providers_to_try = [(provider, model)]
    
    # ★ FIX v7.29 : Si l'utilisateur a choisi un provider explicite (provider n'est pas None/vide),
    # on ignore totalement la fallback_chain pour ne pas basculer sur Groq.
    if fallback_chain and provider in (None, "", "default"):
        providers_to_try.extend(fallback_chain)

    last_err_msg = ""

    for current_prov, current_model in providers_to_try:
        b = _budget(current_prov)
        mt = min(max_tokens or MAX_TOKENS_LLM, b["max_tokens_llm"])
        if current_prov == "groq":
            mt = min(mt, 1024)
        est_in = _estimate_request_tokens(messages)
        if est_in + mt > b["request_tpm_limit"]:
            mt = max(500, b["request_tpm_limit"] - est_in - 300)
            if est_in + mt > b["request_tpm_limit"] and len(messages) > 2:
                largest_idx = max(
                    range(1, len(messages)),
                    key=lambda i: len(messages[i].get("content", "") or "")
                )
                budget_chars = max(500, (b["request_tpm_limit"] - mt - 300) * 3)
                current = messages[largest_idx].get("content", "") or ""
                if len(current) > budget_chars:
                    messages[largest_idx] = {
                        "role": messages[largest_idx].get("role", "user"),
                        "content": current[:budget_chars] + "\n...[tronqué]",
                    }
                    est_in = _estimate_request_tokens(messages)
                    mt = max(500, b["request_tpm_limit"] - est_in - 300)

        try:
            _LVC_STATS["calls"] += 1
            _LVC_STATS["in_tok"] += est_in
            chunks: List[str] = []
            for item in provider_manager.execute_chat_stream(
                messages=messages, provider=current_prov, model=current_model,
                temperature=0.1, max_tokens=mt, disable_internal_fallback=True,
            ):
                if "chunk" in item:
                    chunks.append(item["chunk"])
                elif "error" in item:
                    last_err_msg = str(item["error"])
                    if "413" in last_err_msg or "too large" in last_err_msg.lower() or "429" in last_err_msg or "402" in last_err_msg:
                        last_err_msg = f"QUOTA ATTEINT ({current_prov})"
                    break

            res = "".join(chunks).strip()
            if res:
                _LVC_STATS["out_tok"] += _estimate_tokens(res)
                logger.info("[Codex Loop] ✅ LLM OK via %s/%s (%d chars, in~%d tok, max=%d)",
                            current_prov, current_model, len(res), est_in, mt)
                return res, None
            logger.warning("[Codex Loop] ⚠️ Échec %s : %s. Fallback...",
                           current_prov, last_err_msg)
        except Exception as exc:
            last_err_msg = str(exc)
            logger.warning("[Codex Loop] ⚠️ Exception %s : %s. Fallback...",
                           current_prov, last_err_msg)

    try:
        from memory import save_to_memory
        save_to_memory(
            f"[LECON CODEX] Échec providers : {last_err_msg[:200]}",
            f"Objectif '{messages[-1].get('content', '')[:100]}' a échoué sur tous les providers. "
            f"Dernière erreur : {last_err_msg[:300]}.",
        )
        logger.info("[ReflexLoop] 🧠 Leçon gravée en mémoire après échec provider")
    except Exception:
        pass

    return None, f"Chaîne épuisée. Dernière erreur : {last_err_msg}"

# ==============================================================================
# DISPATCH TOOL (Avec LVC-Test & LVC-Web Interceptor)
# ==============================================================================
def _dispatch_tool(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    tool_lower = tool.lower()
    native_tool = BEK_TO_HERMES.get(tool_lower, tool_lower)

    if native_tool != tool_lower:
        if len(tool_lower) <= 2:
            _LVC_STATS["lvc_calls"] += 1
            logger.info("[BEK-LVC] 🏛️ Compress : %s -> %s", tool_lower, native_tool)
        else:
            logger.info("[BEK-LVC] 🏛️ Rétro-compat : %s -> %s", tool_lower, native_tool)

    try:
        from hermes_core import hermes

        if native_tool == "bash" and "pytest" in str(args.get("cmd", "")):
            logger.info("[LVC-Test] 🧪 Interception de pytest...")
            tool_res = hermes.dispatch({"tool": native_tool, "args": args})

            if hasattr(tool_res, "success"):
                raw_stdout = getattr(tool_res, "data", {}).get("stdout", "") if tool_res.success else ""
                raw_stderr = getattr(tool_res, "error", "")
            elif isinstance(tool_res, dict):
                raw_stdout = tool_res.get("stdout", "")
                raw_stderr = tool_res.get("stderr", "")
            else:
                raw_stdout = ""
                raw_stderr = ""

            clean_msg = _parse_pytest_output(raw_stdout, raw_stderr)
            return {"status": "success" if "PASSED" in clean_msg else "error", "message": clean_msg}

        tool_res = hermes.dispatch({"tool": native_tool, "args": args})

        if hasattr(tool_res, "success"):
            if tool_res.success:
                return getattr(tool_res, "data", None) or {"result": "ok"}
            return {"status": "error", "message": getattr(tool_res, "error", "Erreur")}

        if isinstance(tool_res, dict):
            return tool_res
        return {"result": str(tool_res)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _feedback(messages, assistant_raw, user_msg):
    messages.append({"role": "assistant", "content": assistant_raw})
    messages.append({"role": "user", "content": user_msg})

def _prune_history(messages, max_kept):
    if len(messages) <= max_kept + 2:
        return messages
    return [messages[0], messages[1]] + messages[-max_kept:]

def _prune_history_for_json_retry(messages, max_kept=4):
    if len(messages) <= 2:
        return messages
    system_msg = messages[0]
    tail = messages[-(max_kept * 2):] if len(messages) > max_kept * 2 else messages[1:]
    return [system_msg] + tail

# ==============================================================================
# PHASES
# ==============================================================================
def _run_plan_phase(goal: str, prov: str, mdl: str, ego_prompt: str,
                    memory_context: Optional[str] = None) -> Dict[str, Any]:
    b = _budget(prov)
    mem = (memory_context or "")[:b["memory_chars"]]
    skills = _load_relevant_skills_lvc(goal, b)
    lessons = _fetch_lessons_from_memory(goal)

    engine_type = "godot" if "godot" in goal.lower() else "pygame" if "pygame" in goal.lower() else "generic"
    best_gene_prompt = gene_manager.get_best_gene_with_rules(engine_type)
    logger.info(f"[Codex Loop] 🧬 Gène injecté : {engine_type}")

    sys_prompt = (best_gene_prompt 
                  + f"\n\n{PLAN_SYSTEM_PROMPT}"
                  + (f"\n\n{ego_prompt}" if ego_prompt else "")
                  + (f"\n\n{skills}" if skills else "")
                  + lessons
                  + (f"\n\nMÉMOIRE:\n{mem}" if mem else ""))
    
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"OBJECTIF : {goal}\n\nProduis un PLAN JSON granulaire (1 étape = 1 fichier)."},
    ]
    for attempt in range(1, 3):
        # ★ FIX : On ne passe plus de fallback forcé sur Groq
        raw, err = _call_llm_safe(messages, prov, mdl,
                                  max_tokens=b["max_tokens_llm"])
        if err:
            return {"status": "error", "phase": "plan", "message": err}

        parsed = _extract_json(raw or "")
        raw_steps = _extract_plan_steps(parsed)

        if raw_steps:
            _log_lvc_stats("PLAN")
            _log_facture("PLAN")
            return {
                "status": "plan_ready",
                "phase": "plan",
                "plan": raw_steps,
                "notes": parsed.get("notes", "") or (parsed.get("args", {}) or {}).get("notes", ""),
                "steps_count": len(raw_steps),
                "lvc_stats": dict(_LVC_STATS),
            }

        _LVC_STATS["retries"] += 1
        _feedback(
            messages, raw or "",
            "ERR JSON: Tu dois fournir un plan avec une clé 'steps' contenant une LISTE d'objets. "
            'Format EXACT : {"thought":"planification","tool":"plan","args":{"steps":['
            '{"step":1,"action":"d","file":"...","description":"..."},'
            '{"step":2,"action":"w","file":"...","description":"..."}'
            ']}}'
        )

    return {"status": "error", "phase": "plan", "message": "Plan invalide."}

def _run_step_phase(goal: str, plan: List[Dict[str, Any]], step_num: int,
                    prov: str, mdl: str, ego_prompt: str, budget_s: int,
                    fallback_chain: List[Tuple[str, str]],
                    memory_context: Optional[str] = None) -> Dict[str, Any]:
    if step_num >= len(plan):
        return {"status": "done", "phase": "step", "message": "Plan terminé."}

    b = _budget(prov)
    step = plan[step_num]
    mem = (memory_context or "")[:b["memory_chars"]]
    skills = _load_relevant_skills_lvc(goal, b)

    step_description = (
        step.get("description")
        or step.get("desc")
        or step.get("action", "Étape " + str(step_num + 1))
    )

    engine_type = "godot" if "godot" in goal.lower() else "pygame" if "pygame" in goal.lower() else "generic"
    best_gene_prompt = gene_manager.get_best_gene_with_rules(engine_type)

    sys_prompt = (
        best_gene_prompt
        + f"\n\n{BASE_SYSTEM_PROMPT}"
        + (f"\n\n{ego_prompt}" if ego_prompt else "")
        + (f"\n\n{skills}" if skills else "")
        + (f"\n\nMÉMOIRE:\n{mem}" if mem else "")
        + "\n\nÉTAPE ACTUELLE :\n" + json.dumps(step, ensure_ascii=False)
        + "\n\nRAPPEL : Tu dois faire UNE SEULE action pour cette étape, puis répondre {\"tool\":\"done\"}."
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Exécute l'étape {step_num + 1}. JSON unique. Fais UNE action, puis 'done'."},
    ]

    start = time.time()
    history: List[Dict[str, Any]] = []
    last_file: Optional[str] = None
    last_verification: Optional[str] = None
    invalid_count = 0

    recent_actions = []

    for substep in range(1, MAX_ACTIONS_PER_STEP + 1):
        if (time.time() - start) > budget_s:
            _log_lvc_stats(f"STEP {step_num + 1} (TIMEOUT)")
            return {"status": "error", "phase": "step", "step_num": step_num,
                    "message": "Timeout budget.", "history": history}

        # ★ FIX : On ne passe plus de fallback forcé sur Groq
        raw, err = _call_llm_safe(messages, prov, mdl,
                                  max_tokens=b["max_tokens_llm"])
        if err:
            _log_lvc_stats(f"STEP {step_num + 1} (ERR)")
            return {"status": "error", "phase": "step", "step_num": step_num,
                    "message": err, "history": history}

        parsed = _extract_json(raw or "")
        if not parsed or "tool" not in parsed:
            invalid_count += 1
            _LVC_STATS["retries"] += 1
            diagnosis = _diagnose_json_failure(raw or "")
            logger.warning(
                "[Codex Loop] ⚠️ JSON invalide (%d/%d) — diagnostic : %s",
                invalid_count, MAX_INVALID_JSON_STREAK, diagnosis[:120]
            )
            if invalid_count >= MAX_INVALID_JSON_STREAK:
                _log_lvc_stats(f"STEP {step_num + 1} (JSON×{MAX_INVALID_JSON_STREAK})")
                return {"status": "error", "phase": "step", "step_num": step_num,
                        "message": f"JSON invalide max ({MAX_INVALID_JSON_STREAK} tentatives).",
                        "history": history}
            _feedback(messages, raw or "", diagnosis)
            messages = _prune_history_for_json_retry(messages, max_kept=4)
            continue

        tool = str(parsed.get("tool") or "").strip().lower()
        raw_args = parsed.get("args", {})

        if tool in TERMINAL_ACTIONS:
            _log_lvc_stats(f"STEP {step_num + 1} (LLM DONE)")
            _log_facture(f"STEP {step_num + 1} (LLM DONE)")
            summary = _auto_summary(
                history,
                raw_args.get("summary") if isinstance(raw_args, dict) else None
            )
            return {
                "status": "step_done",
                "phase": "step",
                "step_num": step_num,
                "step_description": step_description,
                "total_steps": len(plan),
                "next_step": (step_num + 1) if (step_num + 1) < len(plan) else None,
                "verify": last_verification,
                "summary": summary,
                "history": history,
                "lvc_stats": dict(_LVC_STATS),
            }

        if tool not in LOCAL_TOOLS and tool not in EXTERNAL_ALLOWED_TOOLS and tool not in BEK_LVC_TOOLS:
            invalid_count += 1
            _LVC_STATS["retries"] += 1
            _feedback(messages, raw or "", f"ERR: Outil '{tool}' interdit.")
            messages = _prune_history(messages, b["max_history_messages"])
            continue

        args = _normalize_args(tool, raw_args)
        missing = _missing_required(tool, args)
        if missing:
            invalid_count += 1
            _LVC_STATS["retries"] += 1
            _feedback(messages, raw or "", f"ERR: Args {missing} manquants.")
            messages = _prune_history(messages, b["max_history_messages"])
            continue

        action_str = f"{tool}:{str(args.get('cmd', '') or args.get('path', '') or args.get('query', '') or args.get('url', ''))}"
        recent_actions.append(action_str)
        if len(recent_actions) > 5:
            recent_actions.pop(0)

        if recent_actions.count(action_str) >= 3:
            _LVC_STATS["retries"] += 1
            logger.warning("[Codex Loop] 🛑 Boucle détectée 3x. Forçage de l'outil 'e'.")
            _feedback(messages, raw or "", "ERR: Tu spam la même action. STOP. Utilise 'e' (edit) pour corriger, ou 'done' si c'est fini.")
            recent_actions.clear()
            continue

        invalid_count = 0
        res_dict = _dispatch_tool(tool, args)
        if not isinstance(res_dict, dict):
            res_dict = {"result": str(res_dict)}

        if res_dict.get("status") == "error" and tool in ("b", "bash"):
            try:
                from memory import save_to_memory
                err_msg = str(res_dict.get("message", ""))[:300]
                save_to_memory(
                    f"[LECON CODEX] Test échoué sur '{goal[:80]}'",
                    f"Étape {step_num + 1}, outil {tool}. Erreur : {err_msg}.",
                )
                logger.info("[ReflexLoop] 🧠 Leçon gravée après échec de test")
            except Exception:
                pass

        if tool in ("write_file", "append_file", "edit_file", "w", "a", "e",
                    "bek-fs.write",
                    "bek-fs.append") and args.get("path"):
            last_file = str(args["path"])
            res_dict.setdefault("verification", "Fichier traité par Hermes.")
            chars = res_dict.get("chars") or res_dict.get("total_size") or 0
            last_verification = f"{last_file} OK ({chars} chars)" if chars else f"{last_file} OK"

            if res_dict.get("status") == "success":
                try:
                    from tools.code_tools import _safe_resolve
                    fp = _safe_resolve(last_file)
                    if fp and fp.exists():
                        content = fp.read_text(encoding="utf-8", errors="replace")
                        is_valid, msg = _validate_syntax(last_file, content)
                        if is_valid:
                            res_dict["syntax_check"] = "OK"
                            last_verification = f"{last_file} OK ({msg})"
                            logger.info("[Codex Loop] 🛡️ %s pour %s", msg, last_file)
                        else:
                            res_dict["syntax_check"] = msg
                            last_verification = f"{last_file} ERROR: {msg}"
                            _LVC_STATS["retries"] += 1
                            logger.warning("[Codex Loop] ❌ %s", msg)
                            _feedback(messages, raw or "", f"ERR {msg}. Fix et réécris.")
                            messages = _prune_history(messages, b["max_history_messages"])
                            continue
                except Exception as e:
                    logger.debug("[Codex Loop] Validation ignorée : %s", e)

        res_str = _compress_tool_result(tool, res_dict)
        history.append({"step": substep, "tool": tool, "result": json.dumps(res_dict, ensure_ascii=False)[:MAX_RESULT_CHARS]})
        _feedback(messages, raw or "", f"RES {res_str}")
        messages = _prune_history(messages, b["max_history_messages"])

    _log_lvc_stats(f"STEP {step_num + 1} (MAX actions)")
    return {"status": "error", "phase": "step", "step_num": step_num,
            "message": f"{MAX_ACTIONS_PER_STEP} actions max sans 'done'.", "history": history}

# ==============================================================================
# POINT D'ENTRÉE PUBLIC
# ==============================================================================
def run_codex_loop(
    goal: str, phase: str = "auto", plan: Optional[List[Dict[str, Any]]] = None,
    step_num: int = 0, max_steps: int = 20, alter_ego: Optional[str] = None,
    provider: Optional[str] = None, model: Optional[str] = None,
    time_budget_s: int = 400, goal_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> Dict[str, Any]:

    skill_goal = goal_context or goal

    target_provider, target_model = _resolve_target(provider, model)
    logger.info(
        "[Codex Loop] 🎯 Cible LLM : provider=%s model=%s (choix utilisateur=%s)",
        target_provider, target_model,
        "explicite" if (provider or model) else "défaut",
    )

    if memory_context is None:
        try:
            from memory_coordinator import coordinate_memories_async
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    mem_obj = None
                else:
                    mem_obj = loop.run_until_complete(
                        coordinate_memories_async(skill_goal, max_chars=300)
                    )
            except RuntimeError:
                mem_obj = asyncio.run(
                    coordinate_memories_async(skill_goal, max_chars=300)
                )
            if mem_obj is not None and getattr(mem_obj, "context", None):
                memory_context = mem_obj.context
                logger.info(
                    "[Codex Loop] 🧠 Mémoire coordonnée : %d faits, sources=%s",
                    len(mem_obj.facts), mem_obj.sources_used,
                )
        except Exception as e:
            logger.debug("[Codex Loop] Coordinator indisponible : %s", e)

    _reset_lvc_stats()

    if phase != "step" and BEK_CPU_AVAILABLE:
        try:
            route_info = BekCPU.execute("BEK-REX", "bek_rex_route", query=skill_goal)
            tier = route_info.get("tier", "TIER_1")
            logger.info("[Codex Loop] 🏛️ BEK-REX a routé vers : %s (conf: %.2f)",
                        tier, route_info.get("confidence", 0))

            eco_info = BekCPU.execute("BEK-ECO", "bek_eco_optimize", tier=tier, query=skill_goal)
            if eco_info.get("decision") == "cached":
                logger.info("[Codex Loop] ⚡ BEK-ECO : cache hit.")
                return {"status": "success", "message": "Réponse depuis le cache BEK-ECO",
                        "data": eco_info.get("cached_value")}
        except Exception as e:
            logger.warning("[Codex Loop] ⚠️ Erreur bek_core : %s", e)

    if phase == "auto":
        logger.info("[Codex Loop] 🤖 Mode AUTO.")

        res_plan = _run_plan_phase(
            skill_goal,
            target_provider, target_model,
            _get_ego_prompt(alter_ego), memory_context
        )
        if res_plan.get("status") != "plan_ready":
            _log_lvc_stats("AUTO (plan failed)")
            return res_plan

        plan_steps = res_plan["plan"]
        logger.info("[Codex Loop] 📋 Plan de %d étapes.", len(plan_steps))

        all_history = []
        # ★ FIX : On ne passe plus de fallback forcé, on laisse vide.
        step_fallback = []
        for i in range(len(plan_steps)):
            step_res = _run_step_phase(
                skill_goal, plan_steps, i,
                target_provider, target_model,
                _get_ego_prompt(alter_ego), time_budget_s,
                step_fallback,
                memory_context
            )
            all_history.extend(step_res.get("history", []))
            
            if step_res.get("status") == "error":
                _log_lvc_stats(f"AUTO (step {i+1} failed)")
                return {"status": "error",
                        "message": f"Étape {i+1} échouée : {step_res.get('message')}",
                        "history": all_history}
            
            logger.info("[Codex Loop] ✅ Étape %d/%d terminée. Fichier sur le disque. Pause de 6s...", 
                        i+1, len(plan_steps))
            time.sleep(6.0)

        _log_lvc_stats("AUTO TOTAL")
        _log_facture("Codex AUTO")
        return {
            "status": "success",
            "phase": "auto",
            "message": f"✅ Tâche terminée : {len(plan_steps)} étapes.",
            "history": all_history,
            "lvc_stats": dict(_LVC_STATS),
        }

    if phase == "plan":
        logger.info("[Codex Loop] 🧠 Planification.")
        return _run_plan_phase(
            skill_goal,
            target_provider, target_model,
            _get_ego_prompt(alter_ego), memory_context
        )

    if phase == "step":
        if not plan or not isinstance(plan, list):
            return {"status": "error", "message": "Plan manquant."}
        logger.info("[Codex Loop] ⚡ Exécution.")
        return _run_step_phase(
            skill_goal, plan, int(step_num),
            target_provider, target_model,
            _get_ego_prompt(alter_ego), int(time_budget_s),
            [], # ★ FIX : plus de fallback forcé ici
            memory_context
        )

    return {"status": "error", "message": f"Phase inconnue : {phase}"}

def _get_ego_prompt(alter_ego: Optional[str]) -> str:
    if not alter_ego:
        return ""
    try:
        from routing import _bek_rex_get_alter_ego_prompt
        return _bek_rex_get_alter_ego_prompt(alter_ego)
    except Exception:
        return ""