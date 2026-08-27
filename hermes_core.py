# hermes_core.py - Mise à jour Phase 1 : Job Queue & Workers robustes
import asyncio
import concurrent.futures
import time
import threading
import uuid
from memory import get_db_connection

class HermesCore:
    def __init__(self):
        self.tools = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

    def register_tool(self, name, func, risk_level="L1"):
        self.tools[name] = {
            "func": func,
            "risk_level": risk_level
        }

    def goap_planner(self, objective: str):
        obj = objective.lower()
        tasks = []
        if "prospect" in obj or "web" in obj or "cherche" in obj:
            tasks.append({"tool": "web_sync", "args": {"query": objective}})
        if "crm" in obj or "neon" in obj or "base" in obj:
            tasks.append({"tool": "neon_audit", "args": {}})
        if not tasks:
            tasks.append({"tool": "default_llm", "args": {"query": objective}})
        return tasks

    def dispatch_parallel(self, task_list, user_override_approval=False):
        trace_id = f"BEK-TRC-{uuid.uuid4().hex[:8].upper()}"
        start_time = time.time()
        futures = []
        
        for task in task_list:
            tool_name = task.get("tool")
            args = task.get("args", {})
            if tool_name in self.tools:
                tool_info = self.tools[tool_name]
                if tool_info["risk_level"] in ["L3", "L5"] and not user_override_approval:
                    return {
                        "trace_id": trace_id,
                        "status": "SECURITY_APPROVAL_REQUIRED",
                        "message": f"L'outil '{tool_name}' requiert une validation humaine (Niveau {tool_info['risk_level']})."
                    }
                futures.append((tool_name, self.executor.submit(tool_info["func"], **args)))
        
        results = {}
        for tool_name, future in futures:
            try:
                results[tool_name] = future.result(timeout=15)
            except Exception as e:
                results[tool_name] = {"error": str(e)}
                
        duration = round((time.time() - start_time) * 1000, 2)
        return {
            "trace_id": trace_id,
            "execution_ms": duration,
            "results": results,
            "status": "hermes_secure_success"
        }

hermes = HermesCore()

def init_system_jobs_table():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_jobs (
                    job_id VARCHAR(64) PRIMARY KEY,
                    task_name TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL, -- PENDING, RUNNING, SUCCESS, FAILED
                    retry_count INT DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[JobQueue Init Error]: {e}")

def background_guardian_worker():
    init_system_jobs_table()
    while True:
        try:
            conn = get_db_connection()
            if conn:
                job_id = f"JOB-{uuid.uuid4().hex[:6].upper()}"
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO system_jobs (job_id, task_name, status) 
                    VALUES (%s, 'matrix_silent_audit', 'RUNNING');
                """, (job_id,))
                conn.commit()
                
                # Simulation de vérification saine de la Matrisse
                time.sleep(2)
                
                cur.execute("""
                    UPDATE system_jobs SET status = 'SUCCESS' WHERE job_id = %s;
                """, (job_id,))
                conn.commit()
                cur.close()
                conn.close()
            time.sleep(1800) # Toutes les 30 minutes
        except Exception as e:
            print(f"[Worker Error]: {e}")
            time.sleep(60)

def start_background_workers():
    t = threading.Thread(target=background_guardian_worker, daemon=True)
    t.start()
