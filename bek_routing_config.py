# bek_routing_config.py
def get_routing_strategy(task_type: str) -> str:
    """
    Détermine la stratégie de routage légère pour l'agent BEK-v15.
    """
    if task_type == "code":
        return "groq"
    elif task_type == "vision":
        return "gemini"
    elif task_type == "complex":
        return "nvidia"
    return "groq"