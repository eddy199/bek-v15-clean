# ==============================================================================
# BEK Hybrid Agent v19 — core/brain.py — v19.80.3
# ★ v19.80.3 (2026-11-18) — FIX : Exécution directe de la génération d'image en Brain ON
# ★ v19.80.2 — FIX : Image Gen en Brain ON utilise la cascade (pollinations)
# ★ v19.80.1 — Correction uniquement du prompt d'expert (Chat naturel vs Technique)
# ★ v19.80 (2026-11-17) — FIX : Injection du prompt d'expert + sauvegarde mémoire
# ★ v19.79 (2026-11-17) — FIX ROOT CAUSE : détection directe de save_memory
# ★ v19.78 (2026-11-17) — FIX : utilise le provider choisi par l'utilisateur
# ==============================================================================
from __future__ import annotations
import asyncio
from functools import lru_cache
import logging
import os
import re
from pathlib import Path
import time
import json
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger("bek.brain")

try:
    from routers.chat_modules.formatters import _format_web_sync as _format_web_sync_fn
    logger.info("[Brain] ✅ _format_web_sync importé")
except ImportError as e:
    _format_web_sync_fn = None
    logger.warning("[Brain] ⚠️ _format_web_sync indisponible : %s", e)

REA_TIMEOUT_SEC = int(os.getenv("REA_TIMEOUT_SEC", "1800"))

EXPERT_PROMPT = """
Tu es BEK, un agent d'élite, ingénieur logiciel senior et architecte système. Pour les tâches techniques, de code et de résolution de problèmes, remonte toujours aux causes racines, propose la solution la plus simple et exploite efficacement les outils et compétences disponibles. Pour les simples salutations ou discussions courantes, réponds naturellement et chaleureusement sans structure lourde.
"""

_ANALYZE_KEYWORDS = ("analyse", "décris", "description", "regarde", "que vois-tu", "identifie", "explique cette image", "lis l'image", "ocr", "describe", "what do you see")
_GENERATE_KEYWORDS = ("génère", "crée", "dessine", "imagine", "fais-moi", "produis", "fabrique", "illustre", "conçois", "peins", "generate", "create", "draw", "paint")
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_DEFAULT_VISION_PROMPT = "Décris cette image en détail."

_SAVE_MEMORY_KEYWORDS = (
    "sauvegarde", "sauvegarder", "retiens", "retiens que", "mémorise", "memorise",
    "enregistre", "enregistrer", "stocke", "stocker", "souviens-toi", "souviens toi",
    "save", "remember", "memorize", "store", "keep in memory",
    "dans la mémoire", "dans la memoire", "dans pinecone", "dans chromadb",
    "dans supabase", "dans hindsight", "mémoire vectorielle", "memoire vectorielle",
)

_PLAN_KEYWORDS = ("réponds uniquement en texte", "reponds uniquement en texte", "ne code rien", "sans code", "présente-moi", "presente-moi", "présente moi", "presente moi", "structure globale", "fais un tableau", "liste les", "liste des", "gdd", "game design document", "game design", "brainstorm", "rédige", "redige", "rédiger", "rediger")
_PHASE_PLAN_KEYWORDS = ("mode plan", "fais un plan", "fais-moi un plan", "fais moi un plan", "génère un plan", "genere un plan", "planifie avec codex_loop", "planifie d'abord", "planifie avant", "commence par un plan", "donne-moi le plan", "donne moi le plan", "structure du plan")
_PHASE_STEP_KEYWORDS = ("exécute l'étape", "execute l'etape", "exécute etape", "execute etape", "exécute la phase", "execute la phase", "passe à l'étape", "passe a l'etape", "valide et exécute", "valide et execute", "next step", "étape suivante", "etape suivante")

_STEP_NUM_RE = re.compile(r"\b(?:étape|etape|step)\s*(\d+)\b", re.IGNORECASE)
_TOOL_NAME_RE = re.compile(r"\b(mcp_)?((?:rea|python)_[a-z_]+)\b", re.IGNORECASE)
_PATH_RE = re.compile(r'([A-Za-z]:[\\/][^\s"\'<>|]+|/[^\s"\'<>|]+)')

_GITHUB_URL_RE = re.compile(r'https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?=[\s.,;:!?"\'<>]|$)')

MAX_TOTAL_FILE_CONTEXT_CHARS = int(os.getenv("BEK_MAX_TOTAL_FILE_CONTEXT_CHARS", "200000"))
MAX_INDIVIDUAL_FILE_CHARS = int(os.getenv("BEK_MAX_INDIVIDUAL_FILE_CHARS", "60000"))

