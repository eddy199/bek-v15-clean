# plugins/plugin_crm.py

- save_to_memory · function · L16-L16 — def save_to_memory(q, r)
- CRMPlugin · class · L18-L302 — class CRMPlugin
- __init__ · method · L25-L29 — def __init__(self)
- _get_database_url · method · L31-L47 — def _get_database_url(self) -> str
- _run_sql_script · method · L49-L74 — def _run_sql_script(self, ts_code: str) -> str
- execute_payload · method · L76-L105 — def execute_payload(self, action: str, params: dict) -> str
- get_stats · method · L107-L126 — def get_stats(self) -> str
- create_contact · method · L128-L150 — def create_contact(self, name: str, email: str = "", phone: str = "") -> str
- create_deal · method · L152-L189 — def create_deal(self, title: str, amount: float = 0) -> str
- create_task · method · L191-L254 — def create_task(self, title: str) -> str
- search_contact · method · L256-L273 — def search_contact(self, query: str) -> str
- update_contact · method · L275-L299 — def update_contact(self, name: str, email: str = "", phone: str = "") -> str
- execute · method · L301-L302 — def execute(self, uin: str) -> str
- GET_AGENT_PLUGIN_CLASS · function · L304-L305 — def GET_AGENT_PLUGIN_CLASS()
