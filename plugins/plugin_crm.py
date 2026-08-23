import json
import os
import sys
import subprocess
from pathlib import Path

# Ajout du dossier racine au PATH pour pouvoir importer memory.py
workspace_dir = "/media/moh/84B00E0BB00E0500/workspacekimi"
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

try:
    from memory import save_to_memory
except ImportError:
    # Fallback silencieux si memory.py n'est pas trouvable
    def save_to_memory(q, r): pass

class CRMPlugin:
    command_names = [
        "/crm", "crm:", "/lead", "ajoute prospect", "créer prospect", "creer prospect",
        "créer deal", "creer deal", "créer tâche", "creer tache", "recherche", "cherche contact",
        "modifie contact", "maj contact"
    ]

    def __init__(self):
        self.workspace_dir = workspace_dir
        self.crm_dir = os.path.join(self.workspace_dir, "bek-v15-clean")
        self.db_dir = os.path.join(self.crm_dir, "packages", "db")
        self.api_url = os.environ.get("CRM_API_URL", "http://localhost:3000/api")

    def _get_database_url(self) -> str:
        paths_to_check = [
            os.path.join(self.db_dir, ".env"),
            os.path.join(self.crm_dir, ".env"),
            os.path.join(self.workspace_dir, "env.txt"),
            os.path.join(self.workspace_dir, ".env")
        ]
        for p in paths_to_check:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("DATABASE_URL=") or line.startswith("DIRECT_URL="):
                                return line.strip().split("=", 1)[1].strip('"\'')
                except Exception:
                    pass
        return os.environ.get("DATABASE_URL", "")

    def _run_sql_script(self, ts_code: str) -> str:
        db_url = self._get_database_url()
        if not db_url:
            return "❌ Erreur : DATABASE_URL introuvable."
        
        full_code = f"""
import {{ SQL }} from 'bun';
import {{ randomUUID }} from 'crypto';

const db = new SQL('{db_url}');
{ts_code}
"""
        try:
            res = subprocess.run(
                ["bun", "-e", full_code],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
            else:
                return f"⚠️ Erreur SQL/Bun :\n{res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return f"❌ Erreur d'exécution : {str(e)}"

    def execute_payload(self, action: str, params: dict) -> str:
        if action == "create_contact":
            name = params.get("name") or params.get("firstName") or "Nouveau Prospect"
            email = params.get("email", "")
            phone = params.get("phone", "")
            return self.create_contact(name, email, phone)

        elif action == "create_deal":
            title = params.get("title") or params.get("name") or "Nouveau Deal"
            amount = params.get("amount", 0)
            return self.create_deal(title, amount)

        elif action == "create_task":
            title = params.get("title") or params.get("name") or "Nouvelle Tâche"
            return self.create_task(title)

        elif action == "search_contact":
            query = params.get("query") or params.get("name") or ""
            return self.search_contact(query)

        elif action == "update_contact":
            name = params.get("name", "")
            email = params.get("email", "")
            phone = params.get("phone", "")
            return self.update_contact(name, email, phone)

        elif action == "get_stats":
            return self.get_stats()

        return f"Action CRM '{{action}}' non supportée."

    def get_stats(self) -> str:
        ts = """
async function main() {
  try {
    const contacts = await db`SELECT count(*) FROM "contact"`;
    const deals = await db`SELECT count(*) FROM "deal"`;
    const companies = await db`SELECT count(*) FROM "company"`;
    console.log(JSON.stringify({
      status: 'ok',
      contacts: contacts[0].count,
      deals: deals[0].count,
      companies: companies[0].count
    }));
  } finally {
    await db.close();
  }
}
main();
"""
        return f"📊 Statistiques Neon : {self._run_sql_script(ts)}"

    def create_contact(self, name: str, email: str = "", phone: str = "") -> str:
        ts = f"""
async function main() {{
  try {{
    const id = randomUUID();
    const now = new Date().toISOString();
    const inserted = await db`
      INSERT INTO "contact" ("id", "firstName", "email", "phone", "createdAt", "updatedAt", "source")
      VALUES (${{id}}, '{name}', ${{'{email}' || null}}, ${{'{phone}' || null}}, ${{now}}, ${{now}}, 'MANUAL')
      RETURNING *
    `;
    console.log(JSON.stringify({{ status: 'created', entity: 'contact', data: inserted[0] }}));
  }} finally {{
    await db.close();
  }}
}}
main();
"""
        result = f"✅ Contact créé dans Neon : {self._run_sql_script(ts)}"
        # MÉMOIRE : Sauvegarde si succès
        if "Erreur" not in result:
            save_to_memory(f"Création d'un prospect/contact nommé {name}", f"Email: {email}, Tel: {phone}. {result}")
        return result

    def create_deal(self, title: str, amount: float = 0) -> str:
        ts = f"""
async function main() {{
  try {{
    const now = new Date().toISOString();
    let companyRes = await db`SELECT id FROM "company" LIMIT 1`;
    let compId = companyRes.length > 0 ? companyRes[0].id : null;
    if (!compId) {{
      compId = randomUUID();
      await db`INSERT INTO "company" ("id", "name", "createdAt", "updatedAt") VALUES (${{compId}}, 'Entreprise Principale', ${{now}}, ${{now}})`;
    }}

    let userRes = await db`SELECT id FROM "user" LIMIT 1`;
    let ownerId = userRes.length > 0 ? userRes[0].id : null;
    if (!ownerId) {{
      ownerId = randomUUID();
      try {{ await db`INSERT INTO "user" ("id", "email", "name", "createdAt", "updatedAt") VALUES (${{ownerId}}, 'agent@kimi.local', 'Agent Kimi', ${{now}}, ${{now}})`; }} 
      catch (e) {{ await db`INSERT INTO "user" ("id", "email") VALUES (${{ownerId}}, 'agent@kimi.local')`; }}
    }}

    const dealId = randomUUID();
    const inserted = await db`
      INSERT INTO "deal" ("id", "name", "amount", "companyId", "ownerId", "createdAt", "updatedAt", "stage")
      VALUES (${{dealId}}, '{title}', {amount}, ${{compId}}, ${{ownerId}}, ${{now}}, ${{now}}, 'DEMO_BOOKED')
      RETURNING *
    `;
    console.log(JSON.stringify({{ status: 'created', entity: 'deal', data: inserted[0] }}));
  }} finally {{
    await db.close();
  }}
}}
main();
"""
        result = f"💼 Deal créé dans Neon : {self._run_sql_script(ts)}"
        # MÉMOIRE : Sauvegarde si succès
        if "Erreur" not in result:
            save_to_memory(f"Création d'un deal ou opportunité : {title}", f"Montant: {amount}. {result}")
        return result

    def create_task(self, title: str) -> str:
        ts = f"""
async function main() {{
  try {{
    const cols = await db`SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = 'agentTask'`;
    const colNames = cols.map(c => c.column_name);

    const insertObj = {{ id: randomUUID() }};
    const now = new Date().toISOString();
    const tomorrow = new Date(Date.now() + 86400000).toISOString();

    if (colNames.includes('createdAt')) insertObj['createdAt'] = now;
    if (colNames.includes('updatedAt')) insertObj['updatedAt'] = now;
    if (colNames.includes('dueAt')) insertObj['dueAt'] = tomorrow;
    if (colNames.includes('dueDate')) insertObj['dueDate'] = tomorrow;

    if (colNames.includes('name')) insertObj['name'] = '{title}';
    else if (colNames.includes('title')) insertObj['title'] = '{title}';
    else if (colNames.includes('description')) insertObj['description'] = '{title}';
    else if (colNames.includes('prompt')) insertObj['prompt'] = '{title}';
    
    if (colNames.includes('reason')) insertObj['reason'] = 'Créé via Agent';

    if (colNames.includes('kind')) {{
       try {{
         const kindEnum = await db`SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = (SELECT udt_name FROM information_schema.columns WHERE table_name = 'agentTask' AND column_name = 'kind') LIMIT 1`;
         insertObj['kind'] = kindEnum.length > 0 ? kindEnum[0].enumlabel : 'TODO';
       }} catch(e) {{ insertObj['kind'] = 'TODO'; }}
    }}

    if (colNames.includes('status')) {{
       try {{
         const statusEnum = await db`SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = (SELECT udt_name FROM information_schema.columns WHERE table_name = 'agentTask' AND column_name = 'status') LIMIT 1`;
         insertObj['status'] = statusEnum.length > 0 ? statusEnum[0].enumlabel : 'PENDING';
       }} catch(e) {{ insertObj['status'] = 'PENDING'; }}
    }}

    if (colNames.includes('ownerId') || colNames.includes('userId')) {{
       let userRes = await db`SELECT id FROM "user" LIMIT 1`;
       if (userRes.length > 0) {{
         if (colNames.includes('ownerId')) insertObj['ownerId'] = userRes[0].id;
         if (colNames.includes('userId')) insertObj['userId'] = userRes[0].id;
       }}
    }}

    const keys = Object.keys(insertObj);
    const colsStr = keys.map(k => `"${{k}}"`).join(', ');
    const valsStr = keys.map(k => typeof insertObj[k] === 'string' ? `'${{insertObj[k]}}'` : insertObj[k]).join(', ');

    const inserted = await db.unsafe(`INSERT INTO "agentTask" (${{colsStr}}) VALUES (${{valsStr}}) RETURNING *`);
    console.log(JSON.stringify({{ status: 'created', entity: 'task', data: inserted[0] }}));
  }} catch(e) {{
    console.error(JSON.stringify({{ error: e.message }}));
  }} finally {{
    await db.close();
  }}
}}
main();
"""
        result = f"📝 Tâche créée dans Neon : {self._run_sql_script(ts)}"
        # MÉMOIRE : Sauvegarde si succès
        if "Erreur" not in result and "error" not in result:
            save_to_memory(f"Création d'une tâche CRM : {title}", f"Résultat: {result}")
        return result

    def search_contact(self, query: str) -> str:
        ts = f"""
async function main() {{
  try {{
    const results = await db`
      SELECT id, "firstName", "lastName", email, phone, "createdAt" 
      FROM "contact"
      WHERE "firstName" ILIKE '%{query}%' OR "lastName" ILIKE '%{query}%' OR email ILIKE '%{query}%'
      LIMIT 5
    `;
    console.log(JSON.stringify({{ status: 'ok', count: results.length, contacts: results }}));
  }} finally {{
    await db.close();
  }}
}}
main();
"""
        return f"🔍 Résultats de recherche Neon : {self._run_sql_script(ts)}"

    def update_contact(self, name: str, email: str = "", phone: str = "") -> str:
        ts = f"""
async function main() {{
  try {{
    const target = await db`SELECT id FROM "contact" WHERE "firstName" ILIKE '{name}' ORDER BY "createdAt" DESC LIMIT 1`;
    if (target.length === 0) {{ return console.log(JSON.stringify({{ status: 'not_found', message: 'Aucun contact trouvé' }})); }}

    const now = new Date().toISOString();
    const updated = await db`
      UPDATE "contact"
      SET email = COALESCE(NULLIF('{email}', ''), email), phone = COALESCE(NULLIF('{phone}', ''), phone), "updatedAt" = ${{now}}
      WHERE id = ${{target[0].id}} RETURNING *
    `;
    console.log(JSON.stringify({{ status: 'updated', data: updated[0] }}));
  }} finally {{
    await db.close();
  }}
}}
main();
"""
        result = f"✏️ Mise à jour Contact Neon : {self._run_sql_script(ts)}"
        # MÉMOIRE : Sauvegarde si succès
        if "Erreur" not in result and "not_found" not in result:
            save_to_memory(f"Mise à jour du contact nommé {name}", f"Nouvel email: {email}, Nouveau tel: {phone}. {result}")
        return result

    def execute(self, uin: str) -> str:
        return self.get_stats()

def GET_AGENT_PLUGIN_CLASS():
    return CRMPlugin()