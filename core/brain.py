# ==============================================================================
# BEK Hybrid Agent v19 — core/brain.py — v19.69
# ★ v19.69 (2026-11-13) — FIX : Application des briques à TOUTES les actions
#   - Ajout de _apply_all_bricks() appelée à la fin de process()
#   - Couvre chat, web, coder, memory, image, analyze_repo, etc.
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

_ANALYZE_KEYWORDS = ("analyse", "décris", "description", "regarde", "que vois-tu", "identifie", "explique cette image", "lis l'image", "ocr", "describe", "what do you see")
_GENERATE_KEYWORDS = ("génère", "crée", "dessine", "imagine", "fais-moi", "produis", "fabrique", "illustre", "conçois", "peins", "generate", "create", "draw", "paint")
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_DEFAULT_VISION_PROMPT = "Décris cette image en détail."

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
    if any(k in q for k in ["mémoire", "souviens", "rappelle", "recall"]): return "memory"

    meta_keywords = ("puissant", "efficace", "performant", "bon", "mauvais", "utile", "fiable", "sérieux")
    project_keywords = ("projet", "repo", "dépôt", "agent", "hermes", "bek", "système", "framework", "outil")
    has_meta = any(k in q for k in meta_keywords)
    has_project = any(k in q for k in project_keywords)
    if has_meta and has_project:
        logger.info("[Brain] 🎯 Question méta sur un projet → intent web")
        return "web"

    return "chat"

