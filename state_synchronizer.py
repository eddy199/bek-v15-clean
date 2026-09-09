# ==============================================================================
# state_synchronizer.py — NEON DB STATE SYNCHRONIZER & FSM (BEK-v15.3)
# ==============================================================================

import logging
from datetime import datetime, timezone
from memory import get_db_connection

logger = logging.getLogger("StateSynchronizer")

def init_state_tables():
    """Initialise la table des états et des compensations dans Neon DB."""
    conn = get_db_connection()
    if not conn:
        logger.warning("❌ [NeonState] Connexion Neon DB indisponible pour l'init des états.")
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bek_task_states (
                task_id VARCHAR(64) PRIMARY KEY,
                correlation_id VARCHAR(64),
                state VARCHAR(32) NOT NULL,
                payload TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✨ [NeonState] Table bek_task_states initialisée avec succès.")
        return True
    except Exception as e:
        logger.error(f"❌ [NeonState] Erreur initialisation table états : {e}")
        if conn:
            try: conn.close()
            except Exception: pass
        return False

def update_task_state(task_id: str, state: str, correlation_id: str = "", payload: str = ""):
    """Met à jour ou insère l'état d'une tâche (PENDING, RUNNING, COMPLETED, FAILED)."""
    valid_states = {"PENDING", "RUNNING", "COMPLETED", "FAILED"}
    if state not in valid_states:
        raise ValueError(f"État invalide : {state}. États autorisés : {valid_states}")

    conn = get_db_connection()
    if not conn:
        logger.warning(f"❌ [NeonState] Impossible de persister l'état {state} pour {task_id} (DB off).")
        return False

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bek_task_states (task_id, correlation_id, state, payload, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (task_id) 
            DO UPDATE SET state = EXCLUDED.state, 
                          correlation_id = EXCLUDED.correlation_id, 
                          payload = EXCLUDED.payload, 
                          updated_at = CURRENT_TIMESTAMP;
        """, (task_id, correlation_id, state, payload))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"🔄 [NeonState] Tâche [{task_id}] -> État mis à jour : {state} (Corr: {correlation_id})")
        return True
    except Exception as e:
        logger.error(f"❌ [NeonState] Erreur mise à jour état tâche : {e}")
        if conn:
            try: conn.rollback(); conn.close()
            except Exception: pass
        return False

def get_pending_or_running_tasks() -> list:
    """Récupère les tâches interrompues pour reprise après redémarrage."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT task_id, correlation_id, state, payload FROM bek_task_states WHERE state IN ('PENDING', 'RUNNING');")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"task_id": r[0], "correlation_id": r[1], "state": r[2], "payload": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"❌ [NeonState] Erreur récupération tâches en cours : {e}")
        if conn:
            try: conn.close()
            except Exception: pass
        return []