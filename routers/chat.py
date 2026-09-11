# ==============================================================================
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

# ── EXPRESSION RÉGULIÈRE UNIQUE (Anti-Coupure Interface) ──
# Utilisation des codes Hex (\x5b = crochet ouvert, \x5d = crochet fermé)
# Cela empêche ton interface web de supprimer le code au copier-coller !
ACTION_REGEX = re.compile(r"\x5bACTION:(\w+)\x5d(.*?)\x5b/ACTION\x5d", re.DOTALL)

# ── AJOUT BEK-INTELLIGENCE : couche additive ──
try:
    from bek_intelligence import (
        smart_router, auto_engine, ResponseQuality, Task
    )
    _INTEL_OK = True
except Exception as _intel_err:
    logger = logging.getLogger("BEKApp")
    logger.warning("BekIntelligence non chargé : %s", _intel_err)
    _INTEL_OK = False
    smart_router = auto_engine = ResponseQuality = None

    class Task:
        CHAT = "chat"
        CODE = "code"
        REASONING = "reasoning"
        VISION = "vision"
        LONG_DOC = "long_doc"
        CREATIVE = "creative"

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
Tu es BEK, agent technique d'exécution sur {CURRENT_OS_NAME}.

# POUVOIRS SYSTÈME ET ACCÈS TERMINAL
- Tu disposes d'un accès TOTAL au système local.
- Accès au terminal, Git, Neon DB, Pinecone.
- INTERDICTION d'affirmer "Je n'ai pas accès à Internet".
- EXÉCUTE DIRECTEMENT via les outils dédiés les actions demandées.

# DIRECTIVES CONVERSATIONNELLES
- Parle naturellement et brièvement. Pas de bavardage.
- Salutations : réponds en une seule phrase courte.

# EXÉCUTION D'OUTILS & ACTIONS (RÈGLE STRICTE)
- DÈS QUE l'utilisateur demande une action, N'ATTENDS PAS.
- INTERDICTION de demander la permission.
- Renvoie UNIQUEMENT la balise [ACTION:nom]{{"param":"v"}}[/ACTION].

# ACTIONS DISPONIBLES :
   - [ACTION:create_dynamic_skill]{{"skill_name": "x", "code_content": "y"}}[/ACTION]
   - [ACTION:orchestrate]{{"goal": "..."}}[/ACTION]
   - [ACTION:web_sync]{{"query": "..."}}[/ACTION]
   - [ACTION:run_script]{{"script_name": "skills/x.py", "args": "--ip 127.0.0.1"}}[/ACTION]
   - [ACTION:execute_command]{{"command": "..."}}[/ACTION]
   - [ACTION:execute_tmux_headless]{{"session_name": "s", "command": "c"}}[/ACTION]
   - [ACTION:save_memory]{{"content": "..."}}[/ACTION]
   - [ACTION:search_memory]{{"query": "..."}}[/ACTION]
   - [ACTION:write_file]{{"filename": "...", "content": "..."}}[/ACTION]
   - [ACTION:read_file]{{"filename": "..."}}[/ACTION]
