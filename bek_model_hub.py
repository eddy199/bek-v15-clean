# bek_model_hub.py
import os

BEK_HUB_CONSTANTS = {
    # CORRECTIF v19 : NVIDIA en premier (gratuit illimité, actif)
    "default_provider": "nvidia",
    "fallback_chain": ["nvidia", "groq", "gemini", "openrouter"],
    "max_tokens_default": 1500,
    "temperature_default": 0.7
}

def get_hub_constants(key: str, default=None):
    return BEK_HUB_CONSTANTS.get(key, default)