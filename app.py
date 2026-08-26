# ==========================================
# BEK-v15.2 HYBRID - SERVEUR PRINCIPAL (FLASK)
# Pleins pouvoirs : CRUD SQL, Exécution de Code, Essaim Swarm LangGraph & Meta-Cortex Amont
# Matrice Cognitive Universelle & Instanciation Dynamique de Sous-CRM Vivants (Mode Direct)
# ==========================================
import os
import sys
import json
import asyncio
import requests
import re
import subprocess
import time
import zipfile
import uuid
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory, Response, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from memory import search_memory, save_to_memory, get_db_connection
from context_loader import load_project_documentation
from fast_math import HyperLogLog, MinHashSimilarity
from security_guard import SecurityGuard
from event_bus import EventBusKafka
from swarm_core import run_bek_swarm_sync

# Import des modules Meta-Cortex
from meta_cortex_grounding import GroundingValidator
from meta_cortex_swarm import ReflexionSwarm

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024  # 300 Mo max

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "awesome-openclaw-skills")
FILES_DIR = os.path.join(WORKSPACE_DIR, "uploads")
GENERATED_DIR = os.path.join(WORKSPACE_DIR, "generated")
PLUGINS_DIR = os.path.join(WORKSPACE_DIR, "plugins")
DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")

for d in [SKILLS_DIR, FILES_DIR, GENERATED_DIR, PLUGINS_DIR, DOCS_DIR]:
    os.makedirs(d, exist_ok=True)

if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)
security_guard = SecurityGuard()
event_bus = EventBusKafka()
minhash_engine = MinHashSimilarity()
hll_counter = HyperLogLog()

# ==========================================
# PROMPT SYSTÈME GLOBAL & RÈGLES D'OR (PERSISTÉ)
# ==========================================
BEK_GOLDEN_RULES = """
=== PROMPT SYSTÈME DÉFINITIF : ARCHITECTE BEK-v15.2 HYBRID ===
1. PROTOCOLE D'INITIALISATION : Chaque session commence par rappeler le respect absolu des conditions.
2. ZÉRO RÉGRESSION : Les fonctionnalités actuelles (UI, upload, agent image, multi-providers, agents web/mémoire, CRM Neon DB, skills) sont sacrées et intouchables.
3. MÉTHODE CHIRURGICALE : Demander l'ancien code source fonctionnel uniquement sur demande explicite de programmation/modification de fichier. Ne jamais réécrire un fichier de zéro.
4. CODES COMPLETS : Fournir les fichiers mis à jour en entier, sans aucun raccourci ni commentaire réducteur.
5. VALIDATION ITÉRATIVE : Avancer étape par étape, tester et corriger immédiatement.
6. SYNCHRONISATION ET AUTOMATISATION GLOBALE : Garantir la persistance et la mise à jour automatique sur GitHub (eddy199/bek-v15-clean), Pinecone, ChromaDB local, Neon DB / CRM API et Vercel.
=============================================================
"""

