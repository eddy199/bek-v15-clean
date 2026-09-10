# ==============================================================================
# BEK-v16 — Routeur Chat Streaming & Human-in-the-Loop (routers/chat.py)
# ==============================================================================
from __future__ import annotations

import re
import json
import ast
import uuid
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from services.tasks import CURRENT_OS_NAME
from services.action_executor import execute_agent_crm_tool
from bek_eval_guard import evaluate_response_quality
from fast_math import HyperLogLog, MinHashSimilarity
from memory import search_memory
from hermes_core import hermes
from provider_manager import provider_manager

try:
    from skills import dispatch_command as dispatch_slash_command
except ImportError:
    dispatch_slash_command = None

try:
    from event_bus import EventBusKafka
    event_bus = EventBusKafka()
except Exception:
    event_bus = None

logger = logging.getLogger("BEKApp")
router = APIRouter(tags=["Chat"])

minhash_engine = MinHashSimilarity(num_perm=64)
hll_counter = HyperLogLog(b=6)

BEK_GOLDEN_RULES = f"""
# RÔLE & PERSONNALITÉ
Tu es BEK, un agent superviseur technique d'exécution directe et précis, opérant sur un environnement hôte {CURRENT_OS_NAME}.

# POUVOIRS SYSTÈME ET ACCÈS TERMINAL
- Tu disposes d'un accès TOTAL au système de fichiers local, au terminal ({CURRENT_OS_NAME}), à Git, aux bases Neon DB et Pinecone, et aux sous-agents.
- INTERDICTION FORMELLE d'affirmer "Je n'ai pas accès à Internet", "Je ne peux pas accéder à GitHub" ou "Cet environnement est isolé".
- Dès que l'utilisateur demande une opération Git (sauvegarde, commit, push), un script, ou une action fichier, TU L'EXÉCUTES DIRECTEMENT via les outils dédiés.

# DIRECTIVES CONVERSATIONNELLES
- Parle naturellement et brièvement. Pas de bavardage.
- Salutations : réponds en une seule phrase courte.

# EXÉCUTION D'OUTILS & ACTIONS (RÈGLE STRICTE)
- DÈS QUE l'utilisateur demande une action technique, TU NE POSES AUCUNE QUESTION.
- INTERDICTION de demander la permission ("Veux-tu que je...").
- INTERDICTION de décrire ce que tu vas faire ou de faire une phrase d'introduction.
- Renvoie UNIQUEMENT la balise [ACTION:nom_action]{{"param":"valeur"}}[/ACTION]. Aucun autre texte n'est toléré avant ou après.

# ACTIONS DISPONIBLES :
   - [ACTION:create_dynamic_skill]{{"skill_name": "...", "code_content": "...", "description": "..."}}[/ACTION]
   - [ACTION:orchestrate]{{"goal": "..."}}[/ACTION]
   - [ACTION:web_sync]{{"query": "..."}}[/ACTION]
   - [ACTION:execute_command]{{"command": "..."}}[/ACTION]
   - [ACTION:execute_tmux_headless]{{"session_name": "...", "command": "..."}}[/ACTION]
   - [ACTION:stop_background_task]{{"session_name": "..."}}[/ACTION]
   - [ACTION:save_memory]{{"content": "..."}}[/ACTION]
   - [ACTION:search_memory]{{"query": "..."}}[/ACTION]
   - [ACTION:delete_memory]{{"record_id": "...", "keyword": "..."}}[/ACTION]
   - [ACTION:write_file]{{"filename": "...", "content": "..."}}[/ACTION]
   - [ACTION:delete_file]{{"filename": "..."}}[/ACTION]
   - [ACTION:read_file]{{"filename": "..."}}[/ACTION]
   - [ACTION:extract_zip]{{"zip_path": "...", "extract_to": "..."}}[/ACTION]
   - [ACTION:create_zip]{{"folder_path": "...", "output_zip": "..."}}[/ACTION]
   - [ACTION:analyze_zip_content]{{"zip_path": "..."}}[/ACTION]
   - [ACTION:analyze_image]{{"image_path": "...", "prompt": "...", "provider": "gemini", "model": "gemini-1.5-flash"}}[/ACTION]
   - [ACTION:generate_image]{{"prompt": "...", "filename": "...", "provider": "gemini", "model": "gemini-3.1-flash-image"}}[/ACTION]
   - [ACTION:merge_and_edit_images]{{"image_paths": ["img1", "img2"], "prompt": "..."}}[/ACTION]
"""

def _detect_user_response(query: str) -> str:
    if not query:
        return "neutral"
    q = query.lower().strip()
    agreed_words = {"oui", "yes", "ok", "okay", "vasy", "vas-y", "go", "d'accord", "ouais", "y", "o", "fine", "fais-le", "lance", "exécute"}
    refused_words = {"non", "no", "stop", "annule", "cancel", "pas maintenant", "jamais"}
    words = set(re.findall(r"\b\w+\b", q))
    if words & agreed_words and not (words & refused_words):
        return "agreed"
    if words & refused_words:
        return "refused"
    return "neutral"

