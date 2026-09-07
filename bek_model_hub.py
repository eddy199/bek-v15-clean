# bek_model_hub.py
import os

BEK_HUB_CONSTANTS = {
    "default_provider": "groq",
    "fallback_chain": ["groq", "nvidia", "openrouter", "gemini"],
    "max_tokens_default": 1500,
    "temperature_default": 0.7
}

def get_hub_constants(key: str, default=None):
    return BEK_HUB_CONSTANTS.get(key, default)