# ==============================================================================
# BEK-v16 — Dockerfile pour Render
# ------------------------------------------------------------------------------
# Python 3.11 + Playwright + FFmpeg + dépendances BEK
# ==============================================================================

FROM python:3.11-slim

# Variables d'env pour Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dépendances système (Playwright + psycopg2 + Pillow + FFmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libffi-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier requirements en premier (cache Docker)
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Installer Chromium pour Playwright
RUN playwright install chromium && \
    playwright install-deps chromium

# Copier le reste du projet
COPY . /app/

# Port
EXPOSE 8765

# Lancer l'application
CMD ["python", "app.py"]