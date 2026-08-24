import os
import sys
import json
import base64
import requests
import re
import subprocess
from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
from memory import search_memory, save_to_memory

# ─── MODULES DE L'ARCHITECTURE BEK-v15.2 ───
from context_loader import load_project_documentation
from fast_math import HyperLogLog, MinHashSimilarity
from security_guard import SecurityGuard
from event_bus import EventBusKafka

app = Flask(__name__)

# ─── CONFIGURATION DES ESPACES DE TRAVAIL & ENVIRONNEMENTS ───
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "awesome-openclaw-skills")
FILES_DIR = os.path.join(WORKSPACE_DIR, "uploads")
GENERATED_DIR = os.path.join(WORKSPACE_DIR, "generated")
PLUGINS_DIR = os.path.join(WORKSPACE_DIR, "plugins")
DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")

if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(PLUGINS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Initialisation des instances BEK-v15.2
GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)
security_guard = SecurityGuard()
event_bus = EventBusKafka()
minhash_engine = MinHashSimilarity()
hll_counter = HyperLogLog()

# Import dynamique et sécurisé du Plugin CRM
try:
    from plugin_crm import CRMPlugin
except ImportError:
    try:
        from plugins.plugin_crm import CRMPlugin
    except Exception:
        CRMPlugin = None

crm_executor = CRMPlugin() if CRMPlugin else None

