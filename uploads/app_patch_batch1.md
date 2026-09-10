# PATCH app.py — Batch 1 (extraction vision / tasks / db)

## Étape 0 — Sécurité Git (AVANT TOUT)
```bash
git checkout -b v16-batch1
git add -A && git commit -m "snapshot: avant batch1 extraction"
```

## Étape 1 — AJOUTER ces imports en haut de app.py (après les imports existants)
```python
from core.paths import WORKSPACE_DIR, SKILLS_DIR, FILES_DIR, GENERATED_DIR, PLUGINS_DIR, DOCS_DIR
from core.utils import json_safe, json_response
from services.vision import analyze_image_with_vision, generate_image_with_provider, merge_and_edit_images
from services.tasks import start_background_task, stop_background_task, RUNNING_BACKGROUND_TASKS
from services.db import execute_database_sql
```

## Étape 2 — SUPPRIMER de app.py (car maintenant importées)
1. Le bloc « DIRECTOIRES UNIVERSELS » (WORKSPACE_DIR ... sys.path.insert) — déplacé dans core/paths.py
2. `def json_safe(...)` (utilitaires JSON)
3. `def json_response(...)`
4. `def get_api_key(...)`
5. `def analyze_image_with_vision(...)` (toute la fonction, ~100 lignes)
6. `def generate_image_with_provider(...)`
7. `def merge_and_edit_images(...)`
8. `def execute_database_sql(...)`
9. Le bloc « GESTIONNAIRE DES TÂCHES DE FOND » : RUNNING_BACKGROUND_TASKS, start_background_task, stop_background_task

⚠️ NE TOUCHEZ À RIEN D'AUTRE. execute_agent_crm_tool, les routes, le chat,
BEK_GOLDEN_RULES, le HITL : tout reste dans app.py pour l'instant.

## Étape 3 — Vérifications obligatoires
```bash
python -c "import app"                      # 1. import OK, zéro erreur
python app.py                               # 2. serveur démarre
# 3.  GET http://localhost:8765/api/health  → {"status": "ok", ...}
# 4.  Dans le chat : "génère une image d'un chat" → l'action generate_image répond
# 5.  Dans le chat : "lance une tâche de fond dir" → start_background_task répond
```

## Étape 4 — Si et SEULEMENT si tout passe
```bash
git add -A && git commit -m "v16-batch1: extraction vision/tasks/db (déplacement à l'identique)"
```
Si un test échoue : `git restore .` → revenez me voir avec le message d'erreur.
