# python_bridge.py
import asyncio
import concurrent.futures
import json
import os
import sys
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("python_bridge")

async def call_python_tool_async(tool_name: str, args: dict):
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python_analyzer_mcp.py")
    server_params = StdioServerParameters(command=sys.executable, args=[server_path], env={**os.environ})
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                if result.content and len(result.content) > 0:
                    return result.content[0].text
                return json.dumps({"status": "error", "message": "Réponse vide"})
    except Exception as e:
        logger.error(f"Erreur pont Python: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def sync_call_python_tool(tool_name: str, args: dict):
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, call_python_tool_async(tool_name, args))
            return future.result(timeout=120)
    except RuntimeError:
        return asyncio.run(call_python_tool_async(tool_name, args))