def _detect_phase(query: str) -> tuple:
    q = query.lower()
    if any(k in q for k in _PHASE_PLAN_KEYWORDS): return "plan", 0
    m = _STEP_NUM_RE.search(q)
    if m: return "step", max(0, int(m.group(1)) - 1)
    if any(k in q for k in _PHASE_STEP_KEYWORDS): return "step", -1
    if any(k in q for k in ["codex_loop", "boucle autonome", "agent autonome"]):
        return "auto", 0
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
        
        if status == "error" or "error" in status:
            lines = [
                "### ⚠️ J'ai rencontré un problème",
                "",
                f"**Ce qui s'est passé :** {message or 'Une erreur est survenue pendant l\'exécution.'}",
                "",
                "**Ce que je propose :**",
                "1. Vérifie que le fichier ou le dossier existe et que tu as les permissions.",
                "2. Si le problème persiste, essaie de reformuler ta demande plus simplement.",
            ]
            return "\n".join(lines)
        
        if "history" in response and status == "success":
            history = response.get("history", [])
            lines = [
                "### ✅ Tâche accomplie",
                "",
                f"**{message or 'J\'ai terminé ce que tu m\'as demandé.'}**",
                "",
            ]
            if history:
                lines.append("**Fichiers créés ou modifiés :**")
                for item in history[:10]:
                    try:
                        res = json.loads(item.get("result", "{}"))
                        path = res.get("path", "")
                        chars = res.get("chars", 0)
                        if path:
                            filename = path.split("\\")[-1].split("/")[-1]
                            lines.append(f"- `{filename}` ({chars} caractères)")
                    except Exception:
                        pass
            return "\n".join(lines)
        
        if "results" in response or "data" in response:
            results = response.get("results") or response.get("data") or []
            if isinstance(results, list) and results:
                lines = [f"### 🔍 J'ai trouvé {len(results)} résultat(s)", ""]
                for i, r in enumerate(results[:5], 1):
                    if isinstance(r, dict):
                        title = r.get("title", r.get("name", "Sans titre"))
                        url = r.get("url", r.get("link", ""))
                        snippet = (r.get("snippet", r.get("content", "")) or "")[:150]
                        lines.append(f"**{i}. {title}**")
                        if url: lines.append(f"   🔗 {url}")
                        if snippet: lines.append(f"   _{snippet}..._")
                        lines.append("")
                return "\n".join(lines)
        
        for key in ("text", "content", "response", "result", "formatted_text"):
            if key in response and response[key]:
                return str(response[key])
        
        if message:
            return message
        
        return f"### 📋 Résultat\n\n```\n{json.dumps(response, indent=2, ensure_ascii=False)[:1500]}\n```"
    
    if isinstance(response, list):
        lines = [f"### 📋 J'ai {len(response)} élément(s)", ""]
        for item in response[:10]:
            lines.append(f"- {str(item)[:200]}")
        return "\n".join(lines)
    
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
                        data = json.load(f)
                        all_skills.extend(data)
                except Exception as e:
                    logger.error(f"Erreur chargement index {p}: {e}")
        return all_skills

    def _detect_category(self, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["code", "fix", "refactor", "bug", "optimise"]): return "CODE"
        if any(w in q for w in ["security", "audit", "vulnerable", "pirate"]): return "SECURITY"
        if any(w in q for w in ["data", "database", "sql", "migration"]): return "DATA"
        if any(w in q for w in ["agent", "orchestre", "team", "skill"]): return "AGENT"
        return "OTHER"

    def get_action_plan(self, query: str) -> Dict[str, Any]:
        category = self._detect_category(query)
        q_words = query.lower().split()
        matched = []
        for skill in self.skills_db:
            if skill.get("category") != category: continue
            text = f"{skill.get('name', '')} {skill.get('description', '')}".lower()
            score = sum(1 for w in q_words if w in text)
            if score > 0: matched.append((score, skill))
        matched.sort(key=lambda x: x[0], reverse=True)
        return {"skills": [m[1] for m in matched[:3]]}

    def get_available_tools_prompt(self, intent: str, query: str = "") -> str:
        try:
            from hermes_core import hermes
        except Exception:
            return "Liste des outils indisponible."

        TOOL_DESCRIPTIONS = {
            "read_file": ("Lire un fichier", "FILE"), "write_file": ("Écrire un fichier", "FILE"),
            "append_file": ("Ajouter du contenu", "FILE"), "edit_file": ("Éditer un fichier", "FILE"),
            "create_dir": ("Créer un dossier", "FILE"), "grep": ("Chercher une regex", "FILE"),
            "glob_files": ("Lister par motif", "FILE"), "ls": ("Lister un dossier", "FILE"),
            "bash": ("Exécuter une commande", "FILE"), "search_skills": ("Chercher dans les skills", "SKILLS"),
            "git_clone": ("Cloner un dépôt", "FILE"), "analyze_architecture": ("Analyser l'architecture", "ANALYZE"),
            "python_analyze_file": ("Analyser un fichier .py", "ANALYZE"), "python_analyze_directory": ("Analyser un dossier .py", "ANALYZE"),
            "python_save_report": ("Générer un rapport Markdown", "ANALYZE"), "rea_analyze_binary": ("Analyser un binaire", "REA"),
            "rea_analyze_javascript": ("Analyser du JS", "REA"), "web_search": ("Recherche web", "WEB"),
            "web_search_docs": ("Recherche docs", "WEB"), "web_agent_scrape": ("Scraper une URL", "WEB"),
            "web_agent_traced": ("Pipeline web", "WEB"), "headless_render": ("Rendre avec JS", "WEB"),
            "headless_scrape": ("Scraper après JS", "WEB"), "headless_search": ("Recherche headless", "WEB"),
            "ga_get_best": ("Meilleur gène", "GA"), "ga_record_result": ("Enregistrer fitness", "GA"),
            "ga_evolve": ("Forcer évolution", "GA"), "cognitive_critique": ("Critiquer", "COGNITIVE"),
            "cognitive_ground": ("Vérifier faits", "COGNITIVE"), "guardian_status": ("Statut guardian", "SECURITY"),
            "guardian_audit_log": ("Logs sécurité", "SECURITY"), "router_route": ("Router requête", "ROUTER"),
            "mcp_list_tools": ("Lister MCP", "MCP"), "mcp_execute": ("Exécuter MCP", "MCP"),
            "generate_image": ("Générer image", "VISION"), "edit_image": ("Éditer image", "VISION"),
            "generate_video": ("Générer vidéo", "VISION"), "edit_video": ("Éditer vidéo", "VISION"),
            "extend_video": ("Étendre vidéo", "VISION"), "extend_video_multiple": ("Étendre en clips", "VISION"),
            "generate_subtitles": ("Générer sous-titres", "VISION"), "burn_subtitles": ("Incruster sous-titres", "VISION"),
            "save_memory": ("Mémoriser", "MEMORY"), "hindsight_query": ("Interroger Hindsight", "MEMORY"),
            "hindsight_recall": ("Récupérer souvenirs", "MEMORY"), "submit_feedback": ("Enregistrer feedback", "MEMORY"),
            "codex_agent": ("Générer code (1 passe)", "CODEX"), "codex_editor": ("Corriger fichier", "CODEX"),
            "codex_loop": ("Boucle multi-étapes", "CODEX"), "orchestrate": ("Orchestrer agents", "ORCH"),
            "tmux_start_task": ("Lancer tâche background", "ORCH"),
        }

        CATEGORY_LABELS = {
            "FILE": "🗂️ FICHIERS & CODE", "ANALYZE": "🐍 ANALYSE PYTHON", "REA": "🔍 REVERSE ENGINEERING",
            "WEB": "🌐 WEB", "SKILLS": "📚 SKILLS", "GA": "🧬 BEK-GA", "COGNITIVE": "🛡️ COGNITIF",
            "SECURITY": "🔒 SÉCURITÉ", "ROUTER": "🔀 ROUTER", "MCP": "🔌 MCP", "VISION": "🎨 VISION",
            "MEMORY": "🧠 MÉMOIRE", "CODEX": "🤖 CODEX", "ORCH": "🎼 ORCHESTRATION",
        }

        available = set(hermes.tools.keys())
        grouped: Dict[str, List[str]] = {cat: [] for cat in CATEGORY_LABELS}

        for name in available:
            canonical = name[4:] if name.startswith("mcp_") else name
            desc_cat = TOOL_DESCRIPTIONS.get(canonical)
            if desc_cat:
                desc, cat = desc_cat
                risk = getattr(hermes.tools[name], "risk_level", "L1")
                grouped[cat].append(f"  - `{name}` (risque:{risk}) : {desc}")
            else:
                risk = getattr(hermes.tools[name], "risk_level", "L1")
                grouped.setdefault("OTHER", []).append(f"  - `{name}` (risque:{risk})")

        lines = ["=== ⚠️ OUTILS DISPONIBLES ===", "",
                 "RÈGLE : Utilise [ACTION:nom_outil]{...}[/ACTION] pour agir.", ""]

        for cat, label in CATEGORY_LABELS.items():
            tools = grouped.get(cat, [])
            if tools:
                lines.append(f"=== {label} ===")
                lines.extend(tools)
                lines.append("")

        if grouped.get("OTHER"):
            lines.append("=== 🔧 AUTRES OUTILS ===")
            lines.extend(grouped["OTHER"])
            lines.append("")

        return "\n".join(lines)


