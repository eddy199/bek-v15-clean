"""
BEK-v15.3 HYBRID - Provider Manager Multi-LLM & Fallback Engine
--------------------------------------------------------------
Gestionnaire universel des 14 fournisseurs d'intelligence artificielle :
- Moonshot Kimi AI (K2.6 → K3, Swarm, Instant, Code), B.ai, Kilo Code, OVHcloud, LLM7.io, Groq, NVIDIA NIM, Google Gemini,
  OpenRouter, Mistral, Cohere, Aion Labs, Zhipu AI, SiliconFlow.
- Support des clés NVIDIA dédiées par modèle depuis env.txt / .env.
- Fallback automatique vers les fournisseurs gratuits en cas de panne de quota.
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
    # ─── MODÈLES PAR FOURNISSEUR ─────────────────────────────────────────────
    PROVIDER_MODELS: Dict[str, List[str]] = {
        # 1. Moonshot Kimi AI (Clé API) — K2.6 → K3, Swarm, Instant, Code
        "kimi": [
            "kimi-k3",
            "kimi-k3-swarm",
            "kimi-k3-instant",
            "kimi-k2.7-code",
            "kimi-k2.6",
            "kimi-k2-0905",
            "moonshot-v1-128k",
            "moonshot-v1-32k",
            "moonshot-v1-8k",
        ],
        # 2. B.ai (Clé API)
        "b_ai": [
            "glm-5.3-flash",
            "qwen3.8-flash",
            "mimo-v2.5",
            "hy3",
        ],
        # 2. Kilo Code (Gratuit / Anonyme)
        "kilo_anonymous": [
            "kilo-nemotron-3-ultra-550b",
            "kilo-step-3.7-flash",
            "kilo-nemotron-3-super-120b",
            "kilo-nemotron-3-nano-omni",
            "kilo-laguna-s",
            "kilo-laguna-xs",
            "kilo-north-mini-code",
            "kilo-openrouter-free",
            "kilo-hy3",
            "kilo-nemotron-lightning",
            "kilo-lfm-2.5",
        ],
        # 3. OVHcloud (Gratuit / Anonyme)
        "ovh_anonymous": [
            "ovh-qwen-3.5-397b",
            "ovh-gpt-oss-120b",
            "ovh-gpt-oss-20b",
            "ovh-llama-3.3-70b",
            "ovh-qwen-3.6-27b",
            "ovh-qwen-3.5-9b",
            "ovh-qwen-3-32b",
            "ovh-qwen-coder-30b",
            "ovh-qwen-vl-72b",
            "ovh-mistral-small-3.2",
            "ovh-mistral-nemo",
            "ovh-mistral-7b",
        ],
        # 4. LLM7.io (Gratuit / Anonyme)
        "llm7_anonymous": [
            "llm7-gpt-oss-20b",
            "llm7-mistral-nemo",
            "llm7-minimax-m2.7",
        ],
        # 5. Groq (Clé API)
        "groq": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ],
        # 6. NVIDIA NIM (Clés spécifiques par modèle ou clé générale)
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
            "openai/gpt-oss-20b",
            "mistralai/mistral-nemotron",
            "mistralai/mistral-medium-3.5-128b",
            "google/gemma-4-31b-it",
            "nvidia/ising-calibration-1.5-31b",
        ],
        # 7. Google Gemini (Mise à jour via capture d'écran)
        "gemini": [
            "gemini-3.6-flash",
            "gemini-1.5-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
            "gemini-3-pro-image",
            "gemini-3.5-live-translate-preview",
            "gemini-3.1-flash-live-preview",
            "gemini-3.1-flash-tts-preview",
            "gemini-2.5-flash-image",
            "gemini-2.5-flash-native-audio-preview-12-2025",
            "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts",
            "veo-3.1-gene-prev",
            "veo-3.1-lite-gene-prev",
            "gemini-omni-flash",
            "lyria-3-pro-preview",
            "lyria-3-clip-preview",
            "lyria-realtime-preview",
        ],
        # 8. OpenRouter (Mise à jour via capture d'écran)
        "openrouter": [
            "auto",
            "gpt-oss-120b",
            "claude-4-sonnet",
            "dots3-note-preview",
            "lfm2.5-2.6b",
            "nemotron-3.5-lightning",
            "laguna-s-2.1",
            "laguna-xs-2.1",
            "free-models-router",
        ],
        # 9. Mistral AI (Clé API)
        "mistral": [
            "mistral-medium-3.5",
            "mistral-small-4",
            "mistral-large-3",
            "ministral-3-8b",
            "codestral",
            "ministral-3-3b",
            "ministral-3-14b",
        ],
        # 10. Cohere (Clé API)
        "cohere": [
            "cohere-command-a-plus",
            "cohere-command-a",
            "cohere-command-r-plus",
            "cohere-command-r",
            "cohere-command-r7b",
            "cohere-aya-expanse-32b",
        ],
        # 11. Aion Labs (Clé API)
        "aionlabs": [
            "aion-2.0",
            "aion-rp-llama-3.1-8b",
            "aion-3.0",
            "aion-3.0-mini",
        ],
        # 12. Zhipu AI (Clé API)
        "zhipu": [
            "glm-4.7-flash",
            "glm-4.5-flash",
            "glm-4.6v-flash",
        ],
        # 13. SiliconFlow (Clé API)
        "siliconflow": [
            "siliconflow-qwen3-8b",
        ],
    }

    # Ordre de fallback avec priorité aux fournisseurs actifs puis aux routes gratuites
    FALLBACK_ORDER: List[str] = [
        "b_ai",
        "groq",
        "nvidia",
        "gemini",
        "kimi",
        "openrouter",
        "kilo_anonymous",
        "ovh_anonymous",
        "llm7_anonymous",
        "mistral",
        "cohere",
        "aionlabs",
        "zhipu",
        "siliconflow",
    ]

    def __init__(self) -> None:
        self.env_cache: Dict[str, str] = {}
        self._load_env_cache()

    def _load_env_cache(self) -> None:
        """Charge toutes les variables depuis env.txt et .env avec nettoyage des guillemets."""
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
                            self.env_cache[k.strip()] = v.strip().strip("\"' \r\n")
            except Exception as exc:
                logger.warning("Erreur lecture %s : %s", filename, exc)

    def get_api_key(self, key_name: str) -> str:
        """Récupère une clé API depuis l'environnement système ou le cache local."""
        val = os.environ.get(key_name, "")
        if val:
            return val.strip("\"' \r\n")
        val = self.env_cache.get(key_name, "")
        if val:
            return val.strip("\"' \r\n")
        self._load_env_cache()
        return self.env_cache.get(key_name, "").strip("\"' \r\n")

    def is_provider_available(self, provider: str) -> bool:
        """Indique si un provider est opérationnel (anonyme ou clé API valide présente)."""
        p = provider.lower().strip()
        if "anonymous" in p:
            return True
        key_map = {
            "kimi": "MOONSHOT_API_KEY",
            "b_ai": "B_AI_API_KEY",
            "groq": "GROQ_API_KEY",
            "nvidia": "NVIDIA_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "COHERE_API_KEY",
            "aionlabs": "AIONLABS_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
        }
        key_name = key_map.get(p)
        if not key_name:
            return False
        if self.get_api_key(key_name):
            return True
        # Kimi accepte aussi KIMI_API_KEY en secours
        if p == "kimi":
            return bool(self.get_api_key("KIMI_API_KEY"))
        return False

    def resolve_provider_endpoint(
        self, provider: str, model: str
    ) -> Tuple[str, str, str]:
        """Résout l'identifiant normalisé, la clé API et l'URL de base."""
        p = provider.lower().strip()

        if p in ["b.ai", "b_ai", "bai"]:
            key = self.get_api_key("B_AI_API_KEY")
            return "b_ai", key, "https://api.b.ai/v1/chat/completions"

        elif p in ["kimi", "moonshot", "moonshot_ai"]:
            key = self.get_api_key("MOONSHOT_API_KEY") or self.get_api_key("KIMI_API_KEY")
            base_url = self.get_api_key("MOONSHOT_BASE_URL") or "https://api.moonshot.cn/v1"
            return "kimi", key, base_url.rstrip("/") + "/chat/completions"

        elif p == "kilo_anonymous":
            return "kilo_anonymous", "none", "https://api.kilo.ai/api/gateway/chat/completions"

        elif p == "ovh_anonymous":
            return "ovh_anonymous", "none", "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"

        elif p == "llm7_anonymous":
            return "llm7_anonymous", "none", "https://api.llm7.io/v1/chat/completions"

        elif p == "groq":
            key = self.get_api_key("GROQ_API_KEY")
            return "groq", key, "https://api.groq.com/openai/v1/chat/completions"

        elif p == "nvidia":
            # 1. Vérifie si une clé spécifique existe pour ce modèle exact dans env.txt
            model_key = self.get_api_key(model)
            key = model_key or self.get_api_key("NVIDIA_API_KEY")
            return "nvidia", key, "https://integrate.api.nvidia.com/v1/chat/completions"

        elif p == "gemini":
            key = self.get_api_key("GEMINI_API_KEY")
            return "gemini", key, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

        elif p == "openrouter":
            key = self.get_api_key("OPENROUTER_API_KEY")
            return "openrouter", key, "https://openrouter.ai/api/v1/chat/completions"

        elif p == "mistral":
            key = self.get_api_key("MISTRAL_API_KEY")
            return "mistral", key, "https://api.mistral.ai/v1/chat/completions"

        elif p == "cohere":
            key = self.get_api_key("COHERE_API_KEY")
            return "cohere", key, "https://api.cohere.com/v2/chat/completions"

        elif p == "aionlabs":
            key = self.get_api_key("AIONLABS_API_KEY")
            return "aionlabs", key, "https://api.aionlabs.ai/v1/chat/completions"

        elif p == "zhipu":
            key = self.get_api_key("ZHIPU_API_KEY")
            return "zhipu", key, "https://open.bigmodel.cn/api/paas/v4/chat/completions"

        elif p == "siliconflow":
            key = self.get_api_key("SILICONFLOW_API_KEY")
            return "siliconflow", key, "https://api.siliconflow.cn/v1/chat/completions"

        else:
            key = self.get_api_key("GROQ_API_KEY")
            return "groq", key, "https://api.groq.com/openai/v1/chat/completions"

    def format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Nettoie et formate les messages au standard OpenAI."""
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
                    elif isinstance(item, str):
                        parts.append(item)
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
        max_tokens: int = 4096,
        top_p: float = 0.9,
    ) -> Generator[Dict[str, Any], None, None]:
        """Exécute un streaming SSE avec bascule automatique sur les alternatives si échec."""
        clean_msgs = self.format_messages(messages)
        if not clean_msgs:
            yield {"error": "Aucun message valide à envoyer."}
            return

        total_chars = sum(len(m.get("content", "")) for m in clean_msgs)

        # Protection TPM Groq : déviation vers B.ai si la charge textuelle dépasse le seuil
        selected_provider = provider
        if provider == "groq" and total_chars > 16000:
            logger.warning("[TPM Guard] Requête volumineuse (%d chars), routage vers B.ai.", total_chars)
            selected_provider = "b_ai"

        # Construction de l'ordre d'essai en démarrant par le choix de l'utilisateur
        attempt_providers = [selected_provider] + [p for p in self.FALLBACK_ORDER if p != selected_provider]
        last_error_message = ""

        for current_prov in attempt_providers:
            available_models = self.PROVIDER_MODELS.get(current_prov, [])
            current_model = model if (current_prov == selected_provider or model in available_models) else (available_models[0] if available_models else model)
            resolved_p, api_key, api_url = self.resolve_provider_endpoint(current_prov, current_model)

            # Ignore les providers payants dont la clé API est vide
            if not api_key and "anonymous" not in resolved_p:
                continue

            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "text/event-stream; charset=utf-8",
                "User-Agent": "BEK-v15.3-Agent",
            }
            if api_key != "none":
                headers["Authorization"] = f"Bearer {api_key}"

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
                    timeout=(10, 120),
                ) as resp:
                    resp.encoding = "utf-8"

                    if resp.status_code != 200:
                        err_text = resp.text[:300]
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