import asyncio
from config import MODELS, NVIDIA_MODELS, GROQ_API_KEY, NVIDIA_API_KEY
from ai_service import call_ai

async def test_all_models():
    print("=" * 65)
    print("TEST COMPLET DES MODÈLES NVIDIA ET GROQ")
    print("=" * 65)

    # 1. Test Groq
    if GROQ_API_KEY:
        print("\n--- [GROQ] Test du modèle principal ---")
        try:
            res = await call_ai([{"role": "user", "content": "Dis 'OK' en un mot."}], provider="groq", model="llama-3.3-70b-versatile")
            print(f"✅ groq/llama-3.3-70b-versatile : {res.strip()}")
        except Exception as e:
            print(f"❌ groq/llama-3.3-70b-versatile : {e}")

    # 2. Test NVIDIA
    print("\n--- [NVIDIA] Test de tous les modèles configurés ---")
    for item in NVIDIA_MODELS:
        m_id = item["model"]
        try:
            res = await call_ai([{"role": "user", "content": "Dis 'OK' en un mot."}], provider="nvidia", model=m_id)
            if "Erreur" in res:
                print(f"❌ {m_id} -> {res.strip()[:90]}")
            else:
                print(f"✅ {m_id} -> {res.strip()[:50]}")
        except Exception as e:
            print(f"❌ {m_id} -> {e}")

if __name__ == "__main__":
    asyncio.run(test_all_models())