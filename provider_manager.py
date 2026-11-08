# ==============================================================================
# BEK-v19 HYBRID — Provider Manager — v21.4 (Modèles NVIDIA 2026 complets)
# ==============================================================================
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
_cur = WORKSPACE_DIR
for _ in range(6):
    if _cur.name == "workspacekimi":
        WORKSPACE_DIR = _cur
        break
    _cur = _cur.parent

BEK_APP_TITLE = "BEK Hybrid Agent v19"
BEK_APP_CREATOR = "BEKKARA Mohamed"

_DEFAULT_TOOL_CAPABLE_PROVIDERS = (
    "groq", "nvidia", "gemini", "openrouter",
    "kimi", "ollama_cloud", "mistral", "cohere",
    "huggingface", "b_ai", "beatapi",
    "local",
)

def _resolve_tool_capable_providers() -> Tuple[str, ...]:
    raw = os.getenv("BEK_TOOL_CAPABLE_PROVIDERS", "").strip()
    if not raw: return _DEFAULT_TOOL_CAPABLE_PROVIDERS
    providers = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
    return providers if providers else _DEFAULT_TOOL_CAPABLE_PROVIDERS

_FALLBACK_TOOL_MODEL = "openai/gpt-oss-20b"
_DEAD_MODEL_STATUS_CODES = {404, 410, 413}
_MAX_MODEL_ROTATION = 1

_FILE_MARKER_START = "--- CONTENU DES FICHIERS JOINTS ---"
_FILE_MARKER_END = "--- FIN DU CONTENU DES FICHIERS JOINTS ---"
_FILE_BLOCK_MARKER = "=== CONTENU DU FICHIER :"

_TPM_GUARD_THRESHOLD = 120_000
_TPM_MAX_SYSTEM_CHARS = 40_000
_TPM_MAX_LAST_USER_CHARS = 80_000

_ANALYSIS_BYPASS_MARKERS = (
    "--- CONTENU DES FICHIERS JOINTS ---",
    "=== CONTENU DU FICHIER :",
    "=== SYNTHÈSE PARTIELLE",
    "--- SYNTHÈSE PARTIELLE",
    "Fichiers joints (",
)

_CIRCUIT_BREAKER_THRESHOLD = 2
_CIRCUIT_BREAKER_COOLDOWN = 60.0


