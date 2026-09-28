# -*- coding: utf-8 -*-
"""
BEK-v18 — Chat Modules
======================
Modules découpés de routers/chat.py pour maintenabilité.

Architecture :
    - config.py      : Configuration et constantes
    - prompts.py     : Prompts système
    - validation.py  : Validation (URLs, traductions, qualité)
    - formatters.py  : Formatage des résultats
    - actions.py     : Exécution des actions
    - scrape.py      : Auto-scrape
    - routing.py     : BEK-REX routing
    - stair.py       : BEK-STAIR anti-hallucination
    - streaming.py   : Streaming SSE
    - chat.py        : Orchestrateur principal
"""