"""
==============================================================================
BEK-v16 — Accès base de données
------------------------------------------------------------------------------
Façade de compatibilité pour les accès SQL.

IMPORTANT :
- L'API publique execute_database_sql() est conservée.
- La connexion Neon reste centralisée dans memory.py pour le moment.
- Aucun code métier ne doit être ajouté ici.
- Ce module pourra ensuite être déplacé vers le domaine persistence/db
  sans casser les consommateurs existants.
==============================================================================
"""

from __future__ import annotations

from typing import Any, Dict

from core.utils import json_safe
from memory import get_db_connection


def execute_database_sql(sql_query: str) -> Dict[str, Any]:
    """
    Exécute une requête SQL sur Neon PostgreSQL.

    Retourne une structure JSON-safe compatible avec les routers,
    nerves et services existants.
    """
    if not isinstance(sql_query, str) or not sql_query.strip():
        return {
            "status": "error",
            "message": "Requête SQL vide.",
        }

    conn = get_db_connection()

    if not conn:
        return {
            "status": "error",
            "message": "Connexion Neon DB indisponible.",
        }

    cur = None

    try:
        cur = conn.cursor()
        cur.execute(sql_query)

        # ------------------------------------------------------------------
        # SELECT / requête retournant des lignes
        # ------------------------------------------------------------------
        if cur.description:
            columns = [description[0] for description in cur.description]
            rows = cur.fetchall()

            results = [
                {column: json_safe(value) for column, value in zip(columns, row)}
                for row in rows
            ]

            return {
                "status": "success",
                "type": "select",
                "data": results,
                "count": len(results),
            }

        # ------------------------------------------------------------------
        # INSERT / UPDATE / DELETE / DDL
        # ------------------------------------------------------------------
        conn.commit()

        return {
            "status": "success",
            "type": "mutation",
            "affected_rows": cur.rowcount,
        }

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass

        return {
            "status": "error",
            "message": str(exc),
        }

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass

        try:
            conn.close()
        except Exception:
            pass