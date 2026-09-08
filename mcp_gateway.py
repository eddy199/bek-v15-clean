# ==============================================================================
# mcp_gateway.py — PASSERELLE MODEL CONTEXT PROTOCOL (MCP) (BEK-v15.3)
# ==============================================================================

import logging
from typing import Dict, Any, Callable

logger = logging.getLogger("MCPGateway")

class MCPGateway:
    """
    Gère l'interopérabilité des outils dynamiques via des schémas normalisés MCP,
    permettant une transmission granulaire du contexte aux sous-agents.
    """
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        logger.info("✨ [MCPGateway] Passerelle MCP initialisée.")

    def register_mcp_tool(self, name: str, description: str, parameters_schema: dict, handler: Callable):
        """Enregistre un outil compatible MCP avec son schéma normalisé."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters_schema": parameters_schema,
            "handler": handler
        }
        logger.info(f"🔌 [MCPGateway] Outil MCP enregistré : [{name}]")

    def get_mcp_manifests(self) -> list:
        """Renvoie la liste des manifestes d'outils pour allocation contextuelle ciblée."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters_schema"]
            }
            for tool in self.tools.values()
        ]

    def execute_tool(self, name: str, arguments: dict) -> Any:
        """Exécute un outil via son protocole MCP."""
        if name not in self.tools:
            return {"status": "error", "message": f"Outil MCP non trouvé : {name}"}
        try:
            return self.tools[name]["handler"](**arguments)
        except Exception as e:
            logger.error(f"❌ [MCPGateway] Erreur exécution outil MCP {name} : {e}")
            return {"status": "error", "message": str(e)}

mcp_gateway = MCPGateway()

if __name__ == "__main__":
    print("--- TEST UNITAIRE MCP GATEWAY BEK-v15.3 ---")
    mcp_gateway.register_mcp_tool(
        name="ping_test",
        description="Outil de test MCP",
        parameters_schema={"message": "str"},
        handler=lambda message: f"Pong: {message}"
    )
    print("Manifestes:", mcp_gateway.get_mcp_manifests())
    print("Exécution:", mcp_gateway.execute_tool("ping_test", {"message": "Hello BEK"}))