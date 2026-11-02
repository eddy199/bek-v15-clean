import subprocess, json, os

# Chemin vers le script de la skill (assume le fichier skill se trouve dans le répertoire 'skills')
skill_path = os.path.join('skills', 'enhance_architecture.py')

# Exécution du script de la skill
result = subprocess.run(['python', skill_path], capture_output=True, text=True)

# Affichage du résultat
print('--- STDOUT ---')
print(result.stdout)
print('--- STDERR ---')
print(result.stderr)

# Lecture du fichier JSON de retour si présent
json_path = 'enhance_architecture.json'
if os.path.exists(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print('--- JSON RESULT ---')
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print('Fichier JSON de résultat non trouvé.')