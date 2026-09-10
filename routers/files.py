# ==============================================================================
# BEK-v16 — Routeur Fichiers & Téléchargements (routers/files.py)
# ==============================================================================
import os
import uuid
import logging
from werkzeug.utils import secure_filename
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from core.paths import FILES_DIR, GENERATED_DIR

logger = logging.getLogger("BEKApp")
router = APIRouter(tags=["Files"])

@router.get("/api/files")
async def list_files():
    files = []
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.startswith("."):
                    filepath = os.path.join(directory, filename)
                    if os.path.isfile(filepath):
                        files.append({"name": filename, "size": os.path.getsize(filepath), "folder": os.path.basename(directory)})
    return {"files": files}

@router.get("/api/download/{filename}")
async def download_file(filename: str):
    filename = secure_filename(filename)
    for directory in [GENERATED_DIR, FILES_DIR]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            return FileResponse(target, filename=filename, media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="Fichier introuvable")

@router.delete("/api/files/{filename}")
async def delete_single_file(filename: str):
    filename = secure_filename(filename)
    deleted = False
    for directory in [FILES_DIR, GENERATED_DIR]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            try:
                os.remove(target)
                deleted = True
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    if deleted:
        return {"status": "success", "message": f"{filename} supprimé."}
    raise HTTPException(status_code=404, detail="Fichier introuvable")

@router.post("/api/files/delete-all")
async def delete_all_files():
    deleted_count = 0
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.startswith("."):
                    target = os.path.join(directory, filename)
                    if os.path.isfile(target):
                        try:
                            os.remove(target)
                            deleted_count += 1
                        except Exception as e:
                            logger.warning("Impossible de supprimer %s: %s", target, e)
    return {"status": "success", "message": f"{deleted_count} fichiers supprimés avec succès."}

@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu")
    raw_filename = file.filename
    if "/" in raw_filename or "\\" in raw_filename:
        raw_filename = os.path.basename(raw_filename)
    filename = secure_filename(raw_filename)
    if not filename:
        ext = os.path.splitext(raw_filename)[1]
        filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(FILES_DIR, filename)
    try:
        content = await file.read()
        with open(save_path, "wb") as dst:
            dst.write(content)
        return {"status": "success", "filename": filename, "folder": "uploads"}
    except Exception as e:
        logger.error("Erreur upload : %s", e)
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except Exception: pass
        raise HTTPException(status_code=500, detail=f"Erreur enregistrement : {str(e)}")