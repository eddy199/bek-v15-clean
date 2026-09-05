import os
import re
import hashlib
import time
import csv
import zipfile
from datetime import datetime
from pathlib import Path

from config import GENERATED_DIR, logger

# ─── Dépendances optionnelles ────────────────────────────────────
_HAS_REPORTLAB = False
_HAS_PIL = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    _HAS_REPORTLAB = True
except ImportError:
    pass

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    pass

# ─── Extensions de fichiers ─────────────────────────────────────
FILE_EXTENSIONS = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "html": ".html", "css": ".css",
    "json": ".json", "yaml": ".yaml", "yml": ".yaml",
    "markdown": ".md", "md": ".md",
    "bash": ".sh", "shell": ".sh", "sh": ".sh",
    "sql": ".sql", "txt": ".txt", "text": ".txt",
    "java": ".java", "cpp": ".cpp", "c": ".c",
    "rust": ".rs", "go": ".go", "php": ".php",
    "xml": ".xml", "csv": ".csv",
}

_CODE_BLOCK_RE = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)


# ════════════════════════════════════════════════════════════════
# DÉTECTION AUTO DES BLOCS DE CODE (depuis réponse IA)
# ════════════════════════════════════════════════════════════════

def detect_and_generate_files(response_text, session_id="unknown"):
    """Détecte les blocs ```langage ... ``` dans une réponse et les sauvegarde."""
    matches = _CODE_BLOCK_RE.findall(response_text)
    if not matches:
        return []
    generated = []
    for lang, code in matches:
        lang = (lang or "txt").lower().strip()
        ext = FILE_EXTENSIONS.get(lang, f".{lang}" if lang else ".txt")
        code = code.strip()
        if not code or len(code) < 5:
            continue
        file_id = hashlib.md5(f"{code}{time.time_ns()}".encode()).hexdigest()[:12]
        filename = f"bek_{session_id[:6]}_{lang}{ext}"
        filepath = GENERATED_DIR / f"{file_id}{ext}"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
            generated.append({
                "file_id": file_id,
                "filename": filename,
                "language": lang,
                "extension": ext,
                "size": len(code.encode("utf-8")),
                "path": str(filepath),
            })
            logger.info(f"Fichier généré: {filename} ({len(code)} chars) → {filepath}")
        except Exception as e:
            logger.error(f"Erreur génération fichier {filename}: {e}")
    return generated


def list_generated_files():
    files = []
    if not GENERATED_DIR.exists():
        return files
    for fn in sorted(os.listdir(GENERATED_DIR), key=lambda f: os.path.getmtime(GENERATED_DIR / f), reverse=True):
        fp = GENERATED_DIR / fn
        file_id = fn.split('.')[0]
        files.append({
            "file_id": file_id,
            "filename": fn,
            "size": os.path.getsize(fp),
            "created_at": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat()
        })
    return files


# ════════════════════════════════════════════════════════════════
# GÉNÉRATION EXPLICITE DE FICHIERS (appelé par /api/generate-file)
# ════════════════════════════════════════════════════════════════

def generate_pdf(filename, content):
    """Génère un PDF à partir de texte."""
    if not _HAS_REPORTLAB:
        raise RuntimeError("reportlab non installé : python -m pip install reportlab")
    fpath = GENERATED_DIR / filename
    c = canvas.Canvas(str(fpath), pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica", 12)
    for line in content.split("\n"):
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 12)
        c.drawString(50, y, line[:120])
        y -= 15
    c.save()
    logger.info(f"PDF généré: {filename} → {fpath}")
    return str(fpath)


def generate_txt(filename, content):
    """Génère un fichier texte."""
    fpath = GENERATED_DIR / filename
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"TXT généré: {filename} → {fpath}")
    return str(fpath)


def generate_csv(filename, rows):
    """Génère un fichier CSV à partir d'une liste de listes."""
    fpath = GENERATED_DIR / filename
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    logger.info(f"CSV généré: {filename} → {fpath}")
    return str(fpath)


def generate_zip(filename, files):
    """Génère un ZIP à partir d'un dict {nom_dans_zip: contenu_texte}."""
    fpath = GENERATED_DIR / filename
    with zipfile.ZipFile(fpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    logger.info(f"ZIP généré: {filename} → {fpath}")
    return str(fpath)


def generate_image(filename, width=400, height=300, bg_color="#1a1a2e"):
    """Génère une image PNG/JPG simple."""
    if not _HAS_PIL:
        raise RuntimeError("Pillow non installé : python -m pip install Pillow")
    fpath = GENERATED_DIR / filename
    img = Image.new("RGB", (width, height), bg_color)
    img.save(fpath)
    logger.info(f"Image générée: {filename} → {fpath}")
    return str(fpath)
