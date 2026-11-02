# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 18 — AGENT DE CODAGE UNIVERSEL (nerves/coder_nerves.py)
# ★ v19.26 (2026-10-30) — Fix summary None + step_description/total_steps/verify
#   → codex_loop.py v7.11 fournit maintenant total_steps, next_step, verify,
#     step_description. Le wrapper les lit correctement.
# ★ v19.25 : Manifeste enrichi avec les skills ECC et les règles
# ★ v19.24 : Fix cascade de retries (disable_internal_fallback=True)
# ==============================================================================
from __future__ import annotations

import ast
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from core.paths import GENERATED_DIR, WORKSPACE_DIR
from core.security.path_guard import find_existing, safe_path

logger = logging.getLogger("bek.nerves.coder")

BEK_TOOLS_MANIFEST = """
## 🏛️ MANIFESTE DE L'ARCHITECTURE BEK v19 - UNIVERSAL CODEX

Tu es un Architecte Logiciel Expert. Ton but est d'écrire du code de qualité production.

### 🧠 SKILLS ECC DISPONIBLES (utilise-les pour les tâches complexes)
- Python : patterns de code, gestion d'erreurs, tests
- FastAPI : architecture API, validation Pydantic
- React/Next.js : composants, hooks, server components
- Rust, Go, C++ : systèmes, performance
- Architecture : design patterns, DDD, hexagonal

### ⚙️ RÈGLES DE CODE (à respecter impérativement)
1. Code lisible > code optimisé.
2. Nomme les variables explicitement (jamais `x`, `y`, `tmp`).
3. Gère les erreurs (try/except, validation des entrées).
4. Docstrings sur les fonctions publiques.
5. Tests unitaires si c'est du Python.

### 🌐 Web & Recherche (Python uniquement)
- from web_agent import web_agent_instance
  → resultat = web_agent_instance.run_pipeline("ta requête")

### 🎨 Vision & Multimédia (Python uniquement)
- from services.vision import generate_image_with_provider

### 🛠️ Tâches longues (Tous langages)
- Si ton code nécessite une compilation longue, utilise l'outil `tmux_start_task` de BEK.

### 🚨 RÈGLES POUR PYTHON
1. N'utilise JAMAIS "import requests" ou "import urllib".
2. N'utilise JAMAIS "pip install".
3. Fais les imports directement, sans try/except ImportError.

### 🚨 RÈGLES POUR LES AUTRES LANGAGES
1. Écris du code propre, compilable et autonome.
2. Inclus les commentaires nécessaires.
3. Ne génère PAS de `package.json` ou `pom.xml` si ce n'est pas demandé.
"""


def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_CODER_NERVES", "true").lower() in ("true", "1", "yes")


