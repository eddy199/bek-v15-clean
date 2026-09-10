"""
rate_limit.py — Module de limitation de débit (Rate Limiting)
Projet : AI Workflow Lab

Configure un Limiter slowapi basé sur l'adresse IP distante du client
(get_remote_address), prêt à limiter la route de chat à 30 requêtes / minute.

Intégration FastAPI (main.py) :
    from slowapi.errors import RateLimitExceeded
    from slowapi import _rate_limit_exceeded_handler
    from rate_limit import limiter, CHAT_RATE_LIMIT

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.post("/chat")
    @limiter.limit(CHAT_RATE_LIMIT)
    async def chat(request: Request, payload: ChatRequest):
        ...
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiteur basé sur l'adresse IP du client
limiter = Limiter(key_func=get_remote_address)

# Limite appliquée à la route de chat : 30 requêtes par minute par IP
CHAT_RATE_LIMIT = "30/minute"
