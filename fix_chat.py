import pathlib

code = '''# ==============================================================================
# BEK-v16 — Routeur Chat Streaming & Human-in-the-Loop (routers/chat.py)
# ==============================================================================
from __future__ import annotations

import ast
import json
import logging
import re
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from bek_eval_guard import evaluate_response_quality
from fast_math import HyperLogLog, MinHashSimilarity
from hermes_core import hermes
from memory import search_memory
from provider_manager import provider_manager
from services.action_executor import execute_agent_crm_tool
from services.tasks import CURRENT_OS_NAME

ACTION_REGEX = re.compile(r"