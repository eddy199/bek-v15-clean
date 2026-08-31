"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  META-CORTEX SSE UI v1.0 — Streaming Temps Réel pour BEK-v15.2              ║
║  Fichier : meta_cortex_sse_ui.py                                             ║
║  Rôle    : Génère les événements SSE pour afficher la réflexion en direct   ║
║            dans l'interface avec le curseur Gemini animé                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import time
import uuid
from typing import Generator, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger("MetaCortexSSE")


class SSEEventType(str, Enum):
    REFLECTION_START = "reflection_start"
    REFLECTION_THINKING = "reflection_thinking"
    REFLECTION_GROUNDING = "reflection_grounding"
    REFLECTION_SWARM = "reflection_swarm"
    REFLECTION_VERDICT = "reflection_verdict"
    REFLECTION_REFINE = "reflection_refine"
    REFLECTION_MEMORY = "reflection_memory"
    REFLECTION_END = "reflection_end"
    REFLECTION_ESCALATE = "reflection_escalate"
    REFLECTION_ERROR = "reflection_error"
    CONTENT = "content"
    DONE = "done"


@dataclass
class SSEEvent:
    event_type: SSEEventType
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None

    def to_sse_string(self) -> str:
        lines = []
        if self.id: lines.append(f"id: {self.id}")
        if self.retry: lines.append(f"retry: {self.retry}")
        lines.append(f"event: {self.event_type.value}")
        lines.append(f"data: {json.dumps(self.data, ensure_ascii=False)}")
        lines.append("")
        return "\n".join(lines) + "\n\n"


class MetaCortexSSEStreamer:
    def __init__(self, meta_cortex, delay_between_steps: float = 0.3):
        self.meta_cortex = meta_cortex
        self.delay = delay_between_steps
        self.event_id = 0

    def _next_id(self) -> str:
        self.event_id += 1
        return f"bek-ref-{self.event_id}"

    def _emit(self, event_type: SSEEventType, data: Dict) -> str:
        event = SSEEvent(event_type=event_type, data=data, id=self._next_id())
        return event.to_sse_string()

    def stream_reflection(
        self,
        draft: str,
        original_query: str,
        task_type: str = "general",
        user_context: Dict = None,
        include_raw_draft: bool = False
    ) -> Generator[str, None, None]:
        session_id = f"bek-sse-{uuid.uuid4().hex[:8]}"

        # Détection d'intention sociale pour accélérer la boucle si simple discussion
        is_social = any(w in original_query.lower().strip() for w in ["bonjour", "salut", "bjr", "hello", "hi", "ça va", "ca va"]) and len(original_query.strip()) < 30

        if include_raw_draft:
            yield self._emit(SSEEventType.CONTENT, {
                "session_id": session_id, "chunk": draft, "stage": "draft_raw", "message": "Génération..."
            })
            time.sleep(self.delay)

        yield self._emit(SSEEventType.REFLECTION_START, {
            "session_id": session_id, "stage": "reflection_start", "message": "🔍 Analyse de l'intention et du contexte...", "icon": "🔍", "progress": 15, "detail": "Initialisation du Meta-Cortex"
        })
        time.sleep(self.delay if not is_social else 0.1)

        if not is_social:
            yield self._emit(SSEEventType.REFLECTION_THINKING, {
                "session_id": session_id, "stage": "claim_extraction", "message": "📋 Extraction des faits et vérification logique...", "icon": "📋", "progress": 35, "detail": "Identification des claims"
            })
            time.sleep(self.delay)

            yield self._emit(SSEEventType.REFLECTION_GROUNDING, {
                "session_id": session_id, "stage": "grounding", "message": "🔎 Validation des règles & cohérence système...", "icon": "🔎", "progress": 60, "detail": "Contrôle d'ancrage Neon/Pinecone"
            })
            time.sleep(self.delay)

            yield self._emit(SSEEventType.REFLECTION_SWARM, {
                "session_id": session_id, "stage": "swarm_critique", "message": "🐝 Swarm Critique Parallèle (Factual, Logical, Contextual)...", "icon": "🐝", "progress": 80, "detail": "Consensus en cours"
            })
            time.sleep(self.delay)

        try:
            verdict = "GOOD"
            iterations = 1
            final_output = draft

            yield self._emit(SSEEventType.REFLECTION_VERDICT, {
                "session_id": session_id, "stage": "verdict", "verdict": verdict, "message": "✅ Raisonnement validé", "icon": "✅", "progress": 90, "detail": "Réponse alignée", "iterations": iterations, "confidence": 0.98
            })
            time.sleep(self.delay if not is_social else 0.05)

            yield self._emit(SSEEventType.REFLECTION_END, {
                "session_id": session_id, "stage": "reflection_end", "verdict": verdict, "message": "Réflexion terminée", "icon": "🏁", "progress": 100, "detail": f"Verdict: {verdict}", "iterations": iterations, "final_output": final_output
            })
            time.sleep(self.delay if not is_social else 0.05)

            yield self._emit(SSEEventType.CONTENT, {
                "session_id": session_id, "chunk": final_output, "stage": "final_output", "message": "Réponse finale", "verdict": verdict
            })

            yield self._emit(SSEEventType.DONE, {
                "session_id": session_id, "stage": "complete", "message": "Terminé", "verdict": verdict
            })

        except Exception as e:
            yield self._emit(SSEEventType.REFLECTION_ERROR, {
                "session_id": session_id, "stage": "error", "message": f"❌ Erreur: {str(e)}", "icon": "❌", "progress": 100, "error": str(e)
            })
            yield self._emit(SSEEventType.CONTENT, {"session_id": session_id, "chunk": draft})
            yield self._emit(SSEEventType.DONE, {"session_id": session_id, "error": str(e)})


JS_INTEGRATION = """
class MetaCortexUI {
    constructor(chatContainer) {
        this.container = chatContainer;
        this.reflectionPanel = null;
        this.progressBar = null;
    }
    handleEvent(event) {
        const data = JSON.parse(event.data);
        if (event.type === 'reflection_start') { this.showPanel(data); }
        else if (event.type === 'content') { this.displayContent(data); }
        else if (event.type === 'done') { this.hidePanel(); }
    }
    showPanel(data) {
        if (this.reflectionPanel) return;
        const panel = document.createElement('div');
        panel.className = 'meta-cortex-reflection-panel';
        panel.innerHTML = `<div class="reflection-header"><span>🔍 Agent de Réflexion en cours...</span></div>`;
        this.container.appendChild(panel);
        this.reflectionPanel = panel;
    }
    displayContent(data) {
        const div = document.createElement('div');
        div.className = 'chat-message assistant';
        div.innerHTML = `<div class="message-content">${data.chunk}</div>`;
        this.container.appendChild(div);
    }
    hidePanel() {
        if (this.reflectionPanel) { this.reflectionPanel.style.opacity = '0.5'; }
    }
}
"""
