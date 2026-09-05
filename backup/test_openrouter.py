import requests
import os

# Lecture propre de la clé depuis env.txt ou directement
api_key = "Sk-or-v1-4597e1c0bb3e358fa976c6431a0a9130a326b2c07c3efa5acd0178cf7a29214a".strip()

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://bek-agent.local",
    "X-Title": "BEK-v15-Hybrid"
}
payload = {
    "model": "openai/gpt-oss-120b",
    "messages": [{"role": "user", "content": "just say hi, nothing else"}],
    "max_tokens": 64
}

print("Envoi de la requête à OpenRouter...")
response = requests.post(url, json=payload, headers=headers)
print("Statut HTTP :", response.status_code)
print("Réponse :", response.text)
