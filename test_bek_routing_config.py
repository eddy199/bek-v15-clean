# test_bek_routing_config.py
from bek_routing_config import get_routing_strategy

def test_routing_strategies():
    assert get_routing_strategy("code") == "groq"
    assert get_routing_strategy("vision") == "gemini"
    assert get_routing_strategy("complex") == "nvidia"
    assert get_routing_strategy("unknown") == "groq"