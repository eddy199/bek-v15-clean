import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
print("=" * 60)
print("DIAGNOSTIC BEK AGENT v15 HYBRID")
print("=" * 60)
print(f"Python : {sys.version.split()[0]}")
print(f"OS     : {sys.platform}")
print(f"Dossier: {ROOT}")

# ─── FICHIERS ESSENTIELS ───
files = [
    "app.py", "config.py", "ai_service.py", "memory.py", "plugins.py",
    "context_loader.py", "fast_math.py", "security_guard.py", "event_bus.py",
    "index.html", "agent-ui.css", "agent-ui.js", "env.txt"
]
print("\n[FICHIERS]")
for f in files:
    status = "OK" if (ROOT / f).exists() else "MANQUANT"
    print(f"  [{status}] {f}")

# ─── DOSSIERS ESSENTIELS ───
dirs = ["uploads", "generated", "plugins", "docs", "awesome-openclaw-skills"]
print("\n[DOSSIERS]")
for d in dirs:
    p = ROOT / d
    if not p.exists():
        p.mkdir(exist_ok=True, parents=True)
        print(f"  [CREE] {d}/")
    else:
        print(f"  [OK]   {d}/")

# ─── DÉPENDANCES PYTHON ───
deps = [
    ("flask", "flask"),
    ("flask_cors", "flask-cors"),
    ("requests", "requests"),
    ("openai", "openai"),
    ("dotenv", "python-dotenv"),
]
print("\n[DÉPENDANCES]")
for mod_name, pip_name in deps:
    try:
        __import__(mod_name)
        print(f"  [OK]   {pip_name}")
    except ImportError:
        print(f"  [KO]   {pip_name}  -> pip install {pip_name}")

# ─── MODULES INTERNES ───
internal_modules = [
    "memory", "context_loader", "fast_math", "security_guard", "event_bus", "plugins"
]
print("\n[MODULES INTERNES]")
for mod in internal_modules:
    try:
        __import__(mod)
        print(f"  [OK]   {mod}.py")
    except Exception as e:
        print(f"  [KO]   {mod}.py : {e}")

# ─── CLÉS API (depuis env.txt) ───
print("\n[CLÉS API]")
env_file = ROOT / "env.txt"
env_keys = {}
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("="):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env_keys[key.strip()] = val.strip().strip('"\' \r\n')

key_checks = [
    ("GROQ_API_KEY", "Groq"),
    ("NVIDIA_API_KEY", "NVIDIA NIM"),
    ("GEMINI_API_KEY", "Google Gemini"),
    ("OPENROUTER_API_KEY", "OpenRouter"),
    ("AGENTROUTER_API_KEY", "AgentRouter"),
    ("PINECONE_API_KEY", "Pinecone"),
]
for key_name, label in key_checks:
    val = env_keys.get(key_name, "")
    status = "OK" if val and len(val) > 10 else "VIDE"
    masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "VIDE"
    print(f"  [{status}] {label:20s} : {masked}")

# ─── CONFIG.PY ───
print("\n[CONFIG.PY]")
try:
    import config
    print(f"  [OK]   config.py chargé")
    for prov in ["groq", "nvidia", "openrouter"]:
        cfg = config.MODELS.get(prov, {})
        key_ok = "OK" if cfg.get("key") else "VIDE"
        model = cfg.get("model", "N/A")
        print(f"  [{key_ok}]   {prov:10s} : modèle={model}")
except Exception as e:
    print(f"  [ERREUR] config.py : {e}")

# ─── COMPTE SKILLS ───
print("\n[SKILLS]")
skills_dirs = [ROOT / "awesome-openclaw-skills", ROOT / "skills"]
total_skills = 0
for sd in skills_dirs:
    if sd.exists():
        try:
            count = len([f for f in os.listdir(sd) if f.endswith(('.json', '.txt'))])
            total_skills += count
            print(f"  [OK]   {sd.name:30s} : {count} skill(s)")
        except Exception as e:
            print(f"  [KO]   {sd.name:30s} : {e}")
if total_skills == 0:
    print("  [INFO] Aucun skill détecté. Créez des fichiers .json ou .txt dans awesome-openclaw-skills/")

print("\n" + "=" * 60)
print("DIAGNOSTIC TERMINÉ")
print("=" * 60)
input("Appuie sur Entrée pour fermer...")