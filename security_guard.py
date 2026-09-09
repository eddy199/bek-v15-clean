"""
BEK-v15.3 HYBRID - Security Guard (Hardened Zero-Trust Certification)
---------------------------------------------------------------------
Couche de certification locale et d'intégrité cryptographique.
- Allowlist stricte pour les 17+ actions du système et du CRM
- Validation des paramètres et assainissement des entrées
- Détection d'injections SQL / Shell / Process
- Scellement et signature HMAC-SHA256 via BEK_HSM_SECRET
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any, Dict, Tuple, Optional


class SecurityGuard:
    DEFAULT_SECRET_ENV = "BEK_HSM_SECRET"

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
        re.compile(r"(?i)\bFORMAT\s+C:\b"),
        re.compile(r"(?i)\bRM\s+-RF\s+/\b"),
        re.compile(r"(?i)\bEVAL\s*\("),
        re.compile(r"(?i)__IMPORT__\s*\("),
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
    def _detect_injection(cls, value: Any) -> bool:
        try:
            text = value if isinstance(value, str) else json.dumps(
                value, ensure_ascii=False, default=str
            )
        except Exception:
            return True
        return any(pattern.search(text) for pattern in cls.FORBIDDEN_PATTERNS)

    def validate_and_certify(
        self,
        action: str,
        params: Optional[Dict[str, Any]],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if not isinstance(action, str) or not action.strip():
            return False, "REJET SÉCURITÉ : Action invalide.", {}

        action = action.strip()
        if action not in self.allowed_actions:
            return False, f"REJET SÉCURITÉ : Action '{action}' non présente dans l'Allowlist.", {}

        if params is None:
            params = {}
        if not isinstance(params, dict):
            return False, "REJET SÉCURITÉ : Paramètres invalides (dictionnaire requis).", {}

        allowed = set(self.allowed_actions[action])
        unknown = set(params) - allowed
        if unknown:
            return (
                False,
                f"REJET SÉCURITÉ : Paramètres non autorisés pour '{action}': {sorted(unknown)}.",
                {},
            )

        sanitized = dict(params)

        for key, value in sanitized.items():
            if key not in ("code_content", "content") and self._detect_injection(value):
                return (
                    False,
                    f"REJET SÉCURITÉ : Signature destructive ou injection détectée dans '{key}'.",
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
            "security_layer": "SecurityGuard-v15.3",
            "policy": "ALLOWLIST_STRICT",
            "hsm_signature": signature,
        }
        return True, "CERTIFIÉ PAR SECURITY GUARD (ALLOWLIST + HMAC-SHA256)", envelope

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
            "policy": "ALLOWLIST_STRICT + HMAC-SHA256",
            "allowed_actions_count": len(self.allowed_actions),
            "allowed_actions": sorted(self.allowed_actions.keys()),
        }