def _normalize_github_repo(owner: str, repo_raw: str) -> Tuple[str, str]:
    repo_name = (repo_raw or "").strip().strip('.').strip()
    repo_name = re.sub(r'[^A-Za-z0-9._-]', '-', repo_name).strip('.-_')
    if not repo_name: repo_name = "repo"
    return owner, repo_name


class BEKBrain:
    def __init__(self):
        self._initialized = False
        self._hermes = None
        self._provider_manager = None
        self._orchestrator = None
        self._web_agent = None
        self._audio = None
        self._nerfs_status: Dict[str, Any] = {}
        self._session_states: Dict[str, Dict[str, Any]] = {}
        self.skill_agent = SkillAgent()

    # ══════════════════════════════════════════════════════════════════════
    # ★ v19.69 : Wrapper universel pour appliquer les briques à toutes les actions
    # ══════════════════════════════════════════════════════════════════════
    async def _apply_all_bricks(
        self,
        res: Dict[str, Any],
        query: str,
        intent: str,
        provider: Optional[str],
        model: Optional[str],
        start_time: float,
        audit_numbers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Applique les briques BEK à n'importe quel résultat (chat, web, code, image, etc.).
        Chaque brique est isolée dans un try/except pour ne jamais casser le flux.
        """
        if not isinstance(res, dict):
            return res

        response_text = str(res.get("response", "") or "")
        if not response_text.strip():
            return res

        # ─── 1. BEK-LVC : compression du résultat (si > 6000 chars) ───
        if len(response_text) > 6000:
            try:
                from bek_core.eco.optimizer import BekEcoOptimizer
                optimizer = BekEcoOptimizer()
                if hasattr(optimizer, "compress_text"):
                    compressed = optimizer.compress_text(response_text, max_chars=6000)
                    if len(compressed) < len(response_text):
                        logger.info(
                            "[Bricks/LVC] 🗜️ %s : %d → %d chars",
                            intent, len(response_text), len(compressed),
                        )
                        response_text = compressed
                        res["response"] = compressed
            except Exception as e:
                logger.debug("[Bricks/LVC] indisponible : %s", e)

        # ─── 2. Security Guard (si action sensible) ───
        try:
            from security_guard import security_guard
            _guard_result = security_guard.sanitize_secrets(response_text)
            if _guard_result != response_text:
                logger.warning("[Bricks/Security] 🔒 Secrets détectés dans la réponse → redacted")
                response_text = _guard_result
                res["response"] = _guard_result
        except Exception as e:
            logger.debug("[Bricks/Security] indisponible : %s", e)

        # ─── 3. Cognitive Nerves (anti-hallucination Swarm + Grounding) ───
        if len(response_text) > 100 and not _is_analysis_query(response_text):
            try:
                from nerves.cognitive_nerves import run_cognitive_pipeline
                logger.info("[Bricks/Cognitive] 🛡️ Vérification anti-hallucination pour %s", intent)
                cognitive_check = await asyncio.to_thread(
                    run_cognitive_pipeline,
                    draft=response_text,
                    original_query=query,
                    provider=provider or "gemini",
                    model=model or "gemini-3.8-flash",
                    enable_swarm=True,
                    enable_grounding=True,
                )
                if isinstance(cognitive_check, dict):
                    if not cognitive_check.get("passed", True):
                        reason = cognitive_check.get("reason", "Faits non vérifiés")
                        logger.warning("[Bricks/Cognitive] ⚠️ %s : %s", intent, reason)
                        response_text += f"\n\n⚠️ **Note anti-hallucination** : {reason}"
                        res["response"] = response_text
                    else:
                        logger.info("[Bricks/Cognitive] ✅ %s validé par les Cognitive Nerves", intent)
            except Exception as e:
                logger.warning("[Bricks/Cognitive] échoué pour %s : %s", intent, e)

        # ─── 4. Validation chiffrée (si audit_numbers fourni) ───
        if audit_numbers:
            try:
                from bek_eval_guard import validate_cited_numbers
                num_check = validate_cited_numbers(response_text, audit_numbers)
                if not num_check.get("passed"):
                    logger.warning(
                        "[Bricks/EvalGuard] ⚠️ Chiffres suspects pour %s : %s",
                        intent, num_check["suspicious_numbers"]
                    )
                    response_text += (
                        f"\n\n⚠️ *Chiffres non vérifiés : "
                        f"{num_check['suspicious_numbers']} (absents de l'audit source)*"
                    )
                    res["response"] = response_text
            except Exception as e:
                logger.debug("[Bricks/EvalGuard] indisponible : %s", e)

        # ─── 5. BEK-GA : fitness ───
        try:
            from nerves.ga_nerves import get_ga_engine
            engine = get_ga_engine()
            best_gene = engine.select_best_gene()
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            tokens_est = len(response_text) // 4
            engine.calculate_fitness(best_gene, True, elapsed_ms, tokens_est)
            logger.info("[Bricks/GA] 🧬 fitness enregistré pour %s", best_gene.gene_id)
        except Exception as e:
            logger.debug("[Bricks/GA] indisponible : %s", e)

        # ─── 6. ReflexLoop : enregistrer l'épisode ───
        try:
            from services.episode_logger import log_episode as _log_ep
            _log_ep(
                action=intent,
                parameters={"query": query, "provider": provider},
                status="success",
                message=f"Bricks appliquées: {len(response_text)} chars",
                latency_ms=(time.perf_counter() - start_time) * 1000,
                source="brain_bricks",
            )
            logger.info("[Bricks/Reflex] 🔁 épisode enregistré pour %s", intent)
        except Exception as e:
            logger.debug("[Bricks/Reflex] indisponible : %s", e)

        # ─── 7. BEK-ECO : cache ───
        try:
            from bek_core.eco.optimizer import BekEcoOptimizer
            optimizer = BekEcoOptimizer()
            cache_key = optimizer._cache_key(query)
            if len(response_text) > 100:
                optimizer.cache_set(cache_key, response_text, query=query)
                logger.info("[Bricks/ECO] 💾 synthèse cachée pour %s", intent)
        except Exception as e:
            logger.debug("[Bricks/ECO] indisponible : %s", e)

        res["bricks_applied"] = [
            "lvc", "security_guard", "cognitive_nerves",
            "bek_eval_guard", "ga", "reflex_loop", "bek_eco",
        ]
        return res

    def _get_ga_prompt(self) -> str:
        try:
            from nerves.ga_nerves import get_ga_engine
            best = get_ga_engine().select_best_gene()
            return best.prompt_template
        except Exception:
            return "Exécute la tâche de manière concise et directe."

    def _record_ga_fitness(self, query: str, res: Dict[str, Any], elapsed_ms: float):
        try:
            from nerves.ga_nerves import get_ga_engine
            engine = get_ga_engine()
            best_gene = engine.select_best_gene()
            tokens_est = len(str(query)) // 4 + len(str(res.get("response", ""))) // 4
            success = res.get("status") == "ok"
            engine.calculate_fitness(best_gene, success, elapsed_ms, tokens_est)
        except Exception:
            pass

    def _observe_economics(self, query: str, intent: str) -> Optional[str]:
        try:
            from bek_core.eco.optimizer import BekEcoOptimizer
            optimizer = BekEcoOptimizer()
            cache_key = optimizer._cache_key(query)
            cached = optimizer.cache_get(cache_key)
            if cached and cached.get("value"): return cached["value"]
            return None
        except Exception: return None

    def _get_session_state(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._session_states:
            self._session_states[session_id] = {"plan": [], "step": 0, "goal": "", "completed": False}
        return self._session_states[session_id]

    def _normalize_hermes_result(self, res: Any) -> Dict[str, Any]:
        if isinstance(res, dict):
            if "results" in res and isinstance(res["results"], dict):
                for task_res in res["results"].values():
                    if isinstance(task_res, dict) and "data" in task_res:
                        return task_res["data"] if isinstance(task_res["data"], dict) else {"result": task_res["data"]}
            return res
        if hasattr(res, "success") and hasattr(res, "data"):
            if res.success: return res.data if isinstance(res.data, dict) else {"result": res.data}
            return {"status": "error", "message": getattr(res, "error", "Erreur inconnue")}
        return {"result": str(res)}

    async def boot(self):
        if self._initialized: return
        try:
            from hermes_core import hermes, start_background_workers
            self._hermes = hermes
            start_background_workers()
        except Exception as e: logger.debug("[BEK Brain] hermes_core non chargé : %s", e)
        try:
            from provider_manager import provider_manager
            self._provider_manager = provider_manager
        except Exception as e: logger.debug("[BEK Brain] provider_manager non chargé : %s", e)
        try:
            from bek_orchestrator import bek_orchestrator
            self._orchestrator = bek_orchestrator
        except Exception as e: logger.debug("[BEK Brain] bek_orchestrator non chargé : %s", e)
        try:
            from web_agent import web_agent_instance
            self._web_agent = web_agent_instance
        except Exception as e: logger.debug("[BEK Brain] web_agent non chargé : %s", e)

        self._initialized = True
        logger.info("[BEK Brain] 🧠 Cerveau initialisé v19.69 (FIX briques universelles)")

    async def shutdown(self):
        try:
            from event_bus import shutdown_event_bus_sync
            shutdown_event_bus_sync()
        except Exception: pass
        try:
            from hindsight_memory import hindsight_close
            hindsight_close()
        except Exception: pass

    async def _refine_image_prompt(self, user_query: str) -> str:
        return user_query.strip()

    async def _handle_fix_self(self) -> Dict[str, Any]:
        try:
            if self._hermes and "codex_loop" in self._hermes.tools:
                res = await asyncio.to_thread(self._call_hermes_tool, "codex_loop", {"task_description": "Analyse les logs récents de BEK, corrige les erreurs et auto-répare le système.", "max_steps": 10, "phase": "auto"})
                return self._wrap(res, "fix_self", ["hermes.codex_loop"])
        except Exception as e: logger.error("[Brain] Erreur fix_self : %s", e)
        return self._wrap("⚠️ Module d'auto-réparation indisponible.", "fix_self", ["hermes.codex_loop"])

    async def process(self, query: str, provider: Optional[str] = None, model: Optional[str] = None, files: Optional[list] = None, session_id: str = "default", on_status: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
        start_time = time.perf_counter()
        if not self._initialized: await self.boot()

        def _status(text: str, type_: str = "thinking"):
            if on_status:
                try: on_status(text, type_)
                except Exception: pass

        _status("🤔 Réflexion en cours...", "thinking")

        if files and len(files) > 0:
            _status("📂 Analyse des fichiers...", "analyze")
            res = await self._process_files(query, files, provider, model)
            elapsed = (time.perf_counter() - start_time) * 1000
            res["latency_ms"] = round(elapsed, 2)
            self._record_ga_fitness(query, res, elapsed)
            # ★ v19.69 : briques universelles
            res = await self._apply_all_bricks(res, query, "files", provider, model, start_time)
            return res

        _github_match = _GITHUB_URL_RE.search(query)
        if _github_match:
            intent = "analyze_repo"
        else:
            intent = _detect_intent(query)
        logger.info(f"[Brain] Intent détecté : {intent}")

        plan = self.skill_agent.get_action_plan(query)
        if plan["skills"]:
            logger.info(f"[Brain] 🧠 SkillAgent : {[s['name'] for s in plan['skills']]}")

        cached_response = self._observe_economics(query, intent)
        if cached_response:
            _status("💾 Réponse depuis le cache...", "done")
            res = self._wrap(cached_response, intent, ["bek_eco_cache"])
            res["latency_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
            return res

        res = {}

        if intent == "analyze_repo" and _github_match:
            github_url_match = _github_match
            owner_raw = github_url_match.group(1)
            repo_raw = github_url_match.group(2)
            owner, repo_name = _normalize_github_repo(owner_raw, repo_raw)
            repo_url = f"https://github.com/{owner}/{repo_name}"
            logger.info("[Brain] 🎯 URL GitHub détectée → clone + analyse (repo=%s)", repo_name)
            _status(f"🐙 Clonage de {repo_name}...", "tool")

            try:
                try:
                    from bek_core import BekCPU
                    route_info = BekCPU.execute("BEK-REX", "bek_rex_route", query=f"analyse repo {repo_name}")
                    logger.info("[Brain/GitHub] 🏛️ BEK-REX routé : %s (conf: %.2f)",
                                route_info.get("tier"), route_info.get("confidence", 0))
                except Exception as e:
                    logger.debug("[Brain/GitHub] BEK-REX indisponible : %s", e)

                clone_result = await asyncio.to_thread(
                    self._call_hermes_tool, "git_clone", {"url": repo_url}
                )
                clone_str = str(clone_result)
                logger.info("[Brain] Clonage : %s", clone_str[:150])

                from core.paths import WORKSPACE_DIR
                repo_dir = None
                if isinstance(clone_result, dict) and clone_result.get("status") == "success":
                    repo_dir = clone_result.get("path")
                if not repo_dir:
                    external_dir = os.path.join(str(WORKSPACE_DIR), "external")
                    candidates = []
                    if os.path.isdir(external_dir):
                        for d in os.listdir(external_dir):
                            if d.rstrip(".").strip() == repo_name and os.path.isdir(os.path.join(external_dir, d)):
                                candidates.append(d)
                    repo_dir = f"external/{candidates[0]}" if candidates else f"external/{repo_name}"

                full_repo_path = os.path.join(str(WORKSPACE_DIR), repo_dir)

                if not os.path.exists(full_repo_path):
                    logger.warning("[Brain] Échec : dossier %s absent", repo_dir)
                    res = self._wrap(f"⚠️ Le dépôt n'a pas pu être cloné : {clone_str}", "analyze_repo", ["git_clone"])
                else:
                    logger.info("[Brain] 📂 Repo trouvé : %s", repo_dir)
                    _status("📊 Génération du rapport technique...", "analyze")

                    report_result = await asyncio.to_thread(
                        self._call_hermes_tool, "mcp_python_save_report",
                        {"dir_path": repo_dir, "output_name": f"audit_{repo_name}"}
                    )
                    _status("🏛️ Analyse architecturale...", "analyze")
                    arch_result = await asyncio.to_thread(
                        self._call_hermes_tool, "analyze_architecture",
                        {"dir_path": repo_dir}
                    )

                    audit_numbers_block = ""
                    audit_numbers_dict = {}
                    try:
                        _rr = report_result if isinstance(report_result, dict) else {}
                        _files_n = _rr.get("files_analyzed") or _rr.get("files") or "?"
                        _lines_n = _rr.get("total_lines") or "?"
                        _warn_list = _rr.get("warnings", [])
                        _warn_n = len(_warn_list) if isinstance(_warn_list, list) else "?"
                        audit_numbers_dict = {
                            "files_analyzed": _files_n if isinstance(_files_n, int) else 0,
                            "total_lines": _lines_n if isinstance(_lines_n, int) else 0,
                            "warnings": _warn_n if isinstance(_warn_n, int) else 0,
                        }
                        audit_numbers_block = (
                            "\n=== 🔢 CHIFFRES OFFICIELS DE L'AUDIT (NE PAS MODIFIER) ===\n"
                            f"- fichiers analysés : {_files_n}\n"
                            f"- lignes totales : {_lines_n}\n"
                            f"- anomalies détectées : {_warn_n}\n"
                            "RÈGLE STRICTE : si tu cites un chiffre, il DOIT venir de cette liste. "
                            "Sinon écris « non mesuré » au lieu d'inventer.\n"
                        )
                    except Exception as _ne:
                        logger.debug("[Brain] Extraction chiffres audit échouée : %s", _ne)

                    _status("🗜️ Compression LVC du rapport...", "analyze")
                    report_str = str(report_result)
                    arch_str = str(arch_result)
                    report_compressed = report_str
                    arch_compressed = arch_str
                    try:
                        from bek_core.eco.optimizer import BekEcoOptimizer
                        optimizer = BekEcoOptimizer()
                        if hasattr(optimizer, "compress_text"):
                            report_compressed = optimizer.compress_text(report_str, max_chars=8000)
                            arch_compressed = optimizer.compress_text(arch_str, max_chars=4000)
                        else:
                            if len(report_str) > 8000:
                                report_compressed = report_str[:8000] + "\n...[tronqué par LVC]"
                            if len(arch_str) > 4000:
                                arch_compressed = arch_str[:4000] + "\n...[tronqué par LVC]"
                        logger.info(
                            "[Brain/GitHub] 🗜️ BEK-LVC : rapport %d → %d chars | archi %d → %d chars",
                            len(report_str), len(report_compressed),
                            len(arch_str), len(arch_compressed),
                        )
                    except Exception as _lvc_err:
                        logger.warning("[Brain/GitHub] BEK-LVC échoué : %s", _lvc_err)

                    _status("🧠 Synthèse LLM de l'audit...", "thinking")
                    synthesis_prompt = (
                        f"Tu es BEK, un architecte logiciel senior. Voici les données d'analyse du repo {repo_url} :\n\n"
                        f"=== RAPPORT TECHNIQUE (compressé par LVC) ===\n{report_compressed}\n\n"
                        f"=== RAPPORT STRATÉGIQUE ===\n{arch_compressed}\n\n"
                        f"{audit_numbers_block}\n"
                        f"=== TA MISSION ===\n"
                        f"Fais-moi une synthèse structurée avec :\n"
                        f"1. Les 3 points forts majeurs du projet.\n"
                        f"2. Les 3 points faibles critiques à corriger en priorité.\n"
                        f"3. Un plan d'action détaillé en 5 étapes pour corriger les problèmes.\n"
                        f"Sois direct, concret, et utilise le format Markdown.\n"
                        f"IMPORTANT : ne cite AUCUN chiffre (nombre de fichiers, de lignes, de doublons) "
                        f"qui ne soit pas explicitement dans les rapports ci-dessus. "
                        f"Si tu n'es pas sûr, dis « non mesuré »."
                    )

                    synthesis = await self._call_chat_pipeline(
                        synthesis_prompt, provider, model, None
                    )

                    synthesis = self._validate_synthesis_numbers(synthesis, audit_numbers_dict)

                    res = self._wrap(
                        f"📊 **Analyse Stratégique du Repo**\n\n{synthesis}",
                        "analyze_repo",
                        ["git_clone", "python_save_report", "analyze_architecture",
                         "bek_rex", "bek_lvc", "bek_ga", "bek_eco",
                         "provider_manager", "cognitive_nerves", "reflex_loop", "bek_eval_guard"]
                    )
                    # ★ v19.69 : on appelle _apply_all_bricks (couvre Cognitive, GA, Reflex, etc.)
                    res = await self._apply_all_bricks(
                        res, query, "analyze_repo", provider, model, start_time,
                        audit_numbers=audit_numbers_dict,
                    )
            except Exception as e:
                logger.error("[Brain] Erreur analyse GitHub : %s", e)
                res = self._wrap(f"❌ Erreur : {e}", "analyze_repo", ["git_clone"])
        
        elif intent == "web":
            _status("🌐 Recherche web en cours...", "search")
            query_for_web = query
            
            if self._hermes and "web_sync" in self._hermes.tools:
                try:
                    logger.info("[Brain/Web] 🔍 web_sync avec requête pure : %r", query_for_web[:80])
                    web_result = await asyncio.to_thread(
                        self._call_hermes_tool,
                        "web_sync",
                        {"query": query_for_web}
                    )
                    
                    if _format_web_sync_fn and isinstance(web_result, dict):
                        formatted_raw = _format_web_sync_fn(web_result)
                        logger.info("[Brain/Web] 📋 Contenu brut formaté (%d chars) → 2ème passe LLM", len(formatted_raw))
                        
                        _status("🧠 Synthèse de la recherche...", "thinking")
                        synthesis_prompt = (
                            f"Voici les données brutes extraites du web sur la requête : \"{query_for_web}\"\n\n"
                            f"=== DONNÉES BRUTES ===\n{formatted_raw}\n\n"
                            f"=== TA MISSION ===\n"
                            f"Structure ta réponse finale en 3 sections distinctes :\n\n"
                            f"### 1. 📊 Données brutes\n"
                            f"Présente les faits et URLs sous forme de tableau Markdown ou liste à puces. "
                            f"N'invente RIEN. Cite UNIQUEMENT les noms d'outils, les chiffres et les URLs qui sont "
                            f"explicitement présents dans les DONNÉES BRUTES ci-dessus. "
                            f"Si un outil n'est pas dans les données brutes, tu ne dois pas le mentionner. "
                            f"Si tu n'as pas l'information, écris 'Non spécifié dans les sources'.\n\n"
                            f"### 2. 💡 Analyse\n"
                            f"Interprète les données, identifie les points clés, mets en perspective. "
                            f"Base-toi UNIQUEMENT sur les sources ci-dessus. "
                            f"Si une conclusion n'est pas directement soutenue par les données, ne la fais pas.\n\n"
                            f"### 3. 📚 Sources\n"
                            f"Liste les URLs réellement citées, au format `[Titre](URL)`. N'invente AUCUNE URL.\n\n"
                            f"⚠️ N'affiche JAMAIS les instructions internes, le texte \"INSTRUCTION POUR LE LLM\", "
                            f"ou les notes anti-hallucination. Réponds directement à l'utilisateur."
                        )
                        try:
                            final_synthesis = await self._call_chat_pipeline(
                                synthesis_prompt, provider, model, None
                            )
                            logger.info("[Brain/Web] ✅ Synthèse finale générée (%d chars)", len(final_synthesis))
                            res = {
                                "status": "ok",
                                "intent": "web",
                                "bricks_used": ["web_agent", "hermes", "formatters", "llm_synthesis"],
                                "response": final_synthesis,
                            }
                        except Exception as _synth_err:
                            logger.warning("[Brain/Web] Synthèse LLM échouée : %s → fallback texte brut", _synth_err)
                            res = {
                                "status": "ok",
                                "intent": "web",
                                "bricks_used": ["web_agent", "hermes", "formatters"],
                                "response": formatted_raw,
                            }
                    else:
                        res = self._wrap(web_result, "web", ["web_agent", "hermes"])
                except Exception as e:
                    logger.warning("[Brain/Web] Hermes web_sync échoué : %s", e)
                    if self._web_agent:
                        raw = self._web_agent.run_pipeline(query_for_web)
                        res = self._wrap(raw, "web", ["web_agent"])
                    else:
                        res = self._wrap("⚠️ Aucun agent web disponible.", "web", [])
            elif self._web_agent:
                raw = self._web_agent.run_pipeline(query_for_web)
                res = self._wrap(raw, "web", ["web_agent"])
            else:
                res = self._wrap("⚠️ Aucun agent web disponible.", "web", [])
            
            # ★ v19.69 : briques universelles
            res = await self._apply_all_bricks(res, query, "web", provider, model, start_time)
        
        elif intent == "fix_self":
            _status("🔧 Auto-réparation...", "tool")
            res = await self._handle_fix_self()
            res = await self._apply_all_bricks(res, query, "fix_self", provider, model, start_time)
        
        elif intent == "generate_image" and self._hermes:
            _status("🎨 Génération de l'image...", "tool")
            refined_prompt = await self._refine_image_prompt(query)
            try:
                from services.vision.image_generation import generate_image_with_provider
                _img_res = await asyncio.to_thread(
                    generate_image_with_provider,
                    prompt=refined_prompt,
                    provider="gemini",
                    model="gemini-2.5-flash-image"
                )
                res = self._wrap(_img_res, "vision_generate", ["generate_image", "gemini"])
            except Exception as _img_err:
                logger.error("[Brain/Image] Erreur : %s", _img_err)
                res = self._wrap(f"⚠️ Erreur génération image : {_img_err}", "vision_generate", ["generate_image"])
            # ★ v19.69 : briques universelles
            res = await self._apply_all_bricks(res, query, "generate_image", provider, model, start_time)
        
        elif intent == "coder" and self._hermes:
            _status("⚙️ Génération de code...", "code")
            res = await asyncio.to_thread(self._handle_coder_intent, query, provider, model, session_id)
            res = await self._apply_all_bricks(res, query, "coder", provider, model, start_time)
        elif intent == "memory":
            _status("🧠 Recherche en mémoire...", "analyze")
            res = self._wrap(await self._handle_memory(query), "memory", ["hindsight_memory"])
            res = await self._apply_all_bricks(res, query, "memory", provider, model, start_time)
        else:
            _status("💬 Traitement de la requête...", "thinking")
            res = self._wrap(await self._call_chat_pipeline(query, provider, model, None), "chat", ["pipeline_chat"])
            # ★ v19.69 : briques universelles pour le chat
            res = await self._apply_all_bricks(res, query, "chat", provider, model, start_time)

        if intent != "web":
            try:
                from bek_core.eco.optimizer import BekEcoOptimizer
                optimizer = BekEcoOptimizer()
                cache_key = optimizer._cache_key(query)
                response_text = res.get("response", "")
                if response_text and len(str(response_text)) > 100:
                    optimizer.cache_set(cache_key, response_text, query=query)
            except Exception: pass

        elapsed = (time.perf_counter() - start_time) * 1000
        res["latency_ms"] = round(elapsed, 2)
        self._record_ga_fitness(query, res, elapsed)
        return res

    def _validate_synthesis_numbers(self, synthesis: str, source: Any) -> str:
        try:
            from bek_eval_guard import evaluate_response_quality, validate_cited_numbers
        except ImportError:
            logger.debug("[Brain] bek_eval_guard indisponible, validation chiffrée ignorée")
            return synthesis

        try:
            guard = evaluate_response_quality("synthèse audit repo", synthesis)
            if not guard.get("passed"):
                logger.warning("[Brain] ⚠️ bek_eval_guard a rejeté la synthèse : %s", guard.get("reason"))
                synthesis += f"\n\n⚠️ *Vérification partielle : {guard.get('reason')}*"

            if isinstance(source, dict) and source:
                num_check = validate_cited_numbers(synthesis, source)
                if not num_check.get("passed"):
                    logger.warning(
                        "[Brain] ⚠️ Chiffres suspects dans la synthèse : %s (officiels : %s)",
                        num_check["suspicious_numbers"], num_check["official_numbers"]
                    )
                    synthesis += (
                        f"\n\n⚠️ *Chiffres non vérifiés dans cette synthèse : "
                        f"{num_check['suspicious_numbers']} (absents de l'audit source)*"
                    )
        except Exception as _ge:
            logger.debug("[Brain] Validation chiffrée échouée : %s", _ge)

        return synthesis

    def _handle_coder_intent(self, query: str, provider: Optional[str] = None, model: Optional[str] = None, session_id: str = "default") -> Dict[str, Any]:
        q_lower = query.lower()
        file_match = re.search(r"\b([a-zA-Z0-9_\-]+\.(?:py|js|ts|html|css|java|cpp|c|php|rs|go))\b", query)
        target_file = file_match.group(1) if file_match else None
        phase, step_num = _detect_phase(query)
        state = self._get_session_state(session_id)
        if phase == "step" and step_num == -1: step_num = state["step"]

        if phase in ("plan", "step"):
            tool_to_use = "codex_loop"
            forced_phase = phase
            if phase == "plan" and not any(k in q_lower for k in ["fais un plan", "mode plan"]):
                forced_phase = "auto"
            params: Dict[str, Any] = {"task_description": query, "max_steps": 25, "phase": forced_phase}
        elif "codex_editor" in q_lower or "corrige" in q_lower or "modifie" in q_lower:
            tool_to_use = "codex_editor"; params = {"task_description": query, "target_file": target_file}
        else:
            tool_to_use = "codex_loop"; params = {"task_description": query, "max_steps": 25, "phase": "auto"}

        if provider: params["provider"] = provider
        if model: params["model"] = model

        try:
            task = {"tool": tool_to_use, "args": params}
            raw_hermes_res = self._hermes.dispatch(task)
            inner_data = self._normalize_hermes_result(raw_hermes_res)
        except Exception as e: return self._wrap({"status": "error", "message": str(e)}, "coder", [f"hermes.{tool_to_use}"])

        return self._wrap(inner_data or raw_hermes_res, "coder", [f"hermes.{tool_to_use}"])

    async def _call_chat_pipeline(self, query: str, provider: Optional[str], model: Optional[str], files: Optional[list]) -> str:
        try:
            is_analysis = _is_analysis_query(query)
            if provider:
                prov = provider
                mdl = model or DEFAULT_CHAT_MODEL
            elif model:
                prov = DEFAULT_CHAT_PROVIDER
                mdl = model
            elif is_analysis:
                prov = ANALYSIS_PROVIDER
                mdl = ANALYSIS_MODEL
            else:
                prov = DEFAULT_CHAT_PROVIDER
                mdl = DEFAULT_CHAT_MODEL

            logger.info("[Brain/ChatPipeline] 🎯 LLM cible : provider=%s model=%s (choix user=%s)", prov, mdl, "oui" if provider else "non")

            tools_prompt = self.skill_agent.get_available_tools_prompt(_detect_intent(query), query=query)
            ga_prompt = self._get_ga_prompt()

            system_extra = (
                f"{ga_prompt}\n\n"
                f"{_ANTI_HALLU_PROMPT}\n\n"
                f"=== OUTILS DISPONIBLES ===\n{tools_prompt}\n\n"
                f"RÈGLE : si l'utilisateur te salue, discute, ou pose une question générale, "
                f"réponds en TEXTE NATUREL. N'affiche JAMAIS de JSON brut comme "
                f'{{"thought": "...", "tool": "", "args": {{}}}}.\n'
                f"Si tu dois appeler un outil, utilise [ACTION:nom_outil]{{...}}[/ACTION]."
            )

            pm = self._provider_manager
            if not pm:
                return "Erreur: ProviderManager non initialisé."
            
            def _sync_generate() -> str:
                messages = [
                    {"role": "system", "content": system_extra},
                    {"role": "user", "content": query}
                ]
                chunks = []
                for item in pm.execute_chat_stream(
                    messages=messages, 
                    provider=prov, 
                    model=mdl, 
                    disable_internal_fallback=True, 
                    max_tokens=8192
                ):
                    if "chunk" in item: 
                        chunks.append(item["chunk"])
                    elif "error" in item: 
                        return f"[Erreur LLM: {item['error']}]"
                return "".join(chunks) or "Réponse vide"

            return await asyncio.to_thread(_sync_generate)
            
        except Exception as e: 
            return f"Erreur pipeline chat : {repr(e)}"

    def _call_hermes_tool(self, tool_name: str, params: Dict) -> Any:
        try:
            task = {"tool": tool_name, "args": params}
            res = self._hermes.dispatch(task)
            return self._normalize_hermes_result(res)
        except Exception as e: return {"status": "error", "message": str(e)}

    async def _handle_memory(self, query: str) -> str:
        try:
            from memory_coordinator import coordinate_memories_async
            memory = await asyncio.wait_for(coordinate_memories_async(query), timeout=15.0)
            context = getattr(memory, 'context', '')
            if isinstance(memory, dict): context = memory.get('context', '')
            if context and context.strip(): return context.strip()
        except Exception: pass
        return 'Aucun souvenir trouvé.'

    def _wrap(self, response: Any, intent: str, bricks: list) -> Dict[str, Any]:
        human_response = _format_human_response(response, context=intent)
        return {
            "status": "ok",
            "intent": intent,
            "bricks_used": bricks,
            "response": human_response,
        }

    def status(self) -> Dict[str, Any]:
        return {"app": "BEK Hybrid Agent v19.69", "bricks": {"hermes": self._hermes is not None, "provider_manager": self._provider_manager is not None}, "initialized": self._initialized}

_brain_instance: Optional[BEKBrain] = None

def get_brain() -> BEKBrain:
    global _brain_instance
    if _brain_instance is None: _brain_instance = BEKBrain()
    return _brain_instance