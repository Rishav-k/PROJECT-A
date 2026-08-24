#!/bin/bash
# ─────────────────────────────────────────────
# Pulse Media — One-click startup
# Installs ngrok if needed, starts server + tunnel
# ─────────────────────────────────────────────

set -e
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load NGROK_TOKEN (and other vars) from .env
if [ -f "$PROJECT/.env" ]; then
  set -a
  source "$PROJECT/.env"
  set +a
fi

if [ -z "$NGROK_TOKEN" ]; then
  echo "  ❌ NGROK_TOKEN not set — add it to $PROJECT/.env"
  exit 1
fi

echo ""
echo "════════════════════════════════════════════"
echo "  🚀 Pulse Media — Startup"
echo "════════════════════════════════════════════"

# ── 1. Install ngrok if not present ──────────
if ! command -v ngrok &>/dev/null && [ ! -f "$HOME/bin/ngrok" ]; then
  echo "  📦 Installing ngrok..."
  mkdir -p "$HOME/bin"
  # Reuse downloaded zip if still there
  if [ ! -f /tmp/ngrok.zip ]; then
    curl -Lo /tmp/ngrok.zip \
      "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-arm64.zip"
  fi
  unzip -o /tmp/ngrok.zip -d "$HOME/bin"
  chmod +x "$HOME/bin/ngrok"
  rm -f /tmp/ngrok.zip
  echo "  ✅ ngrok installed"
fi

# Make sure ~/bin is in PATH for this session
export PATH="$HOME/bin:$PATH"

# Add ~/bin to .zshrc permanently if not already there
if ! grep -q 'HOME/bin' "$HOME/.zshrc" 2>/dev/null; then
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.zshrc"
fi

# ── 2. Configure ngrok auth token ────────────
echo "  🔑 Configuring ngrok auth token..."
ngrok config add-authtoken "$NGROK_TOKEN"
echo "  ✅ Auth token set"

# ── 3. Kill any existing server on 8888 ──────
lsof -ti:8888 | xargs kill -9 2>/dev/null || true
sleep 1

# ── 4. Start dashboard server in background ──
echo "  🖥  Starting dashboard server..."
cd "$PROJECT"
python3 dashboard/server.py > /tmp/pulse_server.log 2>&1 &
SERVER_PID=$!
sleep 3

# Check it started
if kill -0 $SERVER_PID 2>/dev/null; then
  echo "  ✅ Dashboard running (PID $SERVER_PID)"
else
  echo "  ❌ Dashboard failed to start — check /tmp/pulse_server.log"
  cat /tmp/pulse_server.log
  exit 1
fi

# ── 5. Start ngrok tunnel ─────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  🌐 Starting ngrok tunnel on port 8888..."
echo "  📱 Your public URL will appear below."
echo "  🔐 Login: see DASHBOARD_USER / DASHBOARD_PASS in .env"
echo "════════════════════════════════════════════"
echo ""

ngrok http 8888