def get_api_key(key_name):
    val = os.environ.get(key_name, "")
    if val:
        return val.strip('"\' \r\n')

    candidates = [
        os.path.join(WORKSPACE_DIR, "env.txt"),
        os.path.join(WORKSPACE_DIR, ".env"),
        os.path.join(WORKSPACE_DIR, "bek-v15-clean", ".env"),
        os.path.join(WORKSPACE_DIR, "bek-v15-clean", "env.txt"),
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(key_name + "="):
                            return line.split("=", 1)[1].strip('"\' \r\n')
            except Exception:
                pass
    return ""

def get_all_nvidia_models():
    return [
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "nvidia/nemotron-3-super-120b-a12b",
        "mistralai/mistral-nemotron",
        "openai/gpt-oss-120b"
    ]

# ─── AGENT CHERCHEUR (ROUTAGE DES SKILLS) ───
def _agent_researcher_get_skills(query: str, top_k: int = 1) -> str:
    if not os.path.exists(SKILLS_DIR):
        return ""
    
    crm_keywords = {"crm", "prospect", "contact", "deal", "tâche", "tache", "stats", "statistiques"}
    query_words = set(re.findall(r'\w+', query.lower()))
    if not query_words or any(k in query_words for k in crm_keywords):
        return ""

    scored_skills = []
    for f in os.listdir(SKILLS_DIR):
        if f.endswith(".json"):
            try:
                path = os.path.join(SKILLS_DIR, f)
                with open(path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    name = data.get("name", f).lower()
                    desc = data.get("description", "").lower()
                    score = sum(1 for w in query_words if w in name or w in desc)
                    if score > 0:
                        scored_skills.append((score, data))
            except Exception:
                continue
    
    if not scored_skills:
        return ""

    scored_skills.sort(key=lambda x: x[0], reverse=True)
    skills_text = ""
    for _, s in scored_skills[:top_k]:
        skills_text += f"SKILL:{s.get('name')}|{s.get('prompt')}\n"
    return skills_text

# ─── ROUTES WEB & STATIQUES ───
@app.route('/')
def index():
    return send_from_directory(WORKSPACE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(WORKSPACE_DIR, filename)

@app.route('/api/config', methods=['GET'])
def get_config():
    providers = [
        {"id": "groq", "name": "Groq", "configured": bool(get_api_key("GROQ_API_KEY"))},
        {"id": "nvidia", "name": "NVIDIA NIM", "configured": bool(get_api_key("NVIDIA_API_KEY"))},
        {"id": "gemini", "name": "Google Gemini", "configured": bool(get_api_key("GEMINI_API_KEY"))},
        {"id": "openrouter", "name": "OpenRouter", "configured": bool(get_api_key("OPENROUTER_API_KEY"))},
        {"id": "agentrouter", "name": "AgentRouter", "configured": bool(get_api_key("AGENTROUTER_API_KEY"))}
    ]
    
    models = {
        "groq": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"],
        "nvidia": get_all_nvidia_models(),
        "gemini": [
            "gemini-1.5-pro", 
            "gemini-1.5-flash", 
            "gemini-1.0-pro",
            "gemini-3.5-flash",
            "gemini-3.6-flash"
        ],
        "openrouter": ["0x-alpha/0x-alpha", "anthropic/claude-3.5-sonnet"],
        "agentrouter": [
            "gpt-5.6-sol",
            "deepseek-v4f",
            "travail-de-proximité-5",
            "travail-de-près-4-8"
        ]
    }

    # --- COMPTAGE POUR LE MENU DE L'INTERFACE ---
    dossier_principal = os.path.join(WORKSPACE_DIR, "awesome-openclaw-skills")
    dossier_secours = os.path.join(WORKSPACE_DIR, "skills")
    chemin_dossier = dossier_principal if os.path.exists(dossier_principal) else dossier_secours
    
    skills_count = 0
    if os.path.exists(chemin_dossier):
        try:
            skills_count = len([f for f in os.listdir(chemin_dossier) if f.endswith('.json') or f.endswith('.txt')])
        except Exception:
            pass
            
    return jsonify({
        "providers": providers,
        "models": models,
        "context_loaded": bool(GLOBAL_SYSTEM_CONTEXT),
        "radar_status": event_bus.get_radar_status(),
        "skills_count": skills_count
    })

@app.route('/api/skills', methods=['GET'])
@app.route('/skills', methods=['GET'])
def get_skills():
    dossier_principal = os.path.join(WORKSPACE_DIR, "awesome-openclaw-skills")
    dossier_secours = os.path.join(WORKSPACE_DIR, "skills")
    chemin_dossier = dossier_principal if os.path.exists(dossier_principal) else dossier_secours
    
    if not os.path.exists(chemin_dossier):
        return jsonify({"status": "error", "count": 0, "total": 0, "skills": []}), 404
        
    try:
        skills_list = []
        fichiers = [f for f in os.listdir(chemin_dossier) if f.endswith('.json') or f.endswith('.txt')]
        total = len(fichiers)
        
        for f in fichiers[:100]:
            path = os.path.join(chemin_dossier, f)
            if f.endswith('.json'):
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        skills_list.append({
                            "name": data.get("name", f),
                            "description": data.get("description", "Compétence JSON"),
                            "command": data.get("command", f.replace('.json', ''))
                        })
                except Exception:
                    skills_list.append({"name": f, "description": "Fichier JSON", "command": f})
            else:
                skills_list.append({"name": f, "description": "Compétence Texte", "command": f.replace('.txt', '')})
                
        return jsonify({
            "status": "success",
            "count": total,
            "total": total,
            "total_skills": total,
            "skills": skills_list
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "count": 0, "skills": []}), 500

# ─── MOTEUR MULTI-AGENTS & EXÉCUTEUR ───
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    messages = data.get('messages', [])
    provider = data.get('provider', 'groq')
    model = data.get('model', 'llama-3.3-70b-versatile')
    use_memory = data.get('use_memory', True)
    
    last_user_msg = ""
    for m in reversed(messages):
        if m.get('role') == 'user':
            content = m.get('content')
            last_user_msg = content if isinstance(content, str) else " ".join([c.get('text', '') for c in content if c.get('type') == 'text'])
            break

    if "### HISTORIQUE" in last_user_msg and "---" in last_user_msg:
        last_user_msg = last_user_msg.split("---")[-1].strip()
    if last_user_msg:
        hll_counter.add(last_user_msg)

    # Routage dynamique
    if provider == "nvidia":
        api_key = get_api_key(model) or get_api_key("NVIDIA_API_KEY")
        api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    elif provider == "gemini":
        api_key = get_api_key("GEMINI_API_KEY")
        api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    elif provider == "openrouter":
        api_key = get_api_key("OPENROUTER_API_KEY")
        api_url = "https://openrouter.ai/api/v1/chat/completions"
    elif provider == "agentrouter":
        api_key = get_api_key("AGENTROUTER_API_KEY")
        api_url = "https://agentrouter.org/v1/chat/completions"
    else:
        api_key = get_api_key("GROQ_API_KEY")
        api_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate_proxy():
        if not api_key:
            yield f"data: {json.dumps({'error': f'Clé API manquante pour {provider}.'})}\n\n"
            return

        dynamic_context = ""
        if last_user_msg:
            yield f"data: {json.dumps({'chunk': '> 🧠 **Agent Superviseur** : Analyse en cours...\n'})}\n\n"
            
            # --- RÉVEIL VISUEL DE L'AGENT MÉMOIRE (PINECONE) ---
            if use_memory:
                yield f"data: {json.dumps({'chunk': '> 🗄️ **Agent Mémoire** : Interrogation de Pinecone...\n'})}\n\n"
                try:
                    memory_results = search_memory(last_user_msg)
                    if memory_results:
                        dynamic_context += f"CTX:{str(memory_results).strip()[:300]}\n"
                        yield f"data: {json.dumps({'chunk': '> 🗄️ **Agent Mémoire** : Souvenirs pertinents injectés.\n'})}\n\n"
                except Exception:
                    pass

            # --- RÉVEIL VISUEL DE L'AGENT CHERCHEUR ---
            yield f"data: {json.dumps({'chunk': '> 🔎 **Agent Chercheur** : Scan de vos compétences...\n'})}\n\n"
            relevant_skills = _agent_researcher_get_skills(last_user_msg)
            if relevant_skills:
                dynamic_context += relevant_skills
                yield f"data: {json.dumps({'chunk': '> 🔎 **Agent Chercheur** : Compétences trouvées et chargées !\n'})}\n\n"

        supervisor_prompt = (
            "Agent CRM Neon. Tu réponds UNIQUEMENT un JSON minifié si l'utilisateur demande une action CRM :\n"
            "- Contact : {\"action\":\"create_contact\",\"params\":{\"name\":\"...\"}}\n"
            "Sinon texte direct en français."
        )

        clean_messages = [{'role': m.get('role'), 'content': m.get('content')} for m in messages[-2:] if m.get('role') in ['user', 'assistant']]
        exec_messages = [{"role": "system", "content": f"{supervisor_prompt}\n{dynamic_context}".strip()}] + clean_messages

        payload = {
            "model": model,
            "messages": exec_messages,
            "temperature": 0.0, 
            "max_tokens": 4096,
            "stream": False
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://bek-agent.local"
            headers["X-Title"] = "BEK-v15-Hybrid"

        try:
            yield f"data: {json.dumps({'chunk': f'> 👨‍💻 **Agent Exécuteur** : Génération via {model}...\n\n'})}\n\n"
            resp = requests.post(api_url, json=payload, headers=headers, timeout=60)
            
            if resp.status_code != 200:
                yield f"data: {json.dumps({'error': f'Erreur API {provider} : {resp.text}'})}\n\n"
                return
                
            resp_json = resp.json()
            llm_text = resp_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            # --- RÉFLEXE DE RAISONNEMENT ---
            def format_thought(match):
                thought = match.group(1).strip()
                return f"\n\n> 🧠 **Réflexion Profonde ({model})** :\n> *{thought.replace(chr(10), chr(10) + '> ')}*\n\n"
            cleaned_text = re.sub(r'<think>([\s\S]*?)</think>', format_thought, llm_text).strip()
            # -------------------------------

            action_data = None
            try:
                match = re.search(r'(\{[\s\S]*?"action"[\s\S]*?\})', cleaned_text)
                if match: action_data = json.loads(match.group(1))
            except Exception:
                pass

            if isinstance(action_data, dict) and "action" in action_data and crm_executor:
                action = action_data.get("action")
                params = action_data.get("params", {})
                is_valid, reason, env = security_guard.validate_and_certify(action, params)
                if not is_valid:
                    yield f"data: {json.dumps({'chunk': f'> 🛑 **Blocage** : {reason}\n'})}\n\n"
                    return
                exec_result = crm_executor.execute_payload(action, env.get("params", {}))
                yield f"data: {json.dumps({'chunk': exec_result})}\n\n"
                return

            yield f"data: {json.dumps({'chunk': cleaned_text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate_proxy(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8765, debug=True)