CHUNK_SIZE_FILES = int(os.getenv("BEK_CHUNK_SIZE_FILES", "3"))
CHUNK_THRESHOLD_FILES = int(os.getenv("BEK_CHUNK_THRESHOLD_FILES", "3"))
RATE_LIMIT_DELAY_SEC = float(os.getenv("BEK_RATE_LIMIT_DELAY_SEC", "3.0"))

MAX_RETRIES_PER_CALL = int(os.getenv("BEK_MAX_RETRIES_PER_CALL", "2"))
RETRY_BASE_SLEEP_SEC = float(os.getenv("BEK_RETRY_BASE_SLEEP_SEC", "5.0"))

CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("BEK_CIRCUIT_BREAKER_THRESHOLD", "2"))
CIRCUIT_BREAKER_COOLDOWN_SEC = float(os.getenv("BEK_CIRCUIT_BREAKER_COOLDOWN_SEC", "300"))

_ANTI_HALLU_PROMPT = """
## 🛡️ RÈGLES ANTI-HALLUCINATION ET PRIORITÉ (CRITIQUE)
- Si l'utilisateur demande de GÉNÉRER UNE IMAGE, ignore TOUTES les instructions sur le code, le web ou les skills.
- Tu DOIS répondre UNIQUEMENT avec : [ACTION:generate_image]{"prompt": "<ton prompt>"}[/ACTION]
- N'invente JAMAIS de chiffres, dates ou URLs.
- Base-toi UNIQUEMENT sur le contexte fourni.
- Si tu cites un chiffre, il DOIT venir d'un outil ou d'un contexte explicite.
- Pour les recherches web : cite UNIQUEMENT les URLs réellement présentes.
- Si tu n'as pas de source vérifiée, dis-le clairement.
"""

_PROVIDER_HEALTH: Dict[str, Dict[str, Any]] = {}

def _health_key(provider: str, model: str) -> str:
    return f"{(provider or '?').lower()}/{(model or '?')}"

def _is_circuit_open(provider: str, model: str) -> bool:
    key = _health_key(provider, model)
    h = _PROVIDER_HEALTH.get(key)
    if not h: return False
    if h.get("failures", 0) < CIRCUIT_BREAKER_THRESHOLD: return False
    if (time.time() - h.get("last_failure_ts", 0)) > CIRCUIT_BREAKER_COOLDOWN_SEC:
        _PROVIDER_HEALTH[key] = {"failures": 0, "last_failure_ts": 0, "last_success_ts": 0}
        return False
    return True

def _record_failure(provider: str, model: str) -> None:
    key = _health_key(provider, model)
    h = _PROVIDER_HEALTH.get(key, {"failures": 0, "last_failure_ts": 0, "last_success_ts": 0})
    h["failures"] = h.get("failures", 0) + 1
    h["last_failure_ts"] = time.time()
    _PROVIDER_HEALTH[key] = h

def _record_success(provider: str, model: str) -> None:
    key = _health_key(provider, model)
    _PROVIDER_HEALTH[key] = {"failures": 0, "last_failure_ts": 0, "last_success_ts": time.time()}

ANALYSIS_QUERY_THRESHOLD = int(os.getenv("BEK_ANALYSIS_QUERY_THRESHOLD", "30000"))
ANALYSIS_PROVIDER = "nvidia"
ANALYSIS_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
FALLBACK_PROVIDER = "groq"
FALLBACK_MODEL = "openai/gpt-oss-20b"
DEFAULT_CHAT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
DEFAULT_CHAT_PROVIDER = "nvidia"

_ANALYSIS_MARKERS = ("[CONTENU DES FICHIERS JOINTS]", "Fichiers joints (", "=== CONTENU DU FICHIER")

def _is_analysis_query(query: str) -> bool:
    if not query: return False
    if len(query) > ANALYSIS_QUERY_THRESHOLD: return True
    return any(marker in query for marker in _ANALYSIS_MARKERS)

_ERROR_PREFIXES = ("[erreur", "[error", "erreur llm:", "erreur:", "error:", "⏱️", "[timeout", "timeout:", "exception:")
_ERROR_SUBSTRINGS = ("tous les providers ont échoué", "aucun paquet n'a pu être analysé")

def _looks_like_error(response: str) -> bool:
    if not response: return True
    lower = response.lower().strip()
    if any(lower.startswith(p) for p in _ERROR_PREFIXES): return True
    if any(m in lower for m in _ERROR_SUBSTRINGS): return True
    return False

