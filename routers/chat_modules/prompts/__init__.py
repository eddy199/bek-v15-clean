# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v19 — Chat Module : Prompts (Assemblage global)
# ==============================================================================

from .core import get_core_prompt
from .lang import get_lang_prompt
from .anti_hallucination import get_anti_hallucination_prompt
from .decision_table import get_decision_table_prompt
from .orchestration import get_orchestration_prompt
from .memory import get_memory_prompt
from .web import get_web_prompt
from .image import get_image_prompt
from .video import get_video_prompt
from .action_format import get_action_format_prompt

# 🏛️ ASSEMBLAGE DES RÈGLES D'OR (C'est cette variable qui manquait !)
BEK_GOLDEN_RULES = "\n\n".join([
    get_core_prompt(),
    get_lang_prompt(),
    get_anti_hallucination_prompt(),
    get_decision_table_prompt(),
    get_orchestration_prompt(),
    get_memory_prompt(),
    get_web_prompt(),
    get_image_prompt(),
    get_video_prompt(),
    get_action_format_prompt(),
])

__all__ = [
    "BEK_GOLDEN_RULES",
    "get_core_prompt",
    "get_lang_prompt",
    "get_anti_hallucination_prompt",
    "get_decision_table_prompt",
    "get_orchestration_prompt",
    "get_memory_prompt",
    "get_web_prompt",
    "get_image_prompt",
    "get_video_prompt",
    "get_action_format_prompt",
]