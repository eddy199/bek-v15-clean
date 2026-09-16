"""
skills.py — BEK-v15 Hybrid
Compatible avec l'app.py original (list_skills, get_skill, save_skill, delete_skill, build_skill_prompt)
+ Nouveaux skills natifs : /fs, /help, /code, /mem, /web, /img
"""

import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime

# ─── Stockage skills personnalisés ────────────────────────────
SKILLS_FILE = Path("skills.json")

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

# ─── API compatible app.py original ────────────────────────────

def list_skills():
    """Retourne tous les skills (personnalisés + natifs)."""
    custom = _load_custom()
    # Ajouter les natifs
    natifs = [
        {"name": "filesystem", "command": "/fs", "description": "Lecture, écriture, suppression et listing de fichiers", "category": "Système", "tags": ["fs", "files"], "builtin": True, "code": "Skill natif filesystem"},
        {"name": "codeur", "command": "/code", "description": "Génère du code et propose l'écriture sur disque", "category": "Code", "tags": ["code", "dev"], "builtin": True, "code": "Skill natif codeur"},
        {"name": "memory", "command": "/mem", "description": "Sauvegarde une note en mémoire locale", "category": "Mémoire", "tags": ["memoire"], "builtin": True, "code": "Skill natif memory"},
        {"name": "web_search", "command": "/web", "description": "Recherche sur le web", "category": "Web", "tags": ["search", "web"], "builtin": True, "code": "Skill natif web_search"},
        {"name": "image_generator", "command": "/img", "description": "Génération d'images via IA", "category": "Images", "tags": ["image", "ai"], "builtin": True, "code": "Skill natif image_generator"},
        {"name": "help", "command": "/help", "description": "Affiche l'aide des commandes", "category": "Système", "tags": ["help"], "builtin": True, "code": "Skill natif help"},
    ]
    return natifs + custom

def get_skill(name):
    for s in list_skills():
        if s.get("name") == name or s.get("command") == name:
            return s
    return None

def save_skill(data):
    if not data.get("name") or not data.get("code"):
        return {"error": "Nom et instruction (code) requis"}
    skills = _load_custom()
    idx = next((i for i, s in enumerate(skills) if s.get("name") == data["name"]), None)
    if idx is not None:
        skills[idx] = data
    else:
        skills.append(data)
    _save_custom(skills)
    return {"ok": True}

def delete_skill(name):
    skills = _load_custom()
    skills = [s for s in skills if s.get("name") != name]
    _save_custom(skills)
    return {"ok": True}

def build_skill_prompt(skill, user_input):
    code = skill.get("code", "")
    return code.replace("{input}", user_input)

# ─── NOUVEAU : dispatch_command pour routing backend ──────────

# Root workspace
WS_DIR = os.path.dirname(os.path.abspath(__file__))
WS_DIR = os.path.abspath(os.path.normpath(WS_DIR))

def _resolve_path(user_path):
    if not user_path:
        return None, "Chemin vide."
    p = user_path.strip().replace("/", os.sep)
    if os.path.isabs(p):
        p_norm = os.path.normpath(os.path.abspath(p))
        if not p_norm.startswith(WS_DIR):
            return None, "Chemins absolus hors workspace interdits."
        return p_norm, None
    target = os.path.normpath(os.path.join(WS_DIR, p))
    if not target.startswith(WS_DIR):
        return None, "Navigation hors workspace détectée (.. interdit)."
    if os.path.islink(target):
        return None, "Liens symboliques interdits."
    return target, None

