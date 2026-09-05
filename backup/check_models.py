import asyncio
from ai_service import call_ai, GROQ_MODELS, NVIDIA_ACTIVE_MODELS, ENV

def get_api_key(key_name):
    return ENV.get(key_name, "")

async def test_all_models():
    print("=" * 65)
    print("TEST COMPLET DES MODÈLES NVIDIA ET GROQ")
    print("=" * 65)

    groq_key = get_api_key("GROQ_API_KEY")
    nvidia_key = get_api_key("NVIDIA_API_KEY")

    # 1. Test Groq
    if groq_key:
        print(f"\n--- [GROQ] Test de {len(GROQ_MODELS)} modèle(s) ---")
        for model in GROQ_MODELS:
            try:
                res = await call_ai(
                    [{"role": "user", "content": "Dis 'OK' en un mot."}],
                    provider="groq",
                    model=model
                )
                if "Erreur" in res:
                    print(f"❌ groq/{model} : {res.strip()[:120]}")
                else:
                    print(f"✅ groq/{model} : {res.strip()[:50]}")
            except Exception as e:
                print(f"❌ groq/{model} : {e}")
    else:
        print("\n--- [GROQ] Clé API manquante, tests ignorés ---")

    # 2. Test NVIDIA
    if nvidia_key:
        print(f"\n--- [NVIDIA] Test de {len(NVIDIA_ACTIVE_MODELS)} modèle(s) ---")
        for model in NVIDIA_ACTIVE_MODELS:
            try:
                res = await call_ai(
                    [{"role": "user", "content": "Dis 'OK' en un mot."}],
                    provider="nvidia",
                    model=model
                )
                if "Erreur" in res:
                    print(f"❌ {model} -> {res.strip()[:120]}")
                else:
                    print(f"✅ {model} -> {res.strip()[:50]}")
            except Exception as e:
                print(f"❌ {model} -> {e}")
    else:
        print("\n--- [NVIDIA] Clé API manquante, tests ignorés ---")

    print("\n" + "=" * 65)
    print("TEST TERMINÉ")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(test_all_models())