def _extract_code(raw_text: str) -> str:
    match = re.search(r"```[a-zA-Z]*\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    clean = re.sub(r"```[a-zA-Z]*", "", raw_text)
    return clean.replace("```", "").strip()


def _validate_python_syntax(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, "Syntaxe Python OK"
    except SyntaxError as e:
        return False, f"Erreur de syntaxe ligne {e.lineno}: {e.msg}"


def _make_non_blocking_for_test(code: str) -> str:
    test_code = code
    if ".run(" in test_code and ("Flask" in test_code or "FastAPI" in test_code):
        test_code = re.sub(
            r"\b([a-zA-Z0-9_]+)\.run\s*\([^)]*\)",
            r"print('✅ Serveur web initialisé avec succès (mode test non-bloquant)')",
            test_code,
        )
    return test_code


def _execute_python_code(code: str) -> Dict[str, Any]:
    testable_code = _make_non_blocking_for_test(code)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(testable_code)
        temp_path = f.name

    try:
        env_vars = os.environ.copy()
        env_vars["PYTHONPATH"] = str(WORKSPACE_DIR) + os.pathsep + env_vars.get("PYTHONPATH", "")
        env_vars["BEK_TEST_MODE"] = "1"
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(WORKSPACE_DIR),
            env=env_vars,
        )
        return {"success": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timeout (60s)"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def _detect_language(code: str, filename: str = "") -> str:
    if filename:
        ext = filename.split(".")[-1].lower()
        if ext == "py": return "python"
        if ext in ("js", "ts", "html", "css", "java", "cpp", "c", "php", "rs", "go", "rb", "swift", "kt"):
            return ext

    code_lower = code.lower()
    if "<!doctype html>" in code_lower or "<html" in code_lower: return "html"
    if "public class " in code_lower or "public static void main" in code_lower: return "java"
    if "#include <iostream>" in code_lower or "#include <stdio.h>" in code_lower: return "cpp"
    if "<?php" in code_lower: return "php"
    if "fn main()" in code_lower or "println!" in code_lower: return "rs"
    if "package main" in code_lower or "func main()" in code_lower: return "go"
    if "import " in code or "def " in code or "print(" in code: return "python"
    if "const " in code or "let " in code or "function " in code: return "javascript"
    return "txt"


def _get_alter_ego_prompt(alter_ego: Optional[str]) -> str:
    if not alter_ego: return ""
    try:
        from routing import _bek_rex_get_alter_ego_prompt
        prompt = _bek_rex_get_alter_ego_prompt(alter_ego)
        return f"\n\n=== MODE ALTER EGO : {alter_ego.upper()} ===\n{prompt}\n"
    except Exception:
        return ""


def _resolve_output_filename(task_description: str, target_file: Optional[str], lang: str) -> str:
    if target_file: return os.path.basename(target_file)
    match = re.search(r"\b([a-zA-Z0-9_\-]+\.(?:py|js|ts|html|css|java|cpp|c|php|rs|go))\b", task_description)
    if match: return match.group(1)
    ext = "py" if lang == "python" else lang
    return f"codex_{ext}_{uuid.uuid4().hex[:6]}.{ext}"


# ==============================================================================
# HANDLER 1 : codex_agent (création de fichier unique)
# ==============================================================================
def _handler_codex_agent(
    task_description: str,
    target_file: Optional[str] = None,
    alter_ego: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: int = 3,
    **kwargs: Any,
) -> Dict[str, Any]:
    if not task_description:
        return {"status": "error", "message": "Description de la tâche vide."}

    try:
        from provider_manager import provider_manager
    except ImportError:
        return {"status": "error", "message": "provider_manager introuvable."}

    ego_prompt = _get_alter_ego_prompt(alter_ego)
    current_prompt = (
        f"{ego_prompt}\n"
        f"Tu es un expert développeur universel travaillant sur l'architecture BEK.\n"
        f"{BEK_TOOLS_MANIFEST}\n"
        f"TÂCHE : {task_description}\n\n"
        f"RÈGLES :\n"
        f"1. Détecte le langage demandé et écris le code correspondant.\n"
        f"2. Si c'est du Python, utilise 'web_agent' et évite 'requests'.\n"
        f"3. Réponds UNIQUEMENT avec le code complet. Pas de texte avant ou après."
    )

    for attempt in range(1, max_retries + 1):
        logger.info(f"🤖 [CodexAgent] Tentative {attempt}/{max_retries} (AlterEgo: {alter_ego or 'default'})...")
        messages = [{"role": "user", "content": current_prompt}]
        raw_response = ""

        try:
            prov = provider or "nvidia"
            mdl = model or "nvidia/nemotron-3.5-super-vl-120b-a12b"
            for item in provider_manager.execute_chat_stream(
                messages=messages,
                provider=prov,
                model=mdl,
                max_tokens=8192,
                disable_internal_fallback=True,
            ):
                if "chunk" in item:
                    raw_response += item["chunk"]
                elif "error" in item:
                    logger.warning(f"[CodexAgent] Erreur provider : {item['error']}. Retry...")
                    break
        except Exception as e:
            return {"status": "error", "message": f"Exception LLM : {e}"}

        if not raw_response:
            continue

        code = _extract_code(raw_response)
        lang = _detect_language(code, filename=target_file or "")
        filename = _resolve_output_filename(task_description, target_file, lang)

        if lang == "python":
            if "pip install" in code or "import requests" in code or "import urllib" in code:
                current_prompt += "\n\nERREUR : N'utilise jamais 'requests', 'urllib' ou 'pip install'. Réécris le code complet sans eux."
                continue

            is_valid, syntax_err = _validate_python_syntax(code)
            if not is_valid:
                logger.warning(f"[CodexAgent] AST invalide : {syntax_err}")
                current_prompt = f"{ego_prompt}\nLe code précédent a une erreur de syntaxe :\n{syntax_err}\n\nCorrige le code et réponds UNIQUEMENT avec le code Python complet corrigé."
                continue

            result = _execute_python_code(code)
            if result["success"]:
                os.makedirs(GENERATED_DIR, exist_ok=True)
                filepath = os.path.join(GENERATED_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(code)
                try:
                    ws_path = os.path.join(str(WORKSPACE_DIR), filename)
                    with open(ws_path, "w", encoding="utf-8") as f:
                        f.write(code)
                except Exception:
                    pass

                return {
                    "status": "success",
                    "attempts": attempt,
                    "code": code,
                    "filename": filename,
                    "message": f"✅ Application générée et testée (en {attempt} tentative(s)).\n💾 **Fichier** : `{filename}`\n📥 [Ouvrir](/api/download/{filename})",
                }
            else:
                current_prompt = f"{ego_prompt}\nLe code précédent a généré cette erreur Python :\n{result['stderr']}\n\nCorrige le code et réponds UNIQUEMENT avec le code Python complet corrigé."
                continue
        else:
            if lang in ("java", "cpp", "c", "javascript") and code.count("{") != code.count("}"):
                current_prompt += "\n\nErreur de syntaxe : accolades manquantes. Corrige."
                continue

            os.makedirs(GENERATED_DIR, exist_ok=True)
            filepath = os.path.join(GENERATED_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            return {
                "status": "success",
                "attempts": attempt,
                "code": code,
                "filename": filename,
                "message": f"✅ Code {lang.upper()} généré en {attempt} tentative(s).\n💾 **Fichier** : `{filename}`\n📥 [Ouvrir](/api/download/{filename})",
            }

    return {"status": "error", "message": f"Échec après {max_retries} tentatives."}


# ==============================================================================
# HANDLER 2 : codex_editor (modification ciblée)
# ==============================================================================
def _handler_codex_editor(
    task_description: str,
    target_file: str,
    alter_ego: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: int = 3,
    **kwargs: Any,
) -> Dict[str, Any]:
    if not task_description or not target_file:
        return {"status": "error", "message": "Description et target_file obligatoires."}

    target_path = find_existing(target_file)
    if not target_path:
        try:
            target_path = safe_path(target_file)
        except Exception:
            target_path = None
    if not target_path:
        return {"status": "error", "message": f"❌ Chemin invalide : `{target_file}`."}

    try:
        os.makedirs(target_path.parent, exist_ok=True)
        original_code = ""
        backup_path = None
        if target_path.exists():
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                original_code = f.read()
            backup_path = target_path.with_suffix(target_path.suffix + ".bak")
            shutil.copy2(target_path, backup_path)
            logger.info(f"💾 Backup créé : {backup_path.name}")
        from provider_manager import provider_manager
    except Exception as e:
        return {"status": "error", "message": f"Erreur préparation : {e}"}

    lang = _detect_language("", filename=target_path.name)
    is_python = lang == "python"
    ego_prompt = _get_alter_ego_prompt(alter_ego)

    current_prompt = (
        f"{ego_prompt}\n"
        f"Voici le contenu actuel du fichier `{target_path.name}` :\n"
        f"```\n{original_code}\n```\n\n"
        f"Applique la modification suivante : {task_description}\n"
        f"Réponds UNIQUEMENT avec le contenu COMPLET du fichier modifié. Aucun texte autour."
    )

    for attempt in range(1, max_retries + 1):
        logger.info(f"🤖 [CodexEditor] Tentative {attempt}/{max_retries} sur {target_path.name}...")
        messages = [{"role": "user", "content": current_prompt}]
        raw_response = ""

        try:
            prov = provider or "nvidia"
            mdl = model or "nvidia/nemotron-3.5-super-vl-120b-a12b"
            for item in provider_manager.execute_chat_stream(
                messages=messages,
                provider=prov,
                model=mdl,
                max_tokens=8192,
                disable_internal_fallback=True,
            ):
                if "chunk" in item:
                    raw_response += item["chunk"]
                elif "error" in item:
                    break
        except Exception as e:
            return {"status": "error", "message": f"Exception LLM : {e}"}

        if not raw_response:
            continue
        new_code = _extract_code(raw_response)

        if is_python:
            is_valid, syntax_err = _validate_python_syntax(new_code)
            if not is_valid:
                current_prompt = f"Erreur de syntaxe :\n{syntax_err}\nCorrige le code et renvoie le fichier complet."
                continue

            result = _execute_python_code(new_code)
            if not result["success"]:
                current_prompt = f"Erreur Python :\n{result['stderr']}\nCorrige le code et renvoie le fichier complet."
                continue
        else:
            if lang in ("java", "cpp", "c", "javascript") and new_code.count("{") != new_code.count("}"):
                current_prompt = "Erreur de syntaxe : accolades manquantes. Corrige."
                continue

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        return {
            "status": "success",
            "attempts": attempt,
            "code": new_code,
            "message": f"✅ Fichier `{target_path.name}` modifié en {attempt} tentative(s).\n💾 Backup : `{backup_path.name if backup_path else 'Nouveau fichier'}`",
        }

    if backup_path:
        shutil.copy2(backup_path, target_path)
    return {"status": "error", "message": f"Échec après {max_retries} tentatives. Fichier restauré."}


# ==============================================================================
# HANDLER 3 : codex_loop (boucle autonome + phases plan/step/auto)
# ★ v19.26 — Fix summary None + lit total_steps/next_step/verify/step_description
# ==============================================================================
def _handler_codex_loop(
    task_description: str,
    max_steps: int = 20,
    alter_ego: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    phase: str = "auto",
    plan: Optional[List[Dict[str, Any]]] = None,
    step_num: int = 0,
    goal_context: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:

    if not task_description:
        return {"status": "error", "message": "Description de la tâche vide."}

    actual_goal = goal_context or task_description

    try:
        from core.codex_loop import run_codex_loop
        result = run_codex_loop(
            actual_goal,
            phase=phase,
            plan=plan,
            step_num=step_num,
            max_steps=max_steps,
            alter_ego=alter_ego,
            provider=provider,
            model=model,
            memory_context=kwargs.get("memory_context"),
        )

        status = result.get("status", "error")

        if status == "plan_ready":
            plan_steps = result.get("plan", [])
            steps_text = "\n".join(
                f"{i+1}. [{s.get('action', '?')}] {s.get('description', '')}"
                for i, s in enumerate(plan_steps)
            )
            return {
                "status": "success",
                "phase": "plan",
                "plan": plan_steps,
                "notes": result.get("notes", ""),
                "steps_count": result.get("steps_count", 0),
                "lvc_stats": result.get("lvc_stats"),
                "message": (
                    f"📋 **Plan généré ({len(plan_steps)} étapes)**\n\n"
                    f"{result.get('notes', '')}\n\n"
                    f"**Étapes :**\n{steps_text}\n\n"
                    f"👉 Envoie *\"Exécute l'étape 1\"* pour commencer."
                ),
            }

        elif status == "step_done":
            step_idx = result.get("step_num", 0)
            total = result.get("total_steps", 0) or 1
            next_s = result.get("next_step")
            step_desc = result.get("step_description") or ""
            summary = result.get("summary") or ""
            verify_msg = result.get("verify") or ""

            if next_s is not None:
                next_text = f"👉 Prochaine : *\"Exécute l'étape {next_s + 1}\"*"
            else:
                next_text = "✅ **Plan terminé !**"

            message_parts = [f"✅ **Étape {step_idx + 1}/{total} terminée**"]
            if step_desc:
                message_parts.append(f"_{step_desc}_")
            if summary:
                message_parts.append(summary)
            if verify_msg:
                message_parts.append(f"🔍 {verify_msg}")
            message_parts.append(next_text)
            full_message = "\n\n".join(message_parts)

            return {
                "status": "success",
                "phase": "step",
                "step_num": step_idx,
                "step_description": step_desc,
                "next_step": next_s,
                "total_steps": total,
                "verify": result.get("verify"),
                "summary": summary,
                "lvc_stats": result.get("lvc_stats"),
                "message": full_message,
                "history": result.get("history", []),
            }

        elif status == "done":
            return {
                "status": "success",
                "phase": "step",
                "message": f"🎉 {result.get('message', 'Toutes les étapes sont terminées.')}",
            }

        elif status == "success":
            return {
                "status": "success",
                "phase": "auto",
                "lvc_stats": result.get("lvc_stats"),
                "message": (
                    f"✅ Tâche terminée en {result.get('steps', 0)} étapes.\n\n"
                    f"**Résumé** : {result.get('summary') or 'Tâche accomplie.'}"
                ),
                "history": result.get("history", []),
            }

        else:
            return {
                "status": "error",
                "phase": phase,
                "message": result.get("message", "Échec de la boucle."),
                "history": result.get("history", []),
            }

    except Exception as e:
        logger.exception("[Codex Loop] Erreur")
        return {"status": "error", "message": str(e)}


# ==============================================================================
# ACTIVATION
# ==============================================================================
CODER_NERVES_TABLE = {
    "codex_agent": (_handler_codex_agent, "L2"),
    "codex_editor": (_handler_codex_editor, "L3"),
    "codex_loop": (_handler_codex_loop, "L2"),
}


def activate_coder_nerves() -> Dict[str, Any]:
    if not _is_enabled():
        return {"status": "disabled", "reason": "Feature-flag BEK_ENABLE_CODER_NERVES=false"}

    try:
        from hermes_core import hermes
    except ImportError as exc:
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []

    for tool_name, (handler, risk_level) in CODER_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 18] Outil Codex branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})

    try:
        from tools.code_tools import register_code_tools
        code_tools_res = register_code_tools(hermes)
        if code_tools_res.get("status") == "ok":
            activated.extend(code_tools_res.get("activated", []))
            logger.info("✅ [Nerf 18] Code Tools branchés avec succès.")
    except Exception as exc:
        logger.error("❌ [Nerf 18] Impossible d'activer Code Tools : %s", exc)
        failed.append({"tool": "code_tools", "error": str(exc)})

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
    }