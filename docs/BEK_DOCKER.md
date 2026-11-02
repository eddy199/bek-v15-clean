
---

### Fichier 5 : `docs/BEK_DOCKER.md`

```markdown
# BEK-DOCKER — Encapsulation des Agents
## Un Docker par Agent, une Abréviation par Docker

**Version :** 1.0
**Date :** 2026-09-23
**Brevet :** BEK-DOCKER-v1.0

---

## 1. PRINCIPE

Chaque agent BEK est encapsulé dans un **Docker** qui :
- Contient le code de l'agent
- Contient ses dépendances (briques)
- Contient sa documentation
- Expose UNE SEULE abréviation

**Résultat :** un agent = un Docker = une abréviation.

---

## 2. STRUCTURE D'UN DOCKER BEK

```dockerfile
# ==============================================================================
# BEK-DOCKER — Agent BEK v18
# ------------------------------------------------------------------------------
# Abréviation : BEK-AGENT-v18
# Brevet : docs/brevets/BREVET_AGENT_V18.md
# ==============================================================================

FROM python:3.11-slim

# Métadonnées BEK
LABEL bek.agent.abreviation="BEK-AGENT-v18"
LABEL bek.agent.version="18.0"
LABEL bek.agent.brevet="BREVET_AGENT_V18.md"
LABEL bek.agent.dependencies="BEK-REX,BEK-FLUX,BEK-MEM,BEK-LOOP,BEK-ECO"

# Variables d'environnement
ENV BEK_MODE=production
ENV PYTHONUNBUFFERED=1

# Répertoire de travail
WORKDIR /app

# Copier les requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'agent
COPY agents/bek_v18/ /app/agents/bek_v18/

# Copier les briques BEK
COPY bek_core/ /app/bek_core/

# Copier les brevets
COPY docs/brevets/ /app/docs/brevets/

# Copier la config
COPY env.txt /app/env.txt

# Point d'entrée : le CPU BEK
ENTRYPOINT ["python", "-m", "bek_core.cpu"]

# Exposer l'API
EXPOSE 8765