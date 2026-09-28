# ==============================================================================
# BEK-v16 — Exécuteur d'actions & outils optimisé (services/action_executor.py) — FIX v36
# COMPATIBILITÉ MULTI-OS / PATHGUARD / SCAN RAPIDE SANS GEL DU FLUX
# ------------------------------------------------------------------------------
# v22 (2026-09-20) : generate_video + merge_and_edit_videos
# v28 (2026-09-21) : extend_video / extend_video_multiple (Agnes)
# v32 (2026-09-21) : sous-titres Whisper (generate_subtitles + burn_subtitles)
# v33 (2026-09-22) : SANDBOX AST sur create_dynamic_skill + source staging
# v34 (2026-09-22) : Wrapper episodic_log autour du dispatcher
# v35 (2026-09-22) : FIX log non-bloquant + import safe + truncate params
# v36 (2026-09-28) : FIX read_file — lit le DÉBUT du fichier (50k chars)
#                    au lieu des 3000 DERNIERS caractères.
#                    L'agent ne voyait que la fin des fichiers longs.
# ==============================================================================
from __future__ import annotations

import os
import re
import json
import ast
import uuid
import time
import zipfile
import shutil
import subprocess
from pathlib import Path

try:
    from services.episode_logger import log_episode as _log_episode_sync
    _EPISODE_LOG_OK = True
except Exception:
    _EPISODE_LOG_OK = False
    def _log_episode_sync(*a, **k):
        return ""
from core.paths import WORKSPACE_DIR, FILES_DIR, GENERATED_DIR
from core.security.path_guard import find_existing, safe_path
from core.security.skill_sandbox import validate_skill_code
from core.utils import json_safe

# --- Imports vision : image + vidéo ---
from services.vision import (
    analyze_image_with_vision,
    generate_image_with_provider,
    merge_and_edit_images,
    generate_video_with_provider,
    merge_and_edit_videos,
    extend_video_with_agnes,
    extend_video_multiple,
)

from services.tasks import start_background_task, stop_background_task
from state_synchronizer import update_task_state
from memory import save_to_memory, search_memory, delete_from_memory

try:
    from bek_orchestrator import bek_orchestrator
except ImportError:
    bek_orchestrator = None

try:
    from skill_generator import create_and_register_skill
except ImportError:
    create_and_register_skill = None

try:
    from web_agent import web_agent_instance
except ImportError:
    web_agent_instance = None

# ==============================================================================
# FIX v35 — LOG EPISODIQUE NON-BLOQUANT (ne casse plus le chat)
# ==============================================================================
import threading as _th

def _log_episode_bg(**kwargs) -> None:
    if not _EPISODE_LOG_OK:
        return
    if os.getenv("BEK_DISABLE_EPISODE_LOG", "0").strip() in ("1", "true", "yes", "on"):
        return
    try:
        params = kwargs.get("parameters") or {}
        try:
            s = json.dumps(params, default=str, ensure_ascii=False)
            if len(s) > 4000:
                kwargs["parameters"] = {"_truncated": True, "_preview": s[:4000]}
        except Exception:
            kwargs["parameters"] = {}
        t = _th.Thread(target=_log_episode_sync, kwargs=kwargs, daemon=True)
        t.start()
    except Exception:
        pass


# ==============================================================================
# FIX v36 — LECTURE DE FICHIER SANS TRONCATURE ARBITRAIRE
# ------------------------------------------------------------------------------
# Ancien : f.read()[-3000:] → ne gardait que les 3000 DERNIERS caractères.
#          L'agent ne voyait que la fin des fichiers longs (ex: ARCHITECTURE.md).
# Nouveau : lecture du DÉBUT du fichier (max 50 000 caractères par défaut).
#           Configurable via BEK_READ_FILE_MAX_CHARS.
# ==============================================================================
BEK_READ_FILE_MAX_CHARS = int(os.getenv("BEK_READ_FILE_MAX_CHARS", "50000"))


