# BREVET BEK-VISION
## Multimodal Media Pipeline — Image + Video + Subtitles

**Code brevet :** BEK-VISION-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-VISION |
| **Nom court** | VISION |
| **Nom long** | Multimodal Media Pipeline |
| **Sous-titre** | Image + Video + Subtitles |
| **Version** | 1.0 |
| **Catégorie** | Brique multimédia |
| **Statut** | ✅ Actif |
| **Priorité** | 🟠 Haute |

---

## 2. PROBLÈME RÉSOLU

Les agents IA gèrent le texte, mais **pas les médias** :

- Génération d'image : nécessite APIs complexes (Stability, Midjourney)
- Génération de vidéo : Veo est cher, Agnes est peu documenté
- Extension de vidéo : continuité personnage difficile
- Sous-titres : Whisper est lourd à intégrer
- Multi-clips : stitching manuel complexe

**Résultat** : l'agent est aveugle et muet.

---

## 3. SOLUTION UNIQUE

**BEK-VISION unifie 6 providers multimédia derrière une API unique** :

1. **Image** : Pollinations (gratuit) + Gemini + Hugging Face
2. **Vidéo** : Agnes (gratuit, audio natif) + Veo 3.1 (payant)
3. **Audio** : Whisper (local, gratuit)
4. **FFmpeg** : crossfade, concat, trim, codec
5. **Extension** : continuité personnage via keyframes + crossfade 0.5s
6. **Multi-clips** : stitching automatique avec continuité narrative

### Les 12 modules

| Module | Rôle |
|---|---|
| `agnes_client.py` | Client Agnes (rate limit, retry, modes) |
| `veo_client.py` | Client Veo 3.1 (predictLongRunning) |
| `whisper_client.py` | Whisper local (.srt + burn) |
| `pollinations_client.py` | Pollinations (image gratuite) |
| `huggingface_client.py` | HF Inference (image + img2img) |
| `image_generation.py` | Routeur image (Gemini/Pollinations/HF) |
| `image_analysis.py` | Analyse d'image (Gemini Vision) |
| `video_generation.py` | Routeur vidéo (Agnes/Veo) |
| `video_extension.py` | Extension (keyframes + crossfade) |
| `video_concat.py` | Concat (FFmpeg copy + crossfade) |
| `ffmpeg_utils.py` | Helpers FFmpeg (trim, concat, crossfade) |
| `constants.py` | Constantes partagées |

### Formats supportés

- **Image** : `.png`, `.jpg`, `.jpeg`, `.webp`
- **Vidéo** : `.mp4`, `.webm`, `.mov`
- **Audio** : WAV 16kHz mono (interne Whisper)

---

## 4. PREUVE D'EXÉCUTION

```python
from services.vision import (
    generate_image_with_provider,
    generate_video_with_provider,
    extend_video_with_agnes,
    generate_subtitles_from_video,
    burn_subtitles_into_video,
)

# 1. Image (gratuit, Pollinations)
img = generate_image_with_provider(
    prompt="Un chat dans un jardin",
    provider="pollinations",
    model="flux-3d",
)
# → {"status": "success", "filename": "pollinations_xxx.png", ...}

# 2. Vidéo (gratuit, Agnes, avec audio)
vid = generate_video_with_provider(
    prompt="A cat playing in a garden",
    provider="agnes",
    model="agnes-v2.0",
    duration=5,
    with_audio=True,
    audio_style="children",
)
# → {"status": "success", "filename": "agnes_video_xxx.mp4", ...}

# 3. Extension (continuité personnage)
ext = extend_video_with_agnes(
    video_path="LAST",
    new_prompt="The cat continues playing",
    duration=9,
    with_audio=True,
)
# → {"status": "success", "mode_used": "keyframes", "extended_by": 9, ...}

# 4. Sous-titres (Whisper local)
srt = generate_subtitles_from_video(
    video_path="LAST",
    language="fr",
    model_name="base",
)
# → {"status": "success", "srt_path": "...srt", "language": "fr", ...}

# 5. Burn sous-titres
final = burn_subtitles_into_video(video_path="LAST", srt_path=srt["srt_path"])
# → {"status": "success", "filename": "..._subtitled_xxx.mp4", ...}
```

**Résultat :** 5 étapes, image + vidéo + extension + sous-titres + burn. Pipeline complet.

---

## 5. API PUBLIQUE

### Image

| Fonction | Providers |
|---|---|
| `generate_image_with_provider(prompt, provider, model, ...)` | `gemini`, `pollinations`, `huggingface` |
| `merge_and_edit_images(image_paths, prompt, provider, model)` | Fusion multi-images |
| `analyze_image_with_vision(image_path, prompt)` | Gemini Vision |

### Vidéo

| Fonction | Providers |
|---|---|
| `generate_video_with_provider(prompt, provider, model, duration, ...)` | `agnes`, `gemini` (Veo) |
| `extend_video_with_agnes(video_path, new_prompt, duration)` | Agnes extension |
| `extend_video_multiple(video_path, prompts, duration_per_clip)` | Extensions en série |
| `concat_videos(video_paths, output_path, target_duration)` | Concat FFmpeg |
| `merge_and_edit_videos(video_paths, prompt, provider)` | Fusion intelligente |

### Sous-titres

| Fonction | Rôle |
|---|---|
| `generate_subtitles_from_video(video_path, language, model_name)` | Whisper → .srt |
| `burn_subtitles_into_video(video_path, srt_path, font_size)` | Incrustation |

### Endpoints & Model IDs

Via `provider_manager` (BEK-MUX) :

| Méthode | Rôle |
|---|---|
| `get_veo_endpoints(model)` | URLs Veo prêtes |
| `get_agnes_endpoints(model)` | URLs Agnes prêtes |
| `get_huggingface_image_endpoints(model)` | URLs HF prêtes |
| `resolve_veo_model_id(model)` | Mapping nom court → ID Google |
| `resolve_agnes_model_id(model)` | Mapping nom court → ID Agnes |

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `services/vision/__init__.py` | Exports publics |
| `services/vision/constants.py` | Constantes |
| `services/vision/ffmpeg_utils.py` | FFmpeg helpers |
| `services/vision/image_analysis.py` | Gemini Vision |
| `services/vision/image_generation.py` | Routeur image |
| `services/vision/pollinations_client.py` | Pollinations |
| `services/vision/huggingface_client.py` | Hugging Face |
| `services/vision/whisper_client.py` | Whisper |
| `services/vision/veo_client.py` | Veo 3.1 |
| `services/vision/agnes_client.py` | Agnes |
| `services/vision/video_generation.py` | Routeur vidéo |
| `services/vision/video_extension.py` | Extension vidéo |
| `services/vision/video_concat.py` | Concat |
| `services/prompt_optimizer.py` | Optimisation prompts |
| `bek_core/vision/` | **À créer** |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **Runway ML** | Payant, 1 provider | **6 providers unifiés** |
| **Pika Labs** | 1 modèle vidéo | **Agnes + Veo + extension** |
| **Descript** | Édition post-prod | **Génération + sous-titres** |
| **Whisper API** | Payant (OpenAI) | **Whisper local gratuit** |

**Personne n'a un pipeline multimédia aussi complet (image + vidéo + audio + sous-titres + extension).**

---

## 8. DÉPENDANCES

- `requests` (HTTP)
- `openai-whisper` (optionnel — local)
- `ffmpeg` (binaire système)
- `werkzeug` (secure_filename)
- `provider_manager.py` (BEK-MUX)

---

## 9. UTILISÉ PAR

- `action_executor.py` (toutes les actions multimédia)
- `services/vision/` (module complet)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26