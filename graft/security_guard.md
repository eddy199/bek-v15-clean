---
covers: []
---
# security_guard.py

- SecurityGuard · class · L8-L70 — class SecurityGuard
- __init__ · method · L15-L33 — def __init__(self, secret_key: str = "BEK_HSM_DEFAULT_SECRET_KEY")
- _detect_injection · method · L35-L39 — def _detect_injection(self, raw_str: str) -> bool
- validate_and_certify · method · L41-L70 — def validate_and_certify(self, action: str, params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]