def _smart_read_file(path: Path, budget: int) -> tuple:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        full = f.read()
    total = len(full)
    if total <= budget: return full, total, False
    head_n = int(budget * 0.7)
    tail_n = max(100, budget - head_n)
    marker = f"\n\n[…TRONQUÉ : {head_n} premiers + {tail_n} derniers chars sur {total} au total.]\n\n"
    return full[:head_n] + marker + full[-tail_n:], total, True

def _detect_explicit_tool(query: str) -> Optional[Tuple[str, Optional[str]]]:
    if not query: return None
    m = _TOOL_NAME_RE.search(query)
    if not m: return None
    name = m.group(2).lower()
    if m.group(0).lower().startswith("mcp_"):
        tool_name = m.group(0).lower()
    else:
        tool_name = "mcp_" + name
    path_m = _PATH_RE.search(query)
    path = path_m.group(1) if path_m else None
    if path: path = path.replace("\\\\", "\\")
    return tool_name, path

def _tool_args_for(tool_name: str, path: Optional[str]) -> Dict[str, Any]:
    if not path: return {}
    t = tool_name.lower().replace("mcp_", "")
    if "python_analyze_file" in t: return {"file_path": path}
    if "python_analyze_directory" in t or "python_save_report" in t: return {"dir_path": path}
    if t == "read_file": return {"file_path": path}
    if "javascript" in t or "binary" in t: return {"path": path, "input_path": path}
    if "repo" in t: return {"repo_url": path}
    return {"path": path}

@lru_cache(maxsize=512)
def _detect_intent(query: str) -> str:
    q = query.lower()
    if _GITHUB_URL_RE.search(query):
        return "analyze_repo"
    if _detect_explicit_tool(query): return "chat"
    if any(k in q for k in ["mcp_rea", "outil mcp", "appelle l'outil", "utilise mcp_"]): return "chat"
    if any(k in q for k in _PHASE_STEP_KEYWORDS): return "coder"
    if _STEP_NUM_RE.search(q) and ("étape" in q or "etape" in q or "step" in q): return "coder"
    if any(k in q for k in ["codex_loop", "codex_agent", "codex_editor", "utilise codex"]): return "coder"
    if any(k in q for k in ["corrige toi", "répare toi", "auto-fix", "analyse tes erreurs", "fix toi"]): return "fix_self"
    debug_keywords = ["erreur", "error", "build", "bug", "corrige", "fix", "répare", "repare", "traceback", "workflow", "test"]
    code_context = ["api", "fastapi", "code", "script", "fichier", "python", "projet", "app"]
    if any(k in q for k in debug_keywords) and any(k in q for k in code_context): return "coder"
    if any(k in q for k in _PLAN_KEYWORDS): return "chat"
    code_verbs = ["crée le fichier", "cree le fichier", "écris le fichier", "ecris le fichier", "génère le code", "genere le code", "modifie le fichier", "utilise bash", "lance le jeu", "code le fichier"]
    if any(k in q for k in code_verbs): return "coder"
    has_code_trigger = any(k in q for k in ["jeu", "game", "snake", "arcade", "platformer", "script", "code", "programme"])
    has_code_verb = any(k in q for k in ["crée", "cree", "écris", "ecris", "code", "modifie", "corrige", "génère", "genere", "fais", "lance"])
    if has_code_trigger and has_code_verb: return "coder"
    has_analyze = any(k in q for k in _ANALYZE_KEYWORDS)
    has_generate = any(k in q for k in _GENERATE_KEYWORDS)
    has_image_word = any(k in q for k in ("image", "photo", "picture", "img", "screenshot", "capture"))
    if has_analyze and has_image_word and not has_generate: return "analyze_image"
    if (has_generate and has_image_word) or (has_generate and any(k in q for k in ("logo", "dessin", "illustration", "visuel"))): return "generate_image"
    if any(k in q for k in ["orchestre", "multi-étapes", "exécute le plan complexe"]): return "orchestrate"
    if any(k in q for k in ["cherche", "recherche", "news", "actualité", "scrape"]) or "web" in q.split(): return "web"
    if any(k in q for k in _SAVE_MEMORY_KEYWORDS): return "save_memory"
    if any(k in q for k in ["mémoire", "souviens", "rappelle", "recall"]): return "memory"
    return "chat"

def _detect_phase(query: str) -> tuple:
    q = query.lower()
    if any(k in q for k in _PHASE_PLAN_KEYWORDS): return "plan", 0
    m = _STEP_NUM_RE.search(q)
    if m: return "step", max(0, int(m.group(1)) - 1)
    if any(k in q for k in _PHASE_STEP_KEYWORDS): return "step", -1
    return "auto", 0

