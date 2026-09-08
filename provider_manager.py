"""
BEK-v15.3 HYBRID - Provider Manager Multi-LLM & Fallback Engine
--------------------------------------------------------------
Gestionnaire découplé des fournisseurs d'intelligence artificielle :
- B.ai, Groq, NVIDIA NIM, Google Gemini, OpenRouter
- Résolution dynamique des clés API
- Cascade de fallback automatique en cas d'erreur
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests

logger = logging.getLogger("bek.provider_manager")

WORKSPACE_DIR = Path(__file__).resolve().parent


class ProviderManager:
    """
    Gestionnaire centralisé et résilient des requêtes LLM.
    """

    PROVIDER_MODELS = {
        "b_ai": [
            "glm-5.3-flash",
            "qwen3.8-flash",
            "mimo-v2.5",
            "hy3",
        ],
        "groq": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
        ],
        "nvidia": [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.2-11b-vision-instruct",
            "meta/llama-3.2-90b-vision-instruct",
            "nvidia/llama-3.3-nemotron-super-49b-v1",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia/nemotron-nano-12b-v2-vl",
            "nvidia/nvidia-nemotron-nano-9b-v2",
            "openai/gpt-oss-120b",
            "google/gemma-4-31b-it",
        ],
        "gemini": [
            "gemini-3.6-flash",
            "gemini-1.5-pro-preview",
        ],
        "openrouter": [
            "openrouter/auto",
            "openai/gpt-oss-120b",
            "anthropic/claude-4-sonnet",
        ],
    }

    FALLBACK_ORDER = ["b_ai", "groq", "nvidia", "openrouter", "gemini"]

    def __init__(self) -> None:
        self.env_cache: Dict[str, str] = {}
        self._load_env_cache()

    def _load_env_cache(self) -> None:
        for filename in ("env.txt", ".env"):
            path = WORKSPACE_DIR / filename
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8-sig", errors="ignore") as fh:
                    for raw_line in fh:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or line.startswith("="):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            self.env_cache[k.strip()] = v.strip().strip("\"'")
            except Exception as exc:
                logger.warning("Erreur lecture %s : %s", filename, exc)

    def get_api_key(self, key_name: str) -> str:
        val = os.environ.get(key_name, "")
        if val:
            return val.strip("\"' \r\n")
        val = self.env_cache.get(key_name, "")
        if val:
            return val.strip("\"' \r\n")
        self._load_env_cache()
        return self.env_cache.get(key_name, "").strip("\"' \r\n")

    def resolve_provider_endpoint(
        self, provider: str, model: str
    ) -> Tuple[str, str, str]:
        p = provider.lower().strip()

        if p in ["b.ai", "b_ai", "bai"]:
            key = self.get_api_key("B_AI_API_KEY")
            return "b_ai", key, "https://api.b.ai/v1/chat/completions"

        use_headroom = (
            os.environ.get("USE_HEADROOM", self.env_cache.get("USE_HEADROOM", "false"))
            .lower()
            .strip()
            == "true"
        )
        headroom_port = os.environ.get(
            "HEADROOM_PORT", self.env_cache.get("HEADROOM_PORT", "8787")
        )

        if use_headroom:
            if p == "nvidia":
                model_key = self.get_api_key(model)
                key = model_key or self.get_api_key("NVIDIA_API_KEY")
            elif p == "gemini":
                key = self.get_api_key("GEMINI_API_KEY")
            elif p == "openrouter":
                key = self.get_api_key("OPENROUTER_API_KEY")
            else:
                key = self.get_api_key("GROQ_API_KEY")

            return p, key, f"http://localhost:{headroom_port}/v1/chat/completions"

        if p == "nvidia":
            model_key = self.get_api_key(model)
            key = model_key or self.get_api_key("NVIDIA_API_KEY")
            return "nvidia", key, "https://integrate.api.nvidia.com/v1/chat/completions"

        elif p == "gemini":
            key = self.get_api_key("GEMINI_API_KEY")
            return "gemini", key, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

        elif p == "openrouter":
            key = self.get_api_key("OPENROUTER_API_KEY")
            return "openrouter", key, "https://openrouter.ai/api/v1/chat/completions"

        elif p in ["b.ai", "b_ai", "bai"]:
            key = self.get_api_key("B_AI_API_KEY")
            return "b_ai", key, "https://api.b.ai/v1/chat/completions"

        else:
            key = self.get_api_key("GROQ_API_KEY")
            return "groq", key, "https://api.groq.com/openai/v1/chat/completions"

    def format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        formatted = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(item["text"])
                content = " ".join(parts)
            if isinstance(content, str) and content.strip():
                formatted.append({"role": role, "content": content})
        return formatted

    def execute_chat_stream(
        self,
        messages: List[Dict[str, Any]],
        provider: str = "b_ai",
        model: str = "glm-5.3-flash",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        top_p: float = 0.9,
    ) -> Generator[Dict[str, Any], None, None]:
        clean_msgs = self.format_messages(messages)
        if not clean_msgs:
            yield {"error": "Aucun message valide à envoyer."}
            return

        attempt_providers = [provider] + [p for p in self.FALLBACK_ORDER if p != provider]
        last_error_message = ""

        for current_prov in attempt_providers:
            available_models = self.PROVIDER_MODELS.get(current_prov, [])
            current_model = model if (current_prov == provider or model in available_models) else (available_models[0] if available_models else model)
            resolved_p, api_key, api_url = self.resolve_provider_endpoint(current_prov, current_model)

            if not api_key:
                logger.debug("Provider %s ignoré : clé API absente.", resolved_p)
                continue

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "text/event-stream; charset=utf-8",
                "User-Agent": "BEK-v15.2-Agent",
            }

            payload = {
                "model": current_model,
                "messages": clean_msgs,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stream": True,
            }

            try:
                with requests.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    stream=True,
                    timeout=(15, 180),
                ) as resp:
                    resp.encoding = "utf-8"

                    if resp.status_code != 200:
                        err_text = resp.text[:500]
                        logger.warning("Échec provider %s (HTTP %s) : %s", resolved_p, resp.status_code, err_text)
                        last_error_message = f"HTTP {resp.status_code} ({resolved_p})"
                        continue

                    received_chunks = False
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        line = raw_line.strip()
                        if not line.startswith("data:"):
                            continue
                        if line in ("data: [DONE]", "data:[DONE]"):
                            break

                        try:
                            payload_json = json.loads(line[5:].strip())
                            choices = payload_json.get("choices", [{}])
                            if choices:
                                delta = choices[0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    received_chunks = True
                                    yield {
                                        "chunk": chunk,
                                        "provider": resolved_p,
                                        "model": current_model,
                                    }
                        except Exception:
                            continue

                    if received_chunks:
                        yield {"done": True, "provider": resolved_p, "model": current_model}
                        return

            except requests.Timeout:
                last_error_message = f"Timeout ({resolved_p})"
                continue
            except requests.RequestException as exc:
                last_error_message = f"Réseau ({resolved_p}): {str(exc)}"
                continue

        yield {"error": f"Tous les providers ont échoué. Dernière erreur : {last_error_message}"}


provider_manager = ProviderManager()