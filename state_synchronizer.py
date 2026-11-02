# ==============================================================================
# state_synchronizer.py — NEON DB STATE SYNCHRONIZER & FSM (BEK-v15.3)
# ------------------------------------------------------------------------------
# v15.4 (2026-09-22) :
#   - update_task_state : fire-and-forget (thread détaché)
#     → ne bloque PLUS le flux principal (~4s → ~0ms par action)
#   - init_state_tables : conservé synchrone (appelé une seule fois au boot)
#   - get_pending_or_running_tasks : conservé synchrone (appelé rarement)
#   - API publique inchangée (mêmes signatures, mêmes types de retour)
# ==============================================================================

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from memory import get_db_connection

logger = logging.getLogger("StateSynchronizer")


# ==============================================================================
# EXECUTOR DÉDIÉ (fire-and-forget)
# ------------------------------------------------------------------------------
# Pool de threads séparé pour ne pas saturer le pool Hermes/DAG.
# max_workers=4 suffit : les écritures sont petites et rapides.
# ==============================================================================
_STATE_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="bek-state",
)

# Verrou léger pour éviter les races sur l'init (au cas où plusieurs threads
# appellent update_task_state avant que la table soit créée).
_INIT_LOCK = threading.Lock()


# ==============================================================================
# INIT TABLES (synchrone — appelé UNE fois au boot)
# ==============================================================================
def init_state_tables() -> bool:
    """Initialise la table des états et des compensations dans Neon DB."""
    conn = get_db_connection()
    if not conn:
        logger.warning(
            "❌ [NeonState] Connexion Neon DB indisponible pour l'init des états."
        )
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
            try:
                conn.close()
            except Exception:
                pass
        return False


# ==============================================================================
# UPDATE STATE — FIRE & FORGET
# ==============================================================================
def _do_update_task_state(
    task_id: str,
    state: str,
    correlation_id: str,
    payload: str,
) -> None:
    """
    Implémentation réelle de l'écriture Neon.
    Appelée depuis un thread de _STATE_EXECUTOR (jamais sur le flux principal).
    """
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.warning(
                f"❌ [NeonState] Impossible de persister l'état {state} "
                f"pour {task_id} (DB off)."
            )
            return

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO bek_task_states
                (task_id, correlation_id, state, payload, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (task_id)
            DO UPDATE SET
                state = EXCLUDED.state,
                correlation_id = EXCLUDED.correlation_id,
                payload = EXCLUDED.payload,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (task_id, correlation_id, state, payload),
        )
        conn.commit()
        logger.info(
            f"🔄 [NeonState] Tâche [{task_id}] -> État mis à jour : {state} "
            f"(Corr: {correlation_id})"
        )
    except Exception as e:
        logger.error(f"❌ [NeonState] Erreur mise à jour état tâche : {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def update_task_state(
    task_id: str,
    state: str,
    correlation_id: str = "",
    payload: str = "",
) -> bool:
    """
    Programme la mise à jour d'état dans un thread détaché et retourne
    IMMÉDIATEMENT (fire-and-forget).

    - Latence côté appelant : ~0 ms (submission de tâche)
    - L'écriture Neon réelle se fait en arrière-plan
    - En cas d'échec Neon, l'action n'est PAS affectée
    - La validation du state est conservée (lève ValueError si invalide)

    Signature et type de retour inchangés (compatibilité totale).
    """
    valid_states = {"PENDING", "RUNNING", "COMPLETED", "FAILED"}
    if state not in valid_states:
        # On garde la validation synchrone : c'est un bug de programmation
        # si un appelant passe un état invalide.
        raise ValueError(
            f"État invalide : {state}. États autorisés : {valid_states}"
        )

    try:
        _STATE_EXECUTOR.submit(
            _do_update_task_state,
            task_id,
            state,
            correlation_id,
            payload,
        )
    except RuntimeError as e:
        # Cas rare : executor déjà shutdown (arrêt du process)
        logger.debug(
            f"[NeonState] Executor shutdown, état {state} non persisté "
            f"pour {task_id} : {e}"
        )

    return True


# ==============================================================================
# LECTURE — CONSERVÉE SYNCHRONE (appelée rarement, pas sur le flux chaud)
# ==============================================================================
def get_pending_or_running_tasks() -> list:
    """Récupère les tâches interrompues pour reprise après redémarrage."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT task_id, correlation_id, state, payload "
            "FROM bek_task_states "
            "WHERE state IN ('PENDING', 'RUNNING');"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "task_id": r[0],
                "correlation_id": r[1],
                "state": r[2],
                "payload": r[3],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"❌ [NeonState] Erreur récupération tâches en cours : {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return []


# ==============================================================================
# SHUTDOWN PROPRE (optionnel)
# ==============================================================================
def shutdown_state_synchronizer(wait: bool = False) -> None:
    """
    Arrête proprement l'executor. À appeler lors de l'arrêt de l'app
    si tu veux garantir que les dernières écritures sont flushées.
    """
    try:
        _STATE_EXECUTOR.shutdown(wait=wait, cancel_futures=False)
        logger.info("[NeonState] Executor fire-and-forget arrêté.")
    except Exception as e:
        logger.debug(f"[NeonState] Shutdown executor : {e}")