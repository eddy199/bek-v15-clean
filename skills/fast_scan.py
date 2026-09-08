import os, json, time

def run(path='.', extensions=None, name_filter=None, max_depth=10, max_results=500):
    """Scan rapide via os.walk natif.
    extensions: liste comme ['.py', '.json'] ou None pour tout
    name_filter: sous-chaîne du nom de fichier (ex: 'bek') ou None
    """
    start = time.time()
    results = []
    extensions = [e.lower() if e.startswith('.') else '.'+e.lower() for e in extensions] if extensions else None
    base_depth = path.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(path):
        depth = root.rstrip(os.sep).count(os.sep) - base_depth
        if depth > max_depth:
            dirs[:] = []
            continue
        # Skip dossiers lourds inutiles
        dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.next'}]
        for f in files:
            if extensions and os.path.splitext(f)[1].lower() not in extensions:
                continue
            if name_filter and name_filter.lower() not in f.lower():
                continue
            full = os.path.join(root, f)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = -1
            results.append({'path': full, 'size': size})
            if len(results) >= max_results:
                return json.dumps({'status': 'truncated', 'count': len(results), 'elapsed_s': round(time.time()-start, 2), 'files': results}, ensure_ascii=False, indent=1)
    return json.dumps({'status': 'ok', 'count': len(results), 'elapsed_s': round(time.time()-start, 2), 'files': results}, ensure_ascii=False, indent=1)