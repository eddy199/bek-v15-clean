# ==============================================================================
# BEK-v16 — Accès Neon DB (extrait de app.py v15.3, DÉPLACÉ à l'identique)
# ==============================================================================
from memory import get_db_connection
from core.utils import json_safe


def execute_database_sql(sql_query: str) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Connexion Neon DB indisponible."}
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(sql_query)
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results = [{column: json_safe(value) for column, value in zip(columns, row)} for row in rows]
            return {"status": "success", "type": "select", "data": results, "count": len(results)}
        conn.commit()
        return {"status": "success", "type": "mutation", "affected_rows": cur.rowcount}
    except Exception as exc:
        if conn:
            try: conn.rollback()
            except Exception: pass
        return {"status": "error", "message": str(exc)}
    finally:
        if cur:
            try: cur.close()
            except Exception: pass
        if conn:
            try: conn.close()
            except Exception: pass