def _read_file_head(path: Path, max_chars: int = BEK_READ_FILE_MAX_CHARS) -> tuple[str, int]:
    """
    Lit le DÉBUT d'un fichier (pas la fin).

    Retourne (contenu, taille_totale).

    Si le fichier dépasse max_chars, ajoute un marqueur de troncature.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        full = f.read()

    total_len = len(full)

    if total_len <= max_chars:
        return full, total_len

    head = full[:max_chars]
    truncated_marker = (
        f"\n\n[…fichier tronqué : {max_chars} premiers caractères "
        f"sur {total_len} au total. "
        f"Utilise read_file avec un autre fichier ou augmente BEK_READ_FILE_MAX_CHARS.]"
    )
    return head + truncated_marker, total_len


# ==============================================================================
# SCAN RAPIDE DU WORKSPACE (sans gel du flux)
# ==============================================================================
def _fast_workspace_scan(pattern: str = "") -> list[str]:
    """Scanne le workspace instantanément en ignorant les dossiers lourds."""
    ignored_dirs = {
        "node_modules", "node_portable", "venv", ".venv", "env", "ENV",
        "__pycache__", ".turbo", ".output", ".next", ".git", ".pytest_cache",
        "dist", "build", "backup", "archive_old", "graft",
    }
    results = []
    reg = re.compile(pattern, re.IGNORECASE) if pattern else None

    for root, dirs, files in os.walk(WORKSPACE_DIR):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), WORKSPACE_DIR)
            if reg:
                if reg.search(rel_path):
                    results.append(rel_path)
            else:
                results.append(rel_path)
            if len(results) >= 200:
                break
        if len(results) >= 200:
            break
    return results


# ==============================================================================
# DISPATCHER PRINCIPAL (implémentation réelle)
# ==============================================================================
def _execute_agent_crm_tool_impl(action_name: str, parameters: dict) -> dict:
    correlation_id = f"corr_{uuid.uuid4().hex[:12]}"
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    update_task_state(task_id, "RUNNING", correlation_id, f"Action: {action_name}")

    try:
        # ----------------------------------------------------------------------
        # 1. CRÉATION DYNAMIQUE DE SKILLS (SANDBOX AST OBLIGATOIRE)
        # ----------------------------------------------------------------------
        if action_name == "create_dynamic_skill":
            skill_name = parameters.get("skill_name", "")
            code_content = parameters.get("code_content", "")
            description = parameters.get(
                "description",
                "Skill auto-généré par l'orchestrateur BEK",
            )
            source = parameters.get("source", "user")

            if not skill_name or not code_content:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Nom du skill ou contenu manquant.")
                return {"status": "error",
                        "message": "Nom du skill ou contenu manquant."}

            validation = validate_skill_code(code_content)
            if not validation.get("valid"):
                errors_preview = validation.get("errors", [])[:3]
                update_task_state(task_id, "FAILED", correlation_id,
                                  f"Sandbox AST refus: {errors_preview}")
                return {
                    "status": "error",
                    "message": ("🛡️ Skill refusé par le sandbox AST.\n"
                                "Erreurs détectées :\n- " + "\n- ".join(errors_preview)),
                    "errors": validation.get("errors", []),
                }

            if not create_and_register_skill:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Module skill_generator indisponible.")
                return {"status": "error",
                        "message": "Module skill_generator indisponible."}

            try:
                try:
                    res = create_and_register_skill(
                        skill_name, code_content, description, source=source)
                except TypeError:
                    res = create_and_register_skill(
                        skill_name, code_content, description)
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"Skill créé: {skill_name} (source={source})")
                return res
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur intégration skill : {str(e)}"}

        # ----------------------------------------------------------------------
        # 2. ORCHESTRATION & ESSAIM DE SOUS-AGENTS
        # ----------------------------------------------------------------------
        elif action_name in ("orchestrate", "run_swarm_task", "multi_agent_workflow"):
            goal = parameters.get("goal", parameters.get("objective",
                            parameters.get("query", "")))
            if not goal:
                update_task_state(task_id, "FAILED", correlation_id, "Objectif vide.")
                return {"status": "error",
                        "message": "L'objectif d'orchestration ne peut pas être vide."}
            try:
                if bek_orchestrator:
                    orch_report = bek_orchestrator.run(goal)
                    update_task_state(task_id, "COMPLETED", correlation_id,
                                      "Orchestration réussie")
                    return {"status": "success", "message": orch_report}
                update_task_state(task_id, "FAILED", correlation_id,
                                  "bek_orchestrator indisponible")
                return {"status": "error",
                        "message": "Module bek_orchestrator indisponible sur l'hôte."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur Orchestrateur : {str(e)}"}

        # ----------------------------------------------------------------------
        # 3. NAVIGATION & SYNCHRONISATION WEB
        # ----------------------------------------------------------------------
        elif action_name in ("web_sync", "web_search", "web_pipeline"):
            query = parameters.get("query", "")
            if not query:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Requête web_sync vide")
                return {"status": "error",
                        "message": "La requête web_sync est vide."}
            try:
                res = (web_agent_instance.run_pipeline(query)
                       if web_agent_instance else "WebAgent non connecté")
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"Web sync: {query}")
                return {
                    "status": "success",
                    "message": (f"🌐 Synchronisation Web réussie pour '{query}' :\n"
                                f"{str(res)[:2500]}"),
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur web_sync : {str(e)}"}

        # ----------------------------------------------------------------------
        # 4. MÉMOIRE VECTORIELLE & PERSISTANTE
        # ----------------------------------------------------------------------
        elif action_name in ("save_memory", "remember", "save_to_memory"):
            content = parameters.get("content", "")
            if not content:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Contenu mémoire vide")
                return {"status": "error",
                        "message": "Le contenu à mémoriser ne peut pas être vide."}
            try:
                save_to_memory(content)
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  "Mémoire sauvée")
                return {
                    "status": "success",
                    "message": (f"🧠 Information ancrée dans la mémoire vectorielle :\n"
                                f"\"{content}\""),
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur mémoire : {str(e)}"}

        elif action_name in ("search_memory", "recall"):
            query = parameters.get("query", "")
            try:
                mem_res = search_memory(query, top_k=3)
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"Recherche mémoire: {query}")
                return {"status": "success",
                        "message": f"🔍 Résultats mémoire pour '{query}' :\n{mem_res}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur recherche mémoire : {str(e)}"}

        elif action_name in ("delete_memory", "forget", "delete_from_memory"):
            record_id = parameters.get("record_id", "")
            keyword = parameters.get("keyword", "")
            if not record_id and not keyword:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Paramètres de suppression vides")
                return {"status": "error",
                        "message": "Fournis un 'record_id' ou un 'keyword'."}
            try:
                del_res = delete_from_memory(record_id=record_id, keyword=keyword)
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"Suppression mémoire (ID: {record_id}, "
                                  f"Mot-clé: {keyword})")
                return {
                    "status": "success",
                    "message": (
                        f"🗑️ **Suppression de la mémoire effectuée :**\n"
                        f"- Pinecone Cloud : `{del_res.get('pinecone')}`\n"
                        f"- ChromaDB Local : `{del_res.get('chroma')}`\n"
                        f"- Table Neon (sync_log) : `{del_res.get('neon_sync')}`"
                    ),
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur lors de la suppression mémoire : {str(e)}"}

        # ----------------------------------------------------------------------
        # 5. OPÉRATIONS FICHIERS (PATHGUARD)
        # ----------------------------------------------------------------------
        elif action_name in ("write_file", "save_file", "create_file"):
            raw_filename = parameters.get("filename", "generated/agent_output.txt")
            try:
                safe_target = safe_path(raw_filename)
                safe_target.parent.mkdir(parents=True, exist_ok=True)
                content = parameters.get("content", "")
                with open(safe_target, "w", encoding="utf-8") as f:
                    f.write(content)
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"Fichier écrit: {safe_target.name}")
                return {
                    "status": "success",
                    "message": (
                        f"Fichier `{safe_target.name}` enregistré avec succès.\n\n"
                        f"[FILE:{safe_target.name}](/api/download/{safe_target.name})"
                    ),
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur écriture : {str(e)}"}

        elif action_name == "delete_file":
            filename = parameters.get("filename", "")
            target = find_existing(filename)
            if target and target.is_file():
                try:
                    target.unlink()
                    update_task_state(task_id, "COMPLETED", correlation_id,
                                      f"Fichier supprimé: {target.name}")
                    return {"status": "success",
                            "message": f"Fichier {target.name} supprimé."}
                except Exception as e:
                    update_task_state(task_id, "FAILED", correlation_id, str(e))
                    return {"status": "error",
                            "message": f"Erreur suppression : {str(e)}"}
            update_task_state(task_id, "FAILED", correlation_id, "Fichier introuvable")
            return {"status": "error",
                    "message": "Fichier introuvable ou accès refusé."}

        elif action_name == "read_file":
            filename = parameters.get("filename", "")
            target_path = find_existing(filename)
            try:
                if target_path and target_path.is_file():
                    # ★ FIX v36 : lit le DÉBUT du fichier (pas la fin)
                    content, total_len = _read_file_head(target_path)
                    update_task_state(task_id, "COMPLETED", correlation_id,
                                      f"Fichier lu: {target_path.name} "
                                      f"({len(content)}/{total_len} chars)")
                    return {
                        "status": "success",
                        "message": (f"Contenu de {target_path.name} "
                                    f"({total_len} caractères au total) :\n\n{content}"),
                    }
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Fichier introuvable")
                return {"status": "error",
                        "message": "Fichier introuvable ou accès refusé."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur lecture : {str(e)}"}

        # ----------------------------------------------------------------------
        # 6. ARCHIVES ZIP
        # ----------------------------------------------------------------------
        elif action_name == "extract_zip":
            zip_filename = parameters.get("zip_path", "")
            extract_to_folder = parameters.get("extract_to",
                                               "generated/extracted_project")
            zip_path = find_existing(zip_filename)
            if not zip_path or not zip_path.is_file():
                update_task_state(task_id, "FAILED", correlation_id, "ZIP introuvable")
                return {"status": "error",
                        "message": f"Archive ZIP introuvable : {zip_filename}"}

            target_dir = safe_path(extract_to_folder)
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(target_dir)
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"ZIP extrait: {zip_path.name}")
                return {"status": "success",
                        "message": f"Archive `{zip_path.name}` extraite dans "
                                   f"`{target_dir.name}`."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur extraction ZIP : {str(e)}"}

        elif action_name == "create_zip":
            folder_name = parameters.get("folder_path", "generated/ia_project")
            output_zip_name = parameters.get("output_zip",
                                             "generated/export_projet.zip")
            folder_path = safe_path(folder_name)
            output_path = safe_path(output_zip_name)
            try:
                if not folder_path.exists():
                    update_task_state(task_id, "FAILED", correlation_id,
                                      "Dossier introuvable")
                    return {"status": "error",
                            "message": f"Dossier source introuvable : {folder_name}"}
                output_path.parent.mkdir(parents=True, exist_ok=True)
                base_name = str(output_path).replace(".zip", "")
                shutil.make_archive(base_name, "zip", str(folder_path))
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"ZIP créé: {output_path.name}")
                return {
                    "status": "success",
                    "message": (f"Archive `{output_path.name}` créée avec succès.\n\n"
                                f"[FILE:{output_path.name}]"
                                f"(/api/download/{output_path.name})"),
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur création ZIP : {str(e)}"}

        elif action_name == "analyze_zip_content":
            zip_filename = parameters.get("zip_path", "")
            zip_path = find_existing(zip_filename)
            try:
                if not zip_path or not zip_path.is_file():
                    update_task_state(task_id, "FAILED", correlation_id,
                                      "ZIP introuvable")
                    return {"status": "error",
                            "message": f"Archive introuvable : {zip_filename}"}
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    namelist = zip_ref.namelist()
                    file_summaries = {}
                    for name in namelist[:15]:
                        if any(name.endswith(ext) for ext in
                               [".py", ".json", ".txt", ".md", ".js",
                                ".html", ".css", ".ts", ".tsx"]):
                            with zip_ref.open(name) as f:
                                content = f.read(1500).decode("utf-8", errors="ignore")
                                file_summaries[name] = content[:250] + "..."
                update_task_state(task_id, "COMPLETED", correlation_id, "ZIP analysé")
                return {
                    "status": "success",
                    "message": (f"Analyse ZIP réussie. Total fichiers : {len(namelist)}\n"
                                f"Aperçu des fichiers :\n{json_safe(file_summaries)}"),
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur analyse ZIP : {str(e)}"}

        # ----------------------------------------------------------------------
        # 7. VISION MULTIMODALE & IMAGES
        # ----------------------------------------------------------------------
        elif action_name == "analyze_image":
            image_path = parameters.get("image_path", "")
            prompt = parameters.get("prompt", "Analyse cette image.")
            provider = parameters.get("provider", "gemini")
            model = parameters.get("model", "gemini-2.5-flash")
            vision_result = analyze_image_with_vision(
                image_path, prompt, provider=provider, model=model)
            if "Erreur" in vision_result or "Error" in vision_result:
                update_task_state(task_id, "FAILED", correlation_id, "Échec vision")
                return {"status": "error",
                        "message": f"ÉCHEC VISION: {vision_result}"}
            update_task_state(task_id, "COMPLETED", correlation_id, "Vision réussie")
            return {"status": "success",
                    "message": f"Analyse Vision réussie :\n{vision_result}"}

        elif action_name == "generate_image":
            prompt = parameters.get("prompt", "")
            filename = parameters.get("filename",
                                      f"generated_{uuid.uuid4().hex[:6]}.png")
            provider = parameters.get("provider", "pollinations")
            model = parameters.get("model", "flux-3d")
            if not prompt:
                update_task_state(task_id, "FAILED", correlation_id, "Prompt vide")
                return {"status": "error", "message": "Le prompt est obligatoire."}
            gen_result = generate_image_with_provider(
                prompt, provider=provider, model=model, output_filename=filename)
            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id,
                                  gen_result.get("message"))
                return {"status": "error",
                        "message": f"ÉCHEC GÉNÉRATION: {gen_result.get('message')}"}
            final_filename = gen_result.get("filename")
            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Image générée: {final_filename}")
            return {
                "status": "success",
                "message": (f"🎨 **Image générée !**\n\n"
                            f"![{final_filename}](/api/download/{final_filename})"),
            }

        elif action_name == "merge_and_edit_images":
            image_paths = parameters.get("image_paths", [])
            prompt = parameters.get("prompt", "")
            provider = parameters.get("provider", "gemini")
            model = parameters.get("model", "gemini-3.1-flash-image")
            if not image_paths or not prompt:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Paramètres fusion manquants")
                return {"status": "error",
                        "message": "Fournis des images et un prompt."}
            gen_result = merge_and_edit_images(
                image_paths, prompt, provider=provider, model=model)
            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id,
                                  gen_result.get("message"))
                return {"status": "error",
                        "message": f"ÉCHEC FUSION: {gen_result.get('message')}"}
            final_filename = gen_result.get("filename")
            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Fusion réussie: {final_filename}")
            return {
                "status": "success",
                "message": (f"🪄 **Fusion réussie !**\n\n"
                            f"![{final_filename}](/api/download/{final_filename})"),
            }

        # ----------------------------------------------------------------------
        # 7bis. GÉNÉRATION VIDÉO (VEO 3.1)
        # ----------------------------------------------------------------------
        elif action_name in ("generate_video", "create_video", "video_generation"):
            prompt = parameters.get("prompt", "")
            filename = parameters.get("filename",
                                      f"gen_video_{uuid.uuid4().hex[:6]}.mp4")
            provider = parameters.get("provider", "gemini")
            model = parameters.get("model", "veo-3.1-gene-prev")
            aspect_ratio = parameters.get("aspect_ratio", "16:9")
            try:
                duration = int(parameters.get("duration", 8))
            except (TypeError, ValueError):
                duration = 8
            auto_stitch = bool(parameters.get("auto_stitch", True))
            negative_prompt = parameters.get("negative_prompt")
            person_generation = parameters.get("person_generation", "allow_all")

            if not prompt:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Prompt vidéo vide")
                return {"status": "error",
                        "message": "Le prompt est obligatoire pour générer une vidéo."}

            update_task_state(task_id, "RUNNING", correlation_id,
                              f"Vidéo Veo: {duration}s")

            gen_result = generate_video_with_provider(
                prompt=prompt,
                provider=provider,
                model=model,
                output_filename=filename,
                aspect_ratio=aspect_ratio,
                duration=duration,
                auto_stitch=auto_stitch,
                negative_prompt=negative_prompt,
                person_generation=person_generation,
            )

            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id,
                                  gen_result.get("message"))
                return {"status": "error",
                        "message": f"ÉCHEC VIDÉO: {gen_result.get('message')}"}

            final_filename = gen_result.get("filename")
            model_id = gen_result.get("model_id", model)
            stitched = gen_result.get("stitched", False)
            clips = gen_result.get("clips", [])

            info = f"🎬 **Vidéo générée !** ({duration}s, {aspect_ratio})\n"
            info += f"- Modèle API : `{model_id}`\n"
            if stitched and clips:
                info += f"- Mode : multi-clips assemblés `{clips}`\n"
            info += f"\n[FILE:{final_filename}](/api/download/{final_filename})\n\n"
            info += (f'<video controls src="/api/download/{final_filename}" '
                     f'style="max-width:100%;border-radius:8px;"></video>')

            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Vidéo générée: {final_filename}")
            return {"status": "success", "message": info}

        elif action_name in ("merge_and_edit_videos", "merge_videos", "edit_video"):
            video_paths = parameters.get("video_paths", [])
            prompt = parameters.get("prompt", parameters.get("user_prompt", ""))
            provider = parameters.get("provider", "agnes")
            model = parameters.get("model", "agnes-v2.0")
            filename = parameters.get("filename",
                                      f"merged_video_{uuid.uuid4().hex[:6]}.mp4")
            aspect_ratio = parameters.get("aspect_ratio", "16:9")
            try:
                duration = int(parameters.get("duration", 8))
            except (TypeError, ValueError):
                duration = 8
            auto_stitch = bool(parameters.get("auto_stitch", True))

            update_task_state(task_id, "RUNNING", correlation_id,
                              "Fusion/édition vidéo")

            gen_result = merge_and_edit_videos(
                video_paths=video_paths,
                prompt=prompt,
                provider=provider,
                model=model,
                output_filename=filename,
                aspect_ratio=aspect_ratio,
                duration=duration,
                auto_stitch=auto_stitch,
            )

            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id,
                                  gen_result.get("message"))
                return {"status": "error",
                        "message": f"ÉCHEC VIDÉO: {gen_result.get('message')}"}

            final_filename = gen_result.get("filename")
            merged = gen_result.get("videos_merged")
            note = f" ({merged} clips fusionnés)" if merged else ""

            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Vidéo finale: {final_filename}")
            return {
                "status": "success",
                "message": (f"🎞️ **Vidéo finale prête !**{note}\n\n"
                            f"[FILE:{final_filename}]"
                            f"(/api/download/{final_filename})\n\n"
                            f'<video controls src="/api/download/{final_filename}" '
                            f'style="max-width:100%;border-radius:8px;"></video>'),
            }

        # ----------------------------------------------------------------------
        # 7ter. EXTENSION VIDÉO (AGNES multi_reference)
        # ----------------------------------------------------------------------
        elif action_name in ("extend_video", "extend_video_multiple"):
            video_path = parameters.get("video_path", "LAST")
            duration = int(parameters.get("duration", 9))
            with_audio = bool(parameters.get("with_audio", True))
            audio_style = parameters.get("audio_style", "nature")

            update_task_state(task_id, "RUNNING", correlation_id,
                              f"Extension vidéo: {duration}s")

            if action_name == "extend_video_multiple":
                prompts_list = parameters.get("prompts", [])
                if not prompts_list:
                    update_task_state(task_id, "FAILED", correlation_id,
                                      "Liste prompts vide")
                    return {"status": "error",
                            "message": "Fournis une liste 'prompts'."}
                gen_result = extend_video_multiple(
                    video_path=video_path,
                    prompts=prompts_list,
                    duration_per_clip=duration,
                    with_audio=with_audio,
                    audio_style=audio_style,
                )
            else:
                prompt = parameters.get("prompt", "")
                if not prompt:
                    update_task_state(task_id, "FAILED", correlation_id,
                                      "Prompt d'extension vide")
                    return {"status": "error",
                            "message": "Le prompt d'extension est obligatoire."}
                gen_result = extend_video_with_agnes(
                    video_path=video_path,
                    new_prompt=prompt,
                    duration=duration,
                    with_audio=with_audio,
                    audio_style=audio_style,
                )

            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id,
                                  gen_result.get("message"))
                return {"status": "error",
                        "message": f"ÉCHEC EXTENSION: {gen_result.get('message')}"}

            final_filename = gen_result.get("filename")
            mode_used = gen_result.get("mode_used", "multi_reference")
            source_video = gen_result.get("source_video", "")
            extended_by = gen_result.get("extended_by", duration)

            info = f"🎬 **Vidéo étendue !** (+{extended_by}s)\n"
            info += f"- Mode continuité : `{mode_used}`\n"
            if source_video:
                info += f"- Source : `{source_video}`\n"
            if with_audio:
                info += f"- Audio : ✅ ({audio_style})\n"
            info += f"\n[FILE:{final_filename}](/api/download/{final_filename})\n\n"
            info += (f'<video controls loop '
                     f'src="/api/download/{final_filename}" '
                     f'style="max-width:100%;border-radius:8px;"></video>')

            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Vidéo étendue: {final_filename}")
            return {"status": "success", "message": info}

        # ----------------------------------------------------------------------
        # 7quater. SOUS-TITRES WHISPER
        # ----------------------------------------------------------------------
        elif action_name in ("generate_subtitles", "subtitle_video",
                             "whisper_transcribe"):
            from services.vision.whisper_client import generate_subtitles_from_video

            video_path = parameters.get("video_path", "LAST")
            language = parameters.get("language")
            model_name = parameters.get("model", "base")

            update_task_state(task_id, "RUNNING", correlation_id,
                              f"Whisper transcription ({model_name})")

            gen_result = generate_subtitles_from_video(
                video_path=video_path,
                language=language,
                model_name=model_name,
            )

            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id,
                                  gen_result.get("message"))
                return {"status": "error",
                        "message": f"ÉCHEC SOUS-TITRES : {gen_result.get('message')}"}

            srt_filename = gen_result.get("srt_filename")
            language_detected = gen_result.get("language", "?")
            segments = gen_result.get("segments_count", 0)

            info = f"🎤 **Sous-titres générés !**\n"
            info += f"- Langue détectée : `{language_detected}`\n"
            info += f"- Segments : **{segments}**\n"
            info += f"- Modèle Whisper : `{model_name}`\n"
            info += f"\n[FILE:{srt_filename}](/api/download/{srt_filename})\n"

            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Sous-titres : {srt_filename}")
            return {"status": "success", "message": info}

        elif action_name in ("burn_subtitles", "add_subtitles_to_video"):
            from services.vision.whisper_client import (
                generate_subtitles_from_video,
                burn_subtitles_into_video,
            )

            video_path = parameters.get("video_path", "LAST")
            language = parameters.get("language")
            model_name = parameters.get("model", "base")
            srt_path = parameters.get("srt_path")

            update_task_state(task_id, "RUNNING", correlation_id,
                              "Burn sous-titres")

            if not srt_path:
                srt_result = generate_subtitles_from_video(
                    video_path=video_path,
                    language=language,
                    model_name=model_name,
                )
                if srt_result.get("status") == "error":
                    return {"status": "error",
                            "message": f"Échec génération .srt : "
                                       f"{srt_result.get('message')}"}
                srt_path = srt_result.get("srt_path")

            burn_result = burn_subtitles_into_video(
                video_path=video_path,
                srt_path=srt_path,
            )

            if burn_result.get("status") == "error":
                return {"status": "error",
                        "message": f"ÉCHEC INCRUSTATION : "
                                   f"{burn_result.get('message')}"}

            final_filename = burn_result.get("filename")

            info = f"🎬 **Vidéo sous-titrée !**\n"
            info += f"- Source : `{os.path.basename(video_path)}`\n"
            info += f"- Sous-titres : `{os.path.basename(srt_path)}`\n\n"
            info += f"[FILE:{final_filename}](/api/download/{final_filename})\n\n"
            info += (f'<video controls loop '
                     f'src="/api/download/{final_filename}" '
                     f'style="max-width:100%;border-radius:8px;"></video>')

            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Sous-titres brûlés : {final_filename}")
            return {"status": "success", "message": info}

        # ----------------------------------------------------------------------
        # 8. EXÉCUTION SYSTÈME
        # ----------------------------------------------------------------------
        elif action_name in ("execute_command", "run_script", "run_tests"):
            command = parameters.get("command",
                                     "dir" if os.name == "nt" else "ls -la").strip()
            cmd_lower = command.lower()

            if any(k in cmd_lower for k in ["dir /s", "get-childitem",
                                            "find .", "ls -r", "tree"]):
                pattern = ""
                match = re.search(
                    r"[*'\"\\]([a-zA-Z0-9_\-\.]+[*'\"\\]|[a-zA-Z0-9_\-\.]+)",
                    command)
                if match:
                    raw = (match.group(1).replace("*", "")
                           .replace("'", "").replace('"', ""))
                    if raw and raw not in ("s", "b", "f", "r", "w", "v"):
                        pattern = raw

                matched = _fast_workspace_scan(pattern)
                output = (f"Scan instantané ({len(matched)} fichiers trouvés) :\n"
                          + "\n".join(matched[:100]))
                if len(matched) > 100:
                    output += f"\n... et {len(matched) - 100} autres fichiers."
                update_task_state(task_id, "COMPLETED", correlation_id,
                                  f"Scan workspace ({pattern or 'global'})")
                return {"status": "success", "message": output}

            try:
                res = subprocess.run(
                    command,
                    shell=True,
                    cwd=WORKSPACE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                status_str = "success" if res.returncode == 0 else "error"
                update_task_state(
                    task_id,
                    "COMPLETED" if res.returncode == 0 else "FAILED",
                    correlation_id,
                    command[:100],
                )
                return {"status": status_str,
                        "message": f"Commande exécutée :\n{output[-2500:]}"}
            except subprocess.TimeoutExpired:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Timeout (30s)")
                return {"status": "error",
                        "message": "⚠️ Commande interrompue : "
                                   "l'exécution a dépassé 30s."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error",
                        "message": f"Erreur exécution : {str(e)}"}

        # ----------------------------------------------------------------------
        # 9. TÂCHES D'ARRIÈRE-PLAN
        # ----------------------------------------------------------------------
        elif action_name in ("execute_tmux_headless", "execute_background_task",
                             "start_background_task"):
            session_name = parameters.get("session_name",
                                          f"job_{uuid.uuid4().hex[:6]}")
            command = parameters.get("command", "")
            if not command:
                update_task_state(task_id, "FAILED", correlation_id,
                                  "Commande vide")
                return {"status": "error",
                        "message": "La commande ne peut pas être vide."}
            update_task_state(task_id, "RUNNING", correlation_id,
                              f"Tâche de fond: {session_name}")
            return start_background_task(session_name, command)

        elif action_name in ("stop_background_task", "stop_tmux_headless",
                             "kill_session", "stop_session"):
            session_name = parameters.get("session_name", "monitor_task")
            update_task_state(task_id, "COMPLETED", correlation_id,
                              f"Arrêt tâche: {session_name}")
            return stop_background_task(session_name)

        # ----------------------------------------------------------------------
        # 10. FALLBACK
        # ----------------------------------------------------------------------
        update_task_state(task_id, "FAILED", correlation_id,
                          f"Action inconnue : '{action_name}'")
        return {"status": "error",
                "message": f"Action inconnue : '{action_name}'."}

    except Exception as e:
        update_task_state(task_id, "FAILED", correlation_id, str(e))
        return {"status": "error",
                "message": f"Erreur critique outil : {str(e)}"}


# ==============================================================================
# WRAPPER PUBLIC : trace chaque appel dans episodic_log
# ==============================================================================
def execute_agent_crm_tool(action_name: str, parameters: dict) -> dict:
    """
    Wrapper public qui :
      1. mesure la latence de l'appel
      2. appelle le dispatcher réel
      3. persiste l'épisode dans DuckDB (episodic_log)
      4. retourne le résultat inchangé à l'appelant
    """
    t0 = time.monotonic()
    result = None
    status_for_log = "exception"
    error_type = None

    try:
        result = _execute_agent_crm_tool_impl(action_name, parameters)
        status_for_log = (result or {}).get("status", "unknown")
        if status_for_log == "error":
            error_type = (result or {}).get("error_type") or "ActionError"
        return result

    except Exception as exc:
        error_type = type(exc).__name__
        raise

    finally:
        try:
            latency_ms = (time.monotonic() - t0) * 1000.0
            msg = ""
            if isinstance(result, dict):
                msg = str(result.get("message", ""))[:2000]
            _log_episode_bg(
                action=action_name,
                parameters=parameters or {},
                status=status_for_log,
                message=msg,
                error_type=error_type,
                latency_ms=latency_ms,
                source="action_executor",
            )
        except Exception:
            pass