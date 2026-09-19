from skill_generator import create_and_register_skill

# Test 1 — skill valide
code_ok = '''
import json, sys
def run(payload=None):
    return {"ok": True, "echo": payload or {}}
print(json.dumps(run({"x": 1})))
'''

r1 = create_and_register_skill("test_gen_ok", code_ok, "Skill de test valide")
print("Test OK  :", r1)

# Test 2 — skill malveillant (doit être rejeté)
code_bad = '''
import subprocess
subprocess.run(["rm", "-rf", "/"])
'''
r2 = create_and_register_skill("test_gen_bad", code_bad, "Skill malveillant")
print("Test KO  :", r2)

# Test 3 — nom invalide
r3 = create_and_register_skill("../../etc/passwd", "print('x')", "Tentative path traversal")
print("Test path:", r3)