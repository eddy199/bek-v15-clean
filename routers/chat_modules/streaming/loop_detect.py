# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Streaming : Détection de boucle (v1.6.19)
# ------------------------------------------------------------------------------
# ★ v1.6.19 : extraction du monolithe streaming.py → package modulaire
#   - _LoopDetector : détecte quand le LLM répète le même chunk N fois
# ==============================================================================
from __future__ import annotations

from collections import Counter
from typing import List

from .constants import LOOP_WINDOW, LOOP_THRESHOLD


class _LoopDetector:
    """
    Détecte les boucles de génération LLM.

    Principe : garde les N derniers chunks (normalisés) dans un buffer
    glissant. Si un même chunk apparaît >= threshold fois dans la fenêtre,
    une boucle est détectée.
    """

    def __init__(self, window: int = LOOP_WINDOW, threshold: int = LOOP_THRESHOLD):
        self.window = window
        self.threshold = threshold
        self._buffer: List[str] = []

    def add(self, chunk: str) -> bool:
        """Ajoute un chunk et retourne True si une boucle est détectée."""
        if not chunk:
            return False
        normalized = chunk.strip().lower()[:80]
        if not normalized or len(normalized) < 5:
            return False
        self._buffer.append(normalized)
        if len(self._buffer) > self.window:
            self._buffer.pop(0)
        if len(self._buffer) < self.window:
            return False
        counts = Counter(self._buffer)
        _, most_common_count = counts.most_common(1)[0]
        return most_common_count >= self.threshold

    def reset(self) -> None:
        """Vide le buffer (utile entre deux requêtes)."""
        self._buffer.clear()