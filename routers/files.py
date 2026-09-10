import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from werkzeug.utils import secure_filename

router = APIRouter(prefix="/api", tags=["Files"])

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_DIR = os.path.join(WORKSPACE_DIR, "uploads")
GENERATED_DIR = os.path.join(WORKSPACE_DIR, "generated")

@router.get("/files")
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
