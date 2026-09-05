# ==========================================
# BEK-v15.3 HYBRID - MOTEUR D'INSTANCIATION DYNAMIQUE DE SOUS-CRM
# Génération autonome de sous-systèmes de niche & d'outils de dernière génération
# ==========================================

from __future__ import annotations

import os
import sys
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent

def _load_env_fallback(path: Path) -> Dict[str, str]:
    """Charge un fichier env.txt simple de type KEY=VALUE sous Windows/Linux."""
    values: Dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return values
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith("="):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return values

ENV_LOCAL = _load_env_fallback(ROOT_DIR / "env.txt")
ENV_LOCAL.update(_load_env_fallback(ROOT_DIR / ".env"))

def get_db_connection() -> Optional[Any]:
    """Connexion robuste à Neon PostgreSQL avec résilience multi-sources."""
    neon_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL")
        or ENV_LOCAL.get("DATABASE_URL")
        or ENV_LOCAL.get("NEON_DATABASE_URL")
        or ""
    )
    if not neon_url:
        print("[SubCRMEngine] ⚠️ DATABASE_URL non configuré.")
        return None

    try:
        import psycopg2
        return psycopg2.connect(neon_url, connect_timeout=10, sslmode="require")
    except ImportError:
        print("[SubCRMEngine] ❌ psycopg2 n'est pas installé.")
        return None
    except Exception as e:
        print(f"[SubCRMEngine Error] Échec connexion Neon DB : {e}")
        return None


class SubCRMEngine:
    """
    Gestionnaire central des sous-CRMs et matrices de niche avec gestion étanche des curseurs SQL.
    """

    @staticmethod
    def initialize_matrix_schema() -> bool:
        """Assure la création de la table universelle des sous-CRM dans Neon."""
        conn = get_db_connection()
        if not conn:
            return False
        cur = None
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
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            return True
        except Exception as e:
            print(f"[SubCRMEngine Error] Initialisation schéma matrice : {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False
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

    @staticmethod
    def spawn_sub_crm(
        niche_name: str,
        cahier_des_charges: str,
        objectives: list,
        parent_id: Optional[str] = None,
        custom_env: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Instancie dynamiquement un sous-CRM ultra-spécifique de n'importe quel domaine,
        en lui injectant les outils de dernière génération et ses agents dédiés.
        """
        SubCRMEngine.initialize_matrix_schema()

        sub_crm_id = str(uuid.uuid4())

        # Injection exclusive des outils et technologies de dernière génération
        next_gen_tools = [
            {"tool": "LangGraph Advanced Swarm-Core v15.2", "mode": "autonomous_reflection"},
            {"tool": "Meta-Cortex Grounding & Reflexion Engine", "mode": "real_time_verification"},
            {"tool": "Universal External AI Bridge", "mode": "dynamic_api_relay"},
            {"tool": "Secure Sandbox Terminal Executor", "mode": "isolated_code_execution"},
        ]

        environment_payload = custom_env or {
            "RUNTIME_ENV": "production_matrix_node",
            "AI_AUTONOMY_LEVEL": "maximum",
            "SELF_HEALING": "enabled",
        }

        specifications = {
            "objectives": objectives,
            "architecture": "Python/Flask + Neon Polymorphic Layer",
            "generation": "Next-Gen Ultra-Powerful Node",
        }

        conn = get_db_connection()
        if not conn:
            return {"status": "error", "message": "Connexion Neon DB indisponible pour l'instanciation."}

        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO matrix_sub_crms 
                (id, parent_id, niche_name, specifications, environment_vars, active_tools, cahier_des_charges, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                RETURNING id, niche_name, created_at;
                """,
                (
                    sub_crm_id,
                    parent_id,
                    niche_name,
                    json.dumps(specifications),
                    json.dumps(environment_payload),
                    json.dumps(next_gen_tools),
                    cahier_des_charges,
                ),
            )

            row = cur.fetchone()
            conn.commit()

            print(f"[SubCRMEngine] ✅ Sous-CRM instancié avec succès : {niche_name} (ID: {sub_crm_id})")
            return {
                "status": "success",
                "sub_crm_id": str(row[0]),
                "niche_name": row[1],
                "created_at": str(row[2]),
                "tools_injected": next_gen_tools,
                "message": f"Le sous-CRM '{niche_name}' est né, doté de sa propre vie et de ses agents autonomes.",
            }

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {"status": "error", "message": str(e)}
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

    @staticmethod
    def list_sub_crms() -> List[Dict[str, Any]]:
        """Retourne la liste de tous les sous-CRMs instanciés pour l'interface UI."""
        SubCRMEngine.initialize_matrix_schema()
        conn = get_db_connection()
        if not conn:
            return []

        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, parent_id, niche_name, specifications, active_tools, status, created_at 
                FROM matrix_sub_crms 
                ORDER BY created_at DESC;
            """)
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": str(r[0]),
                    "parent_id": str(r[1]) if r[1] else None,
                    "niche_name": r[2],
                    "specifications": r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
                    "active_tools": r[4] if isinstance(r[4], list) else json.loads(r[4] or "[]"),
                    "status": r[5],
                    "created_at": str(r[6]),
                })
            return results
        except Exception as e:
            print(f"[SubCRMEngine Error] Lecture liste sous-CRMs : {e}")
            return []
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

    @staticmethod
    def get_sub_crm(sub_crm_id: str) -> Optional[Dict[str, Any]]:
        """Récupère la configuration détaillée d'un sous-CRM par son ID."""
        conn = get_db_connection()
        if not conn:
            return None

        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, parent_id, niche_name, specifications, environment_vars, active_tools, cahier_des_charges, status, created_at
                FROM matrix_sub_crms 
                WHERE id = %s;
            """, (sub_crm_id,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": str(r[0]),
                "parent_id": str(r[1]) if r[1] else None,
                "niche_name": r[2],
                "specifications": r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
                "environment_vars": r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}"),
                "active_tools": r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]"),
                "cahier_des_charges": r[6],
                "status": r[7],
                "created_at": str(r[8]),
            }
        except Exception as e:
            print(f"[SubCRMEngine Error] Récupération sous-CRM {sub_crm_id} : {e}")
            return None
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