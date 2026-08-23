 
import hashlib
import hmac
import json
import re
from typing import Dict, Any, Tuple

class SecurityGuard:
    """
    Sas de Sécurité & Validation de l'Agent Auditeur (BEK-v15.2)
    - Filtrage OPA Gatekeeper (Liste blanche stricte)
    - Signature cryptographique virtuelle (HSM)
    - Détection d'injections SQL / Commandes destructives
    """
    def __init__(self, secret_key: str = "BEK_HSM_DEFAULT_SECRET_KEY"):
        self.secret_key = secret_key.encode('utf-8')
        
        # Liste blanche stricte des actions autorisées
        self.allowed_actions = {
            "create_contact": ["name", "email", "phone"],
            "create_deal": ["title", "amount"],
            "create_task": ["title"],
            "search_contact": ["query"],
            "update_contact": ["name", "email", "phone"],
            "get_stats": []
        }
        
        # Patterns d'injections et commandes interdites
        self.forbidden_patterns = [
            r"(?i)\b(drop\s+table|delete\s+from|truncate|alter\s+table)\b",
            r"(?i)\b(exec\s*\(|eval\s*\(|subprocess|os\.system|__import__)\b",
            r"(?i)(--|;--|\/\*|\*\/|@@|\bchar\b|\bnchar\b)"
        ]

    def _detect_injection(self, raw_str: str) -> bool:
        for pattern in self.forbidden_patterns:
            if re.search(pattern, raw_str):
                return True
        return False

    def validate_and_certify(self, action: str, params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Valide l'action, filtre les paramètres selon la liste blanche et génère
        le cachet de certification HSM.
        """
        # 1. Vérification de l'action autorisée (OPA Gatekeeper)
        if action not in self.allowed_actions:
            return False, f"REJET OPA: Action '{action}' non autorisée dans la liste blanche.", {}

        # 2. Vérification des injections dans les valeurs
        serialized = json.dumps(params)
        if self._detect_injection(serialized):
            return False, "REJET SÉCURITÉ: Détection de pattern dangereux / injection SQL.", {}

        # 3. Filtrage strict des clés autorisées
        allowed_keys = self.allowed_actions[action]
        sanitized_params = {k: v for k, v in params.items() if k in allowed_keys}

        # 4. Signature HSM Virtuel
        payload_to_sign = f"{action}:{json.dumps(sanitized_params, sort_keys=True)}"
        signature = hmac.new(self.secret_key, payload_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        certified_envelope = {
            "action": action,
            "params": sanitized_params,
            "certified": True,
            "hsm_signature": signature
        }

        return True, "CERTIFIÉ PAR AUDITEUR (OPA + HSM)", certified_envelope


if __name__ == "__main__":
    print("--- TEST UNITAIRE SECURITY_GUARD BEK-v15.2 ---")
    guard = SecurityGuard()

    # Test 1 : Action valide
    valid_ok, valid_msg, env = guard.validate_and_certify("create_contact", {
        "name": "Test User",
        "email": "test@domain.com",
        "hacker_extra_field": "ignore_me"
    })
    print(f"Test 1 (Valide) : {valid_ok} -> {valid_msg}")
    print(f"Payload épuré : {json.dumps(env)}")

    # Test 2 : Action non autorisée
    bad_ok, bad_msg, _ = guard.validate_and_certify("drop_database", {})
    print(f"Test 2 (Action illégale) : {bad_ok} -> {bad_msg}")

    # Test 3 : Tentative d'injection
    inj_ok, inj_msg, _ = guard.validate_and_certify("create_contact", {
        "name": "Admin'; DROP TABLE Contact; --",
        "email": "hacker@test.com"
    })
    print(f"Test 3 (Injection SQL) : {inj_ok} -> {inj_msg}")