def dispatch_command(text):
    """Analyse une commande / et retourne un dict {ok, output} ou None si non gérée."""
    text = text.strip()
    if not text.startswith("/"):
        return None
    parts = text.split(None, 2)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    rest = parts[2] if len(parts) > 2 else ""

    if cmd == "/help":
        lines = [
            "### 📋 Commandes disponibles",
            "",
            "**Skills natifs :**",
            "- `/fs read <fichier>` — Lit un fichier",
            "- `/fs write <fichier> <contenu>` — Écrit un fichier",
            "- `/fs delete <chemin>` — Supprime un fichier ou dossier",
            "- `/fs replace <fichier> <ancien> >>> <nouveau>` — Remplace du texte",
            "- `/fs list <dossier>` — Liste le contenu",
            "- `/fs mkdir <dossier>` — Crée un dossier",
            "- `/code <description>` — Génère du code",
            "- `/mem <texte>` — Sauvegarde en mémoire",
            "- `/web <requête>` — Recherche web",
            "- `/img <description>` — Génère une image",
            "",
            "**Commandes UI :**",
            "- `/help` — Cette aide",
            "- `/new` — Nouvelle conversation",
            "- `/skills` — Liste les skills (onglet Compétences)",
            "- `/memory <requête>` — Recherche mémoire vectorielle",
        ]
        return {"ok": True, "output": "\n".join(lines)}

    if cmd == "/fs":
        tokens = args.split(None, 1)
        action = tokens[0].lower() if tokens else ""
        path_arg = tokens[1] if len(tokens) > 1 else ""
        target, err = _resolve_path(path_arg)
        if err:
            return {"ok": False, "output": "❌ " + err}

        try:
            if action == "read":
                if not os.path.isfile(target):
                    return {"ok": False, "output": f"❌ Fichier introuvable: {path_arg}"}
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    return {"ok": True, "output": f"📄 **{path_arg}**\n```\n{f.read()}\n```"}

            elif action == "write":
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(rest)
                return {"ok": True, "output": f"✅ Fichier écrit: `{path_arg}`"}

            elif action == "delete":
                if os.path.isfile(target):
                    os.remove(target)
                    return {"ok": True, "output": f"🗑️ Fichier supprimé: `{path_arg}`"}
                elif os.path.isdir(target):
                    shutil.rmtree(target)
                    return {"ok": True, "output": f"🗑️ Dossier supprimé: `{path_arg}`"}
                return {"ok": False, "output": f"❌ Introuvable: {path_arg}"}

            elif action == "replace":
                if not os.path.isfile(target):
                    return {"ok": False, "output": f"❌ Fichier introuvable: {path_arg}"}
                if " >>> " in rest:
                    old, new = rest.split(" >>> ", 1)
                else:
                    return {"ok": False, "output": "❌ Format: `/fs replace fichier.py ancien >>> nouveau`"}
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if old not in content:
                    return {"ok": False, "output": f"❌ Texte à remplacer introuvable dans `{path_arg}`"}
                new_content = content.replace(old, new, 1)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return {"ok": True, "output": f"🔄 Remplacement effectué dans `{path_arg}`"}

            elif action == "list":
                if not os.path.isdir(target):
                    return {"ok": False, "output": f"❌ Dossier introuvable: {path_arg}"}
                items = []
                for entry in os.listdir(target):
                    full = os.path.join(target, entry)
                    typ = "📁" if os.path.isdir(full) else "📄"
                    size = os.path.getsize(full) if os.path.isfile(full) else "-"
                    items.append(f"{typ} {entry}  ({size} bytes)")
                return {"ok": True, "output": f"📂 **{path_arg}**\n" + ("\n".join(items) if items else "(vide)")}

            elif action == "mkdir":
                os.makedirs(target, exist_ok=True)
                return {"ok": True, "output": f"📁 Dossier créé: `{path_arg}`"}

            else:
                return {"ok": False, "output": f"❌ Action inconnue: `{action}`. Utilise: read, write, delete, replace, list, mkdir"}

        except PermissionError:
            return {"ok": False, "output": f"❌ Permission refusée: {path_arg}"}
        except Exception as e:
            return {"ok": False, "output": f"❌ Erreur: {e}"}

    if cmd == "/code":
        if not args:
            return {"ok": False, "output": "❌ Usage: `/code <description du code à générer>`"}
        return {
            "ok": True,
            "output": f"💻 **Génération de code**\n\nDemande: {args}\n\n⏳ Envoie cette demande au modèle IA via le chat normal pour obtenir le code."
        }

    if cmd == "/mem":
        if not args:
            return {"ok": False, "output": "❌ Usage: `/mem <texte à mémoriser>`"}
        mem_file = os.path.join(WS_DIR, "memory_store.json")
        entries = []
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                entries = []
        entries.append({"timestamp": datetime.now().isoformat(), "content": args})
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        return {"ok": True, "output": f"🧠 Mémorisé ({len(entries)} entrées au total)."}

    if cmd == "/web":
        if not args:
            return {"ok": False, "output": "❌ Usage: `/web <requête de recherche>`"}
        return {"ok": True, "output": f"🌐 Recherche web pour : {args}\n\n⏳ Envoie cette requête au service de recherche."}

    if cmd == "/img":
        if not args:
            return {"ok": False, "output": "❌ Usage: `/img <description de l'image>`"}
        return {"ok": True, "output": f"🎨 Génération d'image : {args}\n\n⏳ Envoie cette demande au service d'images."}

    # Commande non reconnue par les skills natifs → laisser l'IA gérer
    return None
