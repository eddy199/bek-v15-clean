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
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")
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
        "/media/moh/84B00E0BB00E0500/workspacekimi/bek-v15-clean/.env",
        "/media/moh/84B00E0BB00E0500/workspacekimi/env.txt"
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
    verified_models = [
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-3.2-90b-vision-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-nano-12b-v2-vl",
        "nvidia/nvidia-nemotron-nano-9b-v2",
        "nvidia/ising-calibration-1.5-31b",
        "mistralai/mistral-nemotron"
    ]
    return verified_models

# ─── AGENT CHERCHEUR (ROUTAGE DES SKILLS) ───
def _agent_researcher_get_skills(query: str, top_k: int = 1) -> str:
    if not os.path.exists(SKILLS_DIR):
        return ""
    
    query_words = set(re.findall(r'\w+', query.lower()))
    if not query_words:
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
    top_skills = scored_skills[:top_k]
    
    skills_text = ""
    for _, s in top_skills:
        skills_text += f"SKILL:{s.get('name')}|{s.get('prompt')}\n"
        event_bus.publish("skills-index", {"name": s.get('name'), "query": query})
    
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
        {"id": "gemini", "name": "Google Gemini", "configured": bool(get_api_key("GEMINI_API_KEY"))}
    ]
    
    models = {
        "groq": [
            "openai/gpt-oss-120b", 
            "openai/gpt-oss-20b", 
            "qwen/qwen3.6-27b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ],
        "nvidia": get_all_nvidia_models(),
        "gemini": [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-robotics-er-2-preview",
            "gemini-robotics-er-1.6-preview"
        ]
    }
    
    skills_count = len([f for f in os.listdir(SKILLS_DIR) if f.endswith('.json')]) if os.path.exists(SKILLS_DIR) else 0
    files_count = len(os.listdir(FILES_DIR)) if os.path.exists(FILES_DIR) else 0

    return jsonify({
        "providers": providers,
        "models": models,
        "skills_count": skills_count,
        "files_count": files_count,
        "context_loaded": bool(GLOBAL_SYSTEM_CONTEXT),
        "radar_status": event_bus.get_radar_status()
    })

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

# ─── MOTEUR MULTI-AGENTS, SUPERVISEUR, EXÉCUTEUR & ACTIONNEUR MCP ───
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
            if isinstance(content, str):
                last_user_msg = content
            elif isinstance(content, list):
                last_user_msg = " ".join([c.get('text', '') for c in content if c.get('type') == 'text'])
            break

    if "### HISTORIQUE" in last_user_msg and "---" in last_user_msg:
        last_user_msg = last_user_msg.split("---")[-1].strip()

    if last_user_msg:
        hll_counter.add(last_user_msg)

    radar_state = event_bus.get_radar_status()

    # Routage dynamique des clés et endpoints
    if provider == "nvidia":
        model_specific_key = get_api_key(model)
        api_key = model_specific_key if model_specific_key else get_api_key("NVIDIA_API_KEY")
        api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    elif provider == "gemini":
        api_key = get_api_key("GEMINI_API_KEY")
        api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    else:
        api_key = get_api_key("GROQ_API_KEY")
        api_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate_proxy():
        if not api_key:
            yield f"data: {json.dumps({'error': f'Clé API manquante pour le provider {provider} ou le modèle {model}.'})}\n\n"
            return

        dynamic_context = ""
        
        if last_user_msg:
            yield f"data: {json.dumps({'chunk': '> 🧠 **Agent Superviseur** : Analyse...\n'})}\n\n"
            
            if radar_state.get("radar_red"):
                yield f"data: {json.dumps({'chunk': '> 🚨 **Radar Rouge Actif** : Surveillance active...\n\n'})}\n\n"

            if use_memory:
                try:
                    yield f"data: {json.dumps({'chunk': '> 📚 **Agent Mémoire** : Interrogation Pinecone...\n'})}\n\n"
                    memory_results = search_memory(last_user_msg)
                    if memory_results:
                        clean_mem = str(memory_results).strip()[:300]
                        dynamic_context += f"CTX:{clean_mem}\n"
                        event_bus.publish("vector-context", {"query": last_user_msg, "status": "retrieved"})
                except Exception:
                    pass

            yield f"data: {json.dumps({'chunk': '> 🕵️ **Agent Chercheur** : Scan des skills...\n'})}\n\n"
            relevant_skills = _agent_researcher_get_skills(last_user_msg, top_k=1)
            if relevant_skills:
                dynamic_context += relevant_skills

        supervisor_prompt = (
            "Agent CRM Neon. Si action CRM demandée, réponds UNIQUEMENT le JSON minifié :\n"
            "- Contact : {\"action\":\"create_contact\",\"params\":{\"name\":\"...\",\"email\":\"...\",\"phone\":\"...\"}}\n"
            "- Deal : {\"action\":\"create_deal\",\"params\":{\"title\":\"...\",\"amount\":5000}}\n"
            "- Tâche : {\"action\":\"create_task\",\"params\":{\"title\":\"...\"}}\n"
            "- Recherche : {\"action\":\"search_contact\",\"params\":{\"query\":\"...\"}}\n"
            "- Update : {\"action\":\"update_contact\",\"params\":{\"name\":\"...\",\"email\":\"...\",\"phone\":\"...\"}}\n"
            "Sinon texte direct."
        )

        clean_messages = []
        for m in messages[-2:]:
            if m.get('role') in ['user', 'assistant']:
                clean_messages.append({'role': m.get('role'), 'content': m.get('content')})
        
        while clean_messages and clean_messages[-1].get('role') != 'user':
            clean_messages.pop()

        exec_messages = [{"role": "system", "content": f"{supervisor_prompt}\n{dynamic_context}".strip()}] + clean_messages

        payload = {
            "model": model,
            "messages": exec_messages,
            "temperature": 0.0, 
            "max_tokens": 512,
            "stream": False
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            yield f"data: {json.dumps({'chunk': '> 👨‍💻 **Agent Exécuteur** : Exécution via ' + str(model) + '...\n'})}\n\n"
            resp = requests.post(api_url, json=payload, headers=headers, timeout=60)
            
            if resp.status_code != 200:
                event_bus.publish("error-signals", {"provider": provider, "status_code": resp.status_code, "msg": resp.text})
                yield f"data: {json.dumps({'error': f'Erreur API {provider.upper()} (Code {resp.status_code}) : {resp.text}'})}\n\n"
                return
                
            resp_json = resp.json()
            llm_text = ""
            
            if isinstance(resp_json, list):
                if len(resp_json) > 0 and isinstance(resp_json[0], dict):
                    llm_text = resp_json[0].get('message', {}).get('content', '')
            elif isinstance(resp_json, dict):
                if "error" in resp_json:
                    error_msg = resp_json.get('error', 'Erreur inconnue')
                    event_bus.publish("error-signals", {"provider": provider, "error": error_msg})
                    yield f"data: {json.dumps({'error': f'Erreur {provider.upper()} : {error_msg}'})}\n\n"
                    return
                choices = resp_json.get('choices', [])
                if choices and isinstance(choices, list) and len(choices) > 0:
                    llm_text = choices[0].get('message', {}).get('content', '')
            
            llm_text = (llm_text or "").strip()
            cleaned_text = re.sub(r'<think>[\s\S]*?</think>', '', llm_text).strip()

            action_data = None
            try:
                action_data = json.loads(cleaned_text)
            except Exception:
                match = re.search(r'(\{[\s\S]*?"action"[\s\S]*?\})', cleaned_text)
                if match:
                    try:
                        action_data = json.loads(match.group(1))
                    except Exception:
                        pass

            if isinstance(action_data, dict) and "action" in action_data and crm_executor:
                action = action_data.get("action")
                params = action_data.get("params", {})
                
                yield f"data: {json.dumps({'chunk': f'> 🛡️ **Agent Auditeur** : Contrôle OPA & Certification HSM de `{action}`...\n'})}\n\n"
                is_valid, reason, certified_envelope = security_guard.validate_and_certify(action, params)

                if not is_valid:
                    event_bus.publish("error-signals", {"action": action, "rejection_reason": reason})
                    yield f"data: {json.dumps({'chunk': f'> 🛑 **Blocage Sas de Sécurité** : {reason}\n\n'})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

                sanitized_params = certified_envelope.get("params", {})
                hsm_sig = certified_envelope.get("hsm_signature", "")[:12]

                yield f"data: {json.dumps({'chunk': f'> ⚡ **Agent Actionneur** : Signature `{hsm_sig}...` certifiée. Exécution vers Neon...\n\n'})}\n\n"
                exec_result = crm_executor.execute_payload(action, sanitized_params)
                
                if use_memory:
                    try:
                        mem_text = f"Action CRM réussie : {action} - {json.dumps(sanitized_params)}"
                        save_to_memory(str(mem_text), {"action": str(action)})
                    except Exception:
                        pass

                yield f"data: {json.dumps({'chunk': exec_result})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            yield f"data: {json.dumps({'chunk': f'> 💬 **Réponse Exécuteur** :\n\n{cleaned_text}'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            event_bus.publish("error-signals", {"error_exception": str(e)})
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate_proxy(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8765, debug=True)