with open('agent-ui.js', 'r', encoding='utf-8') as f:
    js = f.read()

# 1. On ajoute Hugging Face dans la liste du menu déroulant
cible_menu = "{id: 'kimi', name: 'Moonshot Kimi AI', configured: true},"
ajout_menu = "{id: 'kimi', name: 'Moonshot Kimi AI', configured: true},\n                {id: 'huggingface', name: '🤗 Hugging Face Inference', configured: true},"
js = js.replace(cible_menu, ajout_menu)

# 2. On lui associe ses modèles d'IA pour le second menu
cible_modeles = "if(!availableModels['kimi']) availableModels['kimi'] = ['kimi-k3', 'kimi-k3-swarm', 'kimi-k3-instant', 'kimi-k2.7-code', 'kimi-k2.6', 'kimi-k2-0905', 'moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'];"
ajout_modeles = cible_modeles + "\n            if(!availableModels['huggingface']) availableModels['huggingface'] = ['meta-llama/Meta-Llama-3-70B-Instruct', 'mistralai/Mistral-7B-Instruct-v0.2', 'deepseek-ai/DeepSeek-R1'];"
js = js.replace(cible_modeles, ajout_modeles)

with open('agent-ui.js', 'w', encoding='utf-8') as f:
    f.write(js)