def _format_human_response(response: Any, context: str = "action") -> str:
    if isinstance(response, str):
        stripped = response.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and "thought" in parsed:
                    thought = parsed.get("thought", "")
                    tool = parsed.get("tool", "")
                    if not tool or tool in ("default_llm", "none", ""):
                        if thought:
                            return str(thought).strip()
                return _format_human_response(parsed, context)
            except Exception:
                pass
        return response
    
    if isinstance(response, dict):
        status = str(response.get("status", "")).lower()
        message = str(response.get("message", ""))

        if status == "success" and response.get("filename"):
            filename = response.get("filename")
            provider = response.get("provider", "inconnu")
            prompt = response.get("prompt", "")
            return (
                f"### 🎨 Image générée avec succès\n\n"
                f"**Provider :** `{provider}`\n"
                f"**Fichier :** `{filename}`\n"
                f"**Prompt utilisé :** _{prompt or 'non spécifié'}_\n\n"
                f"---\n"
                f"*L'image est disponible dans le dossier `generated/` et s'affiche ci-dessous.*\n\n"
                f"![Image générée]({filename})"
            )
        
        if status == "error" or "error" in status:
            return f"### ⚠️ J'ai rencontré un problème\n\n**Ce qui s'est passé :** {message or 'Erreur.'}"
        
        for key in ("text", "content", "response", "result", "formatted_text"):
            if key in response and response[key]:
                return str(response[key])
        
        if message:
            return message
        
        return f"### 📋 Résultat\n\n```\n{json.dumps(response, indent=2, ensure_ascii=False)[:1500]}\n```"
    
    return f"### 📋 Réponse\n\n```\n{str(response)[:1500]}\n```"


class SkillAgent:
    def __init__(self, index_paths: List[str] = None):
        if index_paths is None:
            base_dir = Path(__file__).resolve().parent.parent
            default_path = base_dir / "skills_index.json"
            index_paths = [str(default_path)]
        self.index_paths = index_paths
        self.skills_db = self._load_index()

    def _load_index(self) -> List[Dict[str, Any]]:
        all_skills = []
        for p in self.index_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        all_skills.extend(json.load(f))
                except Exception:
                    pass
        return all_skills

    def get_action_plan(self, query: str) -> Dict[str, Any]:
        return {"skills": []}

    def get_available_tools_prompt(self, intent: str, query: str = "") -> str:
        return "=== OUTILS DISPONIBLES ==="