"""

def _detect_user_response(query: str) -> str:
    if not query:
        return "neutral"
    q = query.lower().strip()
    agreed = {
        "oui", "yes", "ok", "okay", "vasy", "vas-y",
        "go", "d'accord", "ouais", "y", "o", "fine"
    }
    refused = {"non", "no", "stop", "annule", "cancel", "jamais"}
    words = set(re.findall(r"\b\w+\b", q))
    if words & agreed and not (words & refused):
        return "agreed"
    if words & refused:
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

    smart_mode = data.get("smart", True)
    if _INTEL_OK and smart_mode:
        try:
            chosen = smart_router.route(trimmed_messages)
            if chosen:
                provider, model = chosen[0]
                logger.info("[SmartRouter] Route : %s/%s", provider, model)
        except Exception as e:
            logger.warning("[SmartRouter] Échec : %s", e)

    corr_id = f"corr_{uuid.uuid4().hex[:10]}"
    if event_bus and last_user_query:
        event_bus.publish("web-cleaned", {"query": last_user_query})

    if last_user_query.startswith("/") and dispatch_slash_command:
        slash_res = dispatch_slash_command(last_user_query)
        if slash_res and slash_res.get("ok"):
            async def generate_slash():
                j_out = json.dumps({'chunk': slash_res['output']})
                yield f"data: {j_out}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            return StreamingResponse(
                generate_slash(), media_type="text/event-stream"
            )

    if len(trimmed_messages) >= 2:
        prev_msg = trimmed_messages[-2]
        is_ast = prev_msg.get("role") == "assistant"
        has_act = "[ACTION:" in prev_msg.get("content", "")
        
        if is_ast and has_act:
            if user_status == "agreed":
                
                act_content = prev_msg.get("content", "")
                action_matches = list(ACTION_REGEX.finditer(act_content))
                
                if action_matches:
                    match = action_matches[-1]
                    act_name = match.group(1)
                    raw_payload = match.group(2).strip()

                    params = {}
                    try:
                        p_json = json.loads(raw_payload)
                        if isinstance(p_json, dict): params = p_json
                    except Exception:
                        try:
                            p_ast = ast.literal_eval(raw_payload)
                            if isinstance(p_ast, dict): params = p_ast
                        except Exception: pass

                    params["provider"] = provider
                    params["model"] = model

                    exec_res = execute_agent_crm_tool(act_name, params)
                    res_msg = exec_res.get('message', 'Opération OK')
                    if len(res_msg) > 1500:
                        res_msg = res_msg[:1500] + "\n... [tronqué]"

                    inj = (f"\n\n[SYSTÈME - RÉSULTAT DE L'ACTION "
                           f"'{act_name}' :] \n{res_msg}\n\n-> "
                           f"Donne ton retour à l'utilisateur.")
                    trimmed_messages[-1]["content"] += inj
                    
                    old_c = trimmed_messages[-2]["content"]
                    trimmed_messages[-2]["content"] = old_c.replace(
                        "[ACTION:", "[EXECUTED_ACTION:"
                    )

            elif user_status == "refused":
                old_c = trimmed_messages[-2]["content"]
                trimmed_messages[-2]["content"] = old_c.replace(
                    "[ACTION:", "[REFUSED_ACTION:"
                )
                inj = "\n\n[SYSTÈME - ACTION REFUSÉE. Propose autre chose.]"
                trimmed_messages[-1]["content"] += inj
            else:
                old_c = trimmed_messages[-2]["content"]
                trimmed_messages[-2]["content"] = old_c.replace(
                    "[ACTION:", "[CANCELED_ACTION:"
                )

    dynamic_system_prompt = BEK_GOLDEN_RULES.strip()

    if last_user_query:
        sig = minhash_engine.compute_signature(last_user_query)
        hll_counter.add(last_user_query)

        try:
            mem_ctx = search_memory(last_user_query, top_k=3)
            if mem_ctx:
                dynamic_system_prompt += f"\n\n[MÉMOIRE] :\n{mem_ctx}"
        except Exception as e:
            logger.warning("Erreur mémoire : %s", e)

        try:
            plan = hermes.goap_planner(last_user_query)
            if plan:
                f_plan = [t for t in plan if t.get("tool") != "default_llm"]
                if f_plan:
                    p_json = json.dumps(f_plan, ensure_ascii=False)
                    dynamic_system_prompt += f"\n\n[HERMES] :\n{p_json}"
        except Exception as e:
            logger.error("[HERMES] Échec planificateur : %s", e)

    exec_messages = [
        {"role": "system", "content": dynamic_system_prompt}
    ] + trimmed_messages

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

                    j_chunk = json.dumps({'chunk': chunk}, ensure_ascii=False)
                    yield f"data: {j_chunk}\n\n"

                    if action_detected and "[/ACTION]" in current_text:
                        try:
                            action_matches = list(ACTION_REGEX.finditer(current_text))
                            
                            if action_matches:
                                match = action_matches[-1]
                                act_name = match.group(1)
                                raw_payload = match.group(2).strip()
                                params = {}
                                try:
                                    p_json = json.loads(raw_payload)
                                    if isinstance(p_json, dict):
                                        params = p_json
                                except Exception:
                                    try:
                                        p_ast = ast.literal_eval(raw_payload)
                                        if isinstance(p_ast, dict):
                                            params = p_ast
                                    except Exception: pass

                                params["provider"] = provider
                                params["model"] = model

                                msg_imm = '\n\n⚙️ *Exécution...*\n'
                                j_imm = json.dumps({'chunk': msg_imm})
                                yield f"data: {j_imm}\n\n"

                                exec_res = execute_agent_crm_tool(act_name, params)
                                res_msg = exec_res.get('message', 'Opération OK')

                                eval_r = evaluate_response_quality(last_user_query, res_msg)
                                if not eval_r["passed"]:
                                    res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"

                                j_res = json.dumps({'chunk': f'\n\n{res_msg}\n'})
                                yield f"data: {j_res}\n\n"
                        except Exception as e:
                            logger.error("Erreur exécution : %s", e)
                            j_err = json.dumps({'chunk': f'\n⚠️ Erreur : {e}\n'})
                            yield f"data: {j_err}\n\n"
                        break

            full_text = "".join(full_text_accumulated)
            if (_INTEL_OK and full_text.strip() and not action_detected):
                try:
                    score, issues = ResponseQuality.evaluate(full_text, 4096)
                    meta_data = {'quality_score': score, 'issues': issues}
                    j_meta = json.dumps({'meta': meta_data})
                    yield f"data: {j_meta}\n\n"
                    
                    if score < 60:
                        corrective = list(exec_messages) + [
                            {"role": "assistant", "content": full_text},
                            {"role": "user", "content":
                                "[STEERING CORRECTIF] Répare cette erreur : "
                                + ("; ".join(issues) or "mauvaise qualité")}
                        ]
                        corr_stream = auto_engine._run_once(
                            corrective, provider, model, 4096)
                        corrected_text = corr_stream[0]
                        if corrected_text.strip() != full_text.strip():
                            msg_corr = '\n\n--- ✨ Version corrigée ---\n\n'
                            j_msg = json.dumps({'chunk': msg_corr})
                            yield f"data: {j_msg}\n\n"
                            
                            for i in range(0, len(corrected_text), 24):
                                c_part = corrected_text[i:i+24]
                                yield f"data: {json.dumps({'chunk': c_part})}\n\n"
                except Exception as qe:
                    logger.warning("[QualityGate] Échec : %s", qe)

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as stream_err:
            logger.error("[Stream Error] %s", stream_err)
            j_serr = json.dumps({'chunk': f'\n\n⚠️ Flux Error : {stream_err}'})
            yield f"data: {j_serr}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate_proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )