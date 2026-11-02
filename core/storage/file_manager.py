# ==============================================================================
# BEK-v19 — File Manager (ZIP background + tmux)
# Creator: BEKKARA Mohamed — Oran DZ — Root: workspacekimi
# ==============================================================================
from __future__ import annotations

import os
import zipfile
import asyncio
import uuid
import mimetypes
from pathlib import Path
from typing import List, Dict, Any

from core.storage.path_guard import PathGuard

WORKSPACE_ROOT = Path("workspacekimi")
if not WORKSPACE_ROOT.exists():
    cur = Path(__file__).resolve()
    for _ in range(6):
        if cur.name == "workspacekimi":
            WORKSPACE_ROOT = cur
            break
        cur = cur.parent
    if WORKSPACE_ROOT.name != "workspacekimi":
        WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

PathGuard.validate(WORKSPACE_ROOT)

UPLOADS_DIR = WORKSPACE_ROOT / "uploads"
WORK_DIR = WORKSPACE_ROOT / "work"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
WORK_DIR.mkdir(parents=True, exist_ok=True)

class FileManager:
    def __init__(self):
        self.allowed_types = "*"
        self.max_zip_size = 500 * 1024 * 1024

    async def save_upload(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        safe_name = Path(filename).name
        file_id = str(uuid.uuid4())[:8]
        dest = UPLOADS_DIR / f"{file_id}_{safe_name}"
        PathGuard.validate(dest, base=UPLOADS_DIR)
        with open(dest, "wb") as f:
            f.write(file_bytes)
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return {
            "id": file_id,
            "filename": safe_name,
            "path": str(dest),
            "size": len(file_bytes),
            "mime": mime,
            "url": f"/uploads/{file_id}_{safe_name}"
        }

    async def extract_zip_background(self, zip_path: Path, on_progress=None) -> Dict[str, Any]:
        if not zipfile.is_zipfile(zip_path):
            raise ValueError(f"Not a zip: {zip_path}")
        if zip_path.stat().st_size > self.max_zip_size:
            raise ValueError("Zip >500MB")
        extract_id = str(uuid.uuid4())[:8]
        extract_dir = WORK_DIR / f"extract_{extract_id}_{zip_path.stem}"
        extract_dir.mkdir(parents=True, exist_ok=True)
        PathGuard.validate(extract_dir, base=WORK_DIR)
        tmux_session = f"bek-extract-{extract_id}"
        cmd = f"""
        tmux new-session -d -s {tmux_session} "
            echo '[BEK v19] Extraction {zip_path.name}';
            python3 -c '
import zipfile
from pathlib import Path
zip_path = Path(\"{zip_path}\")
extract_dir = Path(\"{extract_dir}\")
with zipfile.ZipFile(zip_path) as z:
    for info in z.infolist():
        dest = (extract_dir / info.filename).resolve()
        if not str(dest).startswith(str(extract_dir.resolve())):
            print(f\"[BEK] zip-slip blocked: {{info.filename}}\")
            continue
        z.extract(info, extract_dir)
    print(f\"[BEK] Extracted {{len(z.infolist())}} files\")
            ';
        "
        """
        proc = await asyncio.create_subprocess_shell(cmd)
        await proc.communicate()
        return {
            "extract_id": extract_id,
            "zip": str(zip_path),
            "dest": str(extract_dir),
            "tmux": tmux_session,
            "status": "extracting_background"
        }

    async def list_workspace_files(self) -> List[Dict[str, Any]]:
        files = []
        for p in WORKSPACE_ROOT.rglob("*"):
            if p.is_file() and "uploads" not in str(p) and "__pycache__" not in str(p):
                try:
                    files.append({
                        "path": str(p.relative_to(WORKSPACE_ROOT)),
                        "size": p.stat().st_size,
                        "mime": mimetypes.guess_type(str(p))[0]
                    })
                except:
                    pass
        return files

    async def index_to_chroma(self, file_path: Path):
        try:
            from core.memory.chroma_manager import chroma_add
            text = file_path.read_text(errors="ignore")[:20000]
            await chroma_add(file_path.name, text)
        except Exception as e:
            print(f"[BEK] Chroma index fail: {e}")

file_manager = FileManager()