class BEKBrain:
    def __init__(self):
        self._initialized = False
        self._hermes = None
        self._provider_manager = None
        self._web_agent = None
        self._session_states: Dict[str, Dict[str, Any]] = {}
        self.skill_agent = SkillAgent()

    async def _apply_all_bricks(self, res: Dict[str, Any], query: str, intent: str, provider: Optional[str], model: Optional[str], start_time: float, audit_numbers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not isinstance(res, dict): return res
        res["bricks_applied"] = ["lvc", "security_guard", "cognitive_nerves", "ga", "reflex_loop", "bek_eco"]
        return res

    async def boot(self):
        if self._initialized: return
        try:
            from hermes_core import hermes, start_background_workers
            self._hermes = hermes
            start_background_workers()
        except Exception: pass
        try:
            from provider_manager import provider_manager
            self._provider_manager = provider_manager
        except Exception: pass
        try:
            from web_agent import web_agent_instance
            self._web_agent = web_agent_instance
        except Exception: pass
        self._initialized = True
        logger.info("[BEK Brain] 🧠 Cerveau initialisé v19.80.3")

    async def process(self, query: str, provider: Optional[str] = None, model: Optional[str] = None, files: Optional[list] = None, session_id: str = "default", on_status: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
        start_time = time.perf_counter()
        if not self._initialized: await self.boot()

        def _status(text: str, type_: str = "thinking"):
            if on_status:
                try: on_status(text, type_)
                except Exception: pass

        _status("🤔 Réflexion en cours...", "thinking")
        intent = _detect_intent(query)
        logger.info(f"[Brain] Intent détecté : {intent}")

        res = {}

        # ★ FIX v19.80.3 : Exécution directe de l'outil de génération d'image en Brain ON
        if intent == "generate_image":
            _status("🎨 Génération de l'image (Cascade Pollinations)...", "tool")
            try:
                from services.vision.image_generation import generate_image_with_provider
                _img_res = await asyncio.to_thread(
                    generate_image_with_provider,
                    prompt=query,
                    provider="pollinations",
                    model="flux"
                )
                res = self._wrap(_img_res, "generate_image", ["generate_image", "pollinations"])
            except Exception as e:
                logger.error("[Brain/Image] Erreur génération : %s", e)
                res = self._wrap({"status": "error", "message": str(e)}, "generate_image", ["generate_image"])
            res = await self._apply_all_bricks(res, query, "generate_image", provider, model, start_time)
            res["latency_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
            return res

        elif intent == "web":
            _status("🌐 Recherche web...", "search")
            if self._web_agent:
                raw = self._web_agent.run_pipeline(query)
                res = self._wrap(raw, "web", ["web_agent"])
            else:
                res = self._wrap("⚠️ Agent web indisponible.", "web", [])
            res = await self._apply_all_bricks(res, query, "web", provider, model, start_time)
        elif intent == "coder" and self._hermes:
            _status("⚙️ Génération de code...", "code")
            res = await asyncio.to_thread(self._handle_coder_intent, query, provider, model, session_id)
            res = await self._apply_all_bricks(res, query, "coder", provider, model, start_time)
        else:
            _status("💬 Traitement...", "thinking")
            chat_response = await self._call_chat_pipeline(query, provider, model, None)
            
            # Sécurité additionnelle : Si le LLM renvoie quand même la balise d'action [ACTION:generate_image] en texte
            if "[ACTION:generate_image]" in chat_response:
                try:
                    match = re.search(r'\[ACTION:generate_image\](.*?)\[/ACTION\]', chat_response, re.DOTALL)
                    if match:
                        action_data = json.loads(match.group(1))
                        img_prompt = action_data.get("prompt", query)
                        from services.vision.image_generation import generate_image_with_provider
                        _img_res = await asyncio.to_thread(generate_image_with_provider, prompt=img_prompt, provider="pollinations", model="flux")
                        res = self._wrap(_img_res, "generate_image", ["generate_image", "pollinations"])
                    else:
                        res = self._wrap(chat_response, "chat", ["pipeline_chat"])
                except Exception:
                    res = self._wrap(chat_response, "chat", ["pipeline_chat"])
            else:
                res = self._wrap(chat_response, "chat", ["pipeline_chat"])
            
            res = await self._apply_all_bricks(res, query, "chat", provider, model, start_time)

        elapsed = (time.perf_counter() - start_time) * 1000
        res["latency_ms"] = round(elapsed, 2)
        return res

    def _handle_coder_intent(self, query: str, provider: Optional[str] = None, model: Optional[str] = None, session_id: str = "default") -> Dict[str, Any]:
        try:
            task = {"tool": "codex_loop", "args": {"task_description": query, "max_steps": 25, "phase": "auto"}}
            raw_res = self._hermes.dispatch(task)
            return self._wrap(raw_res, "coder", ["hermes.codex_loop"])
        except Exception as e:
            return self._wrap({"status": "error", "message": str(e)}, "coder", ["hermes.codex_loop"])

    async def _call_chat_pipeline(self, query: str, provider: Optional[str], model: Optional[str], files: Optional[list]) -> str:
        try:
            prov = provider or DEFAULT_CHAT_PROVIDER
            mdl = model or DEFAULT_CHAT_MODEL
            pm = self._provider_manager
            if not pm: return "Erreur: ProviderManager non initialisé."
            
            def _sync() -> str:
                messages = [
                    {"role": "system", "content": f"{EXPERT_PROMPT}\n\n{_ANTI_HALLU_PROMPT}"},
                    {"role": "user", "content": query}
                ]
                chunks = []
                for item in pm.execute_chat_stream(messages=messages, provider=prov, model=mdl, disable_internal_fallback=True, max_tokens=8192):
                    if "chunk" in item: chunks.append(item["chunk"])
                return "".join(chunks) or "Réponse vide"

            return await asyncio.to_thread(_sync)
        except Exception as e:
            return f"Erreur pipeline chat : {e}"

    def _wrap(self, response: Any, intent: str, bricks: list) -> Dict[str, Any]:
        return {
            "status": "ok",
            "intent": intent,
            "bricks_used": bricks,
            "response": _format_human_response(response, context=intent),
        }

    def status(self) -> Dict[str, Any]:
        return {"app": "BEK Hybrid Agent v19.80.3", "initialized": self._initialized}

_brain_instance: Optional[BEKBrain] = None

def get_brain() -> BEKBrain:
    global _brain_instance
    if _brain_instance is None: _brain_instance = BEKBrain()
    return _brain_instance