class ProviderManager:

    MODEL_ID_MAPPING: Dict[str, str] = {
        "veo-3.1-gene-prev":            "veo-3.1-generate-preview",
        "veo-3.1-lite-gene-prev":       "veo-3.1-lite-generate-preview",
        "veo-3.1-fast-gene-prev":       "veo-3.1-fast-generate-preview",
        "veo-3.1":                      "veo-3.1-generate-preview",
        "veo-3.1-lite":                 "veo-3.1-lite-generate-preview",
        "veo-3.1-fast":                 "veo-3.1-fast-generate-preview",
        "gemini-3.1-flash-image":       "gemini-3.1-flash-image-preview",
        "gemini-3.1-flash-lite-image":  "gemini-3.1-flash-lite-image-preview",
        "gemini-2.5-flash-image":       "gemini-2.5-flash-image",
    }

    AGNES_MODEL_MAPPING: Dict[str, str] = {
        "agnes-v2":            "agnes-video-v2.0",
        "agnes-v2.0":          "agnes-video-v2.0",
        "agnes-video-v2":      "agnes-video-v2.0",
        "agnes-video-v2.0":    "agnes-video-v2.0",
        "agnes-flash":         "agnes-video-2.5-flash",
        "agnes-v2.5-flash":    "agnes-video-2.5-flash",
        "agnes-video-flash":   "agnes-video-2.5-flash",
        "agnes-video-2.5-flash": "agnes-video-2.5-flash",
    }

    HF_IMAGE_MODELS: Dict[str, str] = {
        "hf-flux-schnell":  "black-forest-labs/FLUX.1-schnell",
        "hf-flux-dev":      "black-forest-labs/FLUX.1-dev",
        "hf-sdxl-turbo":    "stabilityai/sdxl-turbo",
        "hf-sd-3.5-large":  "stabilityai/stable-diffusion-3.5-large",
        "hf-sd-3.5-medium": "stabilityai/stable-diffusion-3.5-medium",
        "hf-sd-2.1":        "stabilityai/stable-diffusion-2-1",
        "hf-flux-3-image":  "black-forest-labs/FLUX.3-image",
    }

    VEO_SUPPORTED_DURATIONS: List[int] = [4, 6, 8]
    VEO_MAX_SINGLE_CLIP: int = 8
    VEO_MIN_CLIP: int = 4
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta"
    AGNES_DEFAULT_BASE_URL: str = "https://apihub.agnes-ai.com/v1"
    HF_INFERENCE_BASE: str = "https://router.huggingface.co/hf-inference/models"
    AGNES_V2_MAX_FRAMES: int = 441
    AGNES_V2_MIN_FRAMES: int = 81
    AGNES_V2_DEFAULT_FPS: int = 24
    AGNES_FLASH_MIN_SECONDS: int = 4
    AGNES_FLASH_MAX_SECONDS: int = 12

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v21.4 — PROVIDER_MODELS enrichi avec les 33 modèles NVIDIA 2026
    # ══════════════════════════════════════════════════════════════════════════
    PROVIDER_MODELS: Dict[str, List[str]] = {
        "groq": [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
            "qwen/qwen3.8-27b",
        ],
        "nvidia": [
            # ═══ 🥇 TIER 1 : LLM généralistes performants (chat + tools) ═══
            "moonshotai/kimi-k3.1-pro",                        # 1
            "mistralai/mistral-large-4",                       # 2
            "nvidia/nemotron-3-ultra-550b-a55b",               # 20
            "nvidia/nemotron-3.5-lightning-30b-a3b",           # 16
            "nvidia/nemotron-3.5-bolt-e4b",                    # 4
            "deepseek-ai/deepseek-v4.1-flash",                 # 13
            "z-ai/glm-5-3-flash",                              # 15
            "minimaxai/minimax-m3.1-flash",                    # 5
            "stepfun-ai/step-5-preview",                       # 9
            "meta/muse-glimmer-30b",                           # 17
            "openai/gpt-oss-20b",                              # 32

            # ═══ 🥈 TIER 2 : Multimodal / Vision ═══
            "nvidia/nemotron-3.5-super-vl-120b-a12b",          # 10
            "meta/llama-3.2-90b-vision-instruct",              # 33
            "nvidia/nemotron-3.5-parse",                       # 3
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",   # 24

            # ═══ 🥉 TIER 3 : Embeddings / Rerank ═══
            "nvidia/nemotron-3.5-embed-1b",                    # 6
            "nvidia/nemotron-3.5-rerank-8b",                   # 7

            # ═══ 🛡️ TIER 4 : Sécurité / Guardrails ═══
            "nvidia/nemotron-3.5-content-safety",              # 23
            "meta/llama-guard-4-12b",                          # 31
            "nvidia/llama-3.1-nemotron-safety-guard-8b-v3",    # 28

            # ═══ 🎯 TIER 5 : Spécialisés (hors chat direct) ═══
            "nvidia/riva-translate-4b-instruct-v2",            # 18 (traduction)
            "nvidia/ising-calibration-1.5-31b",                # 19 (calibration)
            "nvidia/magpie-tts-zeroshot",                      # 29 (TTS)
            "nvidia/background-noise-removal",                 # 30 (audio)
            "nvidia/nemotron-voicechat",                       # 26 (voice chat)
            "nvidia/streampetr",                               # 27 (perception 3D)
            "nvidia/3d-body-pose",                             # 12 (pose)
            "ipd/rfd4-proteina",                               # 11 (protéine)
            "nvidia/kumo-tabular",                             # 8  (tabulaire)
            "nvidia/kumo-relational",                          # 14 (relationnel)
            "nvidia/synthetic-video-detector",                 # 25 (détection vidéo)
            "nvidia/cosmos3-nano-reasoner",                    # 21
            "nvidia/cosmos3-nano",                             # 22

            # ═══ 📦 ANCIENS MODÈLES — CONSERVÉS pour compat ═══
            "nvidia/nemotron-3-super-120b-a12b",
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.2-11b-vision-instruct",
            "nvidia/llama-3.3-nemotron-super-49b-v1",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/nemotron-nano-12b-v2-vl",
            "nvidia/nvidia-nemotron-nano-9b-v2",
            "mistralai/mistral-medium-3.5-128b",
            "mistralai/mistral-nemotron",
            "qwen/qwen2.5-7b-instruct",
            "google/gemma-2-27b-it",
            "google/gemma-2-9b-it",
            "microsoft/phi-3-medium-4k-instruct",
            "microsoft/phi-3.5-vision-instruct",
            "google/paligemma",
            "nvidia/vila",
        ],
        "gemini": [
            "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
            "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro",
            "gemma-4-31b", "gemma-4-26b-a4b", "gemini-1.5-pro-preview", "gemini-3-flash-preview",
            "gemini-3.1-flash-lite", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image",
            "gemini-3-pro-image", "gemini-2.5-flash-image", "gemini-3.5-live-translate-preview",
            "gemini-3.1-flash-live-preview", "gemini-3.1-flash-tts-preview",
            "gemini-2.5-flash-native-audio-preview-12-2025", "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts", "gemini-omni-flash",
            "veo-3.1-gene-prev", "veo-3.1-lite-gene-prev", "veo-3.1-fast-gene-prev",
            "veo-3.1-generate-preview", "veo-3.1-lite-generate-preview", "veo-3.1-fast-generate-preview",
            "lyria-3-pro-preview", "lyria-3-clip-preview", "lyria-realtime-preview",
        ],
        "openrouter": [
            "meta/muse-spark-open", "meta/muse-wonder", "odyssey-3", "qwen3-omni-30b-a3b-instruct",
            "gpt-6", "intelligent-ui", "kolibri", "auto", "gpt-oss-120b", "claude-4-sonnet",
            "dots3-note-preview", "lfm2.5-2.6b", "nemotron-3.5-lightning", "laguna-s-2.1",
            "laguna-xs-2.1", "free-models-router",
        ],
        "mistral": [
            "mistral-large-4", "mistral-medium-3.5", "mistral-small-4", "mistral-large-3",
            "ministral-3-8b", "codestral", "ministral-3-3b", "ministral-3-14b",
        ],
        "cohere": [
            "cohere-command-a-plus", "cohere-command-a", "cohere-command-r-plus",
            "cohere-command-r", "cohere-command-r7b", "cohere-aya-expanse-32b",
        ],
        "aionlabs": ["aion-2.0", "aion-rp-llama-3.1-8b", "aion-3.0", "aion-3.0-mini"],
        "zhipu": ["glm-4.7-flash", "glm-4.5-flash", "glm-4.6v-flash"],
        "siliconflow": ["siliconflow-qwen3-8b"],
        "huggingface": [
            "Meta-Llama-3.1-8B-Instruct", "gemma-3-4b-it", "phi-4",
            "Qwen2.5-Coder-7B-Instruct", "Qwen2.5-7B-Instruct",
        ],
        "ollama_cloud": [
            "deepseek-v4-pro", "deepseek-v4-flash", "minimax-m3", "kimi-k3",
            "gpt-oss:120b", "gpt-oss:20b", "nemotron-3-ultra",
            "mistral-large-3:675b", "qwen3.5:397b",
        ],
        "kimi": [
            "kimi-k3", "kimi-k3-swarm", "kimi-k3-instant", "kimi-k2.7-code",
            "kimi-k2.6", "kimi-k2-0905", "moonshot-v1-128k",
            "moonshot-v1-32k", "moonshot-v1-8k",
        ],
        "aisa": ["qwen-flash", "qwen-mt-flash", "qwen-mt-lite"],
        "b_ai": ["gpt-5.2", "gpt-4o", "gpt-image-2"],
        "beatapi": [
            "deepseek-v4.1-flash-free", "deepseek-v4-flash-0731-free",
            "glm-5.3-free", "glm-5.3-flash-free", "gemini-3.8-flash-free",
            "gpt-5.2", "gpt-image-2",
        ],
        "agnes": ["agnes-v2.0", "agnes-v2.5-flash", "agnes-video-v2.0", "agnes-video-2.5-flash"],
        "local": ["qwen2.5-coder-3b", "qwen2.5-coder-7b", "phi3.5", "llama3.2-3b"],
    }

    # ★ Fallback étendu : NVIDIA + Groq + Gemini + OpenRouter + Mistral
    FALLBACK_ORDER: List[str] = ["nvidia", "groq", "gemini", "openrouter", "mistral"]

    PROVIDER_KEY_MAP: Dict[str, str] = {
        "kimi": "MOONSHOT_API_KEY", "aisa": "AISA_API_KEY", "b_ai": "B_AI_API_KEY",
        "beatapi": "BEATAPI_API_KEY", "groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY",
        "gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY", "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY", "aionlabs": "AIONLABS_API_KEY", "zhipu": "ZHIPU_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY", "huggingface": "HUGGINGFACE_API_KEY",
        "ollama_cloud": "OLLAMA_API_KEY", "agnes": "AGNES_API_KEY",
    }

    def __init__(self) -> None:
        self.env_cache: Dict[str, str] = {}
        self._models_cache: Dict[str, Any] = {}
        self._models_cache_ts: float = 0.0
        self._load_env_cache()
        self._cb_failures: Dict[str, int] = {}
        self._cb_cooldown: Dict[str, float] = {}

    def _load_env_cache(self) -> None:
        for filename in ("env.txt", ".env"):
            path = WORKSPACE_DIR / filename
            if not path.exists(): path = Path.cwd() / filename
            if not path.exists(): continue
            try:
                with path.open("r", encoding="utf-8-sig", errors="ignore") as fh:
                    for raw_line in fh:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or line.startswith("="): continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            self.env_cache[k.strip()] = v.strip().strip("\"' \r\n")
            except Exception as exc: logger.warning("Erreur lecture %s : %s", filename, exc)

    def get_api_key(self, key_name: str) -> str:
        val = os.environ.get(key_name, "")
        if val: return val.strip("\"' \r\n")
        val = self.env_cache.get(key_name, "")
        if val: return val.strip("\"' \r\n")
        self._load_env_cache()
        return self.env_cache.get(key_name, "").strip("\"' \r\n")

    def is_provider_available(self, provider: str) -> bool:
        p = provider.lower().strip()
        if p == "local":
            try:
                from local_provider import LocalLlamaProvider
                return LocalLlamaProvider.is_available()
            except Exception:
                return False
        if "anonymous" in p: return True
        key_name = self.PROVIDER_KEY_MAP.get(p)
        if not key_name: return False
        if self.get_api_key(key_name): return True
        if p == "kimi": return bool(self.get_api_key("KIMI_API_KEY"))
        return False

    def _cb_record_failure(self, provider: str) -> None:
        p = provider.lower()
        self._cb_failures[p] = self._cb_failures.get(p, 0) + 1
        if self._cb_failures[p] >= _CIRCUIT_BREAKER_THRESHOLD:
            self._cb_cooldown[p] = time.time() + _CIRCUIT_BREAKER_COOLDOWN
            logger.warning("[ProviderManager/CB] Circuit OUVERT pour %s (cooldown %.0fs)", p, _CIRCUIT_BREAKER_COOLDOWN)

    def _cb_record_success(self, provider: str) -> None:
        p = provider.lower()
        self._cb_failures[p] = 0
        self._cb_cooldown.pop(p, None)

    def _cb_is_open(self, provider: str) -> bool:
        p = provider.lower()
        if p in self._cb_cooldown:
            if time.time() < self._cb_cooldown[p]: return True
            else:
                self._cb_failures[p] = 0
                del self._cb_cooldown[p]
        return False

    def get_provider_health(self) -> Dict[str, Any]:
        return {
            "failures": dict(self._cb_failures),
            "cooldowns": {k: round(max(0, v - time.time()), 1) for k, v in self._cb_cooldown.items() if v > time.time()},
        }

    def resolve_provider_endpoint(self, provider: str, model: str) -> Tuple[str, str, str]:
        p = provider.lower().strip()
        if p == "local":
            return "local", "none", "in-process://llama-cpp"
        if p in ["b.ai", "b_ai", "bai"]: return "b_ai", self.get_api_key("B_AI_API_KEY"), "https://api.b.ai/v1/chat/completions"
        elif p in ["beatapi", "beatapi.io"]: return "beatapi", self.get_api_key("BEATAPI_API_KEY"), "https://api.beatapi.io/v1/chat/completions"
        elif p in ["kimi", "moonshot", "moonshot_ai"]: return "kimi", self.get_api_key("MOONSHOT_API_KEY") or self.get_api_key("KIMI_API_KEY"), (self.get_api_key("MOONSHOT_BASE_URL") or "https://api.moonshot.cn/v1").rstrip("/") + "/chat/completions"
        elif p == "aisa": return "aisa", self.get_api_key("AISA_API_KEY"), "https://api.aisa.one/v1/chat/completions"
        elif p == "groq": return "groq", self.get_api_key("GROQ_API_KEY"), "https://api.groq.com/openai/v1/chat/completions"
        elif p == "nvidia": return "nvidia", self.get_api_key(model) or self.get_api_key("NVIDIA_API_KEY"), "https://integrate.api.nvidia.com/v1/chat/completions"
        elif p == "gemini": return "gemini", self.get_api_key("GEMINI_API_KEY"), "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        elif p == "openrouter": return "openrouter", self.get_api_key("OPENROUTER_API_KEY"), "https://openrouter.ai/api/v1/chat/completions"
        elif p == "mistral": return "mistral", self.get_api_key("MISTRAL_API_KEY"), "https://api.mistral.ai/v1/chat/completions"
        elif p == "cohere": return "cohere", self.get_api_key("COHERE_API_KEY"), "https://api.cohere.com/v2/chat/completions"
        elif p == "aionlabs": return "aionlabs", self.get_api_key("AIONLABS_API_KEY"), "https://api.aionlabs.ai/v1/chat/completions"
        elif p == "zhipu": return "zhipu", self.get_api_key("ZHIPU_API_KEY"), "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        elif p == "siliconflow": return "siliconflow", self.get_api_key("SILICONFLOW_API_KEY"), "https://api.siliconflow.cn/v1/chat/completions"
        elif p == "huggingface": return "huggingface", self.get_api_key("HUGGINGFACE_API_KEY"), "https://router.huggingface.co/v1/chat/completions"
        elif p in ["ollama_cloud", "ollama"]: return "ollama_cloud", self.get_api_key("OLLAMA_API_KEY"), "https://ollama.com/v1/chat/completions"
        else: return "groq", self.get_api_key("GROQ_API_KEY"), "https://api.groq.com/openai/v1/chat/completions"

    def resolve_model_id(self, model_name: str) -> str:
        if not model_name: return model_name
        clean = model_name.replace("models/", "").strip()
        if clean in self.MODEL_ID_MAPPING: return self.MODEL_ID_MAPPING[clean]
        if clean.startswith("veo-") and "generate" in clean: return clean
        if clean.startswith("gemini-") and "image" in clean: return clean
        if clean.startswith("veo-") and clean.endswith("-gene-prev"): return clean.replace("-gene-prev", "-generate-preview")
        return clean

    def resolve_veo_model_id(self, model: str) -> str:
        if not model: return "veo-3.1-generate-preview"
        resolved = self.resolve_model_id(model)
        return resolved if resolved.startswith("veo-") else "veo-3.1-generate-preview"

    def resolve_agnes_model_id(self, model: str) -> str:
        if not model: return "agnes-video-v2.0"
        clean = model.replace("models/", "").strip()
        if clean in self.AGNES_MODEL_MAPPING: return self.AGNES_MODEL_MAPPING[clean]
        return clean if clean.startswith("agnes-video-") else "agnes-video-v2.0"

    def resolve_huggingface_image_model_id(self, model: str) -> str:
        if not model: return "black-forest-labs/FLUX.1-schnell"
        return self.HF_IMAGE_MODELS.get(model.replace("models/", "").strip(), model)

    def get_veo_endpoints(self, model: str) -> Dict[str, Any]:
        model_id = self.resolve_veo_model_id(model)
        api_key = self.get_api_key("GEMINI_API_KEY")
        return {"model_id": model_id, "predict_url": f"{self.GEMINI_API_BASE}/models/{model_id}:predictLongRunning", "operations_base": self.GEMINI_API_BASE, "api_key": api_key, "headers": {"Content-Type": "application/json", "x-goog-api-key": api_key}}

    def get_agnes_endpoints(self, model: str = "agnes-v2.0") -> Dict[str, Any]:
        model_id = self.resolve_agnes_model_id(model)
        api_key = self.get_api_key("AGNES_API_KEY")
        base_url = (self.get_api_key("AGNES_BASE_URL") or self.AGNES_DEFAULT_BASE_URL).rstrip("/")
        return {"model_id": model_id, "base_url": base_url, "create_url": f"{base_url}/videos", "status_url": f"{base_url}/videos", "api_key": api_key, "headers": {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, "is_v2": model_id == "agnes-video-v2.0", "max_frames": self.AGNES_V2_MAX_FRAMES, "min_frames": self.AGNES_V2_MIN_FRAMES, "default_fps": self.AGNES_V2_DEFAULT_FPS, "min_seconds": self.AGNES_FLASH_MIN_SECONDS, "max_seconds": self.AGNES_FLASH_MAX_SECONDS}

    def list_agnes_video_models(self) -> List[str]: return ["agnes-video-v2.0", "agnes-video-2.5-flash"]

    def get_huggingface_image_endpoints(self, model: str = "hf-flux-schnell") -> Dict[str, Any]:
        model_id = self.resolve_huggingface_image_model_id(model)
        api_key = self.get_api_key("HUGGINGFACE_API_KEY")
        return {"model_id": model_id, "predict_url": f"{self.HF_INFERENCE_BASE}/{model_id}", "api_key": api_key, "headers": {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}}

    def list_huggingface_image_models(self) -> List[str]: return ["hf-flux-schnell", "hf-sdxl-turbo", "hf-sd-3.5-large", "hf-sd-3.5-medium", "hf-sd-2.1", "hf-flux-3-image"]

    def detect_available_models(self, provider: str = "gemini", force_refresh: bool = False, cache_ttl: int = 3600) -> Dict[str, Any]:
        p = provider.lower().strip()
        now = time.time()
        cache_key = f"models_{p}"
        if not force_refresh and cache_key in self._models_cache and (now - self._models_cache_ts) < cache_ttl:
            cached = self._models_cache[cache_key]
            return {"provider": p, "source": "cache", "count": len(cached.get("models", [])), "models": cached.get("models", []), "raw": cached.get("raw", {})}
        if p == "gemini":
            api_key = self.get_api_key("GEMINI_API_KEY")
            if not api_key: return self._static_models_response(p)
            try:
                url = f"{self.GEMINI_API_BASE}/models?key={api_key}&pageSize=200"
                res = requests.get(url, timeout=30)
                if res.status_code != 200: return self._static_models_response(p)
                data = res.json()
                models: List[Dict[str, Any]] = []
                for m in data.get("models", []):
                    name = m.get("name", "").replace("models/", "")
                    if not name: continue
                    models.append({"id": name, "displayName": m.get("displayName", name), "description": m.get("description", ""), "inputTokenLimit": m.get("inputTokenLimit"), "outputTokenLimit": m.get("outputTokenLimit"), "supportedMethods": m.get("supportedGenerationMethods", [])})
                self._models_cache[cache_key] = {"models": models, "raw": data}
                self._models_cache_ts = now
                return {"provider": p, "source": "api", "count": len(models), "models": models, "raw": data}
            except requests.RequestException as e:
                logger.warning("[provider_manager] Erreur détection Gemini : %s", e)
                return self._static_models_response(p)
        return self._static_models_response(p)

    def _static_models_response(self, provider: str) -> Dict[str, Any]:
        static_list = self.PROVIDER_MODELS.get(provider, [])
        models = [{"id": m, "displayName": m, "supportedMethods": ["static"]} for m in static_list]
        return {"provider": provider, "source": "static", "count": len(models), "models": models, "raw": {}}

    def list_veo_models(self) -> List[str]: return ["veo-3.1-generate-preview", "veo-3.1-fast-generate-preview", "veo-3.1-lite-generate-preview"]
    def list_gemini_image_models(self) -> List[str]: return ["gemini-3.1-flash-image-preview", "gemini-3.1-flash-lite-image-preview", "gemini-2.5-flash-image"]

    def format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        formatted = []
        for m in messages:
            if not isinstance(m, dict): continue
            role = m.get("role", "user")
            if role not in ["system", "user", "assistant"]: role = "user"
            content = m.get("content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item: parts.append(item["text"])
                    elif isinstance(item, str): parts.append(item)
                content = " ".join(parts)
            if isinstance(content, str) and content.strip():
                formatted.append({"role": role, "content": content})
        return formatted

    @staticmethod
    def _has_attached_file_marker(content: str) -> bool:
        return isinstance(content, str) and (
            _FILE_MARKER_START in content or _FILE_BLOCK_MARKER in content
        )

    @staticmethod
    def _should_skip_tpm_guard(clean_msgs: List[Dict[str, str]]) -> bool:
        if not clean_msgs:
            return False
        for msg in clean_msgs:
            content = msg.get("content", "") or ""
            if any(marker in content for marker in _ANALYSIS_BYPASS_MARKERS):
                return True
            if len(content) > 50_000:
                return True
        return False

    @staticmethod
    def _smart_truncate_last_user(content: str, max_chars: int) -> str:
        if not isinstance(content, str) or len(content) <= max_chars: return content
        original_len = len(content)
        marker_pos = content.find(_FILE_MARKER_START)
        if marker_pos < 0:
            half = max_chars // 2
            return content[:half] + f"\n\n[...{original_len - max_chars} chars omis...]\n\n" + content[-half:]
        user_part = content[:marker_pos]
        file_part = content[marker_pos:]
        user_budget = min(2_000, len(user_part))
        file_budget = max_chars - user_budget
        if file_budget < 500: file_budget = max(500, max_chars - user_budget)
        user_truncated = user_part[:user_budget]
        file_truncated = file_part[:file_budget]
        omitted = original_len - len(user_truncated) - len(file_truncated)
        return user_truncated + file_truncated + f"\n\n[...{omitted} chars omis du fichier joint (TPM Guard)...]"

    def _apply_tpm_guard(self, clean_msgs: List[Dict[str, str]], total_chars: int) -> Tuple[List[Dict[str, str]], int]:
        if total_chars <= _TPM_GUARD_THRESHOLD:
            return clean_msgs, total_chars

        logger.warning(
            "[ProviderManager/TPM] ⚠️ Prompt %d chars > seuil %d — troncature en cours",
            total_chars, _TPM_GUARD_THRESHOLD,
        )

        system_msgs: List[Dict[str, str]] = []
        last_user_msg: Optional[Dict[str, str]] = None
        other_msgs: List[Dict[str, str]] = []
        for i, m in enumerate(clean_msgs):
            role = m.get("role", "")
            if role == "system": system_msgs.append(m)
            elif i == len(clean_msgs) - 1 and role == "user": last_user_msg = m
            else: other_msgs.append(m)
        for m in system_msgs:
            content = m.get("content", "")
            if isinstance(content, str) and len(content) > _TPM_MAX_SYSTEM_CHARS:
                original_len = len(content)
                m["content"] = content[:_TPM_MAX_SYSTEM_CHARS] + f"\n\n[...{original_len - _TPM_MAX_SYSTEM_CHARS} chars omis du system prompt (TPM Guard)...]"
        if last_user_msg is not None:
            content = last_user_msg.get("content", "")
            if isinstance(content, str) and len(content) > _TPM_MAX_LAST_USER_CHARS:
                before = len(content)
                last_user_msg["content"] = self._smart_truncate_last_user(content, _TPM_MAX_LAST_USER_CHARS)
                logger.warning(
                    "[ProviderManager/TPM] ✂️ Dernier message user tronqué : %d → %d chars",
                    before, len(last_user_msg["content"]),
                )
        new_total = sum(len(m.get("content", "")) for m in (system_msgs + other_msgs + ([last_user_msg] if last_user_msg else [])))
        if new_total > _TPM_GUARD_THRESHOLD and other_msgs:
            available_for_others = max(2_000, _TPM_GUARD_THRESHOLD - sum(len(m.get("content", "")) for m in system_msgs + ([last_user_msg] if last_user_msg else [])))
            kept_others: List[Dict[str, str]] = []
            running = 0
            for m in reversed(other_msgs):
                m_len = len(m.get("content", ""))
                if running + m_len > available_for_others: break
                kept_others.insert(0, m)
                running += m_len
            other_msgs = kept_others
        result = system_msgs + other_msgs
        if last_user_msg is not None: result.append(last_user_msg)
        return result, sum(len(m.get("content", "")) for m in result)

    def _build_model_candidates(self, provider: str, primary_model: str) -> List[str]:
        return [primary_model] if primary_model else []

    def execute_chat_stream(
        self, messages: List[Dict[str, Any]], provider: str = "groq", model: str = "openai/gpt-oss-20b",
        temperature: float = 0.7, max_tokens: int = 2048,
        top_p: float = 0.9,
        disable_internal_fallback: bool = False,
        skip_tpm_guard: bool = False,
    ) -> Generator[Dict[str, Any], None, None]:
        clean_msgs = self.format_messages(messages)
        if not clean_msgs:
            yield {"error": "Aucun message valide à envoyer."}
            return

        if provider.lower() == "local":
            try:
                from local_provider import LocalLlamaProvider
            except ImportError as exc:
                yield {"error": f"local_provider.py introuvable : {exc}"}
                return
            llm = LocalLlamaProvider()
            model_key = model or "qwen2.5-coder-3b"
            yield from llm.chat_stream(
                clean_msgs, model_key=model_key,
                max_tokens=max_tokens, temperature=temperature,
            )
            return

        _TOOL_CAPABLE = _resolve_tool_capable_providers()
        _original_provider = provider
        _was_redirected = False
        if provider.lower() not in _TOOL_CAPABLE:
            _was_redirected = True
            provider = "groq"
            model = _FALLBACK_TOOL_MODEL

        total_chars = sum(len(m.get("content", "")) for m in clean_msgs)
        if ":" in model and not model.startswith("http"):
            parts = model.split(":", 1)
            selected_provider, selected_model = parts[0], parts[1]
        else:
            selected_provider, selected_model = provider, model

        will_skip_tpm = skip_tpm_guard or self._should_skip_tpm_guard(clean_msgs)
        if will_skip_tpm:
            logger.info("[ProviderManager/TPM] ✅ Bypass TPM Guard — prompt d'analyse (%d chars)", total_chars)
        else:
            clean_msgs, total_chars = self._apply_tpm_guard(clean_msgs, total_chars)

        attempt_providers = [selected_provider]
        for fb in self.FALLBACK_ORDER:
            if fb not in attempt_providers:
                attempt_providers.append(fb)

        last_error_message = ""

        for current_prov in attempt_providers:
            if self._cb_is_open(current_prov):
                logger.warning("[ProviderManager] ⚡ Circuit ouvert pour %s, on skip.", current_prov)
                continue

            if current_prov == selected_provider:
                primary = selected_model
            else:
                primary = self.PROVIDER_MODELS.get(current_prov, ["default"])[0]

            candidates = self._build_model_candidates(current_prov, primary)

            provider_attempted = False
            for current_model in candidates:
                resolved_p, api_key, api_url = self.resolve_provider_endpoint(current_prov, current_model)
                if not api_key and "anonymous" not in resolved_p:
                    logger.warning("[ProviderManager] 🔑 Clé absente pour %s, on skip.", current_prov)
                    continue
                provider_attempted = True

                headers = {
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "text/event-stream; charset=utf-8",
                    "User-Agent": "BEK-v19-Agent",
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
                    _timeout = (15, 120) if current_prov == "nvidia" else (10, 45)
                    with requests.post(api_url, json=payload, headers=headers, stream=True, timeout=_timeout) as resp:
                        resp.encoding = "utf-8"
                        if resp.status_code != 200:
                            last_error_message = f"HTTP {resp.status_code} ({resolved_p}/{current_model}) - {resp.text[:300]}"
                            logger.warning("[ProviderManager] ❌ Échec %s : %s", current_prov, last_error_message)
                            break
                        received_chunks = False
                        for raw_line in resp.iter_lines(decode_unicode=True):
                            if not raw_line: continue
                            line = raw_line.strip()
                            if not line.startswith("data:"): continue
                            if line in ("data: [DONE]", "data:[DONE]"): break
                            try:
                                payload_json = json.loads(line[5:].strip())
                                choices = payload_json.get("choices", [{}])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    chunk = delta.get("content", "")
                                    if chunk:
                                        received_chunks = True
                                        yield {"chunk": chunk, "provider": resolved_p, "model": current_model, "was_redirected": _was_redirected, "original_provider": _original_provider}
                            except Exception:
                                continue
                        if received_chunks:
                            self._cb_record_success(current_prov)
                            yield {"done": True, "provider": resolved_p, "model": current_model, "was_redirected": _was_redirected, "original_provider": _original_provider}
                            return
                        else:
                            last_error_message = f"Aucun chunk reçu ({resolved_p}/{current_model})"
                            break
                except requests.Timeout:
                    last_error_message = f"Timeout ({resolved_p}/{current_model})"
                    logger.warning("[ProviderManager] ⏱️ Timeout %s", current_prov)
                    break
                except requests.RequestException as exc:
                    last_error_message = f"Réseau ({resolved_p}/{current_model}) : {str(exc)}"
                    logger.warning("[ProviderManager] 🌐 Erreur réseau %s", current_prov)
                    break

            if provider_attempted:
                self._cb_record_failure(current_prov)
                logger.info("[ProviderManager] 🔄 Passage au provider suivant dans la chaîne...")

        yield {"error": f"Tous les providers ont échoué. Dernière erreur : {last_error_message}"}


provider_manager = ProviderManager()