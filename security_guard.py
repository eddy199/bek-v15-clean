from __future__ import annotations

import ast
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger("bek.security_guard")

# ★ FIX : Alignement sur le CODE_WORKSPACE (dossier workspace/)
try:
    from core.paths import CODE_WORKSPACE, ROOT_DIR
    BASE_DIR = ROOT_DIR
    WORKSPACE_DIR = CODE_WORKSPACE
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent
    WORKSPACE_DIR = BASE_DIR / "workspace"


class SecurityGuard:
    DEFAULT_SECRET_ENV = "BEK_HSM_SECRET"

    BLOCKED_SENSITIVE_FILES: Set[str] = {
        ".env", "env.txt", "id_rsa", "id_ed25519",
        "credentials.json", "token.pickle", "config.json",
    }

    # ★ FIX : Ajout des alias (file, text, code) et de goal_context
    ALLOWED_ACTIONS: Dict[str, Tuple[str, ...]] = {
        # CRM
        "create_contact": ("name", "email", "phone", "firstName", "provider", "model"),
        "create_deal": ("title", "amount", "name", "provider", "model"),
        "create_task": ("title", "name", "description", "provider", "model"),
        "search_contact": ("query", "name", "provider", "model"),
        "update_contact": ("name", "email", "phone", "provider", "model"),
        "get_stats": ("provider", "model"),
        "neon_audit": ("tables", "provider", "model"),

        # Orchestration
        "default_llm": ("query", "skill", "prompt", "provider", "model"),
        "create_dynamic_skill": ("skill_name", "code_content", "description", "provider", "model"),
        "orchestrate": ("goal", "objective", "query", "provider", "model"),
        "run_swarm_task": ("goal", "objective", "task_description", "query", "provider", "model"),
        "multi_agent_workflow": ("goal", "objective", "query", "provider", "model"),
        "web_sync": ("query", "skill", "prompt", "provider", "model"),
        "web_search": ("query", "provider", "model"),
        "web_pipeline": ("query", "provider", "model"),

        # Mémoire
        "save_memory": ("content", "provider", "model"),
        "remember": ("content", "provider", "model"),
        "save_to_memory": ("content", "provider", "model"),
        "search_memory": ("query", "top_k", "provider", "model"),
        "recall": ("query", "top_k", "provider", "model"),
        "delete_memory": ("record_id", "keyword", "provider", "model"),
        "forget": ("record_id", "keyword", "provider", "model"),
        "delete_from_memory": ("record_id", "keyword", "provider", "model"),

        # Fichiers (Ajout des alias d'arguments)
        "write_file": ("path", "content", "filename", "file", "text", "code", "base_dir", "provider", "model"),
        "append_file": ("path", "content", "filename", "file", "text", "code", "base_dir", "provider", "model"),
        "create_dir": ("path", "filename", "file", "base_dir", "provider", "model"),
        "read_file": ("path", "filename", "file", "start_line", "end_line", "base_dir", "provider", "model"),
        "edit_file": ("path", "filename", "file", "old_string", "new_string", "base_dir"),
        "delete_file": ("path", "filename", "file", "provider", "model"),
        "extract_zip": ("zip_path", "extract_to", "provider", "model"),
        "create_zip": ("folder_path", "output_zip", "provider", "model"),
        "analyze_zip_content": ("zip_path", "provider", "model"),

        # Multimédia
        "analyze_image": ("image_path", "prompt", "provider", "model"),
        "generate_image": ("prompt", "filename", "provider", "model"),
        "merge_and_edit_images": ("image_paths", "prompt", "provider", "model"),
        "generate_video": (
            "prompt", "image_paths", "reference_images", "provider", "model",
            "duration", "aspect_ratio", "with_audio", "audio_style",
            "resolution", "negative_prompt", "style_preset", "filename"
        ),
        "edit_video": ("video_path", "prompt", "provider", "model", "with_audio", "audio_style", "filename"),
        "extend_video": ("video_path", "prompt", "provider", "model", "duration", "with_audio", "audio_style", "resolution", "filename"),
        "extend_video_multiple": ("video_path", "prompts", "provider", "model", "duration", "with_audio", "audio_style", "resolution", "filename"),
        "generate_subtitles": ("video_path", "provider", "model", "filename"),
        "burn_subtitles": ("video_path", "subtitle_path", "provider", "model", "filename"),

        # Terminal
        "execute_command": ("cmd", "command", "timeout", "cwd", "session_name", "provider", "model"),
        "run_script": ("cmd", "command", "provider", "model"),
        "run_tests": ("cmd", "command", "provider", "model"),
        "bash": ("cmd", "command", "timeout", "cwd", "base_dir"),

        # ★ CODEX TOOLS
        "codex_agent": ("task_description", "target_file", "alter_ego", "provider", "model"),
        "codex_editor": ("task_description", "target_file", "alter_ego", "provider", "model"),
        "codex_loop": (
            "task_description", "max_steps", "alter_ego", "provider", "model",
            "phase", "plan", "step_num", "goal_context", "goal"
        ),

        # Outils internes Codex Loop
        "hindsight_recall": ("query", "top_k", "provider", "model"),
        "headless_scrape": ("url", "provider", "model"),
        "ls": ("path", "base_dir"),
        "grep": ("pattern", "path", "include", "base_dir", "max_results"),
        "glob_files": ("pattern", "base_dir"),
        "search_skills": ("query", "provider", "model"),
    }

    # ★ FIX : Regex destructives corrigées (robustes face aux espaces/chemins)
    FORBIDDEN_PATTERNS = (
        re.compile(r"(?i)\bDROP\s+DATABASE\b"),
        re.compile(r"(?i)\bTRUNCATE\s+TABLE\b"),
        re.compile(r"(?i)\bFORMAT\s+[A-Z]:\b"),
        re.compile(r"(?i)\bRM\s+-[a-z]*r[a-z]*f[a-z]*\s+(?:/|~|\*|\\)"),
        re.compile(r"(?i)\bDEL\s+/[FQS]\s+[A-Z]:\\"),
        re.compile(r"(?i)\bPOWERSHELL\b.*-ENC\b"),
        re.compile(r"(?i)\bNC\b.*-E\b"),
        re.compile(r"(?i)/DEV/(?:TCP|UDP)/"),
    )

    # ★ FIX : Regex de code strict (évite le faux positif sur re.compile)
    FORBIDDEN_CODE_PATTERNS = (
        re.compile(r"(?i)(?<!\.)\beval\s*\("),
        re.compile(r"(?i)(?<!\.)\bexec\s*\("),
        re.compile(r"(?i)__import__\s*\("),
        re.compile(r"(?i)\bglobals\s*\(\s*\)"),
        re.compile(r"(?i)\blocals\s*\(\s*\)"),
        re.compile(r"(?i)\bos\s*\.\s*system\s*\("),
        re.compile(r"(?i)\bos\s*\.\s*popen\s*\("),
        re.compile(r"(?i)\bos\s*\.\s*exec[lv]"),
        re.compile(r"(?i)\bsubprocess\s*\."),
        re.compile(r"(?i)\bpty\s*\."),
        re.compile(r"(?i)\bctypes\s*\."),
        re.compile(r"(?i)\bpickle\s*\.\s*loads\s*\("),
        re.compile(r"(?i)\bmarshal\s*\.\s*loads\s*\("),
        re.compile(r"(?i)\bwinreg\s*\."),
        re.compile(r"(?i)\bsocket\s*\.\s*socket\s*\("),
        re.compile(r"(?i)\burllib\s*\.\s*request\s*\."),
        re.compile(r"(?i)\brequests\s*\.\s*(get|post|put|delete|patch)\s*\("),
    )

    # ★ FIX CRITIQUE : Liste assouplie des imports bannis
    # On garde UNIQUEMENT les modules réellement dangereux pour du code tiers.
    # On retire os, sys, threading, shutil, importlib (utilisés par TON PROPRE CODE).
    BANNED_IMPORTS: Set[str] = {
        "subprocess", "pty", "ctypes", "marshal", "pickle",
        "winreg", "urllib", "requests", "http", "socket",
        "multiprocessing",
    }

    SECRET_PATTERNS = (
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I),
        re.compile(r"AIza[0-9A-Za-z\-_]{35}", re.I),
        re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.I),
        re.compile(r"nvapi-[a-zA-Z0-9\-_]{20,}", re.I),
        re.compile(r"Bearer\s+[a-zA-Z0-9._\-]{20,}", re.I),
    )

    def __init__(self, secret_key: Optional[str] = None):
        key = secret_key or os.environ.get(self.DEFAULT_SECRET_ENV, "")
        if not key:
            key = self._read_env_file(self.DEFAULT_SECRET_ENV)

        self._ephemeral_key_used = False
        if not key:
            key = secrets.token_hex(32)
            self._ephemeral_key_used = True
            logger.warning("SecurityGuard : clé éphémère générée.")

        self.secret_key = key.strip("\"' \r\n").encode("utf-8")
        if len(self.secret_key) < 32:
            raise ValueError("BEK_HSM_SECRET doit contenir au minimum 32 caractères.")

        self.allowed_actions = dict(self.ALLOWED_ACTIONS)

    @staticmethod
    def _read_env_file(name: str) -> str:
        for filename in (".env", "env.txt"):
            path = BASE_DIR / filename
            if not path.exists(): continue
            try:
                with path.open("r", encoding="utf-8-sig", errors="ignore") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith(name + "="):
                            return line.split("=", 1)[1].strip().strip("\"'")
            except OSError: continue
        return ""

    @classmethod
    def sanitize_secrets(cls, text: str) -> str:
        if not isinstance(text, str): return text
        sanitized = text
        for pattern in cls.SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @classmethod
    def validate_code_ast(cls, code_str: str) -> Tuple[bool, str]:
        if not isinstance(code_str, str) or not code_str.strip(): return True, "OK"
        cleaned = code_str.strip().lstrip("\ufeff")
        cleaned = re.sub(r"^```(?:python)?\s*|```$", "", cleaned, flags=re.M).strip()
        try:
            tree = ast.parse(cleaned)
        except SyntaxError as exc:
            return False, f"Code non analysable (SyntaxError) : {exc.msg}"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in cls.BANNED_IMPORTS:
                        return False, f"Import dangereux interdit : '{alias.name}'"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in cls.BANNED_IMPORTS:
                    return False, f"Import dangereux interdit : 'from {node.module}'"
        return True, "OK"

    @classmethod
    def _detect_injection(cls, value: Any, strict_code: bool = False) -> bool:
        try:
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return True
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern.search(text): return True
        if strict_code:
            for pattern in cls.FORBIDDEN_CODE_PATTERNS:
                if pattern.search(text): return True
        return False

    @classmethod
    def _validate_path_confinement(cls, path_val: Any) -> Tuple[bool, str]:
        if not isinstance(path_val, str) or not path_val.strip():
            return False, "Chemin invalide ou vide."
        raw_clean = path_val.strip().strip("\"'")
        if "\x00" in raw_clean: return False, "Caractère nul interdit."
        target_path = Path(raw_clean)
        
        # ★ FIX : Confinement dans WORKSPACE_DIR (CODE_WORKSPACE)
        resolved = target_path.resolve() if target_path.is_absolute() else (WORKSPACE_DIR / target_path).resolve()
        try:
            resolved.relative_to(WORKSPACE_DIR.resolve())
        except ValueError:
            return False, f"Sortie de sandbox refusée pour '{raw_clean}'."
            
        filename = resolved.name.lower()
        if filename in cls.BLOCKED_SENSITIVE_FILES or filename.endswith((".key", ".pem", ".pfx")):
            return False, f"Accès interdit au fichier sensible '{filename}'."
        return True, "OK"

    @staticmethod
    def _canonical_payload(action: str, params: Dict[str, Any]) -> bytes:
        canonical = json.dumps(params, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return f"{action}:{canonical}".encode("utf-8")

    def validate_and_certify(self, action: str, params: Optional[Dict[str, Any]]) -> Tuple[bool, str, Dict[str, Any]]:
        if not isinstance(action, str) or not action.strip():
            return False, "Action invalide.", {}
        action = action.strip()
        if action not in self.allowed_actions:
            return False, f"Action '{action}' non présente dans l'Allowlist.", {}

        if params is None: params = {}
        if not isinstance(params, dict):
            return False, "Paramètres invalides.", {}

        allowed = set(self.allowed_actions[action])
        unknown = set(params) - allowed
        if unknown:
            return False, f"Paramètres non autorisés pour '{action}': {sorted(unknown)}.", {}

        sanitized = dict(params)

        # Validation des chemins
        file_keys = ("path", "filename", "file", "target_file", "zip_path", "extract_to", "folder_path", "output_zip", "image_path")
        for key in file_keys:
            if key in sanitized and isinstance(sanitized[key], str):
                is_safe, err_msg = self._validate_path_confinement(sanitized[key])
                if not is_safe:
                    return False, err_msg, {}

        # Validation AST pour code dynamique
        if action == "create_dynamic_skill" and "code_content" in sanitized:
            valid, error = self.validate_code_ast(sanitized["code_content"])
            if not valid: return False, error, {}

        # ★ FIX : Détection d'injection (strict UNIQUEMENT pour le contenu des fichiers)
        for key, value in sanitized.items():
            strict_code = key in {"content", "code_content", "text", "code"}
            if self._detect_injection(value, strict_code=strict_code):
                return False, f"Signature destructive ou injection détectée dans '{key}'.", {}

        payload = self._canonical_payload(action, sanitized)
        signature = hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()

        envelope = {
            "action": action, "params": sanitized, "certified": True,
            "security_layer": "SecurityGuard-v17-Hardened",
            "policy": "ALLOWLIST_STRICT + SANDBOX + DLP + HMAC-SHA256",
            "hsm_signature": signature, "ephemeral_key": self._ephemeral_key_used,
        }
        return True, "CERTIFIE", envelope

    def verify_signature(self, action: str, params: Dict[str, Any], signature: str) -> bool:
        if not isinstance(action, str) or not isinstance(params, dict) or not isinstance(signature, str):
            return False
        expected = hmac.new(self.secret_key, self._canonical_payload(action, params), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_envelope(self, envelope: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(envelope, dict): return False, "Enveloppe invalide."
        if envelope.get("certified") is not True: return False, "Enveloppe non certifiée."
        action, params, signature = envelope.get("action"), envelope.get("params"), envelope.get("hsm_signature")
        if not all([action, isinstance(params, dict), signature]): return False, "Enveloppe incomplète."
        if action not in self.allowed_actions: return False, "Action absente."
        if set(params) - set(self.allowed_actions[action]): return False, "Paramètres non autorisés."
        if not self.verify_signature(action, params, signature): return False, "Signature invalide."
        return True, "OK"

    def runtime_status(self) -> Dict[str, Any]:
        return {"active": True, "allowed_actions_count": len(self.allowed_actions), "ephemeral_key_used": self._ephemeral_key_used}


security_guard = SecurityGuard()