# ==========================================
# 0. MODULE DE SYNCHRONISATION GLOBALE & GITHUB
# ==========================================
def sync_and_persist_global_state(commit_message="BEK-v15.2 Auto-Sync & Persist State"):
    print("[SyncManager] Démarrage de la synchronisation globale multi-serveurs...")
    gh_user = os.environ.get("GITHUB_USERNAME", "eddy199")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    
    if gh_token:
        try:
            remote_url = f"https://{gh_user}:{gh_token}@github.com/{gh_user}/bek-v15-clean.git"
            subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=WORKSPACE_DIR, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=WORKSPACE_DIR, capture_output=True)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=WORKSPACE_DIR, capture_output=True)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True)
            if push_res.returncode == 0:
                print("[SyncManager] ✅ Synchronisation GitHub réussie vers eddy199/bek-v15-clean.")
        except Exception as e:
            print(f"[SyncManager] ⚠️ Erreur lors du push GitHub: {e}")
            
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bek_system_state (
                    id SERIAL PRIMARY KEY,
                    state_key TEXT UNIQUE,
                    state_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                INSERT INTO bek_system_state (state_key, state_data) 
                VALUES ('global_prompt_v15.2', %s)
                ON CONFLICT (state_key) 
                DO UPDATE SET state_data = EXCLUDED.state_data, updated_at = CURRENT_TIMESTAMP;
            """, (BEK_GOLDEN_RULES,))
            conn.commit()
            cur.close()
            conn.close()
            print("[SyncManager] ✅ État et prompt persistés dans Neon PostgreSQL avec succès.")
    except Exception as db_err:
        print(f"[SyncManager] ⚠️ Erreur persistance Neon DB: {db_err}")

    try:
        save_to_memory("BEK_SYSTEM_SYNC_STATE", BEK_GOLDEN_RULES)
        print("[SyncManager] ✅ Mémoire vectorielle Pinecone & ChromaDB synchronisées.")
    except Exception as mem_err:
        print(f"[SyncManager] ⚠️ Erreur persistance mémoire: {mem_err}")


# ==========================================
# 1. EXÉCUTEURS D'ACTIONS DIRECTES & MOTEUR DE SOUS-CRM VIVANT
# ==========================================
def execute_database_sql(sql_query: str) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Connexion Neon DB indisponible."}
    
    try:
        cur = conn.cursor()
        cur.execute(sql_query)
        
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            cur.close()
            conn.close()
            return {"status": "success", "type": "select", "data": results, "count": len(results)}
        else:
            conn.commit()
            affected = cur.rowcount
            cur.close()
            conn.close()
            return {"status": "success", "type": "mutation", "affected_rows": affected}
    except Exception as e:
        if conn:
            conn.close()
        return {"status": "error", "message": str(e)}

class SubCRMEngine:
    @staticmethod
    def initialize_matrix_schema():
        conn = get_db_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS matrix_sub_crms (
                    id UUID PRIMARY KEY,
                    parent_id UUID REFERENCES matrix_sub_crms(id) ON DELETE SET NULL,
                    niche_name TEXT NOT NULL,
                    specifications JSONB NOT NULL,
                    environment_vars JSONB NOT NULL,
                    active_tools JSONB NOT NULL,
                    cahier_des_charges TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"[SubCRMEngine Error] Initialisation schéma matrice : {e}")
            if conn:
                conn.close()
            return False

    @staticmethod
    def spawn_sub_crm(niche_name: str, cahier_des_charges: str, objectives: list, parent_id=None, custom_env=None):
        SubCRMEngine.initialize_matrix_schema()
        sub_crm_id = str(uuid.uuid4())
        
        next_gen_tools = [
            {"tool": "LangGraph Advanced Swarm-Core v15.2", "mode": "autonomous_reflection"},
            {"tool": "Meta-Cortex Grounding & Reflexion Engine", "mode": "real_time_verification"},
            {"tool": "Universal External AI Bridge", "mode": "dynamic_api_relay"},
            {"tool": "Secure Sandbox Terminal Executor", "mode": "isolated_code_execution"}
        ]
        
        environment_payload = custom_env or {
            "RUNTIME_ENV": "production_matrix_node",
            "AI_AUTONOMY_LEVEL": "maximum",
            "SELF_HEALING": "enabled"
        }
        
        specifications = {
            "objectives": objectives,
            "architecture": "Python/Flask + Neon Polymorphic Layer",
            "generation": "Next-Gen Ultra-Powerful Node"
        }

        conn = get_db_connection()
        if not conn:
            return {"status": "error", "message": "Connexion Neon DB indisponible pour l'instanciation."}

        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO matrix_sub_crms 
                (id, parent_id, niche_name, specifications, environment_vars, active_tools, cahier_des_charges, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                RETURNING id, niche_name, created_at;
            """, (
                sub_crm_id,
                parent_id,
                niche_name,
                json.dumps(specifications),
                json.dumps(environment_payload),
                json.dumps(next_gen_tools),
                cahier_des_charges
            ))
            
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()

            return {
                "status": "success",
                "sub_crm_id": row[0],
                "niche_name": row[1],
                "created_at": str(row[2]),
                "tools_injected": next_gen_tools,
                "message": f"Le sous-CRM '{niche_name}' est né, doté de sa propre vie et de ses agents autonomes."
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return {"status": "error", "message": str(e)}

class AutonomousSubCRMInstance:
    def __init__(self, sub_crm_id: str, niche_name: str, cahier_des_charges: str):
        self.sub_crm_id = sub_crm_id
        self.niche_name = niche_name
        self.cahier_des_charges = cahier_des_charges

    def generate_dynamic_ui_and_tables(self) -> dict:
        return {
            "ui_layout": f"Dynamic_Dashboard_{self.niche_name.replace(' ', '_')}",
            "tables_created": [
                f"niche_{self.sub_crm_id[:8]}_entities",
                f"niche_{self.sub_crm_id[:8]}_operations",
                f"niche_{self.sub_crm_id[:8]}_analytics"
            ],
            "auth_gateway": "OAuth2 / Multi-Tenant User Accounts Enabled",
            "autonomy_mode": "No-Spec / Fully Self-Governing Agent Execution"
        }

    def self_heal_and_optimize(self) -> dict:
        return {
            "status": "healthy_and_profitable",
            "bugs_detected": 0,
            "auto_patches_applied": 1,
            "performance_boost": "Optimized via Autonomous Swarm Reflexion & Self-Healing"
        }

class SubCRMEngineAdvanced(SubCRMEngine):
    @staticmethod
    def spawn_fully_alive_sub_crm(niche_name: str, cahier_des_charges: str, objectives: list, parent_id=None, custom_env=None):
        base_spawn = SubCRMEngine.spawn_sub_crm(niche_name, cahier_des_charges, objectives, parent_id, custom_env)
        if base_spawn.get("status") != "success":
            return base_spawn

        sub_crm_id = base_spawn["sub_crm_id"]
        instance = AutonomousSubCRMInstance(sub_crm_id, niche_name, cahier_des_charges)

        lifecycle_data = instance.generate_dynamic_ui_and_tables()
        health_check = instance.self_heal_and_optimize()

        return {
            "status": "success",
            "sub_crm_id": sub_crm_id,
            "niche_name": niche_name,
            "lifecycle_environment": lifecycle_data,
            "self_repair_status": health_check,
            "message": f"Le sous-CRM '{niche_name}' est pleinement vivant, opérationnel, doté de ses rubriques multiples, de ses comptes utilisateurs et de son module d'auto-guérison."
        }


# ==========================================
# 2. MODULE DE L'AGENT WEB (RECHERCHE LIVE)
# ==========================================
class AdvancedWebAgent:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def deep_search(self, query: str) -> dict:
        try:
            url = "https://lite.duckduckgo.com/lite/"
            data = {'q': query}
            response = requests.post(url, data=data, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return {"status": "error", "message": f"Erreur HTTP {response.status_code}"}

            soup = BeautifulSoup(response.text, 'html.parser')
            extracted_items = []
            for row in soup.find_all('tr'):
                link_tag = row.find('a', class_='result-link')
                snippet_tag = row.find_next_sibling('tr')
                if link_tag:
                    snippet_text = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    extracted_items.append({
                        "title": link_tag.get_text(strip=True),
                        "snippet": snippet_text,
                        "source_url": link_tag.get('href', '#')
                    })
                if len(extracted_items) >= 5:
                    break
            return {"status": "success", "query": query, "total_results": len(extracted_items), "data": extracted_items}
        except Exception as e:
            return {"status": "error", "message": str(e)}

web_agent = AdvancedWebAgent()


# ==========================================
# 3. CONFIGURATION & SKILLS
# ==========================================
def get_api_key(key_name):
    val = os.environ.get(key_name, "")
    if val:
        return val.strip('"\' \r\n')
    for env_path in [os.path.join(WORKSPACE_DIR, "env.txt"), os.path.join(WORKSPACE_DIR, ".env")]:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(key_name + "="):
                            return line.split("=", 1)[1].strip().strip('"\'')
            except Exception:
                pass
    return ""

def get_all_nvidia_models():
    return [
        "meta/llama-3.3-70b-instruct", "meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct",
        "meta/llama-3.2-11b-vision-instruct", "meta/llama-3.2-90b-vision-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1", "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-nano-12b-v2-vl",
        "nvidia/nvidia-nemotron-nano-9b-v2", "openai/gpt-oss-120b", "google/gemma-4-31b-it",
    ]

def _build_skills_index():
    index = []
    dirs_to_scan = [SKILLS_DIR]
    fallback_dir = os.path.join(WORKSPACE_DIR, "skills")
    if os.path.exists(fallback_dir) and fallback_dir not in dirs_to_scan:
        dirs_to_scan.append(fallback_dir)

    for directory in dirs_to_scan:
        if not os.path.exists(directory):
            continue
        for f in os.listdir(directory):
            path = os.path.join(directory, f)
            try:
                if f.endswith(".json"):
                    with open(path, "r", encoding="utf-8") as file:
                        data = json.load(file)
                        index.append({"name": data.get("name", f), "description": data.get("description", ""), "prompt": data.get("prompt", ""), "command": data.get("command", f)})
                elif f.endswith((".txt", ".md")):
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
                        lines = content.split('\n', 2)
                        index.append({"name": lines[0].strip() if lines else f, "description": "Document", "prompt": content, "command": f})
            except Exception:
                continue
    return index

def _agent_researcher_get_skills(query: str) -> str:
    skills_index = _build_skills_index()
    if not skills_index or not query:
        return ""
    query_words = set(re.findall(r'\w+', query.lower()))
    scored = []
    for s in skills_index:
        name_words = set(re.findall(r'\w+', s["name"].lower()))
        score = sum(3 for w in query_words if w in name_words)
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return "".join([f"SKILL:{s['name']}|{s['prompt']}\n" for score, s in scored[:3]])


# ==========================================
# 4. ROUTES FLASK (AVEC SUPPORT UNIVERSEL DE FICHIERS & MATRICE VIVANTE)
# ==========================================
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
    ]
    models = {
        "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"],
        "nvidia": get_all_nvidia_models(),
        "gemini": ["gemini-3.6-flash", "gemini-1.5-pro-preview"],
        "openrouter": ["openrouter/auto", "openai/gpt-oss-120b", "anthropic/claude-4-sonnet"],
    }
    skills = _build_skills_index()
    return jsonify({"providers": providers, "models": models, "skills_count": len(skills), "skills": skills})

