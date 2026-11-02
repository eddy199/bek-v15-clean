# rea_agents_bridge.py
import asyncio
import concurrent.futures
import json
import os
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("rea_agents_bridge")

# ★ Chemin local (fallback npx si absent)
REA_LOCAL_PATH = r"F:\rea-main"
REA_LOCAL_ENTRY = os.path.join(REA_LOCAL_PATH, "dist", "mcp.js")  # adapte selon package.json
if not os.path.exists(REA_LOCAL_ENTRY):
    REA_LOCAL_ENTRY = os.path.join(REA_LOCAL_PATH, "server.js")

if os.path.exists(REA_LOCAL_ENTRY):
    REA_CMD = "node"
    REA_ARGS = [REA_LOCAL_ENTRY, "mcp"]
else:
    REA_CMD = "npx"
    REA_ARGS = ["-y", "rea-agents", "mcp"]

# ★ Timeout configurable — augmente si tu analyses de gros dossiers
REA_TIMEOUT_SEC = int(os.getenv("REA_TIMEOUT_SEC", "1800"))  # 30 min par défaut

async def list_rea_agents_tools():
    server_params = StdioServerParameters(command=REA_CMD, args=REA_ARGS, env={**os.environ})
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()

async def call_rea_agents_tool(tool_name: str, args: dict):
    server_params = StdioServerParameters(command=REA_CMD, args=REA_ARGS, env={**os.environ})
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info(f"[REA] Appel {tool_name} args={args} (timeout={REA_TIMEOUT_SEC}s)")
                # ★ Timeout explicite sur l'appel MCP
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=args),
                    timeout=REA_TIMEOUT_SEC,
                )
                if result.content and len(result.content) > 0:
                    return result.content[0].text
                return json.dumps({"status": "error", "message": "Réponse MCP vide."})
    except asyncio.TimeoutError:
        msg = f"Timeout {REA_TIMEOUT_SEC}s dépassé pour {tool_name} (cible trop grosse ou REA bloqué)."
        logger.error("[REA] %s", msg)
        return json.dumps({"status": "error", "message": msg})
    except Exception as e:
        # ★ Capture les crashs silencieux (OOM kill → e est souvent vide)
        err = str(e) or repr(e) or "crash inconnu (probable OOM Node.js)"
        logger.error(f"[REA] Erreur {tool_name}: {err}")
        return json.dumps({"status": "error", "message": err})

def sync_call_rea_agents_tool(tool_name: str, args: dict):
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, call_rea_agents_tool(tool_name, args))
            return future.result(timeout=REA_TIMEOUT_SEC + 30)  # marge
    except RuntimeError:
        return asyncio.run(call_rea_agents_tool(tool_name, args))

if __name__ == "__main__":
    print("🚀 Test de connexion au serveur MCP REA...")
    try:
        tools = asyncio.run(list_rea_agents_tools())
        print(f"✅ {len(tools.tools)} outils disponibles :")
        for t in tools.tools:
            print(f"  - {t.name}: {(t.description or '')[:80]}")
    except Exception as e:
        print(f"❌ Erreur critique : {e}")