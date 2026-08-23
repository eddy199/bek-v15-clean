import os
import json
import base64
import requests
from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ─── CONFIGURATION DES ESPACES DE TRAVAIL & ENVIRONNEMENTS ───
WORKSPACE_DIR = "/media/moh/84B00E0BB00E0500/workspacekimi"
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")
FILES_DIR = os.path.join(WORKSPACE_DIR, "uploads")
GENERATED_DIR = os.path.join(WORKSPACE_DIR, "generated")
ENV_FILE = os.path.join(WORKSPACE_DIR, "env.txt")

os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)

def get_api_key(key_name):
    """Récupère une clé API depuis env.txt ou les variables d'environnement."""
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(key_name + "="):
                        return line.strip().split("=", 1)[1].strip('"\'')
        except Exception:
            pass
    return os.environ.get(key_name, "")

# ─── OUTILS AUTONOMES DE L'AGENT ───

def lister_skills_locaux(filtre: str = "") -> str:
    """Explore le dossier local skills/ et retourne la liste des compétences de l'agent."""
    if not os.path.exists(SKILLS_DIR):
        return "Le dossier skills/ est introuvable."
    
    fichiers = os.listdir(SKILLS_DIR)
    skills_recup = []
    
    for f in fichiers:
        if f.endswith(".json"):
            chemin = os.path.join(SKILLS_DIR, f)
            try:
                with open(chemin, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    nom = data.get("name", f)
                    desc = data.get("description", "Pas de description")
                    cmd = data.get("command", nom)
                    if not filtre or filtre.lower() in nom.lower() or filtre.lower() in desc.lower():
                        skills_recup.append(f"- **Cmd:** `/{cmd}` | **Nom:** {nom} : {desc}")
            except Exception:
                continue
                
    if not skills_recup:
        return "Aucune compétence correspondante trouvée."
    
    return f"🛠️ **Compétences chargées ({len(skills_recup)}) :**\n" + "\n".join(skills_recup[:50])


# ─── ROUTES WEB & STATIQUES ───

@app.route('/')
def index():
    return send_from_directory(WORKSPACE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(WORKSPACE_DIR, filename)


# ─── GESTION DES CONFIGURATIONS ET CLEFS ───

@app.route('/api/config', methods=['GET'])
def get_config():
    providers = [
        {"id": "groq", "name": "Groq", "configured": bool(get_api_key("GROQ_API_KEY"))},
        {"id": "nvidia", "name": "NVIDIA NIM", "configured": bool(get_api_key("NVIDIA_API_KEY"))}
    ]
    models = {
        "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "allam-2-7b"],
        "nvidia": ["nvidia/nemotron-3-super-120b-a12b", "meta/llama-3.2-11b-vision-instruct"]
    }
    
    skills_count = len([f for f in os.listdir(SKILLS_DIR) if f.endswith('.json')]) if os.path.exists(SKILLS_DIR) else 0
    files_count = len(os.listdir(FILES_DIR)) if os.path.exists(FILES_DIR) else 0

    return jsonify({
        "providers": providers,
        "models": models,
        "skills_count": skills_count,
        "files_count": files_count
    })


# ─── GESTION DES COMPÉTENCES (SKILLS) ───

@app.route('/api/skills', methods=['GET'])
def get_skills():
    skills = []
    if os.path.exists(SKILLS_DIR):
        for f in os.listdir(SKILLS_DIR):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(SKILLS_DIR, f), 'r', encoding='utf-8') as file:
                        skills.append(json.load(file))
                except Exception:
                    pass
    return jsonify({"skills": skills})


# ─── ROUTE DE TÉLÉVERSEMENT (MODE GEMINI : EXTRACTION TEXTE) ───

@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        uploaded_file = None
        if request.files:
            for key in request.files:
                uploaded_file = request.files[key]
                break
        
        if not uploaded_file or uploaded_file.filename == '':
            return jsonify({"ok": False, "error": "Aucun fichier reçu"}), 400

        filename = secure_filename(uploaded_file.filename)
        destination = os.path.join(FILES_DIR, filename)
        uploaded_file.save(destination)
        
        # Extraction du texte pour imiter Gemini et permettre à l'IA de lire le fichier
        text_sample = ""
        try:
            with open(destination, 'r', encoding='utf-8') as f:
                text_sample = f.read(50000)  # Limite à 50k caractères pour ne pas surcharger le prompt
        except UnicodeDecodeError:
            pass # Si c'est un binaire (image, zip, pdf lourd), on ignore l'extraction texte
        
        return jsonify({
            "ok": True,
            "success": True,
            "status": "success",
            "filename": filename,
            "path": destination,
            "text_sample": text_sample,
            "message": f"Fichier {filename} téléversé avec succès"
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── MOTEUR DE CHAT ET PROXY API MULTIMODAL ───

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    messages = data.get('messages', [])
    provider = data.get('provider', 'groq')
    model = data.get('model', 'openai/gpt-oss-120b')
    
    # 1. Traitement autonome des skills si demandés
    if messages and len(messages) > 0:
        dernier_msg = messages[-1].get('content', '')
        if isinstance(dernier_msg, str) and any(kw in dernier_msg.lower() for kw in ["skills", "compétences", "liste", "tableau", "codage", "programmation", "workspace"]):
            filtre = "code" if "codage" in dernier_msg.lower() or "programmation" in dernier_msg.lower() else ""
            resultats_skills = lister_skills_locaux(filtre)
            
            def generate_skills_stream():
                yield f"data: {json.dumps({'chunk': f'### 🧠 Analyse autonome de l\'espace de travail :\n\n{resultats_skills}'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            return Response(generate_skills_stream(), mimetype='text/event-stream')

    # 2. Sécurisation anti-crash pour les modèles de vision (NVIDIA)
    # Force un maximum d'une image par message pour s'adapter à la limite du modèle Open Source
    for msg in messages:
        if isinstance(msg.get('content'), list):
            filtered_content = []
            img_count = 0
            for part in msg['content']:
                if part.get('type') == 'image_url':
                    if img_count < 1:  
                        filtered_content.append(part)
                        img_count += 1
                else:
                    filtered_content.append(part)
            msg['content'] = filtered_content

    # 3. Préparation de la requête vers le provider choisi
    api_key = ""
    api_url = ""
    
    if provider == "nvidia":
        api_key = get_api_key("NVIDIA_API_KEY")
        api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    else:
        api_key = get_api_key("GROQ_API_KEY")
        api_url = "https://api.groq.com/openai/v1/chat/completions"

    if not api_key:
        def generate_error():
            yield f"data: {json.dumps({'error': f'Clé API manquante pour le provider {provider}.'})}\n\n"
        return Response(generate_error(), mimetype='text/event-stream')

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": True
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    def generate_proxy():
        try:
            resp = requests.post(api_url, json=payload, headers=headers, stream=True, timeout=60)
            if resp.status_code != 200:
                yield f"data: {json.dumps({'error': f'Erreur API externe ({resp.status_code}): {resp.text[:150]}'})}\n\n"
                return
                
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data_str = decoded[6:]
                        if data_str.strip() == '[DONE]':
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break
                        try:
                            parsed = json.loads(data_str)
                            delta = parsed.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield f"data: {json.dumps({'chunk': content})}\n\n"
                        except Exception:
                            pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate_proxy(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8765, debug=True)