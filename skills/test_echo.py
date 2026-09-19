import json
import sys

try:
    payload = json.loads(sys.stdin.read() or "{}")
except Exception:
    payload = {}

print(json.dumps({"echo": payload, "ok": True}))