# AGENT_WORKSPACE_v15/uploads/ai_service.py

- make_client · function · L14-L17 — def make_client(base_url, api_key)
- get_client · function · L20-L27 — def get_client(provider)
- configured_providers · function · L30-L31 — def configured_providers()
- provider_name · function · L34-L35 — def provider_name(provider)
- fetch_models · function · L38-L54 — def fetch_models(provider)
- list_models · function · L57-L69 — def list_models(provider)
- is_multimodal_model · function · L72-L76 — def is_multimodal_model(model_name)
- get_nvidia_key_for_model · function · L79-L84 — def get_nvidia_key_for_model(model_name)
- call_ai_stream · function · L87-L206 — async def call_ai_stream(conv, provider="nvidia", model=None, base_url=None, api_key=None, max_tokens=4096, temperature=0.7)
- call_ai · function · L209-L219 — async def call_ai(conv, provider="nvidia", model=None, base_url=None, api_key=None, max_tokens=2000, temperature=0.7)