@router.post("/api/chat")
async def chat(request: Request):
    data = await request.json() or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "b_ai")
    model = data.get("model", "glm-5.3-flash")

    trimmed_messages = [m for m in messages[-6:] if isinstance(m, dict)]
    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = _detect_user_response(last_user_query)

    corr_id = f"corr_{uuid.uuid4().hex[:10]}"
    if event_bus and last_user_query:
        event_bus.publish("web-cleaned", {"query": last_user_query, "correlation_id": corr_id})

    if last_user_query.startswith("/") and dispatch_slash_command:
        slash_res = dispatch_slash_command(last_user_query)
        if slash_res and slash_res.get("ok"):
            async def generate_slash():
                yield f"data: {json.dumps({'chunk': slash_res['output']}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return StreamingResponse(generate_slash(), media_type="text/event-stream")

    if len(trimmed_messages) >= 2:
        prev_msg = trimmed_messages[-2]
        if prev_msg.get("role") == "assistant" and "[ACTION:" in prev_msg.get("content", ""):
            if user_status == "agreed":
                action_matches = list(re.finditer(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", prev_msg.get("content", ""), re.DOTALL))
                if action_matches:
                    match = action_matches[-1]
                    act_name = match.group(1)
                    raw_payload = match.group(2).strip()

                    params = {}
                    try:
                        parsed = json.loads(raw_payload)
                        if isinstance(parsed, dict): params = parsed
                    except Exception:
                        try:
                            parsed = ast.literal_eval(raw_payload)
                            if isinstance(parsed, dict): params = parsed
                        except Exception: pass

                    params["provider"] = provider
                    params["model"] = model

                    exec_res = execute_agent_crm_tool(act_name, params)
                    res_msg = exec_res.get('message', 'Opération réussie')
                    if len(res_msg) > 1500:
                        res_msg = res_msg[:1500] + "\n... [contenu tronqué]"

                    injection = f"\n\n[SYSTÈME - L'UTILISATEUR A VALIDÉ L'ACTION '{act_name}'. RÉSULTAT :] \n{res_msg}\n\n-> Analyse ce résultat et donne ton retour à l'utilisateur de manière fluide."
                    trimmed_messages[-1]["content"] += injection
                    trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[EXECUTED_ACTION:")

            elif user_status == "refused":
                trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[REFUSED_ACTION:")
                injection = "\n\n[SYSTÈME - L'UTILISATEUR A REFUSÉ L'ACTION. Propose une alternative ou demande comment poursuivre.]"
                trimmed_messages[-1]["content"] += injection
            else:
                trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[CANCELED_ACTION:")

    dynamic_system_prompt = BEK_GOLDEN_RULES.strip()

    if last_user_query:
        sig = minhash_engine.compute_signature(last_user_query)
        hll_counter.add(last_user_query)

        try:
            memory_context = search_memory(last_user_query, top_k=3)
            if memory_context:
                dynamic_system_prompt += f"\n\n[CONTEXTE EN MÉMOIRE (POUR INFO)] :\n{memory_context}"
        except Exception as e:
            logger.warning("Erreur injection mémoire : %s", e)

        try:
            plan = hermes.goap_planner(last_user_query)
            if plan:
                filtered_plan = [t for t in plan if t.get("tool") != "default_llm"]
                if filtered_plan:
                    dynamic_system_prompt += f"\n\n[PLAN D'ACTION HERMES (SKILLS DISPONIBLES)] :\n{json.dumps(filtered_plan, ensure_ascii=False, indent=2)}"
        except Exception as e:
            logger.error("[HERMES] Échec du planificateur GOAP : %s", e)

    exec_messages = [{"role": "system", "content": dynamic_system_prompt}] + trimmed_messages

    async def generate_proxy():
        full_text_accumulated = []
        action_detected = False

        try:
            for item in provider_manager.execute_chat_stream(
                messages=exec_messages,
                provider=provider,
                model=model,
                temperature=0.7,
                max_tokens=4096,
            ):
                if "chunk" in item:
                    chunk = item["chunk"]
                    full_text_accumulated.append(chunk)
                    current_text = "".join(full_text_accumulated)

                    if "[ACTION:" in current_text:
                        action_detected = True

                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

                    if action_detected and "[/ACTION]" in current_text:
                        try:
                            action_matches = list(re.finditer(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", current_text, re.DOTALL))
                            if action_matches:
                                match = action_matches[-1]
                                act_name = match.group(1)
                                raw_payload = match.group(2).strip()
                                params = {}
                                try:
                                    parsed = json.loads(raw_payload)
                                    if isinstance(parsed, dict): params = parsed
                                except Exception:
                                    try:
                                        parsed = ast.literal_eval(raw_payload)
                                        if isinstance(parsed, dict): params = parsed
                                    except Exception: pass

                                params["provider"] = provider
                                params["model"] = model

                                immediate_msg_json = json.dumps({'chunk': '\n\n⚙️ *Exécution immédiate...*\n'}, ensure_ascii=False)
                                yield f"data: {immediate_msg_json}\n\n"

                                exec_res = execute_agent_crm_tool(act_name, params)
                                res_msg = exec_res.get('message', 'Opération réussie')

                                eval_result = evaluate_response_quality(last_user_query, res_msg)
                                if not eval_result["passed"]:
                                    res_msg = f"⚠️ [BEK Guard] Résultat d'action filtré : {eval_result['reason']}"

                                res_chunk_json = json.dumps({'chunk': f'\n\n{res_msg}\n'}, ensure_ascii=False)
                                yield f"data: {res_chunk_json}\n\n"
                        except Exception as e:
                            logger.error("Erreur exécution inline : %s", e)
                            err_chunk_json = json.dumps({'chunk': f'\n\n⚠️ Erreur technique : {str(e)}\n'}, ensure_ascii=False)
                            yield f"data: {err_chunk_json}\n\n"
                        break

            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        except Exception as stream_err:
            logger.error("[Stream Error] %s", stream_err)
            err_stream_json = json.dumps({'chunk': f'\n\n⚠️ **[Avertissement Flux]** {stream_err}'}, ensure_ascii=False)
            yield f"data: {err_stream_json}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )