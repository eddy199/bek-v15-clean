import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

from config import (
    ROOT, ENV_FILE, ENV, MODELS, NVIDIA_MODELS, GROQ_API_KEY, NVIDIA_API_KEY,
    PINECONE_API_KEY, WS_DIR, SKILLS_DIR, PLUGINS_DIR, GENERATED_DIR, UPLOAD_DIR, logger
)
from ai_service import (
    call_ai_stream, call_ai, configured_providers, 
    list_models, fetch_models, PROVIDER_NAMES
)

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 350 * 1024 * 1024

AGENT_BRIDGE_SECRET = os.getenv("AGENT_BRIDGE_SECRET", "dev-bridge-secret-crm-bek-2026")

def _check_auth():
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {AGENT_BRIDGE_SECRET}"
    if not auth_header or auth_header != expected:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None

# ─── Service Fichiers Statiques ───────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory(ROOT, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    file_path = ROOT / path
    if file_path.exists():
        return send_from_directory(ROOT, path)
    return jsonify({"status": "BEK-v15 HYBRID Agent running", "time": datetime.now(timezone.utc).isoformat()})

# ─── Routes API UI Agent ─────────────────────────────────

@app.route("/api/config", methods=["GET"])
def api_config():
    providers_list = []
    for pid, pcfg in MODELS.items():
        providers_list.append({
            "id": pid,
            "name": PROVIDER_NAMES.get(pid, pid.capitalize()),
            "configured": bool(pcfg.get("key"))
        })
    
    models_dict = {}
    for pid in MODELS:
        models_dict[pid] = list_models(pid)

    skills_count = len(list(SKILLS_DIR.glob("*.json"))) if SKILLS_DIR.exists() else 0
    files_count = len(list(GENERATED_DIR.glob("*"))) if GENERATED_DIR.exists() else 0

    return jsonify({
        "agent": "BEK-v15-HYBRID",
        "providers": providers_list,
        "models": models_dict,
        "skills_count": skills_count,
        "files_count": files_count
    })

@app.route("/api/system/status", methods=["GET"])
def api_system_status():
    return jsonify({
        "status": "ok",
        "providers": {pid: bool(cfg.get("key")) for pid, cfg in MODELS.items()}
    })

@app.route("/api/keys", methods=["GET", "POST"])
def api_keys():
    if request.method == "GET":
        return jsonify({
            "GROQ_API_KEY": bool(MODELS.get("groq", {}).get("key")),
            "NVIDIA_API_KEY": bool(MODELS.get("nvidia", {}).get("key")),
            "PINECONE_API_KEY": bool(PINECONE_API_KEY),
        })

    data = request.get_json(silent=True) or {}
    key_name = data.get("key_name")
    key_value = data.get("key_value", "").strip()

    if not key_name or not key_value:
        return jsonify({"ok": False, "error": "Nom et valeur de clé requis"}), 400

    ENV[key_name] = key_value
    
    prov_map = {
        "GROQ_API_KEY": "groq",
        "NVIDIA_API_KEY": "nvidia"
    }
    if key_name in prov_map:
        MODELS[prov_map[key_name]]["key"] = key_value

    try:
        lines = []
        if ENV_FILE.exists():
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{key_name}="):
                new_lines.append(f"{key_name}={key_value}\n")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"\n{key_name}={key_value}\n")

        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        return jsonify({"ok": True, "message": f"Clé {key_name} enregistrée"})
    except Exception as e:
        logger.error(f"Erreur sauvegarde clé {key_name}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/models/fetch", methods=["POST"])
def api_models_fetch():
    data = request.get_json(silent=True) or {}
    provider = data.get("provider", "nvidia")
    models = fetch_models(provider)
    return jsonify({"ok": True, "provider": provider, "models": models})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "nvidia")
    model = data.get("model")

    async def generate():
        try:
            async for item in call_ai_stream(messages, provider=provider, model=model):
                yield f"data: {json.dumps(item)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    def sync_gen():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = generate()
        try:
            while True:
                item = loop.run_until_complete(gen.__anext__())
                yield item
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    return Response(sync_gen(), mimetype="text/event-stream")

# ─── Upload Tout Format (jusqu'à 300 Mo) ───────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Aucun fichier reçu"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "Nom de fichier invalide"}), 400
    
    save_path = UPLOAD_DIR / file.filename
    file.save(save_path)
    file_size = save_path.stat().st_size

    text_content = ""
    ext = save_path.suffix.lower()
    text_extensions = [".txt", ".py", ".js", ".html", ".css", ".json", ".md", ".sh", ".csv", ".yml", ".yaml", ".env", ".c", ".cpp", ".ts", ".sql"]
    if ext in text_extensions and file_size < 5 * 1024 * 1024:
        try:
            text_content = save_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "filename": file.filename,
        "path": str(save_path),
        "size": file_size,
        "is_text": bool(text_content),
        "text_sample": text_content[:25000] if text_content else ""
    })

# ─── Autres routes API ────────────────────────────────────

@app.route("/api/skills", methods=["GET", "POST"])
def api_skills():
    if request.method == "GET":
        skills = []
        if SKILLS_DIR.exists():
            for f in SKILLS_DIR.glob("*.json"):
                try:
                    skills.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    pass
        return jsonify({"ok": True, "skills": skills})
    
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"ok": False, "error": "Nom requis"}), 400
    filepath = SKILLS_DIR / f"{name}.json"
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"ok": True, "skill": data})

@app.route("/api/skills/<name>", methods=["DELETE"])
def api_skill_del(name):
    filepath = SKILLS_DIR / f"{name}.json"
    if filepath.exists():
        filepath.unlink()
    return jsonify({"ok": True})

@app.route("/api/files", methods=["GET"])
def api_files():
    files = []
    if GENERATED_DIR.exists():
        for f in GENERATED_DIR.glob("*"):
            if f.is_file():
                stat = f.stat()
                files.append({
                    "file_id": f.name,
                    "filename": f.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
    return jsonify({"ok": True, "files": files})

@app.route("/api/files/<filename>", methods=["GET"])
def api_file_get(filename):
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

@app.route("/api/memory/stats", methods=["GET"])
def api_memory_stats():
    return jsonify({
        "pinecone": bool(PINECONE_API_KEY),
        "chroma": False,
        "dimension": 1536
    })

@app.route("/api/memory/search", methods=["POST"])
def api_memory_search():
    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "results": []})

@app.route("/api/memory/add", methods=["POST"])
def api_memory_add():
    return jsonify({"ok": True})

@app.route("/api/plugins", methods=["GET"])
def api_plugins():
    return jsonify({"ok": True, "plugins": []})

@app.route("/api/connectors", methods=["GET", "POST"])
def api_connectors():
    return jsonify({"ok": True, "connectors": []})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"BEK-v15 HYBRID lancé sur http://{host}:{port}/")
    app.run(host=host, port=port, debug=True)