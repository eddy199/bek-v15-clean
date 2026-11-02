import os, re, json, time
start = time.time()
root = 'F:/workspacekimi'
exclude = {'venv', '.git', 'node_modules', '__pycache__'}
keywords = re.compile(r'(?i)(connector|ovh|kilo|provider)')
matches = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in exclude]
    for f in filenames:
        if keywords.search(f):
            full = os.path.join(dirpath, f)
            matches.append(full)
print(json.dumps({'count': len(matches), 'files': matches}, ensure_ascii=False, indent=2))
