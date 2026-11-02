# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio, json, logging, math, os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from services.episode_logger import fetch_recent_episodes

logger = logging.getLogger("bek.reflex_loop")

DEFAULT_HOURS = 24
MIN_OCCURRENCES = 3
TOP_N = 20
REPORTS_DIR = "./data/reflex_reports"
AUTO_FIX_MIN_CONFIDENCE = 0.90
AUTONOMOUS_INTERVAL_SEC = 120

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    return default if not v else v in ("1", "true", "yes", "on")
def _env_float(name: str, default: float) -> float:
    try: return float(os.getenv(name, str(default)))
    except (TypeError, ValueError): return default
def _env_int(name: str, default: int) -> int:
    try: return int(os.getenv(name, str(default)))
    except (TypeError, ValueError): return default

class ReflexLoop:
    def __init__(self, hours: int = DEFAULT_HOURS, min_occurrences: int = MIN_OCCURRENCES, top_n: int = TOP_N, reports_dir: str = REPORTS_DIR, sio: Any = None) -> None:
        self.hours = hours; self.min_occurrences = min_occurrences; self.top_n = top_n
        self.reports_dir = Path(reports_dir); self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.sio = sio; self._stop_autonomous = False

    async def _stream(self, msg: str, level: str = "info"):
        logger.info("[ReflexStream] %s", msg)
        if self.sio:
            try: await self.sio.emit("reflex:stream", {"message": msg, "level": level})
            except Exception: pass

    async def run_cycle(self, hours: Optional[int] = None, with_critic: bool = True, critic_max_patterns: int = 3, with_code_analysis: bool = True, with_alter_egos: bool = True, with_skills: bool = True, auto_fix: bool = False) -> Dict[str, Any]:
        h = hours if hours is not None else self.hours
        started_at = datetime.now(timezone.utc)
        await self._stream("🧠 [ReflexLoop] Démarrage du cycle...", "start")

        episodes = fetch_recent_episodes(hours=h, limit=5000)
        if not episodes:
            await self._stream("  → Aucun épisode récent.", "warn")
            return self._empty_report(h, started_at)
        await self._stream(f"  → {len(episodes)} épisodes lus.", "info")

        patterns = self._mine_patterns(episodes)
        significant = [p for p in patterns if p["count"] >= self.min_occurrences]
        significant.sort(key=lambda p: p["count"] * p["avg_latency_ms"], reverse=True)
        top_patterns = significant[: self.top_n]
        await self._stream(f"  → {len(significant)} patterns significatifs.", "info")

        enriched_critiques = []
        for pattern in top_patterns:
            if pattern["signature"]["status"] != "error": continue
            if len(enriched_critiques) >= critic_max_patterns: break
            await self._stream(f"  🔍 Analyse : {pattern['signature']['action']}...", "info")
            enriched = await self._analyze_error_pattern(pattern=pattern, with_critic=with_critic, with_code_analysis=with_code_analysis, with_alter_egos=with_alter_egos, with_skills=with_skills)
            enriched_critiques.append(enriched)

        auto_fixes_applied = []
        if auto_fix:
            await self._stream("  🔧 Auto-correction...", "info")
            auto_fixes_applied = await self._apply_auto_fixes(enriched_critiques)

        finished_at = datetime.now(timezone.utc)
        report = {
            "report_id": f"reflex_{started_at.strftime('%Y%m%d_%H%M%S')}",
            "generated_at_utc": started_at.isoformat(),
            "duration_ms": round((finished_at - started_at).total_seconds() * 1000, 2),
            "window_hours": h, "summary": self._compute_summary(episodes, patterns, significant),
            "top_patterns": top_patterns, "critiques_enriched": enriched_critiques,
            "auto_fixes_applied": auto_fixes_applied,
        }
        self._write_report(report)
        await self._stream("✅ Cycle terminé.", "success")
        return report

    async def _analyze_error_pattern(self, pattern: Dict[str, Any], with_critic: bool = True, with_code_analysis: bool = True, with_alter_egos: bool = True, with_skills: bool = True) -> Dict[str, Any]:
        sig = pattern["signature"]; action = sig["action"]
        result = {"pattern_signature": sig, "count": pattern["count"], "avg_latency_ms": pattern["avg_latency_ms"], "critic_analysis": None, "code_analysis": None, "alter_ego_advice": None, "suggested_fix": None, "confidence": 0.0, "source_file": None}

        if with_critic:
            await self._stream("    ⚖️ Critic...", "debug")
            result["critic_analysis"] = await asyncio.to_thread(self._call_critic, pattern)
        if with_code_analysis:
            source = self._find_source_file_for_action(action)
            if source:
                await self._stream(f"    👁️ Lecture de {source}...", "debug")
                result["source_file"] = source
                result["code_analysis"] = await asyncio.to_thread(self._analyze_code_with_codex, source, pattern)
        if with_alter_egos:
            await self._stream("    🎭 Alter Ego...", "debug")
            result["alter_ego_advice"] = await asyncio.to_thread(self._consult_alter_ego, pattern)
        result["suggested_fix"] = self._synthesize_fix(result, pattern)
        result["confidence"] = self._compute_confidence(result)
        
        # ★ PATCH 1 : On grave la leçon dans la mémoire vectorielle !
        if result["suggested_fix"] and result["confidence"] > 0.5:
            try:
                from memory import save_to_memory
                lesson = f"[LECON CODEX] Action: {action} | Erreur: {sig.get('error_type')} | Solution: {result['suggested_fix'][:500]}"
                save_to_memory(lesson)
                await self._stream(f"    💾 Leçon gravée en mémoire pour {action}", "info")
            except Exception as e:
                logger.warning(f"Impossible de sauvegarder la leçon : {e}")

        return result

    def _find_source_file_for_action(self, action: str) -> Optional[str]:
        return {"codex_agent": "nerves/coder_nerves.py", "codex_editor": "nerves/coder_nerves.py", "web_sync": "web_agent.py", "generate_image": "services/vision/image_generation.py", "generate_video": "services/vision/video_generation.py", "hindsight_query": "hindsight_memory.py", "orchestrate": "bek_orchestrator.py"}.get(action)

    def _analyze_code_with_codex(self, source_file: str, pattern: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            from hermes_core import hermes
            if not hermes: return None
            prompt = f"Analyse `{source_file}` pour l'erreur `{pattern['signature'].get('error_type')}`.\nMessage : {pattern['sample_messages'][0] if pattern['sample_messages'] else 'N/A'}\nIdentifie le bug et propose un correctif."
            result = hermes.dispatch("codex_agent", {"task_description": prompt, "target_file": source_file})
            return {"status": "success", "analysis": result.get("message", "")[:2000] if isinstance(result, dict) else str(result)[:2000]}
        except Exception as e: return None

    async def _apply_auto_fixes(self, critiques: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        applied = []
        for c in critiques:
            if c.get("confidence", 0) < AUTO_FIX_MIN_CONFIDENCE: continue
            if not c.get("source_file") or not c.get("suggested_fix"): continue
            if c["source_file"] in ("app.py", "hermes_core.py", "security_guard.py", "provider_manager.py", "core/brain.py"):
                await self._stream(f"    ⏭️ Refusé (critique) : {c['source_file']}", "warn")
                continue
            await self._stream(f"    🛠️ Fix sur {c['source_file']}...", "info")
            try:
                from hermes_core import hermes
                result = hermes.dispatch("codex_editor", {"task_description": c["suggested_fix"], "target_file": c["source_file"]})
                applied.append({"pattern": c["pattern_signature"], "file": c["source_file"], "result": result})
                await self._stream(f"    ✅ Fix appliqué : {c['source_file']}", "success")
            except Exception as e: await self._stream(f"    ❌ Échec : {e}", "error")
        return applied

    async def start_autonomous(self, interval_sec: int = AUTONOMOUS_INTERVAL_SEC, auto_fix: bool = True) -> None:
        self._stop_autonomous = False
        await self._stream(f"🔁 Autonome activé ({interval_sec//60} min)", "start")
        while not self._stop_autonomous:
            try:
                await asyncio.sleep(interval_sec)
                if self._stop_autonomous: break
                await self.run_cycle(hours=24, auto_fix=auto_fix)
            except asyncio.CancelledError: break
            except Exception as e: logger.error(f"Erreur boucle : {e}")

    def stop_autonomous(self) -> None: self._stop_autonomous = True

    def _call_critic(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from services.critic import Critic
            return Critic(dry_run=True).analyze_pattern(pattern)
        except Exception as e: return {"status": "unavailable", "error": str(e)}

    def _consult_alter_ego(self, pattern: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            from routing import _bek_rex_get_alter_ego_prompt
            from provider_manager import provider_manager
        except ImportError: return None
        error_type = (pattern["signature"].get("error_type") or "").lower()
        ego = "atlas" if "timeout" in error_type else "oracle" if "code" in error_type else "suntzu"
        try:
            ego_prompt = _bek_rex_get_alter_ego_prompt(ego)
            if not ego_prompt: return None
            messages = [{"role": "system", "content": ego_prompt}, {"role": "user", "content": f"Analyse : {pattern['signature']}. Stratégie ?"}]
            response = ""
            for chunk in provider_manager.execute_chat_stream(
                messages=messages,
                provider="nvidia",
                model="nvidia/nemotron-3.5-super-vl-120b-a12b",
                max_tokens=500,
            ):
                if "chunk" in chunk: response += chunk["chunk"]
            return {"alter_ego": ego, "advice": response.strip()[:1000]}
        except Exception: return None

    def _synthesize_fix(self, analysis: Dict[str, Any], pattern: Dict[str, Any]) -> Optional[str]:
        parts = []
        if analysis.get("critic_analysis", {}).get("fix_suggestion"): parts.append(f"[Critic] {analysis['critic_analysis']['fix_suggestion']}")
        if analysis.get("code_analysis"): parts.append(f"[Code] {analysis['code_analysis'].get('analysis', '')[:400]}")
        if analysis.get("alter_ego_advice"): parts.append(f"[{analysis['alter_ego_advice']['alter_ego'].upper()}] {analysis['alter_ego_advice']['advice'][:400]}")
        return "\n\n".join(parts) if parts else None

    def _compute_confidence(self, analysis: Dict[str, Any]) -> float:
        score = 0.0
        if analysis.get("critic_analysis", {}).get("status") == "success": score += 0.4
        if analysis.get("code_analysis"): score += 0.3
        if analysis.get("alter_ego_advice"): score += 0.2
        return round(min(score, 1.0), 2)

    def _mine_patterns(self, episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets = defaultdict(list)
        for ep in episodes:
            sig = (str(ep.get("action", "unknown")), str(ep.get("status", "unknown")), str(ep.get("error_type", "")))
            buckets[sig].append(ep)
        patterns = []
        for (action, status, error_type), group in buckets.items():
            latencies = [float(e.get("latency_ms") or 0.0) for e in group]
            messages = [str(e.get("message", ""))[:200] for e in group if e.get("message")]
            patterns.append({"signature": {"action": action, "status": status, "error_type": error_type}, "count": len(group), "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0, "sample_messages": messages[:3]})
        return patterns

    def _compute_summary(self, episodes, patterns, significant) -> Dict[str, Any]:
        total = len(episodes)
        success = sum(1 for e in episodes if str(e.get("status")) == "success")
        return {"total_episodes": total, "success_count": success, "error_count": total - success, "patterns_significant": len(significant)}

    def _write_report(self, report: Dict[str, Any]) -> Path:
        path = self.reports_dir / f"{report['report_id']}.json"
        with open(path, "w", encoding="utf-8") as f: json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        return path

    def _empty_report(self, hours: int, started_at: datetime) -> Dict[str, Any]:
        return {"report_id": f"reflex_{started_at.strftime('%Y%m%d_%H%M%S')}", "summary": {"total_episodes": 0}}