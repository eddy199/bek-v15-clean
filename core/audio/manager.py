# ==============================================================================
# BEK-v19 — Audio Manager — FIX COUPE RAPIDE — WORKSPACEKIMI — DÉFINITIF
# Fusion: ton ancien PathGuard + websocket emit + mon fix duck
# Creator: BEKKARA Mohamed — Oran DZ — Root: workspacekimi
# ==============================================================================
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bek.audio")

# ========== RACINE workspacekimi — TON CODE GARDÉ ==========
WORKSPACE_ROOT = Path("workspacekimi")
if not WORKSPACE_ROOT.exists():
    WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
    while WORKSPACE_ROOT.name != "workspacekimi" and WORKSPACE_ROOT.parent != WORKSPACE_ROOT:
        WORKSPACE_ROOT = WORKSPACE_ROOT.parent
        if WORKSPACE_ROOT == WORKSPACE_ROOT.parent:
            break

try:
    from core.storage.path_guard import PathGuard
    PathGuard.validate(WORKSPACE_ROOT)
except Exception:
    pass

class AudioManager:
    def __init__(self):
        # FIX v19 PRINCIPAL — AVANT 0.8s coupait trop vite
        self.VAD_SILENCE_THRESHOLD = 1.8
        self.KEEP_BUFFER = 0.6
        self.SAMPLE_RATE = 16000
        self.SAMPLE_RATE_COMPAT = 16000
        
        self.is_speaking = False
        self.is_tool_running = False
        self.current_volume = 1.0
        self._volume = 1.0
        self._is_ducked = False
        self._is_playing = False
        self._duck_volume = 0.15
        self.BEK_STREAM_TIMEOUT_SEC = 300
        self._lock = asyncio.Lock()

    # ========== FIX: DUCK AU LIEU DE STOP ==========
    async def duck(self, volume: float = 0.15):
        async with self._lock:
            self.current_volume = volume
            self._volume = volume
            self._is_ducked = True
            logger.info(f"[BEK v19 AUDIO workspacekimi] duck to {volume} - DAG running, chat boot ALIVE")
            await self.emit("audio:duck", {"volume": volume, "keep_alive": True, "chat_boot": "ALIVE"})
            return {"status": "ducked", "volume": volume, "chat_boot": "ALIVE"}

    async def unduck(self):
        async with self._lock:
            self.current_volume = 1.0
            self._volume = 1.0
            self._is_ducked = False
            logger.info("[BEK v19 AUDIO] unduck to 1.0 - DAG fini")
            await self.emit("audio:unduck", {"volume": 1.0})
            return {"status": "unducked", "volume": 1.0}

    async def on_tool_start(self):
        self.is_tool_running = True
        return await self.duck(self._duck_volume)

    async def on_tool_end(self):
        self.is_tool_running = False
        return await self.unduck()

    async def on_vad_silence(self, silence_duration: float) -> bool:
        if silence_duration < self.VAD_SILENCE_THRESHOLD:
            return False
        if self.is_tool_running:
            await self.duck(0.15)
            return False
        return True

    # Ton ancien bug était ici:
    async def stop(self):
        logger.warning("[BEK v19] stop() appelé → converti en duck() pour éviter coupe chat boot")
        return await self.duck(self._duck_volume)

    async def emit(self, event: str, data: dict):
        try:
            from app import sio
            await sio.emit(event, data)
        except Exception:
            pass

    def get_state(self):
        return {
            "volume": self._volume,
            "is_ducked": self._is_ducked,
            "is_playing": self._is_playing,
            "vad_silence": self.VAD_SILENCE_THRESHOLD,
            "keep_buffer": self.KEEP_BUFFER,
            "is_tool_running": self.is_tool_running,
            "fix": "VAD 1.8s + duck 15% — chat boot ne coupe plus",
            "app": "BEK Hybrid Agent v19",
            "creator": "BEKKARA Mohamed"
        }

    # Compat
    async def play(self, *args, **kwargs):
        self._is_playing = True
        return {"status": "playing", "volume": self._volume}
    async def pause(self):
        return await self.duck()
    async def resume(self):
        return await self.unduck()

audio_manager = AudioManager()