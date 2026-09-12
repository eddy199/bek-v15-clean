from __future__ import annotations

import ast
import hashlib
import hmac
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger("bek.security_guard")
BASE_DIR = Path(__file__).resolve().parent


class SecurityGuard:
    DEFAULT_SECRET_ENV = "BEK_HSM_SECRET"

    # Fichiers sensibles strictement interdits à la lecture/écriture
    BLOCKED_SENSITIVE_FILES: Set[str] = {
        ".env",
        "env.txt",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "token.pickle",
        "config.json",
    }

    # Allowlist exhaustive des actions Hermes, CRM, Fichiers, Images et Terminal
    ALLOWED_ACTIONS: Dict[str, Tuple[str, ...]] = {
        # Actions CRM natives & Plugins
        "create_contact": ("name", "email", "phone", "firstName", "provider", "model"),
        "create_deal": ("title", "amount", "name", "provider", "model"),
        "create_task": ("title", "name", "description", "provider", "model"),
        "search_contact": ("query", "name", "provider", "model"),
        "update_contact": ("name", "email", "phone", "provider", "model"),
        "get_stats": ("provider", "model"),
        "neon_audit": ("tables", "provider", "model"),
        "default_llm": ("query", "skill", "prompt", "provider", "model"),

        # Actions Orchestration & Compétences
        "create_dynamic_skill": ("skill_name", "code_content", "description", "provider", "model"),
        "orchestrate": ("goal", "objective", "query", "provider", "model"),
        "run_swarm_task": ("goal", "objective", "task_description", "query", "provider", "model"),
        "multi_agent_workflow": ("goal", "objective", "query", "provider", "model"),
        "web_sync": ("query", "skill", "prompt", "provider", "model"),
        "web_search": ("query", "provider", "model"),
        "web_pipeline": ("query", "provider", "model"),

        # Actions Mémoire Vectorielle
        "save_memory": ("content", "provider", "model"),
        "remember": ("content", "provider", "model"),
        "save_to_memory": ("content", "provider", "model"),
        "search_memory": ("query", "top_k", "provider", "model"),
        "recall": ("query", "top_k", "provider", "model"),
        "delete_memory": ("record_id", "keyword", "provider", "model"),
        "forget": ("record_id", "keyword", "provider", "model"),
        "delete_from_memory": ("record_id", "keyword", "provider", "model"),

        # Actions Fichiers & Archives
        "write_file": ("filename", "content", "provider", "model"),
        "save_file": ("filename", "content", "provider", "model"),
        "create_file": ("filename", "content", "provider", "model"),
        "delete_file": ("filename", "provider", "model"),
        "read_file": ("filename", "provider", "model"),
        "extract_zip": ("zip_path", "extract_to", "provider", "model"),
        "create_zip": ("folder_path", "output_zip", "provider", "model"),
        "analyze_zip_content": ("zip_path", "provider", "model"),

        # Actions Multimédias & Vision
        "analyze_image": ("image_path", "prompt", "provider", "model"),
        "generate_image": ("prompt", "filename", "provider", "model"),
        "merge_and_edit_images": ("image_paths", "prompt", "provider", "model"),

        # Actions Terminal & Background (Validation L4/L5)
        "execute_command": ("command", "session_name", "provider", "model"),
        "run_script": ("command", "provider", "model"),
        "run_tests": ("command", "provider", "model"),
        "execute_tmux_headless": ("session_name", "command", "provider", "model"),
        "execute_background_task": ("session_name", "command", "provider", "model"),
        "start_background_task": ("session_name", "command", "provider", "model"),
        "stop_background_task": ("session_name", "provider", "model"),
        "stop_tmux_headless": ("session_name", "provider", "model"),
        "kill_session": ("session_name", "provider", "model"),
        "stop_session": ("session_name", "provider", "model"),
    }

    FORBIDDEN_PATTERNS = (
        re.compile(r"(?i)\bDROP\s+DATABASE\b"),
        re.compile(r"(?i)\bTRUNCATE\s+TABLE\b"),
        re.compile(r"(?i)\bFORMAT\s+[A-Z]:\b"),
        re.compile(r"(?i)\bRM\s+-RF\s+/\b"),
        re.compile(r"(?i)\bDEL\s+/[FQS]\s+[A-Z]:\\"),
        re.compile(r"(?i)\bEVAL\s*\("),
        re.compile(r"(?i)__IMPORT__\s*\("),
        re.compile(r"(?i)\bPOWERSHELL\b.*-ENC\b"),
        re.compile(r"(?i)\bNC\b.*-E\b"),
        re.compile(r"(?i)/DEV/(?:TCP|UDP)/"),
    )

    BANNED_IMPORTS: Set[str] = {
        "subprocess", "pty", "ctypes", "marshal", "pickle", "winreg"
    }

    SECRET_PATTERNS = (
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I),
        re.compile(r"AIza[0-9A-Za-z-_]{35}", re.I),
        re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.I),
        re.compile(r"nvapi-[a-zA-Z0-9-_]{20,}", re.I),
        re.compile(r"Bearer\s+[a-zA-Z0-9._\-]{20,}", re.I),
    )

    def __init__(self, secret_key: Optional[str] = None):
        key = secret_key or os.environ.get(self.DEFAULT_SECRET_ENV, "")
        if not key:
            key = self._read_env_file(self.DEFAULT_SECRET_ENV)
        if not key:
            key = "b078731f6b9fef2fafeac998854e8811b02f5427b95da0298dec3180a62aec0a"

        self.secret_key = key.strip("\"' \r\n").encode("utf-8")
        self.allowed_actions = dict(self.ALLOWED_ACTIONS)

    @staticmethod
    def _read_env_file(name: str) -> str:
        base = os.path.dirname(os.path.abspath(__file__))
        for filename in (".env", "env.txt"):
            path = os.path.join(base, filename)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith(name + "="):
                            return line.split("=", 1)[1].strip().strip("\"'")
            except OSError:
                continue
        return ""

    @classmethod
    def sanitize_secrets(cls, text: str) -> str:
        """DLP: Masque automatiquement les clés et tokens sensibles."""
        if not isinstance(text, str):
            return text
        sanitized = text
        for pattern in cls.SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @classmethod
    def validate_code_ast(cls, code_str: str) -> Tuple[bool, str]:
        """Analyse syntaxique AST tolérante (nettoie les balises markdown et le BOM)."""
        if not isinstance(code_str, str) or not code_str.strip():
            return True, "OK"
        
        cleaned = code_str.strip().lstrip("\ufeff")
        cleaned = re.sub(r"^```(?:python)?\s*|```$", "", cleaned, flags=re.M).strip()

        try:
            tree = ast.parse(cleaned)
        except SyntaxError:
            return True, "Ignoré (non-Python ou script brut)"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in cls.BANNED_IMPORTS:
                        return False, f"Import dangereux interdit : '{alias.name}'"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in cls.BANNED_IMPORTS:
                    return False, f"Import dangereux interdit : 'from {node.module}'"

        return True, "OK"

    @classmethod
    def _detect_injection(cls, value: Any) -> bool:
        try:
            text = value if isinstance(value, str) else json.dumps(
                value, ensure_ascii=False, default=str
            )
        except Exception:
            return True
        return any(pattern.search(text) for pattern in cls.FORBIDDEN_PATTERNS)

    @classmethod
    def _validate_path_confinement(cls, path_val: Any) -> Tuple[bool, str]:
        if not isinstance(path_val, str) or not path_val.strip():
            return False, "Chemin de fichier invalide ou vide."

        raw_clean = path_val.strip().strip("\"'")

        if ".." in raw_clean or raw_clean.startswith("/") or re.match(r"^[a-zA-Z]:", raw_clean):
            target_path = Path(raw_clean)
            if not target_path.is_absolute():
                target_path = (BASE_DIR / target_path).resolve()
            else:
                target_path = target_path.resolve()

            try:
                target_path.relative_to(BASE_DIR.resolve())
            except ValueError:
                return False, f"Sortie de sandbox refusee pour '{raw_clean}'."

        filename = Path(raw_clean).name.lower()
        if filename in cls.BLOCKED_SENSITIVE_FILES or filename.endswith((".key", ".pem", ".pfx")):
            return False, f"Acces interdit au fichier sensible '{filename}'."

        return True, "OK"

    def validate_and_certify(
        self,
        action: str,
        params: Optional[Dict[str, Any]],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if not isinstance(action, str) or not action.strip():
            return False, "REJET SECURITE : Action invalide.", {}

        action = action.strip()
        if action not in self.allowed_actions:
            return False, f"REJET SECURITE : Action '{action}' non presente dans l'Allowlist.", {}

        if params is None:
            params = {}
        if not isinstance(params, dict):
            return False, "REJET SECURITE : Parametres invalides (dictionnaire requis).", {}

        allowed = set(self.allowed_actions[action])
        unknown = set(params) - allowed
        if unknown:
            return (
                False,
                f"REJET SECURITE : Parametres non autorises pour '{action}': {sorted(unknown)}.",
                {},
            )

        sanitized = dict(params)

        # 1. Validation de confinement de chemin (Path Traversal Guard)
        file_keys = ("filename", "zip_path", "extract_to", "folder_path", "output_zip", "image_path")
        for f_key in file_keys:
            if f_key in sanitized:
                is_safe, err_msg = self._validate_path_confinement(sanitized[f_key])
                if not is_safe:
                    return False, f"REJET SECURITE : {err_msg}", {}

        # 2. Validation AST uniquement pour la création de code dynamique (EXCLUSION TOTALE de read_file)
        if action == "create_dynamic_skill" and "code_content" in sanitized:
            is_valid_code, err_code = self.validate_code_ast(sanitized["code_content"])
            if not is_valid_code:
                return False, f"REJET SECURITE : {err_code}", {}

        # 3. Détection d'injections
        for key, value in sanitized.items():
            if key not in ("code_content", "content") and self._detect_injection(value):
                return (
                    False,
                    f"REJET SECURITE : Signature destructive ou injection detectee dans '{key}'.",
                    {},
                )

        canonical = json.dumps(
            sanitized,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload = f"{action}:{canonical}"
        signature = hmac.new(
            self.secret_key,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        envelope = {
            "action": action,
            "params": sanitized,
            "certified": True,
            "security_layer": "SecurityGuard-v15.3-Hardened",
            "policy": "ALLOWLIST_STRICT + SANDBOX + DLP",
            "hsm_signature": signature,
        }
        return True, "CERTIFIE PAR SECURITY GUARD (ALLOWLIST + SANDBOX + HMAC-SHA256)", envelope

    def verify_signature(
        self,
        action: str,
        params: Dict[str, Any],
        signature: str,
    ) -> bool:
        if not isinstance(signature, str):
            return False
        canonical = json.dumps(
            params,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload = f"{action}:{canonical}"
        expected = hmac.new(
            self.secret_key,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "active": True,
            "policy": "ALLOWLIST_STRICT + SANDBOX + DLP + HMAC-SHA256",
            "allowed_actions_count": len(self.allowed_actions),
            "allowed_actions": sorted(self.allowed_actions.keys()),
        }


security_guard = SecurityGuard()
