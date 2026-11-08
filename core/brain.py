# ==============================================================================
# BEK Hybrid Agent v19 — core/brain.py — v19.59
# ★ v19.59 (2026-11-08) — Pipeline web : GA + Hermes + Anti-Hallucination
#   - Injection du gène BEK-GA dans la requête web
#   - Appel via Hermes web_sync (anti-hallu + guardian)
#   - Fallback WebAgent direct si Hermes indisponible
#   - Ajout de l'anti-hallucination dans _call_chat_pipeline
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

# ★ Anti-hallucination prompt (utilisé dans _call_chat_pipeline)
_ANTI_HALLU_PROMPT = """
## 🛡️ RÈGLES ANTI-HALLUCINATION (CRITIQUE)
- Si tu ne sais pas, dis "Je ne sais pas".
- N'invente JAMAIS de chiffres, dates ou URLs.
- Base-toi UNIQUEMENT sur le contexte fourni.
- Si tu cites un chiffre (nombre de fichiers, lignes, etc.), il DOIT
  provenir d'un outil ou d'un contexte fourni explicitement.
- Pour les recherches web : cite UNIQUEMENT les URLs réellement présentes
  dans le contexte. Ne fabrique pas de sources.
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
    logger.warning("[Brain/CB] %s échec #%d (circuit %s)", key, h["failures"], "OUVERT" if h["failures"] >= CIRCUIT_BREAKER_THRESHOLD else "sain")

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
    marker = f"\n\n[…TRONQUÉ : {head_n} premiers + {tail_n} derniers chars sur {total} au total. Utilise l'outil read_file pour un extrait précis.]\n\n"
    return full[:head_n] + marker + full[-tail_n:], total, True

def _detect_explicit_tool(query: str) -> Optional[Tuple[str, Optional[str]]]:
    if not query: return None
    m = _TOOL_NAME_RE.search(query)
    if not m: return None
    prefix = (m.group(1) or "").lower()
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

# ==============================================================================
# ★ FORMATAGE HUMAIN UNIVERSEL
# ==============================================================================
def _format_human_response(response: Any, context: str = "action") -> str:
    if isinstance(response, str):
        stripped = response.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return _format_human_response(json.loads(stripped), context)
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
                "3. Tu peux aussi demander : *« Explique-moi l'erreur en détail »*.",
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
                        syntax = res.get("syntax_check", "")
                        if path:
                            filename = path.split("\\")[-1].split("/")[-1]
                            badge = f" ✓" if syntax == "OK" else ""
                            lines.append(f"- `{filename}` ({chars} caractères){badge}")
                    except Exception:
                        pass
            lines.append("")
            lines.append("**Prochaine étape :**")
            lines.append("Tu peux tester le résultat, ou me demander d'ajouter d'autres fonctionnalités.")
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
                grouped.setdefault("OTHER", []).append(f"  - `{name}` (risque:{risk}) : (outil branché, pas de description)")

        lines = ["=== ⚠️ OUTILS DISPONIBLES — TU DOIS LES UTILISER POUR AGIR ⚠️ ===", "",
                 "RÈGLE ABSOLUE :",
                 "1. Si l'utilisateur demande une action (analyser, lire, écrire, chercher, générer),",
                 "   tu DOIS appeler l'outil correspondant. NE JAMAIS inventer de nom d'outil.",
                 "2. Format d'appel STRICT :",
                 '   [ACTION:nom_exact_de_l_outil]{"param1": "valeur1", "param2": "valeur2"}[/ACTION]',
                 "3. Si aucun outil ne correspond, réponds en texte naturel sans inventer.", ""]

        for cat, label in CATEGORY_LABELS.items():
            tools = grouped.get(cat, [])
            if tools:
                lines.append(f"=== {label} ===")
                lines.extend(tools)
                lines.append("")

        if grouped.get("OTHER"):
            lines.append("=== 🔧 AUTRES OUTILS BRANCHÉS ===")
            lines.extend(grouped["OTHER"])
            lines.append("")

        lines.append("=== 🎯 RACCOURCIS CONTEXTUELS ===")
        q_lower = (query or "").lower()
        if intent == "coder":
            lines.append("- Pour écrire du code : `codex_agent` ou `codex_loop`")
            lines.append("- Pour corriger un fichier : `edit_file` ou `codex_editor`")
        elif any(k in q_lower for k in ("analyse mon repo", "analyse mon dépôt", "analyse mon projet", "analyse le repo", "audit mon code", "audit du repo", "structure de mon projet")):
            lines.append("- Pour analyser le repo : `python_save_report` avec dir_path")
        elif intent == "web":
            lines.append("- Pour chercher sur le web : `web_search` ou `web_agent_traced`")
        elif intent == "analyze_image":
            lines.append("- Pour analyser une image : `vision_analyze` (via uploads/)")
        elif intent == "memory":
            lines.append("- Pour la mémoire : `hindsight_query` ou `hindsight_recall`")
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

    def _get_ga_prompt(self) -> str:
        try:
            from nerves.ga_nerves import get_ga_engine
            best = get_ga_engine().select_best_gene()
            logger.debug("[BEK-GA] Gène actif : %s (fitness=%s)", best.gene_id, best.fitness)
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
            if not success:
                engine.evolve()
                logger.info("[BEK-GA] ⚡ Évolution déclenchée (échec détecté)")
        except Exception as ga_exc:
            logger.debug("[BEK-GA] Enregistrement fitness ignoré : %s", ga_exc)

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
        logger.info("[BEK Brain] 🧠 Cerveau initialisé v19.59 (Pipeline web : GA + Hermes + Anti-Hallu)")

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
        if not user_query or not user_query.strip(): return user_query
        pm = self._provider_manager
        if pm is None: return user_query
        def _sync_llm_call() -> str:
            chunks = []
            for item in pm.execute_chat_stream(
                messages=[{"role": "system", "content": "Expert prompt engineer. Output ONE detailed English prompt."}, {"role": "user", "content": user_query}],
                provider="nvidia", model="nvidia/nemotron-3.5-super-vl-120b-a12b", temperature=0.4, max_tokens=200,
            ):
                if "chunk" in item: chunks.append(item["chunk"])
                elif "error" in item: raise RuntimeError(item["error"])
            return "".join(chunks).strip()
        try:
            refined = await asyncio.to_thread(_sync_llm_call)
        except Exception: return user_query
        refined = refined.strip().strip('"').strip("'").strip("`")
        if "prompt:" in refined.lower():
            idx = refined.lower().find("prompt:")
            candidate = refined[idx + len("prompt:"):].strip()
            if candidate: refined = candidate
        if len(refined) < 15: return user_query
        return refined

    async def _handle_fix_self(self) -> Dict[str, Any]:
        try:
            if self._hermes and "codex_loop" in self._hermes.tools:
                res = await asyncio.to_thread(self._call_hermes_tool, "codex_loop", {"task_description": "Analyse les logs récents de BEK, corrige les erreurs et auto-répare le système.", "max_steps": 10, "phase": "auto"})
                return self._wrap(res, "fix_self", ["hermes.codex_loop"])
        except Exception as e: logger.error("[Brain] Erreur fix_self : %s", e)
        return self._wrap("⚠️ Module d'auto-réparation indisponible ou non configuré.", "fix_self", ["hermes.codex_loop"])

    async def process(self, query: str, provider: Optional[str] = None, model: Optional[str] = None, files: Optional[list] = None, session_id: str = "default", on_status: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
        start_time = time.perf_counter()
        if not self._initialized: await self.boot()

        def _status(text: str, type_: str = "thinking"):
            if on_status:
                try:
                    on_status(text, type_)
                except Exception:
                    pass

        _status("🤔 Réflexion en cours...", "thinking")

        if files and len(files) > 0:
            _status("📂 Analyse des fichiers...", "analyze")
            res = await self._process_files(query, files, provider, model)
            elapsed = (time.perf_counter() - start_time) * 1000
            res["latency_ms"] = round(elapsed, 2)
            self._record_ga_fitness(query, res, elapsed)
            return res

        intent = _detect_intent(query)
        logger.info(f"[Brain] Intent détecté : {intent} (session: {session_id})")

        plan = self.skill_agent.get_action_plan(query)
        skills_context = ""
        if plan["skills"]:
            logger.info(f"[Brain] 🧠 SkillAgent a trouvé {len(plan['skills'])} compétences : {[s['name'] for s in plan['skills']]}")
            skills_context = "\n\n=== COMPÉTENCES SÉLECTIONNÉES PAR SKILLAGENT ===\n"
            for s in plan["skills"]:
                skills_context += f"--- Skill : {s['name']} ---\n{s.get('prompt', s.get('description', ''))}\n\n"
            query = f"{query}\n{skills_context}"

        cached_response = self._observe_economics(query, intent)
        if cached_response:
            _status("💾 Réponse depuis le cache...", "done")
            res = self._wrap(cached_response, intent, ["bek_eco_cache"])
            res["latency_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
            res["cached"] = True
            return res

        res = {}

        if any(k in query.lower() for k in [
            "analyse mon repo", "analyse mon dépôt", "analyse mon projet",
            "analyse le repo", "analyse le dépôt", "analyze repo",
            "analyse mon code", "audit mon code", "structure de mon projet",
            "audit de mon projet", "audit du repo",
        ]):
            _status("📊 Analyse du repo en cours...", "analyze")
            if self._hermes and "python_save_report" in self._hermes.tools:
                logger.info("[Brain] 🎯 Demande d'analyse de repo détectée → python_save_report")
                path_match = re.search(r'([A-Za-z]:\\[^\s"\']+|/[\w/]+)', query)
                if path_match:
                    target_path = path_match.group(1).replace("\\\\", "\\")
                else:
                    from core.paths import WORKSPACE_DIR
                    target_path = str(WORKSPACE_DIR)

                try:
                    result = await asyncio.to_thread(
                        self._call_hermes_tool,
                        "python_save_report",
                        {"dir_path": target_path, "output_name": "audit_repo"}
                    )
                    result_str = str(result)
                    md_match = re.search(r'([A-Za-z]:\\[^"\']+?\.md)', result_str)
                    md_path = md_match.group(1).replace("\\\\", "\\") if md_match else None

                    if md_path and os.path.exists(md_path):
                        def _read_sync_report():
                            with open(md_path, "r", encoding="utf-8") as f:
                                return f.read()
                        report_text = await asyncio.to_thread(_read_sync_report)

                        synthesis_prompt = (
                            f"Voici le rapport d'analyse de mon projet :\n\n{report_text}\n\n"
                            f"=== TA MISSION ===\n"
                            f"1. Les 3 plus gros problèmes de structure.\n"
                            f"2. Les 3 fichiers à refactoriser en priorité.\n"
                            f"3. Une recommandation prioritaire.\n"
                            f"Sois direct et concret. "
                            f"N'invente AUCUN chiffre : cite uniquement ceux du rapport."
                        )
                        synthesis = await self._call_with_fallback(
                            synthesis_prompt,
                            provider or DEFAULT_CHAT_PROVIDER,
                            model or DEFAULT_CHAT_MODEL,
                        )
                        synthesis = self._validate_synthesis_numbers(synthesis, result)
                        res = self._wrap(
                            f"📊 **Rapport généré**\n\n{synthesis}\n\n---\n*Fichier : `{md_path}`*",
                            "analyze_repo",
                            ["python_save_report", "provider_manager", "bek_eval_guard"],
                        )
                    else:
                        res = self._wrap(
                            f"⚠️ Rapport généré mais fichier introuvable.\nSortie : {result_str[:500]}",
                            "analyze_repo",
                            ["python_save_report"],
                        )
                except Exception as e:
                    logger.error("[Brain] Erreur analyse repo : %s", e, exc_info=True)
                    res = self._wrap(
                        f"❌ Erreur analyse repo : {e}",
                        "analyze_repo",
                        ["python_save_report"],
                    )
            else:
                res = self._wrap(
                    "⚠️ Outil `python_save_report` indisponible. Vérifie le Nerf 6 (MCP).",
                    "analyze_repo",
                    [],
                )
        elif _GITHUB_URL_RE.search(query):
            _status("🐙 Clonage du repo GitHub...", "tool")
            github_url_match = _GITHUB_URL_RE.search(query)
            owner_raw = github_url_match.group(1)
            repo_raw = github_url_match.group(2)
            owner, repo_name = _normalize_github_repo(owner_raw, repo_raw)
            repo_url = f"https://github.com/{owner}/{repo_name}"
            logger.info("[Brain] 🎯 URL GitHub détectée → clone + analyse (repo=%s)", repo_name)

            try:
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

                if os.path.exists(full_repo_path):
                    logger.info("[Brain] 📂 Repo trouvé : %s", repo_dir)

                    report_result = await asyncio.to_thread(
                        self._call_hermes_tool, "mcp_python_save_report",
                        {"dir_path": repo_dir, "output_name": f"audit_{repo_name}"}
                    )

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

                    synthesis_prompt = (
                        f"Tu es BEK, un architecte logiciel senior. Voici les données d'analyse du repo {repo_url} :\n\n"
                        f"=== RAPPORT TECHNIQUE ===\n{report_result}\n\n"
                        f"=== RAPPORT STRATÉGIQUE ===\n{arch_result}\n\n"
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

                    logger.info("[Brain] 🧠 Synthèse LLM via pipeline (active LVC, GA, Skills, Anti-Hallucination)")
                    synthesis = await self._call_chat_pipeline(
                        synthesis_prompt, provider, model, None
                    )

                    synthesis = self._validate_synthesis_numbers(synthesis, audit_numbers_dict)

                    res = self._wrap(
                        f"📊 **Analyse Stratégique du Repo**\n\n{synthesis}",
                        "analyze_repo",
                        ["git_clone", "python_save_report", "analyze_architecture",
                         "provider_manager", "bek_ga", "bek_lvc", "skill_agent",
                         "cognitive_nerves", "bek_eval_guard"]
                    )
                else:
                    logger.warning("[Brain] Échec : dossier %s absent", repo_dir)
                    res = self._wrap(f"⚠️ Le dépôt n'a pas pu être cloné : {clone_str}", "analyze_repo", ["git_clone"])
            except Exception as e:
                logger.error("[Brain] Erreur analyse GitHub : %s", e)
                res = self._wrap(f"❌ Erreur : {e}", "analyze_repo", ["git_clone"])
        elif intent == "fix_self":
            _status("🔧 Auto-réparation en cours...", "tool")
            res = await self._handle_fix_self()
        elif intent == "analyze_image":
            _status("🖼️ Analyse de l'image...", "analyze")
            res = await self._process_analyze_without_attachment(query, provider, model)
        elif intent == "generate_image" and self._hermes:
            _status("🎨 Génération de l'image...", "tool")
            refined_prompt = await self._refine_image_prompt(query)
            res = self._wrap(self._call_hermes_tool("generate_image", {"prompt": refined_prompt}), "vision_generate", ["hermes.generate_image", "prompt_refiner"])
        elif intent == "coder" and self._hermes:
            _status("⚙️ Génération de code en cours...", "code")
            res = await asyncio.to_thread(self._handle_coder_intent, query, provider, model, session_id)

        # ★ v19.59 — PIPELINE WEB AMÉLIORÉ (GA + Hermes + Anti-Hallu)
        elif intent == "web":
            _status("🌐 Recherche web en cours...", "search")
            
            # 1. Injecter le gène BEK-GA dans la requête
            try:
                ga_prompt = self._get_ga_prompt()
                query_with_gene = f"{query}\n\n[INSTRUCTION DE RECHERCHE — Gène BEK-GA]\n{ga_prompt}"
            except Exception:
                query_with_gene = query
            
            # 2. Essayer Hermes web_sync (bénéficie de l'anti-hallu + guardian)
            if self._hermes and "web_sync" in self._hermes.tools:
                try:
                    logger.info("[Brain/Web] 🔍 web_sync via Hermes (gène BEK-GA injecté)")
                    web_result = await asyncio.to_thread(
                        self._call_hermes_tool,
                        "web_sync",
                        {"query": query_with_gene}
                    )
                    res = self._wrap(
                        web_result,
                        "web",
                        ["web_agent", "bek_ga", "hermes", "anti_hallucination"]
                    )
                except Exception as e:
                    logger.warning("[Brain/Web] Hermes web_sync échoué : %s → fallback WebAgent", e)
                    if self._web_agent:
                        res = self._wrap(
                            self._web_agent.run_pipeline(query_with_gene),
                            "web",
                            ["web_agent", "bek_ga"]
                        )
                    else:
                        res = self._wrap(
                            "⚠️ Aucun agent web disponible.",
                            "web",
                            []
                        )
            elif self._web_agent:
                logger.info("[Brain/Web] 🔍 web_sync via WebAgent direct (gène BEK-GA injecté)")
                res = self._wrap(
                    self._web_agent.run_pipeline(query_with_gene),
                    "web",
                    ["web_agent", "bek_ga"]
                )
            else:
                res = self._wrap(
                    "⚠️ Aucun agent web disponible. Vérifie la configuration.",
                    "web",
                    []
                )
        
        elif intent == "orchestrate" and self._orchestrator:
            _status("🎼 Orchestration des agents...", "tool")
            res = self._wrap(self._orchestrator.run(query), "orchestrate", ["bek_orchestrator"])
        elif intent == "memory":
            _status("🧠 Recherche en mémoire...", "analyze")
            res = self._wrap(await self._handle_memory(query), "memory", ["hindsight_memory"])
        else:
            _status("💬 Traitement de la requête...", "thinking")
            explicit = _detect_explicit_tool(query)
            if explicit and self._hermes:
                tool_name, path = explicit
                tool = self._hermes.tools.get(tool_name)
                if tool is None:
                    alt = tool_name[4:] if tool_name.startswith("mcp_") else "mcp_" + tool_name
                    tool = self._hermes.tools.get(alt)
                    if tool is not None: tool_name = alt

                if tool is None:
                    available = [n for n in self._hermes.tools.keys() if n.startswith(("mcp_", "rea_", "python_"))]
                    res = self._wrap(f"❌ Outil '{tool_name}' introuvable dans Hermes.\nOutils MCP disponibles : {', '.join(available) if available else 'aucun'}", "chat", ["hermes.dispatch"])
                else:
                    _status(f"⚙️ Appel de l'outil {tool_name}...", "tool")
                    args = _tool_args_for(tool_name, path)
                    if not args:
                        res = self._wrap(f"⚠️ Aucun chemin détecté dans la requête pour {tool_name}. Exemple : 'Utilise {tool_name} sur F:\\dossier\\fichier.js'", "chat", [f"hermes.{tool_name}"])
                    else:
                        logger.info("[Brain] 🎯 Appel DIRECT outil MCP : %s args=%s", tool_name, args)
                        try:
                            result = await asyncio.to_thread(self._call_hermes_tool, tool_name, args)
                            res = self._wrap(result, "chat", [f"hermes.{tool_name}"])
                        except Exception as e:
                            logger.error("[Brain] Erreur appel direct %s : %s", tool_name, e, exc_info=True)
                            res = self._wrap({"status": "error", "message": f"{type(e).__name__}: {e}"}, "chat", [f"hermes.{tool_name}"])
            else:
                res = self._wrap(await self._call_chat_pipeline(query, provider, model, None), "chat", ["pipeline_chat"])

        if not (intent == "chat" and _detect_explicit_tool(query)):
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

            if isinstance(source, dict):
                official = source
            else:
                official = {}
                try:
                    if isinstance(source, str):
                        start = source.find('{')
                        end = source.rfind('}')
                        if start != -1 and end != -1:
                            parsed = json.loads(source[start:end+1])
                            if isinstance(parsed, dict):
                                official = {
                                    "files_analyzed": parsed.get("files_analyzed", 0),
                                    "total_lines": parsed.get("total_lines", 0),
                                    "warnings": len(parsed.get("warnings", [])) if isinstance(parsed.get("warnings"), list) else 0,
                                }
                except Exception:
                    pass

            if official:
                num_check = validate_cited_numbers(synthesis, official)
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
            if phase == "plan" and not any(k in q_lower for k in ["fais un plan", "mode plan", "structure du plan", "commence par un plan"]):
                forced_phase = "auto"
            
            params: Dict[str, Any] = {"task_description": query, "max_steps": 25, "phase": forced_phase}
            
            if forced_phase == "plan":
                state["plan"] = []; state["step"] = 0; state["goal"] = query; state["completed"] = False
            elif forced_phase == "step":
                if state["completed"]: return self._wrap({"status": "error", "message": "✅ Ce plan est déjà terminé. Lance un nouveau plan."}, "coder", ["hermes.codex_loop"])
                if not state["plan"]: 
                    logger.warning("[Brain/Coder] ⚠️ Aucun plan en mémoire. Bascule forcée en mode 'auto'.")
                    params["phase"] = "auto"
                else:
                    params["plan"] = state["plan"]; params["step_num"] = step_num; params["goal_context"] = state["goal"]
        elif "codex_editor" in q_lower or "corrige" in q_lower or "modifie" in q_lower:
            tool_to_use = "codex_editor"; params = {"task_description": query, "target_file": target_file}
        else:
            tool_to_use = "codex_loop"; params = {"task_description": query, "max_steps": 25, "phase": "auto"}

        user_provider = provider
        user_model = model
        if user_model and not user_provider and "/" in user_model:
            user_provider = user_model.split("/", 1)[0]

        if user_provider: params["provider"] = user_provider
        if user_model: params["model"] = user_model

        if user_provider or user_model:
            logger.info("[Brain/Coder] 🎯 LLM choisi par l'utilisateur : provider=%s model=%s (outil=%s)", user_provider or "auto", user_model or "auto", tool_to_use)
        else:
            logger.info("[Brain/Coder] ⚠️ Aucun LLM fourni par l'utilisateur, codex_loop utilisera ses défauts historiques.")

        if tool_to_use == "codex_loop":
            try:
                memory_context = asyncio.run(self._handle_memory(query))
                if memory_context and memory_context.strip() and memory_context.strip() != "Aucun souvenir trouvé.":
                    params["memory_context"] = memory_context.strip()[:4000]
            except Exception: pass

        try:
            task = {"tool": tool_to_use, "args": params}
            raw_hermes_res = self._hermes.dispatch(task)
            inner_data = self._normalize_hermes_result(raw_hermes_res)
        except Exception as e: return self._wrap({"status": "error", "message": str(e)}, "coder", [f"hermes.{tool_to_use}"])

        if params.get("phase") == "plan" and inner_data:
            new_plan = inner_data.get("plan", [])
            if new_plan: state["plan"] = new_plan; state["step"] = 0
        if params.get("phase") == "step" and inner_data and inner_data.get("status") == "success" and inner_data.get("phase") == "step":
            next_step = inner_data.get("next_step")
            if next_step is not None: state["step"] = next_step
            else: state["completed"] = True
        return self._wrap(inner_data or raw_hermes_res, "coder", [f"hermes.{tool_to_use}"])

    async def _process_analyze_without_attachment(self, query: str, provider: Optional[str], model: Optional[str]) -> Dict[str, Any]:
        try:
            from core.paths import WORKSPACE_DIR
            uploads_dir = Path(WORKSPACE_DIR) / "uploads"
            if not uploads_dir.exists(): return self._wrap("📷 Aucune image.", "analyze_image", ["file_manager"])
            candidates = [p for p in uploads_dir.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS]
            if not candidates: return self._wrap("📷 Aucune image dans uploads/.", "analyze_image", ["file_manager"])
            latest = max(candidates, key=lambda p: p.stat().st_mtime)
            from services.vision import analyze_image_with_vision
            description = analyze_image_with_vision(str(latest), _DEFAULT_VISION_PROMPT)
            return self._wrap(description, "analyze_image", ["vision.analyze", "provider_manager", "file_manager"])
        except Exception as e: return self._wrap(f"Erreur : {e}", "error", ["vision.analyze"])

    async def _call_llm_direct(self, query: str, provider: Optional[str], model: Optional[str]) -> str:
        try:
            pm = self._provider_manager
            if not pm: return "Erreur: ProviderManager non initialisé."
            is_analysis = _is_analysis_query(query)
            if model: prov = provider or DEFAULT_CHAT_PROVIDER; mdl = model
            elif is_analysis: prov = provider or ANALYSIS_PROVIDER; mdl = ANALYSIS_MODEL
            else: prov = provider or DEFAULT_CHAT_PROVIDER; mdl = DEFAULT_CHAT_MODEL

            try:
                from bek_core.eco.optimizer import BekEcoOptimizer
                eco = BekEcoOptimizer()
                limit_check = eco.check_limits("daily_tokens")
                if limit_check.get("exceeded", False):
                    return "🛑 [BEK-LVC] Budget de tokens quotidien épuisé. Réponse mise en pause pour éviter la surconsommation."
            except Exception: pass

            def _sync_call() -> str:
                messages = [{"role": "user", "content": query}]
                try:
                    from ai_service import compress_messages, is_headroom_enabled
                    if is_headroom_enabled():
                        optimized_messages = compress_messages(messages, model=mdl)
                        if isinstance(optimized_messages, list) and optimized_messages: messages = optimized_messages
                except Exception: pass
                chunks: List[str] = []
                for item in pm.execute_chat_stream(messages=messages, provider=prov, model=mdl, disable_internal_fallback=True, max_tokens=4096):
                    if "chunk" in item: chunks.append(item["chunk"])
                    elif "error" in item: return f"Erreur LLM: {item['error']}"
                return "".join(chunks) or "Réponse vide"
            return await asyncio.to_thread(_sync_call)
        except Exception as e: return f"Erreur: {repr(e)}"

    async def _call_with_fallback(self, prompt: str, primary_provider: str, primary_model: str) -> str:
        if _is_circuit_open(primary_provider, primary_model):
            return f"[Erreur] Le circuit est ouvert pour {primary_provider}/{primary_model}."
        try:
            response = await self._call_llm_direct(prompt, primary_provider, primary_model)
            if not _looks_like_error(response):
                _record_success(primary_provider, primary_model); return response
            _record_failure(primary_provider, primary_model)
            return f"[Erreur] Échec avec {primary_provider}/{primary_model} : {response[:300]}"
        except Exception as exc:
            _record_failure(primary_provider, primary_model)
            return f"[Erreur] Exception avec {primary_provider}/{primary_model} : {exc}"

    async def _process_files(self, query: str, files: list, provider: Optional[str], model: Optional[str]) -> Dict[str, Any]:
        from core.paths import WORKSPACE_DIR
        file_contexts: List[Dict[str, Any]] = []
        bricks_used: List[str] = ["file_manager"]
        stats: List[Dict[str, Any]] = []
        resolved_files: List[tuple] = []
        for f in files:
            filename = f if isinstance(f, str) else f.get("filename", "")
            if not filename: continue
            possible_paths = [Path(WORKSPACE_DIR) / "uploads" / filename, Path(WORKSPACE_DIR) / filename]
            target = next((p for p in possible_paths if p.exists()), None)
            if target: resolved_files.append((filename, target))
            else:
                file_contexts.append({"filename": filename, "content": f"[Fichier {filename} INTROUVABLE]"}); stats.append({"file": filename, "status": "not_found"})

        n = max(1, len(resolved_files))
        per_file_budget = min(MAX_INDIVIDUAL_FILE_CHARS, MAX_TOTAL_FILE_CONTEXT_CHARS // n)
        for filename, target in resolved_files:
            ext = target.suffix.lower()
            if ext in _IMAGE_EXTENSIONS:
                try:
                    from services.vision import analyze_image_with_vision
                    description = analyze_image_with_vision(str(target), _DEFAULT_VISION_PROMPT)
                    file_contexts.append({"filename": filename, "content": f"[Description de {filename}]\n{description}"}); bricks_used.append("vision.analyze"); stats.append({"file": filename, "type": "image", "status": "vision"})
                except Exception as e: file_contexts.append({"filename": filename, "content": f"[Erreur image : {e}]"})
            else:
                try:
                    content, total, truncated = _smart_read_file(target, per_file_budget)
                    suffix = " [TRONQUÉ]" if truncated else ""
                    file_contexts.append({"filename": filename, "content": f"[Contenu de {filename}{suffix} ({total} chars)]\n{content}"}); stats.append({"file": filename, "type": "text", "total_chars": total, "sent_chars": len(content), "truncated": truncated})
                except Exception as e:
                    file_contexts.append({"filename": filename, "content": f"[Erreur lecture : {e}]"}); stats.append({"file": filename, "status": "error", "error": str(e)})

        clean_query = re.sub(r"\[Fichiers joints\s*:\s*[^\]]+\]", "", query).strip()
        if not clean_query: clean_query = query
        primary_provider = provider or ANALYSIS_PROVIDER; primary_model = model or ANALYSIS_MODEL

        if len(resolved_files) > CHUNK_THRESHOLD_FILES:
            partial_summaries: List[str] = []; successful_packets = 0; failed_packets: List[str] = []
            for i in range(0, len(file_contexts), CHUNK_SIZE_FILES):
                chunk = file_contexts[i:i + CHUNK_SIZE_FILES]; chunk_names = ", ".join(c["filename"] for c in chunk); chunk_text = "\n\n".join(c["content"] for c in chunk)
                map_prompt = f"Voici une partie des fichiers à analyser ({chunk_names}):\n\n{chunk_text}\n\n=== CONSIGNE ===\nFais une synthèse brique par brique de ces fichiers uniquement. Sois précis et technique. Ne réponds pas à la question finale, contente-toi de résumer ces fichiers."
                partial_res = await self._call_with_fallback(map_prompt, primary_provider, primary_model)
                if _looks_like_error(partial_res): failed_packets.append(chunk_names); partial_summaries.append(f"--- PAQUET {chunk_names} ---\n[INDISPONIBLE — provider en échec]")
                else: successful_packets += 1; partial_summaries.append(f"--- SYNTHÈSE PARTIELLE ({chunk_names}) ---\n{partial_res}")
                await asyncio.sleep(RATE_LIMIT_DELAY_SEC)
            if successful_packets == 0: return self._wrap(f"[Erreur] Aucun paquet n'a pu être analysé. Providers en échec : {', '.join(failed_packets)}. Vérifie ta configuration provider.", "files", bricks_used + ["provider_manager (all-failed)"])
            final_prompt = f"Voici les synthèses partielles de {len(resolved_files)} fichiers :\n\n" + "\n\n".join(partial_summaries) + f"\n\n=== QUESTION FINALE ===\n{clean_query}\n\nRéponds à la question finale en te basant sur les synthèses ci-dessus. Structure ta réponse brique par brique." + (f"\n\n⚠️ Note : les paquets suivants n'ont pas pu être analysés à cause d'erreurs provider : {', '.join(failed_packets)}." if failed_packets else "")
            await asyncio.sleep(RATE_LIMIT_DELAY_SEC); response_text = await self._call_with_fallback(final_prompt, primary_provider, primary_model); bricks_used.append("provider_manager (map-reduce resilient)")
        else:
            context_str = "\n\n".join(c["content"] for c in file_contexts)
            full_prompt = f"Fichiers joints ({len(resolved_files)} fichier(s)) :\n{context_str}\n\n=== QUESTION ===\n{clean_query}\n\nRéponds en te basant UNIQUEMENT sur le contenu ci-dessus. Si un fichier est marqué [TRONQUÉ], précise-le."
            response_text = await self._call_with_fallback(full_prompt, primary_provider, primary_model); bricks_used.append("provider_manager")
        return self._wrap(response_text, "files", bricks_used)

    async def _call_chat_pipeline(self, query: str, provider: Optional[str], model: Optional[str], files: Optional[list]) -> str:
        try:
            is_analysis = _is_analysis_query(query)
            if model: prov = provider or DEFAULT_CHAT_PROVIDER; mdl = model
            elif is_analysis: prov = provider or ANALYSIS_PROVIDER; mdl = ANALYSIS_MODEL
            else: prov = provider or DEFAULT_CHAT_PROVIDER; mdl = DEFAULT_CHAT_MODEL

            logger.info("[Brain/ChatPipeline] 🎯 LLM cible : provider=%s model=%s (choix user=%s)",
                        prov, mdl, "explicite" if model else "défaut")

            tools_prompt = self.skill_agent.get_available_tools_prompt(_detect_intent(query), query=query)
            ga_prompt = self._get_ga_prompt()

            # ★ v19.59 : Ajout anti-hallucination
            system_extra = (
                f"{ga_prompt}\n\n"
                f"{_ANTI_HALLU_PROMPT}\n\n"
                f"=== OUTILS DISPONIBLES (à utiliser AVANT de générer du code) ===\n{tools_prompt}\n\n"
                f"RÈGLE ABSOLUE : si l'utilisateur nomme un outil "
                f"(ex: rea_analyze_javascript, mcp_rea_*), APPELLE l'outil via "
                f"[ACTION:nom_outil]{{...}}[/ACTION] et NE GÉNÈRE PAS de code Python/JS à la place."
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
        try:
            from hindsight_memory import hindsight_recall_async
            results = await asyncio.wait_for(hindsight_recall_async(query), timeout=15.0)
        except Exception:
            try:
                from hindsight_memory import hindsight_recall
                results = await asyncio.wait_for(asyncio.to_thread(hindsight_recall, query), timeout=15.0)
            except Exception: return 'Aucun souvenir trouvé.'
        if not results: return 'Aucun souvenir trouvé.'
        if isinstance(results, list): return chr(10).join('- ' + str(r.get('text', r) if isinstance(r, dict) else r) for r in results[:5])
        return str(results)

    def _wrap(self, response: Any, intent: str, bricks: list) -> Dict[str, Any]:
        human_response = _format_human_response(response, context=intent)
        return {
            "status": "ok",
            "intent": intent,
            "bricks_used": bricks,
            "response": human_response,
        }

    def status(self) -> Dict[str, Any]:
        return {"app": "BEK Hybrid Agent v19.59", "bricks": {"hermes": self._hermes is not None, "provider_manager": self._provider_manager is not None}, "nerfs": self._nerfs_status, "initialized": self._initialized, "active_sessions": len(self._session_states)}

_brain_instance: Optional[BEKBrain] = None

def get_brain() -> BEKBrain:
    global _brain_instance
    if _brain_instance is None: _brain_instance = BEKBrain()
    return _brain_instance