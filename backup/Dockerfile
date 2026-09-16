# ==========================================
# DOCKERFILE BEK-v15 HYBRID (Python + Node + Glab + Claude)
# ==========================================

FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Installation des dépendances système de base
RUN apt-get update -q && apt-get install -y \
    curl \
    wget \
    gpg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Installation de Node.js (Requis pour Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Installation de Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Installation de Glab (GitLab CLI)
RUN curl -sSL https://raw.githubusercontent.com/upciti/wakemeops/main/assets/install_repository | bash && \
    apt-get install -y glab

WORKDIR /app

# Copie de tout le projet
COPY . /app/

# Installation des requirements Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Configuration Git
RUN git config --global user.email "claudecode@gitlab.com" && \
    git config --global user.name "Claude Code"

# Script de démarrage pour configurer GitLab dynamiquement et lancer Flask
RUN echo '#!/bin/bash\n\
if [ ! -z "$AI_FLOW_GITLAB_HOSTNAME" ] && [ ! -z "$AI_FLOW_GITLAB_TOKEN" ]; then\n\
  echo "Configuration de glab-cli..."\n\
  mkdir -p ~/.config/glab-cli\n\
  cat > ~/.config/glab-cli/config.yml <<EOF\n\
hosts:\n\
  $AI_FLOW_GITLAB_HOSTNAME:\n\
    token: $AI_FLOW_GITLAB_TOKEN\n\
    is_oauth2: "true"\n\
    client_id: "bypass"\n\
    oauth2_refresh_token: ""\n\
    oauth2_expiry_date: "01 Jan 50 00:00 UTC"\n\
    api_host: $AI_FLOW_GITLAB_HOSTNAME\n\
    user: ClaudeCode\n\
check_update: "false"\n\
git_protocol: https\n\
EOF\n\
  chmod 600 ~/.config/glab-cli/config.yml\n\
fi\n\
echo "Lancement de BEK-v15..."\n\
python app.py' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8765

CMD ["/app/start.sh"]
