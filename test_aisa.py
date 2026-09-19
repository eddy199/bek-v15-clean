from provider_manager import provider_manager

msgs = [{"role": "user", "content": "Dis bonjour en 5 mots."}]

for model in ["MiniMax-M2.5", "glm-4.6v-flash", "step-3.7-flash", "qwen-flash"]:
    print(f"\n=== Test modèle : {model} ===")
    try:
        for chunk in provider_manager.execute_chat_stream(
            msgs, provider="aisa", model=model, max_tokens=50
        ):
            print(chunk)
            if chunk.get("provider") == "aisa":
                print(f"✅ {model} fonctionne !")
                break
    except Exception as e:
        print(f"❌ {model} : {e}")