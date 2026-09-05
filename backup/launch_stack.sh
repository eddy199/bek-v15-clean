#!/usr/bin/env bash
# ============================================================
# BEK-v15.2 HYBRID - TMUX & HEADLESS & BACKEND ORCHESTRATOR
# ============================================================

SESSION_NAME="bek-stack"
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$WORKSPACE_DIR" || exit 1

# Détection de l'environnement virtuel Python
PYTHON_BIN="python3"
if [ -f "$WORKSPACE_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$WORKSPACE_DIR/venv/bin/python"
fi

# Nettoyage d'une ancienne session existante si présente
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

echo "🚀 Démarrage de la stack BEK-v15.2 sous Tmux ($SESSION_NAME)..."

# 1. Fenêtre 0 : Proxy Headroom (ou veille si binaire absent)
tmux new-session -d -s "$SESSION_NAME" -n "headroom" -c "$WORKSPACE_DIR" "bash"
tmux send-keys -t "$SESSION_NAME:0" "export HEADROOM_OUTPUT_SHAPER=1 HEADROOM_TLS_STRICT=0" C-m
tmux send-keys -t "$SESSION_NAME:0" "if command -v headroom >/dev/null 2>&1; then headroom proxy --port 8787; else echo 'Proxy Headroom standalone non requis - routage direct actif.'; fi" C-m

# 2. Fenêtre 1 : Serveur Backend Flask & Hermes Core (Port 8765)
tmux new-window -t "$SESSION_NAME:1" -n "backend" -c "$WORKSPACE_DIR" "bash"
tmux send-keys -t "$SESSION_NAME:1" "$PYTHON_BIN app.py" C-m

# 3. Fenêtre 2 : Worker Headless Playwright
tmux new-window -t "$SESSION_NAME:2" -n "headless" -c "$WORKSPACE_DIR" "bash"
tmux send-keys -t "$SESSION_NAME:2" "$PYTHON_BIN worker_headless.py" C-m

# Attente brève pour stabilisation
sleep 1

# Vérification que la session est bien active
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "✅ Stack opérationnelle dans la session Tmux '$SESSION_NAME'."
    echo ""
    echo "Commandes d'accès :"
    echo "   tmux attach -t $SESSION_NAME   (Pour ouvrir la console multi-fenêtres)"
    echo "   http://localhost:8765          (Interface Web BEK-v15.2)"
else
    echo "❌ Erreur lors de la création de la session Tmux."
fi
