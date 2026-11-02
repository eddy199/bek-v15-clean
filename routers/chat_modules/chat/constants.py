# ==============================================================================
# BEK-v18 — Chat : Constants
# ------------------------------------------------------------------------------
# ★ v19.24 (2026-10-24) — Augmentation des limites pour analyses multi-fichiers
#   - MAX_CHARS_PER_MESSAGE : 20000 → 60000
#   - MAX_TOTAL_CHARS       : 60000 → 120000
#   - BEK_MAX_TOKENS        : 4096  → 8192
#   - AUCUNE AUTRE MODIFICATION (100 % rétrocompatible)
# ==============================================================================
from __future__ import annotations

import os
import re
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# LIMITES DE SÉCURITÉ
# ══════════════════════════════════════════════════════════════════════════════

MAX_REQUEST_BYTES = 20_000_000
MAX_INPUT_MESSAGES = 200
MAX_PROVIDER_LENGTH = 64
MAX_MODEL_LENGTH = 128
MAX_MEMORY_CHARS = 4_000

# ★ v19.24 — Limites de troncature (consommées par streaming/core.py)
MAX_CHARS_PER_MESSAGE = int(os.getenv("BEK_MAX_CHARS_PER_MESSAGE", "60000")) # Avant 20000
MAX_TOTAL_CHARS = int(os.getenv("BEK_MAX_TOTAL_CHARS", "120000"))            # Avant 60000
BEK_MAX_TOKENS = int(os.getenv("BEK_MAX_TOKENS", "8192"))                    # Avant 4096

# Limites fichiers joints
MAX_FILE_CHARS = 20_000
MAX_TOTAL_FILE_CHARS = int(os.getenv("BEK_MAX_TOTAL_FILE_CHARS", "120000"))

# Timeouts (conservés de v19.23)
MEMORY_COORDINATOR_TIMEOUT_SEC = float(os.getenv("BEK_MEMORY_COORDINATOR_TIMEOUT", "90.0"))
MEMORY_PINECONE_TIMEOUT_SEC = float(os.getenv("BEK_MEMORY_PINECONE_TIMEOUT", "20.0"))
MEMORY_HINDSIGHT_TIMEOUT_SEC = float(os.getenv("BEK_MEMORY_HINDSIGHT_TIMEOUT", "20.0"))
HERMES_PLANNER_TIMEOUT_SEC = float(os.getenv("BEK_HERMES_PLANNER_TIMEOUT", "3.0"))


# ══════════════════════════════════════════════════════════════════════════════
# REGEX DE VALIDATION (inchangés)
# ══════════════════════════════════════════════════════════════════════════════

_PROVIDER_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
_MODEL_RE = re.compile(r"^[a-zA-Z0-9_./:-]{1,128}$")

_FILES_ATTACHED_RE = re.compile(
    r"\[\s*Fichiers?\s+joints?\s*:\s*([^\]]+)\]",
    re.IGNORECASE,
)

_STRUCTURAL_LINE_RE = re.compile(
    r"^\s*("
    r"#{1,6}\s"
    r"|def\s|class\s|async\s+def\s"
    r"|function\s|export\s|const\s|let\s|var\s"
    r"|public\s|private\s|protected\s"
    r"|<\w+[^>]*>"
    r"|[\{\}\[\]]\s*$"
    r"|-\s|\*\s|\d+\.\s"
    r"|={3,}|-{3,}"
    r")",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
# EXTENSIONS & PATHS (inchangés)
# ══════════════════════════════════════════════════════════════════════════════

_TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".xml", ".csv", ".tsv", ".log", ".ini",
    ".cfg", ".conf", ".toml", ".sql", ".sh", ".bash", ".bat", ".ps1",
    ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb", ".php",
    ".env", ".gitignore", ".dockerfile", ".makefile", ".gradle",
}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_UPLOAD_DIRS = [
    _WORKSPACE_ROOT / "uploads",
    _WORKSPACE_ROOT / "data" / "uploads",
    _WORKSPACE_ROOT / "generated",
    _WORKSPACE_ROOT / "data" / "generated",
    _WORKSPACE_ROOT / "static" / "uploads",
]