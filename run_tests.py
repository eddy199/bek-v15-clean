import json
import urllib.request
import urllib.error

def main():
    config_file = "models_config_2.json"

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Erreur : Le fichier {config_file} est introuvable.")
        return

    url = config.get("base_url")
    api_key = config.get("api_key")
    models = config.get("models", [])

    print(f"--- Test du provider : {config.get('provider')} ---")
    print(f"URL : {url}\n")

    for idx, model_info in enumerate(models, 1):
        model_name = model_info["name"]
        print(f"[{idx}] Test du modèle : {model_name}...")

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": "Hello World"
                }
            ],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 100
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                print(f"Succès ({model_name}) :")
                print(response_body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"Erreur HTTP {e.code} pour {model_name} : {error_body}")
        except urllib.error.URLError as e:
            print(f"Erreur réseau pour {model_name} : {e.reason}")
        except Exception as e:
            print(f"Erreur inattendue pour {model_name} : {str(e)}")

        print("-" * 50)

if __name__ == "__main__":
    main()