
import json, sys
def run(payload=None):
    return {"ok": True, "echo": payload or {}}
print(json.dumps(run({"x": 1})))
