import time
import asyncio
from routers.chat import _INTEL_OK, smart_router
from memory import search_memory
from provider_manager import provider_manager

async def run_benchmark():
    messages = [{"role": "user", "content": "bjr"}]
    
    print("--- DÉBUT DU BENCHMARK DE LATENCE ---")
    
    # 1. Test du SmartRouter
    t0 = time.time()
    if _INTEL_OK:
        chosen = smart_router.route(messages)
    print(f"⏱️ SmartRouter : {time.time() - t0:.4f}s (Route choisie: {chosen if _INTEL_OK else 'Désactivé'})")
    
    # 2. Test de la mémoire Pinecone
    t0 = time.time()
    try:
        search_memory("bjr", top_k=3)
    except Exception as e:
        print(f"⚠️ Erreur mémoire : {e}")
    print(f"⏱️ Recherche Pinecone (Mémoire) : {time.time() - t0:.4f}s")
    
    # 3. Test de réponse LLM (Streaming)
    t0 = time.time()
    provider, model = chosen[0] if _INTEL_OK else ("b_ai", "glm-5.3-flash")
    print(f"🔄 Test d'appel LLM brut sur {provider}/{model}...")
    
    chunks_count = 0
    try:
        for item in provider_manager.execute_chat_stream(
            messages=[{"role": "system", "content": "Réponds brièvement."}] + messages,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=100
        ):
            if "chunk" in item:
                chunks_count += 1
    except Exception as e:
        print(f"⚠️ Erreur LLM : {e}")
        
    print(f"⏱️ Premier retour du LLM (Time-to-First-Token) / Total : {time.time() - t0:.4f}s (Chunks reçus: {chunks_count})")
    print("--- FIN DU BENCHMARK ---")

if __name__ == "__main__":
    asyncio.run(run_benchmark())