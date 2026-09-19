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

BASE_DIR = Path(__file__).resolve().parent


class SecurityGuard:
    DEFAULT_SECRET_ENV = "BEK_HSM_SECRET"

    BLOCKED_SENSITIVE_FILES: Set[str] = {
        ".env",
        "env.txt",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "token.pickle",
        "config.json",
    }

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
        "create_dynamic_skill": (
            "skill_name",
            "code_content",
            "description",
            "provider",
            "model",
        ),
        "orchestrate": ("goal", "objective", "query", "provider", "model"),
        "run_swarm_task": (
            "goal",
            "objective",
            "task_description",
            "query",
            "provider",
            "model",
        ),
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

        # Fichiers
        "write_file": ("filename", "content", "provider", "model"),
        "save_file": ("filename", "content", "provider", "model"),
        "create_file": ("filename", "content", "provider", "model"),
        "delete_file": ("filename", "provider", "model"),
        "read_file": ("filename", "provider", "model"),
        "extract_zip": ("zip_path", "extract_to", "provider", "model"),
        "create_zip": ("folder_path", "output_zip", "provider", "model"),
        "analyze_zip_content": ("zip_path", "provider", "model"),

        # Multimédia
        "analyze_image": ("image_path", "prompt", "provider", "model"),
        "generate_image": ("prompt", "filename", "provider", "model"),
        "merge_and_edit_images": (
            "image_paths",
            "prompt",
            "provider",
            "model",
        ),

        # Terminal / Background
        "execute_command": ("command", "session_name", "provider", "model"),
        "run_script": ("command", "provider", "model"),
        "run_tests": ("command", "provider", "model"),
        "execute_tmux_headless": (
            "session_name",
            "command",
            "provider",
            "model",
        ),
        "execute_background_task": (
            "session_name",
            "command",
            "provider",
            "model",
        ),
        "start_background_task": (
            "session_name",
            "command",
            "provider",
            "model",
        ),
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
        re.compile(r"(?i)\bPOWERSHELL\b.*-ENC\b"),
        re.compile(r"(?i)\bNC\b.*-E\b"),
        re.compile(r"(?i)/DEV/(?:TCP|UDP)/"),
    )

    FORBIDDEN_CODE_PATTERNS = (
        re.compile(r"(?i)\beval\s*\("),
        re.compile(r"(?i)\bexec\s*\("),
        re.compile(r"(?i)\bcompile\s*\("),
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

    BANNED_IMPORTS: Set[str] = {
        "subprocess",
        "pty",
        "ctypes",
        "marshal",
        "pickle",
        "winreg",
        "urllib",
        "requests",
        "http",
        "socket",
        "shutil",
        "os",
        "sys",
        "importlib",
        "multiprocessing",
        "threading",
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

            logger.warning(
                "SecurityGuard : aucune clé HMAC persistante trouvée. "
                "Une clé éphémère a été générée pour cette session. "
                "Définissez BEK_HSM_SECRET en production."
            )

        self.secret_key = key.strip("\"' \r\n").encode("utf-8")

        if len(self.secret_key) < 32:
            raise ValueError(
                "BEK_HSM_SECRET doit contenir au minimum 32 caractères."
            )

        self.allowed_actions = dict(self.ALLOWED_ACTIONS)

    # ------------------------------------------------------------------
    # ENV
    # ------------------------------------------------------------------

    @staticmethod
    def _read_env_file(name: str) -> str:
        for filename in (".env", "env.txt"):
            path = BASE_DIR / filename

            if not path.exists():
                continue

            try:
                with path.open(
                    "r",
                    encoding="utf-8-sig",
                    errors="ignore",
                ) as fh:
                    for line in fh:
                        line = line.strip()

                        if line.startswith(name + "="):
                            return (
                                line.split("=", 1)[1]
                                .strip()
                                .strip("\"'")
                            )

            except OSError:
                continue

        return ""

    # ------------------------------------------------------------------
    # DLP
    # ------------------------------------------------------------------

    @classmethod
    def sanitize_secrets(cls, text: str) -> str:
        if not isinstance(text, str):
            return text

        sanitized = text

        for pattern in cls.SECRET_PATTERNS:
            sanitized = pattern.sub(
                "[REDACTED_SECRET]",
                sanitized,
            )

        return sanitized

    # ------------------------------------------------------------------
    # AST
    # ------------------------------------------------------------------

    @classmethod
    def validate_code_ast(cls, code_str: str) -> Tuple[bool, str]:
        if not isinstance(code_str, str) or not code_str.strip():
            return True, "OK"

        cleaned = code_str.strip().lstrip("\ufeff")

        cleaned = re.sub(
            r"^```(?:python)?\s*|```$",
            "",
            cleaned,
            flags=re.M,
        ).strip()

        try:
            tree = ast.parse(cleaned)
        except SyntaxError as exc:
            return False, f"Code non analysable (SyntaxError) : {exc.msg}"

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]

                    if root_mod in cls.BANNED_IMPORTS:
                        return (
                            False,
                            f"Import dangereux interdit : '{alias.name}'",
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]

                    if root_mod in cls.BANNED_IMPORTS:
                        return (
                            False,
                            f"Import dangereux interdit : "
                            f"'from {node.module}'",
                        )

        return True, "OK"

    # ------------------------------------------------------------------
    # INJECTION
    # ------------------------------------------------------------------

    @classmethod
    def _detect_injection(
        cls,
        value: Any,
        strict_code: bool = False,
    ) -> bool:

        try:
            text = (
                value
                if isinstance(value, str)
                else json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                )
            )
        except Exception:
            return True

        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern.search(text):
                return True

        if strict_code:
            for pattern in cls.FORBIDDEN_CODE_PATTERNS:
                if pattern.search(text):
                    return True

        return False

    # ------------------------------------------------------------------
    # PATH CONFINEMENT
    # ------------------------------------------------------------------

    @classmethod
    def _validate_path_confinement(
        cls,
        path_val: Any,
    ) -> Tuple[bool, str]:

        if not isinstance(path_val, str) or not path_val.strip():
            return False, "Chemin de fichier invalide ou vide."

        raw_clean = path_val.strip().strip("\"'")

        if "\x00" in raw_clean:
            return False, "Chemin contenant un caractère nul interdit."

        target_path = Path(raw_clean)

        # Tous les chemins sont résolus dans BASE_DIR.
        if target_path.is_absolute():
            resolved = target_path.resolve()
        else:
            resolved = (BASE_DIR / target_path).resolve()

        try:
            resolved.relative_to(BASE_DIR.resolve())
        except ValueError:
            return (
                False,
                f"Sortie de sandbox refusée pour '{raw_clean}'.",
            )

        filename = resolved.name.lower()

        if (
            filename in cls.BLOCKED_SENSITIVE_FILES
            or filename.endswith((".key", ".pem", ".pfx"))
        ):
            return (
                False,
                f"Accès interdit au fichier sensible '{filename}'.",
            )

        return True, "OK"

    # ------------------------------------------------------------------
    # CANONICALISATION HMAC
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical_payload(
        action: str,
        params: Dict[str, Any],
    ) -> bytes:

        canonical = json.dumps(
            params,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return f"{action}:{canonical}".encode("utf-8")

    # ------------------------------------------------------------------
    # CERTIFICATION
    # ------------------------------------------------------------------

    def validate_and_certify(
        self,
        action: str,
        params: Optional[Dict[str, Any]],
    ) -> Tuple[bool, str, Dict[str, Any]]:

        if not isinstance(action, str) or not action.strip():
            return (
                False,
                "REJET SECURITE : Action invalide.",
                {},
            )

        action = action.strip()

        if action not in self.allowed_actions:
            return (
                False,
                f"REJET SECURITE : Action '{action}' "
                "non presente dans l'Allowlist.",
                {},
            )

        if params is None:
            params = {}

        if not isinstance(params, dict):
            return (
                False,
                "REJET SECURITE : Parametres invalides.",
                {},
            )

        allowed = set(self.allowed_actions[action])
        unknown = set(params) - allowed

        if unknown:
            return (
                False,
                f"REJET SECURITE : Parametres non autorises "
                f"pour '{action}': {sorted(unknown)}.",
                {},
            )

        sanitized = dict(params)

        # --------------------------------------------------------------
        # PATHS
        # --------------------------------------------------------------

        file_keys = (
            "filename",
            "zip_path",
            "extract_to",
            "folder_path",
            "output_zip",
            "image_path",
        )

        for key in file_keys:
            if key in sanitized:

                is_safe, err_msg = self._validate_path_confinement(
                    sanitized[key]
                )

                if not is_safe:
                    return (
                        False,
                        f"REJET SECURITE : {err_msg}",
                        {},
                    )

        # --------------------------------------------------------------
        # CODE AST
        # --------------------------------------------------------------

        if (
            action == "create_dynamic_skill"
            and "code_content" in sanitized
        ):
            valid, error = self.validate_code_ast(
                sanitized["code_content"]
            )

            if not valid:
                return (
                    False,
                    f"REJET SECURITE : {error}",
                    {},
                )

        # --------------------------------------------------------------
        # INJECTION / DLP
        # --------------------------------------------------------------

        for key, value in sanitized.items():

            strict_code = key in {
                "content",
                "code_content",
            }

            if self._detect_injection(
                value,
                strict_code=strict_code,
            ):
                return (
                    False,
                    "REJET SECURITE : Signature destructive "
                    f"ou injection detectee dans '{key}'.",
                    {},
                )

        # --------------------------------------------------------------
        # HMAC
        # --------------------------------------------------------------

        payload = self._canonical_payload(
            action,
            sanitized,
        )

        signature = hmac.new(
            self.secret_key,
            payload,
            hashlib.sha256,
        ).hexdigest()

        envelope = {
            "action": action,
            "params": sanitized,
            "certified": True,
            "security_layer": "SecurityGuard-v16-Hardened",
            "policy": (
                "ALLOWLIST_STRICT + SANDBOX + DLP "
                "+ HMAC-SHA256"
            ),
            "hsm_signature": signature,
            "ephemeral_key": self._ephemeral_key_used,
        }

        return (
            True,
            "CERTIFIE PAR SECURITY GUARD "
            "(ALLOWLIST + SANDBOX + DLP + HMAC-SHA256)",
            envelope,
        )

    # ------------------------------------------------------------------
    # VERIFY SIGNATURE
    # ------------------------------------------------------------------

    def verify_signature(
        self,
        action: str,
        params: Dict[str, Any],
        signature: str,
    ) -> bool:

        if not isinstance(action, str):
            return False

        if not isinstance(params, dict):
            return False

        if not isinstance(signature, str):
            return False

        expected = hmac.new(
            self.secret_key,
            self._canonical_payload(action, params),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(
            expected,
            signature,
        )

    # ------------------------------------------------------------------
    # VERIFY ENVELOPE
    # ------------------------------------------------------------------

    def verify_envelope(
        self,
        envelope: Dict[str, Any],
    ) -> Tuple[bool, str]:

        if not isinstance(envelope, dict):
            return False, "Enveloppe absente ou invalide."

        if envelope.get("certified") is not True:
            return False, "Enveloppe non certifiée."

        action = envelope.get("action")
        params = envelope.get("params")
        signature = envelope.get("hsm_signature")

        if (
            not isinstance(action, str)
            or not action
            or not isinstance(params, dict)
            or not isinstance(signature, str)
            or not signature
        ):
            return (
                False,
                "Enveloppe incomplète "
                "(action/params/signature manquants).",
            )

        # L'action doit toujours être présente dans l'allowlist.
        if action not in self.allowed_actions:
            return (
                False,
                f"Action '{action}' absente de l'Allowlist.",
            )

        # Les paramètres de l'enveloppe doivent eux-mêmes
        # respecter l'allowlist.
        allowed = set(self.allowed_actions[action])

        if set(params) - allowed:
            return (
                False,
                "Paramètres de l'enveloppe non autorisés.",
            )

        if not self.verify_signature(
            action,
            params,
            signature,
        ):
            return False, "Signature HMAC invalide."

        return True, "OK"

    # ------------------------------------------------------------------
    # RUNTIME STATUS
    # ------------------------------------------------------------------

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "active": True,
            "policy": (
                "ALLOWLIST_STRICT + SANDBOX + DLP "
                "+ HMAC-SHA256"
            ),
            "allowed_actions_count": len(
                self.allowed_actions
            ),
            "allowed_actions": sorted(
                self.allowed_actions.keys()
            ),
            "ephemeral_key_used": self._ephemeral_key_used,
        }


security_guard = SecurityGuard()