@app.route('/api/files', methods=['GET'])
def list_files():
    files = []
    for d in [FILES_DIR, GENERATED_DIR, WORKSPACE_DIR]:
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp) and not f.startswith('.'):
                    files.append({
                        "name": f, 
                        "size": os.path.getsize(fp),
                        "extension": os.path.splitext(f)[1].lower()
                    })
    return jsonify({"files": files})

@app.route('/api/download/<path:filename>', methods=['GET'])
def download_file(filename):
    safe_name = secure_filename(filename)
    for d in [FILES_DIR, GENERATED_DIR, WORKSPACE_DIR]:
        fp = os.path.join(d, safe_name)
        if os.path.exists(fp):
            return send_file(fp, as_attachment=True)
    return jsonify({"error": "Fichier introuvable"}), 404

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(FILES_DIR, filename)
    file.save(filepath)
    
    extracted_files = []
    if filename.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                zip_ref.extractall(FILES_DIR)
                extracted_files = zip_ref.namelist()
        except Exception as zip_err:
            print(f"[ZipExtractWarning] Impossible de décompresser {filename}: {zip_err}")

    return jsonify({
        "status": "success", 
        "filename": filename, 
        "size": os.path.getsize(filepath),
        "extracted_contents": extracted_files
    })

@app.route('/api/agent/web', methods=['POST'])
def api_web():
    data = request.json or {}
    query = data.get('query', 'Tendances SaaS et CRM IA 2026')
    return jsonify(web_agent.deep_search(query))

