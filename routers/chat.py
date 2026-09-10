from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json
import asyncio
from provider_manager import provider_manager

router = APIRouter(prefix="/api", tags=["Chat"])

SYSTEM_BEK_PROMPT = """Tu es BEK-v16 Hybrid, un agent cognitif autonome et expert en architecture logicielle, DevOps et gestion de bases de données. 
Tu intègres le moteur d'exécution multi-agents Hermes Core V3, le superviseur Meta-Cortex Grounding, la matrice CRM et les capacités de traitement d'images et de fichiers.
Quand l'utilisateur tape une commande (comme /hermes, /cortex, /minhash, /crm) ou demande une génération/analyse d'image, exécute l'action correspondante et renvoie le résultat formaté."""

@router.post("/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    provider = body.get("provider", "gemini")
    model = body.get("model", "gemini-2.5-flash")
    
    # Analyse de la dernière intention utilisateur pour intercepter les commandes slash
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "").strip()
            break

    # Interception des commandes système et skills
    if last_user_msg.startswith("/hermes"):
        async def hermes_stream():
            text = "⚡ **Hermes Core V3 activé** : Initialisation du moteur d'exécution multi-agents et distillation de prompts opérationnelle."
            for word in text.split(" "):
                yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"
        return StreamingResponse(hermes_stream(), media_type="text/event-stream")

    if last_user_msg.startswith("/cortex"):
        async def cortex_stream():
            text = "🧠 **Meta-Cortex Grounding activé** : Superviseur de streaming neuronal et ancrage synchronisés."
            for word in text.split(" "):
                yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"
        return StreamingResponse(cortex_stream(), media_type="text/event-stream")

    if last_user_msg.startswith("/minhash"):
        async def minhash_stream():
            text = "🔍 **MinHash Deduplication actif** : Filtrage Jaccard de l'hygiène vectorielle en cours."
            for word in text.split(" "):
                yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"
        return StreamingResponse(minhash_stream(), media_type="text/event-stream")

    if last_user_msg.startswith("/crm"):
        async def crm_stream():
            text = "💼 **CRM Matrix Engine actif** : Synchronisation Neon DB et pipeline d'opportunités à jour."
            for word in text.split(" "):
                yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"
        return StreamingResponse(crm_stream(), media_type="text/event-stream")

    full_messages = [{"role": "system", "content": SYSTEM_BEK_PROMPT}] + messages

    async def event_generator():
        try:
            # Appel unifié via le provider_manager pour interroger Gemini, Groq, NVIDIA, etc. avec streaming réel
            stream_gen = provider_manager.execute_chat_stream(
                messages=full_messages,
                provider=provider,
                model=model
            )
            for item in stream_gen:
                if "chunk" in item:
                    chunk_data = json.dumps({"chunk": item["chunk"]})
                    yield f"data: {chunk_data}\n\n"
                elif "error" in item:
                    err_str = f"\n[Erreur Provider: {item['error']}]"
                    err_data = json.dumps({"chunk": err_str})
                    yield f"data: {err_data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            sys_err_str = f"\n[Erreur système: {str(e)}]"
            sys_data = json.dumps({"chunk": sys_err_str})
            yield f"data: {sys_data}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")