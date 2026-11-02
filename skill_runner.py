"""
skills.py — BEK-v20.1 (Scan Absolu & Affichage Brut)
"""
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

SKILLS_FILE = Path("skills.json")
SKILLS_DIR = Path(__file__).resolve().parent / "skills"

def _load_custom():
    if SKILLS_FILE.exists():
        try:
            with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_custom(data):
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def list_skills():
    custom = _load_custom()
    
    # 1. Skills Natifs
    natifs = [
        {"name": "filesystem", "command": "/fs", "description": "Gestionnaire de fichiers", "category": "Système", "tags": ["fs"], "builtin": True, "code": "Skill natif filesystem"},
        {"name": "codeur", "command": "/code", "description": "Génération de code", "category": "Code", "tags": ["code"], "builtin": True, "code": "Skill natif codeur"},
        {"name": "memory", "command": "/mem", "description": "Mémoire locale", "category": "Mémoire", "tags": ["mem"], "builtin": True, "code": "Skill natif memory"},
        {"name": "web_search", "command": "/web", "description": "Recherche web", "category": "Web", "tags": ["web"], "builtin": True, "code": "Skill natif web_search"},
        {"name": "image_generator", "command": "/img", "description": "Génération d'images", "category": "Images", "tags": ["img"], "builtin": True, "code": "Skill natif image_generator"},
        {"name": "help", "command": "/help", "description": "Aide", "category": "Système", "tags": ["help"], "builtin": True, "code": "Skill natif help"},
    ]
    
    # 2. Scan Absolu avec os.walk (entre dans tous les sous-dossiers)
    folder_skills = []
    if SKILLS_DIR.exists():
        for root, dirs, files in os.walk(SKILLS_DIR):
            for file in files:
                # On ignore les fichiers cachés et les .pyc
                if file.startswith(".") or file.endswith(".pyc"):
                    continue
                
                filepath = Path(root) / file
                ext = filepath.suffix.lower()
                
                # On accepte tous les formats
                if ext not in (".md", ".txt", ".py", ".json", ".yaml", ".yml"):
                    continue

                # Si c'est un alter-ego (SKILL.md), on prend le nom du dossier parent
                name = filepath.stem
                if file == "SKILL.md":
                    name = filepath.parent.name

                category = "Fichier"
                if "game" in str(filepath).lower() or "jeu" in str(filepath).lower():
                    category = "Jeu"
                elif "alter-egos" in str(filepath).lower():
                    category = "Alter Ego"

                desc = f"Fichier : {file}"
                if ext == ".md":
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                if line.startswith("# "):
                                    desc = line.replace("# ", "").strip()
                                    break
                    except: pass

                folder_skills.append({
                    "name": name,
                    "command": f"/{name}",
                    "description": desc,
                    "category": category,
                    "tags": [ext.replace(".", "")],
                    "builtin": False,
                    "code": f"Chemin: {filepath}"
                })

    # 3. Fusion (Natifs + Custom + Tous les fichiers trouvés)
    return natifs + custom + folder_skills

def get_skill(name):
    for s in list_skills():
        if s.get("name") == name or s.get("command") == name:
            return s
    return None

def save_skill(data):
    if not data.get("name") or not data.get("code"): return {"error": "Données manquantes"}
    skills = _load_custom()
    idx = next((i for i, s in enumerate(skills) if s.get("name") == data["name"]), None)
    if idx is not None: skills[idx] = data
    else: skills.append(data)
    _save_custom(skills)
    return {"ok": True}

def delete_skill(name):
    skills = _load_custom()
    skills = [s for s in skills if s.get("name") != name]
    _save_custom(skills)
    return {"ok": True}

def build_skill_prompt(skill, user_input):
    return skill.get("code", "").replace("{input}", user_input)

WS_DIR = os.path.dirname(os.path.abspath(__file__))
def _resolve_path(user_path):
    if not user_path: return None, "Chemin vide."
    target = os.path.normpath(os.path.join(WS_DIR, user_path.strip()))
    return target, None

def dispatch_command(text):
    return None