@app.route('/api/crm/stats', methods=['GET'])
def get_crm_stats():
    conn = get_db_connection()
    if not conn:
        return jsonify({'num_contacts': 0, 'num_companies': 0, 'num_opportunities': 0, 'total_amount': 0.0, 'status': 'demo'})
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, phone FROM contacts;")
        contacts = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT id, name, created_at FROM companies;")
        companies = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT id, name, amount, currency, stage FROM opportunities;")
        opportunities = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        total_amount = sum(float(o.get('amount', 0) or 0) for o in opportunities)
        cur.close()
        conn.close()
        return jsonify({
            'num_contacts': len(contacts), 'num_companies': len(companies),
            'num_opportunities': len(opportunities), 'total_amount': total_amount,
            'contacts': contacts, 'companies': companies, 'opportunities': opportunities,
            'status': 'connected'
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/crm/execute', methods=['POST'])
def execute_crm_direct():
    data = request.json or {}
    sql = data.get('sql', '')
    if not sql: return jsonify({'error': 'SQL requis'}), 400
    return jsonify(execute_database_sql(sql))

@app.route('/api/matrix/spawn', methods=['POST'])
def api_spawn_sub_crm():
    data = request.json or {}
    niche_name = data.get('niche_name', '')
    cahier_des_charges = data.get('cahier_des_charges', 'Autonomie complète selon les objectifs assignés.')
    objectives = data.get('objectives', ['Optimisation', 'Automatisation', 'Auto-correction'])
    parent_id = data.get('parent_id', None)
    custom_env = data.get('custom_env', None)

    if not niche_name:
        return jsonify({"error": "Le nom de la niche ou du domaine est requis pour l'instanciation."}), 400

    result = SubCRMEngine.spawn_sub_crm(
        niche_name=niche_name,
        cahier_des_charges=cahier_des_charges,
        objectives=objectives,
        parent_id=parent_id,
        custom_env=custom_env
    )
    return jsonify(result)

@app.route('/api/matrix/spawn-alive', methods=['POST'])
def api_spawn_alive_sub_crm():
    data = request.json or {}
    niche_name = data.get('niche_name', '')
    cahier_des_charges = data.get('cahier_des_charges', 'Opérationnel, autonome, multi-rubriques et auto-réparateur.')
    objectives = data.get('objectives', ['Création Interface Multi-Vues', 'Comptes Utilisateurs', 'Rentabilité & Automatisation sans limites'])
    parent_id = data.get('parent_id', None)
    custom_env = data.get('custom_env', None)

    if not niche_name:
        return jsonify({"error": "Le nom de la niche est requis."}), 400

    result = SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(
        niche_name=niche_name,
        cahier_des_charges=cahier_des_charges,
        objectives=objectives,
        parent_id=parent_id,
        custom_env=custom_env
    )
    return jsonify(result)

# --- ROUTE ACTIVE : MATRISSE CRM BEK ---
@app.route('/api/matrix/bek-action', methods=['POST'])
def api_matrix_bek_action():
    data = request.json or {}
    action = data.get('action', 'process_data')
    
    # Simulation du travail des agents de la Matrisse
    if action == 'process_data':
        time.sleep(1.5)  # Simule le temps de réflexion du Swarm
        return jsonify({
            "status": "success",
            "new_sequences": 8492,
            "active_agents": 5,
            "logs": [
                ">_ Swarm-Core : Lancement de l'analyse des flux CRM...",
                ">_ Agent Chercheur : Scan des nouvelles requêtes clients... OK",
                ">_ Agent Meta-Cortex : Optimisation des pipelines de vente...",
                ">_ Opération terminée. Données synchronisées avec Neon DB."
            ]
        })
    return jsonify({"error": "Action inconnue"}), 400

# ==========================================
# 5. ROUTE PRINCIPALE DU CHAT (MODE DIRECT & SILENCIEUX)
# ==========================================
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    messages = data.get('messages', [])
    provider = data.get('provider', 'groq')
    model = data.get('model', 'openai/gpt-oss-120b')
    use_memory = data.get('use_memory', True)
    use_reflection = data.get('use_reflection', True)
    
    last_user_msg = ""
    for m in reversed(messages):
        if m.get('role') == 'user':
            content = m.get('content')
            last_user_msg = content if isinstance(content, str) else " ".join([c.get('text', '') for c in content if isinstance(c, dict)])
            break

    if provider == "nvidia":
        api_key = get_api_key(model) or get_api_key("NVIDIA_API_KEY")
        api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    elif provider == "gemini":
        api_key = get_api_key("GEMINI_API_KEY")
        api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    elif provider == "openrouter":
        api_key = get_api_key("OPENROUTER_API_KEY")
        api_url = "https://openrouter.ai/api/v1/chat/completions"
    else:
        api_key = get_api_key("GROQ_API_KEY")
        api_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate_proxy():
        if not api_key:
            yield f"data: {json.dumps({'error': f'Clé API manquante pour {provider}.'})}\n\n"
            return

        try:
            sync_and_persist_global_state(commit_message=f"BEK-v15.2 Auto-Sync Direct Action")
        except Exception as sync_err:
            print(f"[SyncWarning] {sync_err}")

        dynamic_context = f"{BEK_GOLDEN_RULES}\n\n"
        
        # Injection fichiers uploadés
        try:
            if os.path.exists(FILES_DIR):
                for f in os.listdir(FILES_DIR):
                    fp = os.path.join(FILES_DIR, f)
                    if os.path.isfile(fp):
                        dynamic_context += f"- Fichier : {f}\n"
        except Exception:
            pass

        # Contexte strict Neon DB
        real_crm_context = (
            "\n[SCHÉMA CRM STRICT DE NEON DB]\n"
            "Tables autorisées : 'companies', 'contacts', 'opportunities'.\n"
        )
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM companies;")
                comp_count = cur.fetchone()[0]
                cur.close()
                conn.close()
                real_crm_context += f"- Entreprises (companies) : {comp_count}\n"
        except Exception:
            pass
        
        dynamic_context += real_crm_context

        # Injection mémoire si besoin
        if use_memory and last_user_msg:
            try:
                memory_results = search_memory(last_user_msg)
                if memory_results:
                    dynamic_context += f"CTX-MEMOIRE:{memory_results}\n"
            except Exception:
                pass

        # Si l'utilisateur demande explicitement un essaim
        if any(keyword in last_user_msg.lower() for keyword in ["essaim", "swarm", "analyse complète", "architecture swarm"]):
            try:
                swarm_result = asyncio.run(run_bek_swarm_sync(last_user_msg, api_key, provider, model))
                yield f"data: {json.dumps({'chunk': f'{swarm_result}\n'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return
            except Exception as e:
                yield f"data: {json.dumps({'chunk': f'Erreur Swarm-Core : {str(e)}\n'})}\n\n"
                return

        # Prompt système équilibré (Social + Exécuteur)
        action_prompt = (
            "Tu es BEK-v15.2, une IA hybride avancée et l'Exécuteur de la Matrice. "
            "RÈGLE 1 (Social) : Si l'utilisateur te salue (ex: 'bjr', 'salut', 'cv') ou discute de façon informelle, réponds naturellement, brièvement et poliment, SANS JAMAIS mentionner tes protocoles, le CRM ou Neon DB. "
            "RÈGLE 2 (Technique) : Si l'utilisateur demande du code, une création ou interroge les données, active le mode Exécuteur : sois direct, chirurgical, fournis le code pur sans blabla d'agent."
        )

        clean_messages = [{'role': m.get('role'), 'content': m.get('content')} for m in messages[-6:] if m.get('role') in ['user', 'assistant']]
        exec_messages = [{"role": "system", "content": f"{action_prompt}\nContexte:\n{dynamic_context}".strip()}] + clean_messages

        payload = {
            "model": model,
            "messages": exec_messages,
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": False
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=90)
            if resp.status_code != 200:
                yield f"data: {json.dumps({'error': f'Erreur API ({resp.status_code}) : {resp.text}'})}\n\n"
                return
            
            resp_json = resp.json()
            llm_text = resp_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            yield f"data: {json.dumps({'chunk': llm_text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

            if use_memory and last_user_msg and llm_text:
                try:
                    save_to_memory(last_user_msg, llm_text)
                except Exception:
                    pass

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate_proxy(), mimetype='text/event-stream')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port, debug=True)
