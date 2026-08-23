import os, sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
print("=" * 60)
print("DIAGNOSTIC BEK AGENT v15 HYBRID")
print("=" * 60)
print(f"Python: {sys.version.split()[0]}")
print(f"Dossier: {ROOT}")

files = ["app.py", "config.py", "ai_service.py", "memory.py", "plugins.py",
         "file_gen.py", "skills.py", "index.html", "agent-ui.css", "agent-ui.js", "env.txt"]
print("\nFichiers:")
for f in files:
    status = "OK" if (ROOT / f).exists() else "MANQUANT"
    print(f"  [{status}] {f}")

for d in ["sessions", "skills", "plugins", "generated", "AGENT_WORKSPACE_v15"]:
    p = ROOT / d
    if not p.exists():
        p.mkdir(exist_ok=True)
        print(f"  [CREE] {d}/")
    else:
        print(f"  [OK]   {d}/")

deps = [("flask", "flask"), ("flask_cors", "flask-cors"), ("openai", "openai"),
        ("requests", "requests"), ("chromadb", "chromadb"), ("jsonschema", "jsonschema")]
print("\nDependances:")
for mod_name, pip_name in deps:
    try:
        __import__(mod_name)
        print(f"  [OK]   {pip_name}")
    except ImportError:
        print(f"  [KO]   {pip_name}  -> pip install {pip_name}")

try:
    import config
    print("\nConfig:")
    print(f"  [OK]   config.py charge")
    for prov in ["groq", "nvidia", "openrouter"]:
        cfg = config.MODELS.get(prov, {})
        key_ok = "OUI" if cfg.get("key") else "NON"
        print(f"  [{key_ok}]   {prov}: cle={'*' * 8 if cfg.get('key') else 'VIDE'}")
except Exception as e:
    print(f"\n  [ERREUR] config.py: {e}")

print("\n" + "=" * 60)
input("Appuie sur Entree pour fermer...")
