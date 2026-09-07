# test_bek_model_hub.py
from bek_model_hub import get_hub_constants

def test_model_hub_constants():
    assert get_hub_constants("default_provider") == "groq"
    assert "nvidia" in get_hub_constants("fallback_chain")
    assert get_hub_constants("max_tokens_default") == 1500