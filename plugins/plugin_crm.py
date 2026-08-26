import json
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Ajout du dossier racine au PATH pour pouvoir importer memory.py
workspace_dir = "/media/moh/84B00E0BB00E0500/workspacekimi"
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

try:
    from memory import save_to_memory
except ImportError:
    def save_to_memory(q, r): pass


class CRMPlugin:
    command_names = [
        "/crm", "crm:", "/lead", "ajoute prospect", "créer prospect", "creer prospect",
        "créer deal", "creer deal", "créer tâche", "creer tache", "recherche", "cherche contact",
        "modifie contact", "maj contact", "stats", "statistiques"
    ]

    def __init__(self):
        self.workspace_dir = workspace_dir
        self.crm_dir = os.path.join(self.workspace_dir, "bek-v15-clean")
        self.db_dir = os.path.join(self.crm_dir, "packages", "db")
        self.api_url = os.environ.get("CRM_API_URL", "http://localhost:3000/api")
        self._bun_available = shutil.which("bun") is not None

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

    def _run_bun_script(self, ts_code: str, params: dict = None) -> str:
        """Exécute du TypeScript via Bun en passant les params sécurisés via process.argv."""
        if not self._bun_available:
            return "❌ Erreur : Bun n'est pas installé ou introuvable dans le PATH."

        db_url = self._get_database_url()
        if not db_url:
            return "❌ Erreur : DATABASE_URL introuvable."

        # Passage sécurisé des paramètres via JSON + process.argv
        params_json = json.dumps(params or {}, ensure_ascii=False)
        full_code = f"""
import {{ SQL }} from 'bun';
const db = new SQL('{db_url}');
const params = JSON.parse(process.argv[2] || '{{}}');

try {{
  {ts_code}
}} catch (e) {{
  console.error(JSON.stringify({{ error: e.message }}));
}} finally {{
  await db.close();
}}
"""
        try:
            res = subprocess.run(
                ["bun", "-e", full_code, params_json],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            output = res.stdout.strip() or res.stderr.strip()
            if res.returncode != 0 and not output:
                return f"⚠️ Erreur Bun (code {res.returncode}) : {res.stderr.strip()}"
            return output
        except subprocess.TimeoutExpired:
            return "❌ Erreur : Timeout Bun (15s dépassé)."
        except Exception as e:
            return f"❌ Erreur d'exécution Bun : {str(e)}"

    def execute(self, uin: str) -> str:
        """Parse la commande utilisateur et route vers la bonne action CRM."""
        uin_lower = uin.lower().strip()

        # ─── STATS ───
        if any(k in uin_lower for k in ["stats", "statistiques", "/crm", "crm:"]):
            return self.get_stats()

        # ─── CRÉER CONTACT / PROSPECT ───
        if any(k in uin_lower for k in ["ajoute prospect", "créer prospect", "creer prospect", "créer contact", "creer contact"]):
            # Extraction naive du nom (tout après la commande)
            name = uin.split(" ", 2)[-1].strip() if len(uin.split()) > 1 else "Nouveau Prospect"
            return self.create_contact(name)

        # ─── CRÉER DEAL ───
        if any(k in uin_lower for k in ["créer deal", "creer deal", "nouveau deal"]):
            title = uin.split(" ", 2)[-1].strip() if len(uin.split()) > 1 else "Nouveau Deal"
            return self.create_deal(title)

        # ─── CRÉER TÂCHE ───
        if any(k in uin_lower for k in ["créer tâche", "creer tache", "nouvelle tâche"]):
            title = uin.split(" ", 2)[-1].strip() if len(uin.split()) > 1 else "Nouvelle Tâche"
            return self.create_task(title)

        # ─── RECHERCHE CONTACT ───
        if any(k in uin_lower for k in ["recherche", "cherche contact"]):
            query = uin.split(" ", 1)[-1].strip() if len(uin.split()) > 1 else ""
            return self.search_contact(query)

        # ─── MODIFIER CONTACT ───
        if any(k in uin_lower for k in ["modifie contact", "maj contact"]):
            # Format attendu : "modifie contact Karim email@tel"
            parts = uin.split()
            name = parts[2] if len(parts) > 2 else ""
            return self.update_contact(name)

        # Fallback
        return self.get_stats()

    def execute_payload(self, action: str, params: dict) -> str:
        """Appelé par l'agent Python avec un JSON d'action structuré."""
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

        return f"Action CRM '{action}' non supportée."

    def get_stats(self) -> str:
        ts = """
const contacts = await db\`SELECT count(*)::int as c FROM "contact"\`;
const deals = await db\`SELECT count(*)::int as c FROM "deal"\`;
const companies = await db\`SELECT count(*)::int as c FROM "company"\`;
console.log(JSON.stringify({
  status: 'ok',
  contacts: contacts[0]?.c || 0,
  deals: deals[0]?.c || 0,
  companies: companies[0]?.c || 0
}));
"""
        result = self._run_bun_script(ts)
        return f"📊 Statistiques Neon : {result}"

    def create_contact(self, name: str, email: str = "", phone: str = "") -> str:
        ts = """
const {{ randomUUID }} = require('crypto');
const id = randomUUID();
const now = new Date().toISOString();
const inserted = await db\`
  INSERT INTO "contact" ("id", "firstName", "email", "phone", "createdAt", "updatedAt", "source")
  VALUES (${id}, ${params.name}, ${params.email || null}, ${params.phone || null}, ${now}, ${now}, 'MANUAL')
  RETURNING *
\`;
console.log(JSON.stringify({ status: 'created', entity: 'contact', data: inserted[0] }));
"""
        result = self._run_bun_script(ts, {"name": name, "email": email, "phone": phone})
        if "error" not in result.lower():
            save_to_memory(f"Création d'un prospect/contact nommé {name}", f"Email: {email}, Tel: {phone}. {result}")
        return f"✅ Contact créé dans Neon : {result}"

    def create_deal(self, title: str, amount: float = 0) -> str:
        ts = """
const {{ randomUUID }} = require('crypto');
const now = new Date().toISOString();

let companyRes = await db\`SELECT id FROM "company" LIMIT 1\`;
let compId = companyRes.length > 0 ? companyRes[0].id : null;
if (!compId) {{
  compId = randomUUID();
  await db\`INSERT INTO "company" ("id", "name", "createdAt", "updatedAt") VALUES (${{compId}}, 'Entreprise Principale', ${{now}}, ${{now}})\`;
}}

let userRes = await db\`SELECT id FROM "user" LIMIT 1\`;
let ownerId = userRes.length > 0 ? userRes[0].id : null;
if (!ownerId) {{
  ownerId = randomUUID();
  try {{ await db\`INSERT INTO "user" ("id", "email", "name", "createdAt", "updatedAt") VALUES (${{ownerId}}, 'agent@kimi.local', 'Agent Kimi', ${{now}}, ${{now}})\`; }}
  catch (e) {{ await db\`INSERT INTO "user" ("id", "email") VALUES (${{ownerId}}, 'agent@kimi.local')\`; }}
}}

const dealId = randomUUID();
const inserted = await db\`
  INSERT INTO "deal" ("id", "name", "amount", "companyId", "ownerId", "createdAt", "updatedAt", "stage")
  VALUES (${{dealId}}, ${{params.title}}, ${{params.amount}}, ${{compId}}, ${{ownerId}}, ${{now}}, ${{now}}, 'DEMO_BOOKED')
  RETURNING *
\`;
console.log(JSON.stringify({{ status: 'created', entity: 'deal', data: inserted[0] }}));
"""
        result = self._run_bun_script(ts, {"title": title, "amount": amount})
        if "error" not in result.lower():
            save_to_memory(f"Création d'un deal : {title}", f"Montant: {amount}. {result}")
        return f"💼 Deal créé dans Neon : {result}"

    def create_task(self, title: str) -> str:
        ts = """
const {{ randomUUID }} = require('crypto');
const cols = await db\`SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = 'agentTask'\`;
const colNames = cols.map(c => c.column_name);

const insertObj = {{ id: randomUUID() }};
const now = new Date().toISOString();
const tomorrow = new Date(Date.now() + 86400000).toISOString();

if (colNames.includes('createdAt')) insertObj['createdAt'] = now;
if (colNames.includes('updatedAt')) insertObj['updatedAt'] = now;
if (colNames.includes('dueAt')) insertObj['dueAt'] = tomorrow;
if (colNames.includes('dueDate')) insertObj['dueDate'] = tomorrow;
if (colNames.includes('name')) insertObj['name'] = params.title;
else if (colNames.includes('title')) insertObj['title'] = params.title;
else if (colNames.includes('description')) insertObj['description'] = params.title;
else if (colNames.includes('prompt')) insertObj['prompt'] = params.title;
if (colNames.includes('reason')) insertObj['reason'] = 'Créé via Agent';

if (colNames.includes('kind')) {{
  try {{
    const kindEnum = await db\`SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = (SELECT udt_name FROM information_schema.columns WHERE table_name = 'agentTask' AND column_name = 'kind') LIMIT 1\`;
    insertObj['kind'] = kindEnum.length > 0 ? kindEnum[0].enumlabel : 'TODO';
  }} catch(e) {{ insertObj['kind'] = 'TODO'; }}
}}

if (colNames.includes('status')) {{
  try {{
    const statusEnum = await db\`SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = (SELECT udt_name FROM information_schema.columns WHERE table_name = 'agentTask' AND column_name = 'status') LIMIT 1\`;
    insertObj['status'] = statusEnum.length > 0 ? statusEnum[0].enumlabel : 'PENDING';
  }} catch(e) {{ insertObj['status'] = 'PENDING'; }}
}}

if (colNames.includes('ownerId') || colNames.includes('userId')) {{
  let userRes = await db\`SELECT id FROM "user" LIMIT 1\`;
  if (userRes.length > 0) {{
    if (colNames.includes('ownerId')) insertObj['ownerId'] = userRes[0].id;
    if (colNames.includes('userId')) insertObj['userId'] = userRes[0].id;
  }}
}}

const keys = Object.keys(insertObj);
const colsStr = keys.map(k => \`"\${{k}}"\`).join(', ');
const valsStr = keys.map(k => typeof insertObj[k] === 'string' ? \`'\${{insertObj[k]}}'\` : insertObj[k]).join(', ');

const inserted = await db.unsafe(\`INSERT INTO "agentTask" (\${{colsStr}}) VALUES (\${{valsStr}}) RETURNING *\`);
console.log(JSON.stringify({{ status: 'created', entity: 'task', data: inserted[0] }}));
"""
        result = self._run_bun_script(ts, {"title": title})
        if "error" not in result.lower():
            save_to_memory(f"Création d'une tâche CRM : {title}", f"Résultat: {result}")
        return f"📝 Tâche créée dans Neon : {result}"

    def search_contact(self, query: str) -> str:
        ts = """
const results = await db\`
  SELECT id, "firstName", "lastName", email, phone, "createdAt"
  FROM "contact"
  WHERE "firstName" ILIKE \${'%' + params.query + '%'}
     OR "lastName" ILIKE \${'%' + params.query + '%'}
     OR email ILIKE \${'%' + params.query + '%'}
  LIMIT 5
\`;
console.log(JSON.stringify({ status: 'ok', count: results.length, contacts: results }));
"""
        result = self._run_bun_script(ts, {"query": query})
        return f