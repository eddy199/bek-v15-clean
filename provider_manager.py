# ==============================================================================
# BEK-v16 — Provider Manager (provider_manager.py)
# ------------------------------------------------------------------------------
# v24 (2026-09-20) :
#   - AJOUT : Provider AGNES AI (vidéo gratuite)
#   - AGNES_API_KEY + AGNES_BASE_URL dans PROVIDER_KEY_MAP
#   - resolve_agnes_model_id() : conversion noms courts UI -> IDs officiels
#   - get_agnes_endpoints() : URLs create + status prêtes à l'emploi
#   - list_agnes_video_models() : liste des modèles Agnes disponibles
#   - Mapping centralisé Veo 3.1 + Gemini image (v22 conservé)
#   - Détection dynamique des modèles (v22 conservé)
#   - Aucune régression : fallback chain texte inchangée
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


class ProviderManager:

    # ==========================================================================
    # MAPPING CENTRALISÉ DES MODEL IDS OFFICIELS GOOGLE
    # ==========================================================================
    MODEL_ID_MAPPING: Dict[str, str] = {
        # --------- Veo 3.1 (vidéo) ---------
        "veo-3.1-gene-prev":            "veo-3.1-generate-preview",
        "veo-3.1-lite-gene-prev":       "veo-3.1-lite-generate-preview",
        "veo-3.1-fast-gene-prev":       "veo-3.1-fast-generate-preview",
        "veo-3.1":                      "veo-3.1-generate-preview",
        "veo-3.1-lite":                 "veo-3.1-lite-generate-preview",
        "veo-3.1-fast":                 "veo-3.1-fast-generate-preview",
        # --------- Gemini Image ---------
        "gemini-3.1-flash-image":       "gemini-3.1-flash-image-preview",
        "gemini-3.1-flash-lite-image":  "gemini-3.1-flash-lite-image-preview",
        "gemini-2.5-flash-image":       "gemini-2.5-flash-image",
    }

    # ==========================================================================
    # ★ NOUVEAU v24 — MAPPING AGNES VIDEO
    # --------------------------------------------------------------------------
    # Noms courts UI -> IDs officiels Agnes
    # ==========================================================================
    AGNES_MODEL_MAPPING: Dict[str, str] = {
        # Noms courts UI
        "agnes-v2":            "agnes-video-v2.0",
        "agnes-v2.0":          "agnes-video-v2.0",
        "agnes-video-v2":      "agnes-video-v2.0",
        "agnes-video-v2.0":    "agnes-video-v2.0",
        "agnes-flash":         "agnes-video-2.5-flash",
        "agnes-v2.5-flash":    "agnes-video-2.5-flash",
        "agnes-video-flash":   "agnes-video-2.5-flash",
        "agnes-video-2.5-flash": "agnes-video-2.5-flash",
    }

    # Durées officiellement supportées par Veo 3.1 (en secondes)
    VEO_SUPPORTED_DURATIONS: List[int] = [4, 6, 8]
    VEO_MAX_SINGLE_CLIP: int = 8
    VEO_MIN_CLIP: int = 4

    # Endpoints
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta"
    AGNES_DEFAULT_BASE_URL: str = "https://apihub.agnes-ai.com/v1"

    # ==========================================================================
    # LIMITES AGNES VIDEO
    # ==========================================================================
    # - v2.0     : num_frames max 441 (~18 s @ 24 fps), 1080p
    # - 2.5-flash: seconds max 12, 720p
    # - RPM      : 1 (une requête par minute)
    # ==========================================================================
    AGNES_V2_MAX_FRAMES: int = 441
    AGNES_V2_MIN_FRAMES: int = 81
    AGNES_V2_DEFAULT_FPS: int = 24

    AGNES_FLASH_MIN_SECONDS: int = 4
    AGNES_FLASH_MAX_SECONDS: int = 12

    # ==========================================================================
    # MODÈLES PAR FOURNISSEUR
    # ==========================================================================
    PROVIDER_MODELS: Dict[str, List[str]] = {
        # 1. Moonshot Kimi AI
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
        # 2. AIsa — Unified Gateway (modèles GRATUITS uniquement)
        "aisa": [
            "qwen-flash",
            "qwen-mt-flash",
            "qwen-mt-lite",
        ],
        # 3. B.ai
        "b_ai": [
            "glm-5.3-flash",
            "qwen3.8-flash",
            "mimo-v2.5",
            "hy3",
        ],
        # 4. Kilo Code
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
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "stepfun/step-3.7-flash:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "poolside/laguna-s-2.1:free",
            "poolside/laguna-xs-2.1:free",
            "cohere/north-mini-code:free",
            "openrouter/free",
            "tencent/hy3:free",
            "nvidia/nemotron-3.5-lightning:free",
            "liquid/lfm-2.5-2.6b:free",
        ],
        # 5. OVHcloud
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
        # 6. LLM7.io
        "llm7_anonymous": [
            "llm7-gpt-oss-20b",
            "llm7-mistral-nemo",
            "llm7-minimax-m2.7",
        ],
        # 7. Groq
        "groq": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "groq/compound",
            "groq/compound-mini",
        ],
        # 8. NVIDIA NIM
        "nvidia": [
            "z-ai/glm-5.3",
            "moonshotai/kimi-k3",
            "deepseek-ai/deepseek-v4-flash-0731",
            "nvidia/nemotron-3.5-lightning-30b-a3b",
            "meta/muse-glimmer-30b",
            "nvidia/ising-calibration-1.5-31b",
            "poolside/laguna-xs-2.1",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            "nvidia/nemotron-3-super-120b-a12b",
            "mistralai/mistral-nemotron",
            "meta/llama-3.2-11b-vision-instruct",
            "meta/llama-3.2-90b-vision-instruct",
        ],
        # 9. Google Gemini
        "gemini": [
            # ----- Chat / Texte -----
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
            "gemma-4-31b",
            "gemma-4-26b-a4b",
            "gemini-1.5-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",

            # ----- Images -----
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
            "gemini-3-pro-image",
            "gemini-2.5-flash-image",

            # ----- Live / TTS -----
            "gemini-3.5-live-translate-preview",
            "gemini-3.1-flash-live-preview",
            "gemini-3.1-flash-tts-preview",
            "gemini-2.5-flash-native-audio-preview-12-2025",
            "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts",
            "gemini-omni-flash",

            # ----- Veo 3.1 : noms courts UI -----
            "veo-3.1-gene-prev",
            "veo-3.1-lite-gene-prev",
            "veo-3.1-fast-gene-prev",

            # ----- Veo 3.1 : IDs officiels API -----
            "veo-3.1-generate-preview",
            "veo-3.1-lite-generate-preview",
            "veo-3.1-fast-generate-preview",

            # ----- Audio (Lyria) -----
            "lyria-3-pro-preview",
            "lyria-3-clip-preview",
            "lyria-realtime-preview",
        ],

        # ★ NOUVEAU v24 — Agnes AI (vidéo gratuite) ★
        "agnes": [
            # Noms courts UI (recommandés)
            "agnes-v2.0",             # 1080p, 18s max, frame-based
            "agnes-v2.5-flash",       # 720p, 12s max, second-based

            # IDs officiels
            "agnes-video-v2.0",
            "agnes-video-2.5-flash",
        ],

        # 10. OpenRouter
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
        # 11. Mistral AI
        "mistral": [
            "mistral-medium-3.5",
            "mistral-small-4",
            "mistral-large-3",
            "ministral-3-8b",
            "codestral",
            "ministral-3-3b",
            "ministral-3-14b",
        ],
        # 12. Cohere
        "cohere": [
            "cohere-command-a-plus",
            "cohere-command-a",
            "cohere-command-r-plus",
            "cohere-command-r",
            "cohere-command-r7b",
            "cohere-aya-expanse-32b",
        ],
        # 13. Aion Labs
        "aionlabs": [
            "aion-2.0",
            "aion-rp-llama-3.1-8b",
            "aion-3.0",
            "aion-3.0-mini",
        ],
        # 14. Zhipu AI
        "zhipu": [
            "glm-4.7-flash",
            "glm-4.5-flash",
            "glm-4.6v-flash",
        ],
        # 15. SiliconFlow
        "siliconflow": [
            "siliconflow-qwen3-8b",
        ],
        # 16. Hugging Face
        "huggingface": [
            "Meta-Llama-3.1-8B-Instruct",
            "gemma-3-4b-it",
            "phi-4",
            "Qwen2.5-Coder-7B-Instruct",
            "Qwen2.5-7B-Instruct",
        ],
        # 17. Ollama Cloud
        "ollama_cloud": [
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "minimax-m3",
            "kimi-k3",
            "gpt-oss:120b",
            "gpt-oss:20b",
            "nemotron-3-ultra",
            "mistral-large-3:675b",
            "qwen3.5:397b",
        ],
    }

    # ==========================================================================
    # CHAÎNE DE FALLBACK (texte/chat)
    # ==========================================================================
    FALLBACK_ORDER: List[str] = [
        "nvidia",
        "aisa",
        "groq",
        "kimi",
        "b_ai",
        "gemini",
        "kilo_anonymous",
        "huggingface",
        "openrouter",
        "ovh_anonymous",
        "llm7_anonymous",
    ]

    # ==========================================================================
    # CLÉS API PAR FOURNISSEUR
    # ==========================================================================
    PROVIDER_KEY_MAP: Dict[str, str] = {
        "kimi":          "MOONSHOT_API_KEY",
        "aisa":          "AISA_API_KEY",
        "b_ai":          "B_AI_API_KEY",
        "groq":          "GROQ_API_KEY",
        "nvidia":        "NVIDIA_API_KEY",
        "gemini":        "GEMINI_API_KEY",
        "openrouter":    "OPENROUTER_API_KEY",
        "mistral":       "MISTRAL_API_KEY",
        "cohere":        "COHERE_API_KEY",
        "aionlabs":      "AIONLABS_API_KEY",
        "zhipu":         "ZHIPU_API_KEY",
        "siliconflow":   "SILICONFLOW_API_KEY",
        "huggingface":   "HUGGINGFACE_API_KEY",
        "ollama_cloud":  "OLLAMA_API_KEY",
        # ★ NOUVEAU v24 ★
        "agnes":         "AGNES_API_KEY",
    }

    # ==========================================================================
    # INITIALISATION
    # ==========================================================================
    def __init__(self) -> None:
        self.env_cache: Dict[str, str] = {}
        self._models_cache: Dict[str, Any] = {}
        self._models_cache_ts: float = 0.0
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
                            self.env_cache[k.strip()] = v.strip().strip("\"' \r\n")
            except Exception as exc:
                logger.warning("Erreur lecture %s : %s", filename, exc)

    # ==========================================================================
    # CLÉ API
    # ==========================================================================
    def get_api_key(self, key_name: str) -> str:
        val = os.environ.get(key_name, "")
        if val:
            return val.strip("\"' \r\n")
        val = self.env_cache.get(key_name, "")
        if val:
            return val.strip("\"' \r\n")
        self._load_env_cache()
        return self.env_cache.get(key_name, "").strip("\"' \r\n")

    def is_provider_available(self, provider: str) -> bool:
        p = provider.lower().strip()
        if "anonymous" in p:
            return True
        key_name = self.PROVIDER_KEY_MAP.get(p)
        if not key_name:
            return False
        if self.get_api_key(key_name):
            return True
        if p == "kimi":
            return bool(self.get_api_key("KIMI_API_KEY"))
        return False

    # ==========================================================================
    # RÉSOLUTION DES ENDPOINTS (chat texte)
    # ==========================================================================
    def resolve_provider_endpoint(
        self, provider: str, model: str
    ) -> Tuple[str, str, str]:
        p = provider.lower().strip()

        if p in ["b.ai", "b_ai", "bai"]:
            key = self.get_api_key("B_AI_API_KEY")
            return "b_ai", key, "https://api.b.ai/v1/chat/completions"

        elif p in ["kimi", "moonshot", "moonshot_ai"]:
            key = self.get_api_key("MOONSHOT_API_KEY") or self.get_api_key("KIMI_API_KEY")
            base_url = self.get_api_key("MOONSHOT_BASE_URL") or "https://api.moonshot.cn/v1"
            return "kimi", key, base_url.rstrip("/") + "/chat/completions"

        elif p == "aisa":
            key = self.get_api_key("AISA_API_KEY")
            return "aisa", key, "https://api.aisa.one/v1/chat/completions"

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

        elif p == "huggingface":
            key = self.get_api_key("HUGGINGFACE_API_KEY")
            return "huggingface", key, "https://router.huggingface.co/v1/chat/completions"

        elif p in ["ollama_cloud", "ollama"]:
            key = self.get_api_key("OLLAMA_API_KEY")
            return "ollama_cloud", key, "https://ollama.com/v1/chat/completions"

        else:
            key = self.get_api_key("GROQ_API_KEY")
            return "groq", key, "https://api.groq.com/openai/v1/chat/completions"

    # ==========================================================================
    # RÉSOLUTION DES MODEL IDS (Veo 3.1 + Gemini image)
    # ==========================================================================
    def resolve_model_id(self, model_name: str) -> str:
        """
        Convertit un nom court UI vers le model ID officiel Google.
        Fonctionne pour Veo 3.1 et Gemini Image.
        """
        if not model_name:
            return model_name

        clean = model_name.replace("models/", "").strip()

        # Mapping direct
        if clean in self.MODEL_ID_MAPPING:
            mapped = self.MODEL_ID_MAPPING[clean]
            logger.info("[provider_manager] resolve_model_id: %s -> %s", clean, mapped)
            return mapped

        # Déjà un ID officiel Veo ?
        if clean.startswith("veo-") and "generate" in clean:
            return clean

        # Déjà un ID officiel Gemini image ?
        if clean.startswith("gemini-") and "image" in clean:
            return clean

        # Fallback générique : veo-xxx-gene-prev -> veo-xxx-generate-preview
        if clean.startswith("veo-") and clean.endswith("-gene-prev"):
            normalized = clean.replace("-gene-prev", "-generate-preview")
            logger.warning(
                "[provider_manager] resolve_model_id fallback: %s -> %s",
                clean, normalized,
            )
            return normalized

        return clean

    def resolve_veo_model_id(self, model: str) -> str:
        """Raccourci sémantique pour Veo."""
        if not model:
            return "veo-3.1-generate-preview"
        resolved = self.resolve_model_id(model)
        if not resolved.startswith("veo-"):
            logger.warning(
                "[provider_manager] resolve_veo_model_id: '%s' n'est pas un modèle Veo, "
                "fallback sur veo-3.1-generate-preview", model,
            )
            return "veo-3.1-generate-preview"
        return resolved

    # ==========================================================================
    # ★ NOUVEAU v24 — RÉSOLUTION DES MODEL IDS AGNES
    # ==========================================================================
    def resolve_agnes_model_id(self, model: str) -> str:
        """
        Convertit un nom court UI vers le model ID officiel Agnes.

        Exemples :
            "agnes-v2.0"       -> "agnes-video-v2.0"
            "agnes-v2"         -> "agnes-video-v2.0"
            "agnes-flash"      -> "agnes-video-2.5-flash"
            "agnes-v2.5-flash" -> "agnes-video-2.5-flash"
        """
        if not model:
            # Par défaut : v2.0 (1080p, plus de contrôle)
            return "agnes-video-v2.0"

        clean = model.replace("models/", "").strip()

        # Mapping direct
        if clean in self.AGNES_MODEL_MAPPING:
            mapped = self.AGNES_MODEL_MAPPING[clean]
            logger.info("[provider_manager] resolve_agnes_model_id: %s -> %s", clean, mapped)
            return mapped

        # Déjà un ID officiel ?
        if clean.startswith("agnes-video-"):
            return clean

        # Fallback : v2.0
        logger.warning(
            "[provider_manager] resolve_agnes_model_id: '%s' inconnu, fallback sur agnes-video-v2.0",
            model,
        )
        return "agnes-video-v2.0"

    # ==========================================================================
    # ENDPOINTS VEO (predictLongRunning + polling)
    # ==========================================================================
    def get_veo_endpoints(self, model: str) -> Dict[str, Any]:
        """Retourne les URLs prêtes à l'emploi pour Veo 3.1."""
        model_id = self.resolve_veo_model_id(model)
        api_key = self.get_api_key("GEMINI_API_KEY")

        return {
            "model_id":         model_id,
            "predict_url":      f"{self.GEMINI_API_BASE}/models/{model_id}:predictLongRunning",
            "operations_base":  self.GEMINI_API_BASE,
            "api_key":          api_key,
            "headers": {
                "Content-Type":   "application/json",
                "x-goog-api-key": api_key,
            },
        }

    # ==========================================================================
    # ★ NOUVEAU v24 — ENDPOINTS AGNES (create + status)
    # ==========================================================================
    def get_agnes_endpoints(self, model: str = "agnes-v2.0") -> Dict[str, Any]:
        """
        Retourne les URLs prêtes à l'emploi pour Agnes AI Video.

        Usage :
            ep = provider_manager.get_agnes_endpoints("agnes-v2.0")
            # ep = {
            #   "model_id":     "agnes-video-v2.0",
            #   "base_url":     "https://apihub.agnes-ai.com/v1",
            #   "create_url":   "https://apihub.agnes-ai.com/v1/videos",
            #   "status_url":   "https://apihub.agnes-ai.com/agnesapi",
            #   "api_key":      "sk-...",
            #   "headers":      { Authorization, Content-Type },
            #   "is_v2":        True,   # True = v2.0 (frames), False = 2.5-flash (seconds)
            #   "max_frames":   441,
            #   "max_seconds":  12,
            #   "default_fps":  24,
            # }
        """
        model_id = self.resolve_agnes_model_id(model)
        api_key = self.get_api_key("AGNES_API_KEY")
        base_url = (
            self.get_api_key("AGNES_BASE_URL")
            or self.AGNES_DEFAULT_BASE_URL
        ).rstrip("/")

        is_v2 = model_id == "agnes-video-v2.0"

        return {
            "model_id":     model_id,
            "base_url":     base_url,
            "create_url":   f"{base_url}/videos",
            # Endpoint de status (différent du /v1 !)
            "status_url":   f"{base_url.replace('/v1', '')}/agnesapi",
            "api_key":      api_key,
            "headers": {
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            "is_v2":        is_v2,
            "max_frames":   self.AGNES_V2_MAX_FRAMES,     # 441
            "min_frames":   self.AGNES_V2_MIN_FRAMES,     # 81
            "default_fps":  self.AGNES_V2_DEFAULT_FPS,    # 24
            "min_seconds":  self.AGNES_FLASH_MIN_SECONDS, # 4
            "max_seconds":  self.AGNES_FLASH_MAX_SECONDS, # 12
        }

    def list_agnes_video_models(self) -> List[str]:
        """Retourne la liste des modèles Agnes vidéo disponibles (IDs officiels)."""
        return [
            "agnes-video-v2.0",
            "agnes-video-2.5-flash",
        ]

    # ==========================================================================
    # DÉTECTION DYNAMIQUE DES MODÈLES DISPONIBLES
    # ==========================================================================
    def detect_available_models(
        self,
        provider: str = "gemini",
        force_refresh: bool = False,
        cache_ttl: int = 3600,
    ) -> Dict[str, Any]:
        """Détecte dynamiquement les modèles disponibles pour un fournisseur."""
        p = provider.lower().strip()
        now = time.time()

        # Cache valide ?
        cache_key = f"models_{p}"
        if (
            not force_refresh
            and cache_key in self._models_cache
            and (now - self._models_cache_ts) < cache_ttl
        ):
            cached = self._models_cache[cache_key]
            return {
                "provider":  p,
                "source":    "cache",
                "count":     len(cached.get("models", [])),
                "models":    cached.get("models", []),
                "raw":       cached.get("raw", {}),
            }

        # --- Gemini : appel API réel ---
        if p == "gemini":
            api_key = self.get_api_key("GEMINI_API_KEY")
            if not api_key:
                logger.warning("[provider_manager] Pas de GEMINI_API_KEY, fallback statique")
                return self._static_models_response(p)

            try:
                url = f"{self.GEMINI_API_BASE}/models?key={api_key}&pageSize=200"
                res = requests.get(url, timeout=30)
                if res.status_code != 200:
                    logger.warning(
                        "[provider_manager] GET /models HTTP %s : %s",
                        res.status_code, res.text[:300],
                    )
                    return self._static_models_response(p)

                data = res.json()
                models: List[Dict[str, Any]] = []
                for m in data.get("models", []):
                    name = m.get("name", "").replace("models/", "")
                    if not name:
                        continue
                    models.append({
                        "id":                name,
                        "displayName":       m.get("displayName", name),
                        "description":       m.get("description", ""),
                        "inputTokenLimit":   m.get("inputTokenLimit"),
                        "outputTokenLimit":  m.get("outputTokenLimit"),
                        "supportedMethods":  m.get("supportedGenerationMethods", []),
                    })

                self._models_cache[cache_key] = {"models": models, "raw": data}
                self._models_cache_ts = now

                logger.info("[provider_manager] %d modèles Gemini détectés via API", len(models))
                return {
                    "provider":  p,
                    "source":    "api",
                    "count":     len(models),
                    "models":    models,
                    "raw":       data,
                }

            except requests.RequestException as e:
                logger.warning("[provider_manager] Erreur détection Gemini : %s", e)
                return self._static_models_response(p)

        # --- Autres fournisseurs : statique ---
        return self._static_models_response(p)

    def _static_models_response(self, provider: str) -> Dict[str, Any]:
        """Retourne la liste statique d'un fournisseur au même format."""
        static_list = self.PROVIDER_MODELS.get(provider, [])
        models = [{"id": m, "displayName": m, "supportedMethods": ["static"]} for m in static_list]
        return {
            "provider": provider,
            "source":   "static",
            "count":    len(models),
            "models":   models,
            "raw":      {},
        }

    def list_veo_models(self) -> List[str]:
        """Retourne la liste des modèles Veo disponibles (IDs officiels)."""
        return [
            "veo-3.1-generate-preview",
            "veo-3.1-fast-generate-preview",
            "veo-3.1-lite-generate-preview",
        ]

    def list_gemini_image_models(self) -> List[str]:
        """Retourne les modèles image Gemini disponibles (IDs officiels)."""
        return [
            "gemini-3.1-flash-image-preview",
            "gemini-3.1-flash-lite-image-preview",
            "gemini-2.5-flash-image",
        ]

    # ==========================================================================
    # FORMATAGE DES MESSAGES
    # ==========================================================================
    def format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        formatted = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user")
            if role not in ["system", "user", "assistant"]:
                role = "user"
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

    # ==========================================================================
    # EXÉCUTION CHAT EN STREAM
    # ==========================================================================
    def execute_chat_stream(
        self,
        messages: List[Dict[str, Any]],
        provider: str = "nvidia",
        model: str = "nvidia/nemotron-3-super-120b-a12b",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.9,
    ) -> Generator[Dict[str, Any], None, None]:
        clean_msgs = self.format_messages(messages)
        if not clean_msgs:
            yield {"error": "Aucun message valide à envoyer."}
            return

        total_chars = sum(len(m.get("content", "")) for m in clean_msgs)

        if ":" in model:
            parts = model.split(":", 1)
            selected_provider = parts[0]
            selected_model = parts[1]
        else:
            selected_provider = provider
            selected_model = model

        if selected_provider == "groq" and total_chars > 16000:
            logger.warning(
                "[TPM Guard] Requête volumineuse (%d chars), routage vers nvidia.",
                total_chars,
            )
            selected_provider = "nvidia"

        attempt_providers = [selected_provider] + [
            p for p in self.FALLBACK_ORDER if p != selected_provider
        ]
        last_error_message = ""

        for current_prov in attempt_providers:
            available_models = self.PROVIDER_MODELS.get(current_prov, [])

            if current_prov == selected_provider:
                current_model = selected_model
            else:
                if current_prov == "nvidia":           current_model = "nvidia/nemotron-3-super-120b-a12b"
                elif current_prov == "aisa":           current_model = "qwen-flash"
                elif current_prov == "kimi":           current_model = "kimi-k3"
                elif current_prov == "b_ai":           current_model = "glm-5.3-flash"
                elif current_prov == "gemini":         current_model = "gemini-3.8-flash"
                elif current_prov == "kilo_anonymous": current_model = "kilo-nemotron-3-ultra-550b"
                else:                                  current_model = available_models[0] if available_models else "default"

            resolved_p, api_key, api_url = self.resolve_provider_endpoint(current_prov, current_model)

            if not api_key and "anonymous" not in resolved_p:
                continue

            headers = {
                "Content-Type":  "application/json; charset=utf-8",
                "Accept":        "text/event-stream; charset=utf-8",
                "User-Agent":    "BEK-v16-Agent",
            }
            if api_key != "none":
                headers["Authorization"] = f"Bearer {api_key}"

            payload = {
                "model":       current_model,
                "messages":    clean_msgs,
                "temperature": temperature,
                "top_p":       top_p,
                "max_tokens":  max_tokens,
                "stream":      True,
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
                        logger.warning(
                            "Échec provider %s (HTTP %s) : %s",
                            resolved_p, resp.status_code, err_text,
                        )
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
                                        "chunk":    chunk,
                                        "provider": resolved_p,
                                        "model":    current_model,
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
                last_error_message = f"Réseau ({resolved_p}) : {str(exc)}"
                continue

        yield {"error": f"Tous les providers ont échoué. Dernière erreur : {last_error_message}"}


# ==============================================================================
# SINGLETON
# ==============================================================================
provider_manager = ProviderManager()