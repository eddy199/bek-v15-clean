# ==============================================================================
# BEK-v16 — Routeur Matrice CRM & Neon DB (routers/crm.py)
# ==============================================================================
from fastapi import APIRouter, Request, HTTPException
from services.db import execute_database_sql

try:
    from sub_crm_engine import SubCRMEngine
except ImportError:
    SubCRMEngine = None

router = APIRouter(tags=["CRM"])

@router.get("/api/matrix/sub_crms")
async def api_list_sub_crms():
    if SubCRMEngine:
        return {"status": "success", "data": SubCRMEngine.list_sub_crms()}
    return {"status": "success", "data": []}

@router.get("/api/crm/opportunities")
async def api_list_opportunities():
    res = execute_database_sql('SELECT id, name, amount, currency, stage, created_at FROM "opportunities" ORDER BY id DESC LIMIT 20;')
    return {"status": "success", "data": res.get("data", [])}

@router.post("/api/crm/execute")
async def api_execute_crm_sql(request: Request):
    data = await request.json() or {}
    sql = data.get("sql", "")
    if not sql:
        raise HTTPException(status_code=400, detail="Requête SQL manquante")
    return execute_database_sql(sql)

@router.get("/api/crm/stats")
async def api_crm_stats():
    res_companies = execute_database_sql('SELECT count(*)::int as c FROM "companies";')
    res_contacts = execute_database_sql('SELECT count(*)::int as c FROM "contacts";')
    res_opportunities = execute_database_sql('SELECT count(*)::int as c, COALESCE(SUM(amount), 0)::float as total FROM "opportunities";')
    return {
        "status": "ok",
        "companies": res_companies.get("data", [{}])[0].get("c", 0),
        "contacts": res_contacts.get("data", [{}])[0].get("c", 0),
        "deals": res_opportunities.get("data", [{}])[0].get("c", 0),
        "pipeline_total": res_opportunities.get("data", [{}])[0].get("total", 0)
    }