# -*- coding: utf-8 -*-
"""
Charge env.txt / .env dans os.environ au tout début du programme.
Doit être importé AVANT tout autre module qui lit os.getenv().

Correctif v2 :
  - Suppression des commentaires inline ("valeur    # commentaire")
  - Gestion correcte des valeurs entre guillemets
  - Ne touche pas aux URLs contenant des '#'
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("bek.env_loader")

_LOADED = False


def _strip_inline_comment(value: str) -> str:
    """
    Retire un éventuel commentaire inline ('valeur  # commentaire').
    Respecte les valeurs entre guillemets (simples ou doubles).
    Ne casse PAS les URLs avec '#' (ex. https://x.fr/page#anchor).
    """
    if not value:
        return value

    v = value.strip()

    # Valeur entièrement entre guillemets → on ne touche à rien
    if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
        return v[1:-1]

    # Cherche " #" (espace puis #) et "\t#" (tab puis #) — pattern classique de commentaire
    # On n'attaque pas un '#' collé au mot (URLs, valeurs techniques)
    candidates = []
    for marker in (" #", "\t#"):
        idx = v.find(marker)
        if idx != -1:
            candidates.append(idx)

    if candidates:
        cut = min(candidates)
        v = v[:cut].rstrip()

    # Retire les guillemets externes éventuels
    if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
        v = v[1:-1]

    return v


def load_env(force: bool = False) -> int:
    """
    Charge les variables depuis env.txt puis .env.
    N'écrase JAMAIS une variable déjà présente dans os.environ.

    Retourne le nombre de variables chargées.
    """
    global _LOADED
    if _LOADED and not force:
        return 0

    root = Path(__file__).resolve().parent
    count = 0

    for filename in ("env.txt", ".env"):
        path = root / filename
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8-sig", errors="ignore") as fh:
                for raw in fh:
                    line = raw.rstrip("\r\n")

                    # Lignes vides ou de pur commentaire → on saute
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue

                    # Doit contenir un '='
                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    if not key:
                        continue

                    # Nettoie le commentaire inline éventuel
                    value = _strip_inline_comment(value)

                    # N'écrase pas une variable déjà définie
                    if key not in os.environ:
                        os.environ[key] = value
                        count += 1
        except Exception as exc:
            logger.warning("Erreur lecture %s : %s", filename, exc)

    _LOADED = True
    if count:
        logger.info("env_loader : %d variables chargées depuis env.txt/.env", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    n = load_env()
    print(f"\nVariables chargées : {n}")
    print()
    for k in (
        "REDIS_URL",
        "BEK_EVENTBUS_MODE",
        "BEK_ENABLE_EVENT_BUS_NERVES",
        "BEK_ENABLE_HERMES_NERVES",
        "BEK_CHAT_HISTORY_WINDOW",
        "PORT",
        "AISA_API_KEY",
    ):
        v = os.getenv(k, "(absent)")
        # masque les secrets
        if v and ("KEY" in k or "SECRET" in k):
            v = v[:12] + "…" if len(v) > 12 else v
        print(f"  {k:35s} = {v!r}")