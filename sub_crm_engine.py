# ==========================================
# BEK-v15.3 HYBRID - MOTEUR D'INSTANCIATION DYNAMIQUE DE SOUS-CRM
# Génération autonome de sous-systèmes de niche & d'outils de dernière génération
# ------------------------------------------------------------------------------
# ★ v18.2 (2026-09-27) : Migration Neon → Supabase + fix cache env.txt
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


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT ENV — v18.2 : Priorité à os.environ + rechargement dynamique
# ══════════════════════════════════════════════════════════════════════════════

def _reload_env_local() -> Dict[str, str]:
    """Recharge env.txt à chaque appel (évite le cache au boot)."""
    values = _load_env_fallback(ROOT_DIR / "env.txt")
    values.update(_load_env_fallback(ROOT_DIR / ".env"))
    return values


# Chargement initial (peut être obsolète si env.txt a changé)
ENV_LOCAL = _reload_env_local()


def _get_db_url() -> str:
    """
    Retourne l'URL PostgreSQL active.

    Priorité (v18.2) :
      1. os.environ["DATABASE_URL"]      (défini par env_loader.load_env())
      2. os.environ["NEON_DATABASE_URL"] (fallback ancien nom)
      3. ENV_LOCAL rechargé dynamiquement (env.txt / .env)
      4. os.environ["SUPABASE_DATABASE_URL"] (nouveau nom optionnel)
    """
    # 1. Priorité maximale : variables d'environnement actuelles
    for key in ("DATABASE_URL", "NEON_DATABASE_URL", "SUPABASE_DATABASE_URL"):
        val = os.environ.get(key)
        if val and val.strip():
            return val.strip()

    # 2. Fallback : recharger env.txt (au cas où il a changé après le boot)
    fresh_env = _reload_env_local()
    for key in ("DATABASE_URL", "NEON_DATABASE_URL", "SUPABASE_DATABASE_URL"):
        val = fresh_env.get(key)
        if val and val.strip():
            return val.strip()

    return ""


def get_db_connection() -> Optional[Any]:
    """Connexion robuste à PostgreSQL (Supabase) avec résilience multi-sources."""
    db_url = _get_db_url()
    if not db_url:
        print("[SubCRMEngine] ⚠️ DATABASE_URL non configuré.")
        return None

    try:
        import psycopg2
        return psycopg2.connect(db_url, connect_timeout=10, sslmode="require")
    except ImportError:
        print("[SubCRMEngine] ❌ psycopg2 n'est pas installé.")
        return None
    except Exception as e:
        # Masquer le mot de passe dans le message d'erreur
        safe_msg = str(e)
        if "@" in safe_msg and "://" in safe_msg:
            try:
                prefix = safe_msg.split("://", 1)[0]
                rest = safe_msg.split("://", 1)[1]
                if "@" in rest:
                    safe_msg = f"{prefix}://[REDACTED]@{rest.split('@', 1)[1]}"
            except Exception:
                pass
        print(f"[SubCRMEngine Error] Échec connexion DB : {safe_msg}")
        return None


class SubCRMEngine:
    """
    Gestionnaire central des sous-CRMs et matrices de niche
    avec gestion étanche des curseurs SQL.
    """

    @staticmethod
    def initialize_matrix_schema() -> bool:
        """Assure la création de la table universelle des sous-CRM."""
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
            "architecture": "Python/Flask + Supabase Polymorphic Layer",
            "generation": "Next-Gen Ultra-Powerful Node",
        }

        conn = get_db_connection()
        if not conn:
            return {"status": "error", "message": "Connexion DB indisponible pour l'instanciation."}

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