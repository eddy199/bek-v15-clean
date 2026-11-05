# ==============================================================================
# BEK-v19.51 — MASTER ORCHESTRATOR v2.4
# ------------------------------------------------------------------------------
# v2.4 (2026-11-05) : ★ BEK-GA intégré
#   - Récupération du prompt évolutif via ga_get_best
#   - Enregistrement du fitness après chaque process()
#   - Évolution automatique en cas d'échec
# v2.3 (2026-10-01) : ★ Fix encodage UTF-8 + Timeout vidéo
# v2.2 (2026-10-01) : Activation des 12 nerfs au démarrage
# ==============================================================================

from __future__ import annotations

# ★ FIX ENCODAGE WINDOWS — DOIT ÊTRE AVANT TOUS LES IMPORTS
import sys
import io
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, Exception):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─── Imports standards (APRÈS le bloc if) ───
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.master")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Master] %(message)s",
)


# ══════════════════════════════════════════════════════════════════════════════
# Mots-clés de détection AVANT BEK-REX
# ══════════════════════════════════════════════════════════════════════════════
VISION_TRIGGERS = (
    "génère une image", "génère une vidéo", "génère un",
    "crée une image", "crée une vidéo", "crée un",
    "fais une vidéo", "fais une image", "fais-moi une",
    "dessine", "vidéo de", "image de", "animate",
)

WEB_TRIGGERS = (
    "cherche", "recherche", "trouve", "actualité", "news",
    "web", "scrape", "article", "quelles sont les",
    "quels sont les", "dernières",
)

SHELL_TRIGGERS = (
    "exécute la commande", "lance la commande", "run command",
    "$ ", "cmd>",
)


# ══════════════════════════════════════════════════════════════════════════════
# ★ ACTIVATION DES NERFS (avant tout le reste)
# ══════════════════════════════════════════════════════════════════════════════
def _activate_all_nerves() -> Dict[str, Any]:
    """Active tous les nerfs BEK dans le bon ordre de dépendances."""
    report: Dict[str, Any] = {"ok": [], "failed": [], "skipped": []}

    NERFS_ORDER = [
        ("Nerf 3  EventBus",    "nerves.event_bus_nerves",   "activate_event_bus_nerves"),
        ("Nerf 8  Skills",      "nerves.skills_nerves",      "activate_skills_nerves"),
        ("Nerf 1  Hermes",      "nerves.hermes_nerves",      "activate_hermes_nerves"),
        ("Nerf 2  Cognitif",    "nerves.cognitive_nerves",   "activate_cognitive_nerves"),
        ("Nerf 4  WebAgent",    "nerves.web_agent_nerves",   "activate_web_agent_nerves"),
        ("Nerf 5  Approval",    "nerves.approval_nerves",    "activate_approval_nerves"),
        ("Nerf 6  MCP",         "nerves.mcp_nerves",         "activate_mcp_nerves"),
        ("Nerf 7  Router",      "nerves.router_nerves",      "activate_router_nerves"),
        ("Nerf 9  Guardian",    "nerves.guardian_nerves",    "activate_guardian_nerves"),
        # ★ Désactivé — CRM non utilisé
        # ("Nerf 10 CRM",         "nerves.crm_nerves",         "activate_crm_nerves"),
        ("Nerf 11-13 Headless", "nerves.headless_nerves",    "activate_headless_nerves"),
        ("Nerf 14-17 Tmux",     "nerves.tmux_nerves",        "activate_tmux_nerves"),
        ("Nerf 20 BEK-GA",      "nerves.ga_nerves",          "activate_ga_nerves"),
    ]

    print("=" * 70)
    print("ACTIVATION DES NERFS BEK")
    print("=" * 70)

    for label, module_name, func_name in NERFS_ORDER:
        try:
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name)
            result = func()

            status = result.get("status", "unknown") if isinstance(result, dict) else "ok"

            if status in ("ok", "already_activated"):
                count = result.get("activated_count") or result.get("skills_loaded", 0)
                print(f"  [OK]  {label:22s} | {status:18s} | {count} outils/skills")
                report["ok"].append({"nerf": label, "result": result})
            elif status == "disabled":
                print(f"  [--]  {label:22s} | disabled (feature-flag)")
                report["skipped"].append({"nerf": label, "reason": "feature-flag"})
            else:
                print(f"  [!!]  {label:22s} | {status}")
                report["failed"].append({"nerf": label, "result": result})
        except ImportError as e:
            print(f"  [XX]  {label:22s} | ImportError: {e}")
            report["failed"].append({"nerf": label, "error": f"ImportError: {e}"})
        except Exception as e:
            print(f"  [XX]  {label:22s} | {type(e).__name__}: {e}")
            report["failed"].append({"nerf": label, "error": str(e)})

    print("=" * 70)
    print(f"RESULTAT : {len(report['ok'])} actives | "
          f"{len(report['skipped'])} desactives | "
          f"{len(report['failed'])} echecs")
    print("=" * 70)

    return report


