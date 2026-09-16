"""
BEK-v15.2 HYBRID
Security Guard
----------------
Validation locale des actions Hermes/BEK.

Le Guard :
- applique une allowlist d'actions ;
- valide les paramètres ;
- détecte quelques signatures de payload dangereux ;
- signe les enveloppes avec HMAC ;
- ne lance ni SQL ni commande système.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any, Dict, Tuple


class SecurityGuard:
    DEFAULT_SECRET_ENV = "BEK_HSM_SECRET"

    ALLOWED_ACTIONS: Dict[str, Tuple[str, ...]] = {
        "create_contact": ("name", "email", "phone"),
        "create_deal": ("title", "amount"),
        "create_task": ("title",),
        "search_contact": ("query",),
        "update_contact": ("name", "email", "phone"),
        "get_stats": (),
        "web_sync": ("query", "skill", "prompt"),
        "neon_audit": (),
        "default_llm": ("query", "skill", "prompt"),
    }

    FORBIDDEN_PATTERNS = (
        re.compile(r"(?i)\bDROP\s+TABLE\b"),
        re.compile(r"(?i)\bDROP\s+DATABASE\b"),
        re.compile(r"(?i)\bTRUNCATE(?:\s+TABLE)?\b"),
        re.compile(r"(?i)\bALTER\s+TABLE\b"),
        re.compile(r"(?i)\bDELETE\s+FROM\b"),
        re.compile(r"(?i)\bEXEC(?:UTE)?\s*\("),
        re.compile(r"(?i)\bEVAL\s*\("),
        re.compile(r"(?i)\bSUBPROCESS\b"),
        re.compile(r"(?i)\bOS\.SYSTEM\b"),
        re.compile(r"(?i)__IMPORT__"),
    )

    def __init__(self, secret_key: str | None = None):
        key = secret_key or os.environ.get(self.DEFAULT_SECRET_ENV, "")
        if not key:
            key = self._read_env_file(self.DEFAULT_SECRET_ENV)
        if not key:
            raise RuntimeError(
                "BEK_HSM_SECRET is not configured. "
                "SecurityGuard refuses to start."
            )
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
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
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
        params: Dict[str, Any] | None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if not isinstance(action, str) or not action.strip():
            return False, "REJET SÉCURITÉ : action invalide.", {}

        action = action.strip()
        if action not in self.allowed_actions:
            return False, f"REJET OPA : Action '{action}' non autorisée.", {}

        if params is None:
            params = {}
        if not isinstance(params, dict):
            return False, "REJET SÉCURITÉ : paramètres invalides.", {}

        allowed = set(self.allowed_actions[action])
        unknown = set(params) - allowed
        if unknown:
            return (
                False,
                f"REJET SÉCURITÉ : paramètres non autorisés pour '{action}': {sorted(unknown)}.",
                {},
            )

        sanitized = dict(params)

        for key, value in sanitized.items():
            if self._detect_injection(value):
                return (
                    False,
                    f"REJET SÉCURITÉ : payload dangereux dans '{key}'.",
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
            "security_layer": "SecurityGuard",
            "policy": "ALLOWLIST",
            "hsm_signature": signature,
        }
        return True, "CERTIFIÉ PAR SECURITY GUARD (ALLOWLIST + HMAC)", envelope

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
        """Retourne uniquement l'état local du Guard, sans appel externe."""
        return {
            "active": True,
            "policy": "ALLOWLIST + HMAC",
            "allowed_actions": sorted(self.allowed_actions.keys()),
        }
