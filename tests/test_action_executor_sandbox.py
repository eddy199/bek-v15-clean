# -*- coding: utf-8 -*-
"""Vérifie que create_dynamic_skill passe bien par le sandbox AST."""
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from services.action_executor import execute_agent_crm_tool


def main():
    # ----- TEST 1 : skill malveillant → REJET sandbox -----
    print("\n=== TEST 1 : skill avec import subprocess → doit être rejeté ===")
    res = execute_agent_crm_tool(
        "create_dynamic_skill",
        {
            "skill_name": "evil_skill",
            "code_content": (
                "import subprocess\n"
                "output = subprocess.run(['ls'])\n"
            ),
            "description": "test malveillant",
        },
    )
    print(f"Status : {res.get('status')}")
    print(f"Message : {res.get('message', '')[:200]}")
    assert res.get("status") == "error", "Le sandbox aurait dû refuser."
    assert "sandbox" in res.get("message", "").lower() \
        or "refus" in res.get("message", "").lower()
    print("✅ TEST 1 OK")

    # ----- TEST 2 : skill propre → sandbox OK -----
    print("\n=== TEST 2 : skill propre → sandbox OK ===")
    res = execute_agent_crm_tool(
        "create_dynamic_skill",
        {
            "skill_name": "clean_skill",
            "code_content": (
                "import math\n"
                "output = math.sqrt(16)\n"
            ),
            "description": "test propre",
        },
    )
    print(f"Status : {res.get('status')}")
    print(f"Message : {res.get('message', '')[:200]}")
    assert "refus" not in res.get("message", "").lower()
    assert "sandbox" not in res.get("message", "").lower()
    print("✅ TEST 2 OK")

    # ----- TEST 3 : action inconnue → error explicite -----
    print("\n=== TEST 3 : action inconnue ===")
    res = execute_agent_crm_tool("action_qui_nexiste_pas", {})
    print(f"Status : {res.get('status')}")
    print(f"Message : {res.get('message', '')[:200]}")
    assert res.get("status") == "error"
    assert "inconnue" in res.get("message", "").lower()
    print("✅ TEST 3 OK")

    print("\n🎉 TOUS LES TESTS PASSENT — ÉTAPE 5 VALIDÉE.\n")


if __name__ == "__main__":
    main()