# Activation UNIQUE au moment de l'import
_NERF_ACTIVATION_REPORT: Dict[str, Any] = _activate_all_nerves()


class BEKMasterOrchestrator:
    """CERVEAU CENTRAL de BEK — 6 briques core + 7 externes + 13 nerfs."""

    TIMEOUT_DEFAULT = 30
    TIMEOUT_VISION = 300
    TIMEOUT_SHELL = 60

    def __init__(self):
        self.session_id = f"master_{uuid.uuid4().hex[:8]}"
        self._core_bricks: List[str] = []
        self._external_bricks: Dict[str, Any] = {}
        self._initialized = False
        self._nerfs_report = _NERF_ACTIVATION_REPORT

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        from bek_core import BekCPU
        self._core_bricks = BekCPU.list()
        logger.info("[Master] OK Core BEK | %d briques", len(self._core_bricks))

        externals = [
            ("hermes", "hermes_core", "hermes"),
            ("swarm", "swarm_core", "run_bek_swarm_sync"),
            ("web", "web_agent", "web_agent_instance"),
            ("orchestrator", "bek_orchestrator", "bek_orchestrator"),
            ("memory_coordinator", "memory_coordinator", "coordinate_memories_async"),
            ("hindsight", "hindsight_memory", "hindsight_build_context"),
            ("provider_manager", "provider_manager", "provider_manager"),
        ]
        for key, mod_name, attr in externals:
            try:
                module = __import__(mod_name, fromlist=[attr])
                self._external_bricks[key] = getattr(module, attr)
                logger.info("[Master] OK %s", key)
            except Exception as e:
                logger.warning("[Master] ATTENTION %s : %s", key, e)

        self._initialized = True
        logger.info(
            "[Master] Init | core=%d | external=%d | nerfs=%d",
            len(self._core_bricks), len(self._external_bricks),
            len(self._nerfs_report.get("ok", [])),
        )

    def _detect_intent(self, query: str) -> Optional[str]:
        q = query.lower()
        if any(kw in q for kw in VISION_TRIGGERS):
            return "vision"
        if any(kw in q for kw in WEB_TRIGGERS):
            return "web"
        if any(kw in q for kw in SHELL_TRIGGERS):
            return "shell"
        return None

    # ─── BEK-GA : Récupération du prompt évolutif ───
    def _get_ga_prompt(self) -> str:
        """Demande au moteur génétique le meilleur prompt évolutif."""
        try:
            from nerves.ga_nerves import get_ga_engine
            best = get_ga_engine().select_best_gene()
            logger.debug("[BEK-GA] Gène actif : %s (fitness=%s)", best.gene_id, best.fitness)
            return best.prompt_template
        except Exception:
            return "Exécute la tâche de manière concise et directe."

    # ─── BEK-GA : Enregistrement du fitness ───
    def _record_ga_fitness(self, query: str, result: dict, elapsed_ms: float):
        """Enregistre le fitness du gène actif dans le moteur génétique."""
        try:
            from nerves.ga_nerves import get_ga_engine
            engine = get_ga_engine()
            best_gene = engine.select_best_gene()
            tokens_est = len(str(query)) // 4 + len(str(result.get("response", ""))) // 4
            success = result.get("status") == "success"
            engine.calculate_fitness(best_gene, success, elapsed_ms, tokens_est)
            if not success:
                engine.evolve()
                logger.info("[BEK-GA] ⚡ Évolution déclenchée (échec master)")
        except Exception as ga_exc:
            logger.debug("[BEK-GA] Enregistrement fitness ignoré : %s", ga_exc)

    # ═════════════════════════════════════════════════════════════════════════
    # POINT D'ENTRÉE
    # ═════════════════════════════════════════════════════════════════════════
    async def process(
        self,
        user_query: str,
        provider: str = "nvidia",
        model: str = "nvidia/nemotron-3-super-120b-a12b",
    ) -> Dict[str, Any]:
        t0 = time.monotonic()
        self._ensure_initialized()
        from bek_core import BekCPU

        # ★ BEK-GA : Récupération du prompt évolutif
        ga_prompt = self._get_ga_prompt()
        logger.debug("[BEK-GA] Prompt actif : %s...", ga_prompt[:80])

        result = {
            "status": "success",
            "response": "",
            "tier": "TIER_3",
            "intent": None,
            "bricks_used": [],
            "duration_ms": 0,
            "session_id": self.session_id,
        }

        intent = self._detect_intent(user_query)
        result["intent"] = intent

        # ─── BEK-REX ───
        try:
            routing = BekCPU.execute("BEK-REX", "bek_rex_route", query=user_query)
            tier = routing.get("tier", "TIER_3")
            logger.info("[Master] BEK-REX -> %s", tier)
        except Exception as e:
            logger.warning("[Master] BEK-REX echec : %s", e)
            tier = "TIER_3"

        if intent in ("vision", "web", "shell"):
            tier = "TIER_3"
            logger.info("[Master] Intent=%s -> TIER_3 force", intent)

        result["tier"] = tier
        result["bricks_used"].append("BEK-REX")

        # ─── BEK-ECO ───
        cache_key = f"{tier}:{user_query.lower().strip()}"
        try:
            limits = BekCPU.execute("BEK-ECO", "bek_eco_check_limits")
            if limits.get("daily_remaining", 0) <= 0:
                result["status"] = "error"
                result["message"] = "Quota BEK-ECO atteint."
                elapsed_ms = (time.monotonic() - t0) * 1000
                self._record_ga_fitness(user_query, result, elapsed_ms)
                return result

            cached = BekCPU.execute("BEK-ECO", "bek_eco_cache_get", key=cache_key)
            if cached and cached.get("value"):
                cached_val = cached["value"]
                if isinstance(cached_val, dict):
                    result["response"] = cached_val.get("response", str(cached_val))
                else:
                    result["response"] = str(cached_val)
                result["bricks_used"].append("BEK-ECO")
                result["duration_ms"] = int((time.monotonic() - t0) * 1000)
                result["cached"] = True
                logger.info("[Master] BEK-ECO CACHE HIT")

                # ★ BEK-GA : Enregistrement du fitness
                elapsed_ms = (time.monotonic() - t0) * 1000
                self._record_ga_fitness(user_query, result, elapsed_ms)
                return result
            result["bricks_used"].append("BEK-ECO")
        except Exception as e:
            logger.warning("[Master] BEK-ECO echec : %s", e)

        # ─── MEMORY ───
        memory_context = ""
        if tier != "TIER_0":
            memory_context = await self._build_memory_context(user_query)
            if memory_context:
                result["bricks_used"].append("MEMORY")

        # ─── DECISION ───
        if tier == "TIER_0" and not intent:
            response = await self._llm_direct(user_query, memory_context, provider, model)
            result["bricks_used"].append("LLM_DIRECT")
        elif intent == "vision":
            response = await self._execute_vision(user_query)
            result["bricks_used"].append("HERMES_VISION")
        elif intent == "web":
            response = await self._execute_web(user_query)
            result["bricks_used"].append("WEB_AGENT")
        elif intent == "shell":
            response = await self._execute_shell(user_query)
            result["bricks_used"].append("HERMES_SHELL")
        else:
            response = await self._pipeline_full(user_query, memory_context, tier, provider, model)
            result["bricks_used"].append("PIPELINE_FULL")

        result["response"] = response

        # ─── BEK-LOOP ───
        try:
            BekCPU.execute("BEK-LOOP", "bek_loop_record",
                           episode={"query": user_query[:200], "tier": tier,
                                    "intent": intent, "response_len": len(response)})
            result["bricks_used"].append("BEK-LOOP")
        except Exception:
            pass

        # ─── Cache ───
        if intent != "vision":
            try:
                BekCPU.execute("BEK-ECO", "bek_eco_cache_set",
                               key=cache_key,
                               value={"response": response, "tier": tier})
            except Exception:
                pass

        result["duration_ms"] = int((time.monotonic() - t0) * 1000)

        # ★ BEK-GA : Enregistrement du fitness
        elapsed_ms = (time.monotonic() - t0) * 1000
        self._record_ga_fitness(user_query, result, elapsed_ms)

        return result

    # ═════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════════════════════════════
    async def _build_memory_context(self, query: str) -> str:
        parts = []
        coord = self._external_bricks.get("memory_coordinator")
        if coord:
            try:
                unified = await coord(query, max_chars=3000)
                if unified and unified.context:
                    parts.append(unified.context)
            except Exception:
                pass
        if not parts:
            hindsight = self._external_bricks.get("hindsight")
            if hindsight:
                try:
                    ctx = hindsight(query, max_results=3)
                    if ctx:
                        parts.append(ctx)
                except Exception:
                    pass
        return "\n\n".join(parts)

    async def _execute_vision(self, query: str) -> str:
        q = query.lower()
        is_video = any(k in q for k in ("vidéo", "video", "film"))

        if is_video:
            logger.info("[Master] VIDEO via services.vision (timeout etendu)")
            try:
                from services.vision import generate_video_with_provider
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: generate_video_with_provider(prompt=query)
                )
                if not isinstance(result, dict):
                    return f"(resultat invalide : {type(result).__name__})"
                status = result.get("status", "")
                if status == "success" and result.get("filepath"):
                    return (
                        f"VIDEO GENEREE : {result.get('filename', 'video.mp4')}\n"
                        f"Chemin : {result.get('filepath')}\n"
                        f"Duree : {result.get('duration', '?')}s\n"
                        f"Provider : {result.get('provider', '?')} "
                        f"({result.get('model_version', '?')})\n"
                        f"Mode : {result.get('mode_used', '?')}\n"
                        f"Reference images : {result.get('reference_images_count', 0)}"
                    )
                if result.get("message"):
                    return f"(echec video) {result['message']}"
                return f"(resultat vide) {result}"
            except Exception as e:
                logger.error("[Master] Vision echec : %s", e)
                traceback.print_exc()
                return f"(erreur vision : {e})"

        hermes = self._external_bricks.get("hermes")
        if not hermes:
            return "(Hermes indisponible)"

        try:
            logger.info("[Master] IMAGE via Hermes")
            result = hermes.dispatch("generate_image", {"prompt": query})
            if not result or result.get("status") == "FAILED":
                return "(echec generate_image)"
            task_data = None
            results_dict = result.get("results", {})
            for task_id, task_res in results_dict.items():
                if isinstance(task_res, dict):
                    task_data = task_res.get("data", task_res)
                    break
            if not task_data:
                task_data = result.get("data", result)
            if isinstance(task_data, dict):
                if task_data.get("message"):
                    return str(task_data["message"])
            return str(task_data) if task_data else "(resultat vide pour image)"
        except Exception as e:
            logger.error("[Master] Image echec : %s", e)
            return f"(erreur image : {e})"

    async def _execute_web(self, query: str) -> str:
        web = self._external_bricks.get("web")
        if not web:
            return "(WebAgent indisponible)"
        try:
            logger.info("[Master] WebAgent pipeline")
            return web.run_pipeline(query)
        except Exception as e:
            logger.error("[Master] Web echec : %s", e)
            return f"(erreur web : {e})"

    async def _execute_shell(self, query: str) -> str:
        hermes = self._external_bricks.get("hermes")
        if not hermes:
            return "(Hermes indisponible)"
        try:
            import re
            m = re.search(r"(?:commande|command)\s*[:\-]?\s*(.+)", query, re.I)
            cmd = m.group(1).strip() if m else query
            result = hermes.dispatch("execute_command", {"command": cmd})
            if result and result.get("status") != "FAILED":
                return str(result.get("data", result))
        except Exception as e:
            logger.error("[Master] Shell echec : %s", e)
            return f"(erreur shell : {e})"

    async def _llm_direct(self, query, memory_context, provider, model) -> str:
        pm = self._external_bricks.get("provider_manager")
        if not pm:
            return "(provider_manager indisponible)"

        system_parts = ["Tu es BEK, un agent IA puissant et precis."]
        if memory_context:
            system_parts.append(f"\n[MEMOIRE]\n{memory_context[:3000]}")

        messages = [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": query},
        ]

        chunks = []
        try:
            for item in pm.execute_chat_stream(
                messages=messages, provider=provider, model=model,
                temperature=0.7, max_tokens=2048,
            ):
                if "chunk" in item:
                    chunks.append(item["chunk"])
        except Exception as e:
            logger.error("[Master] LLM echec : %s", e)
            return f"(erreur LLM : {e})"
        return "".join(chunks) or "(pas de reponse)"

    async def _pipeline_full(self, query, memory_context, tier, provider, model) -> str:
        if tier == "TIER_4":
            swarm = self._external_bricks.get("swarm")
            if swarm:
                try:
                    pm = self._external_bricks.get("provider_manager")
                    api_key = "dummy"
                    if pm:
                        api_key = pm.get_api_key(f"{provider.upper()}_API_KEY") or "dummy"
                    result = await swarm(user_query=query, api_key=api_key,
                                        provider=provider, model=model)
                    if result and len(result) > 20:
                        return result
                except Exception:
                    pass

        if tier == "TIER_3":
            orch = self._external_bricks.get("orchestrator")
            if orch:
                try:
                    report = orch.run(query)
                    if report and len(report) > 20:
                        return report
                except Exception:
                    pass

        return await self._llm_direct(query, memory_context, provider, model)

    async def close(self):
        for closer_name, module_name in [
            ("hindsight_close", "hindsight_memory"),
            ("shutdown_event_bus_sync", "event_bus_client"),
        ]:
            try:
                module = __import__(module_name, fromlist=[closer_name])
                closer = getattr(module, closer_name, None)
                if closer:
                    closer()
                    logger.debug("[Master] %s ferme", closer_name)
            except Exception as e:
                logger.debug("[Master] %s : %s", closer_name, e)

    def stats(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return {
            "session_id": self.session_id,
            "core_bricks": self._core_bricks,
            "core_count": len(self._core_bricks),
            "external_bricks": list(self._external_bricks.keys()),
            "external_count": len(self._external_bricks),
            "nerfs_ok": len(self._nerfs_report.get("ok", [])),
            "nerfs_failed": len(self._nerfs_report.get("failed", [])),
            "nerfs_skipped": len(self._nerfs_report.get("skipped", [])),
        }


bek_master = BEKMasterOrchestrator()


if __name__ == "__main__":
    async def _test():
        master = BEKMasterOrchestrator()
        print("=" * 70)
        print("TEST BEK MASTER v2.4 (BEK-GA intégré)")
        print("=" * 70)
        print("\n[Stats]")
        for k, v in master.stats().items():
            print(f"  {k}: {v}")

        tests = ["bonjour", "génère une vidéo de chat"]

        try:
            for q in tests:
                print(f"\n[Test] {q!r}")
                r = await master.process(q)
                print(f"  Status : {r['status']}")
                print(f"  Tier   : {r['tier']}")
                print(f"  Intent : {r['intent']}")
                print(f"  Bricks : {r['bricks_used']}")
                print(f"  Cached : {r.get('cached', False)}")
                print(f"  Duree  : {r['duration_ms']}ms")
                resp = r['response']
                print(f"  Reponse: {resp}")
        finally:
            await master.close()

    asyncio.run(_test())