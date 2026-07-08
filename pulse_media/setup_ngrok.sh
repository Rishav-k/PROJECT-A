#!/bin/bash
# ─────────────────────────────────────────────
# Pulse Media — ngrok setup for Apple Silicon
# Run once: bash setup_ngrok.sh
# ─────────────────────────────────────────────

set -e

echo ""
echo "════════════════════════════════════════"
echo "  📦 Installing ngrok to ~/bin"
echo "════════════════════════════════════════"

# 1 ── Create ~/bin if it doesn't exist ───────
mkdir -p "$HOME/bin"

# 2 ── Download ngrok (Apple Silicon) ─────────
echo "  ↓ Downloading ngrok..."
curl -Lo /tmp/ngrok.zip \
  "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-arm64.zip"
unzip -o /tmp/ngrok.zip -d "$HOME/bin"
rm /tmp/ngrok.zip
chmod +x "$HOME/bin/ngrok"
echo "  ✅ ngrok installed → $HOME/bin/ngrok"

# 3 ── Add ~/bin to PATH in .zshrc if not already there ───
ZSHRC="$HOME/.zshrc"
if ! grep -q 'export PATH="$HOME/bin:$PATH"' "$ZSHRC" 2>/dev/null; then
  echo '' >> "$ZSHRC"
  echo '# Added by Pulse Media setup' >> "$ZSHRC"
  echo 'export PATH="$HOME/bin:$PATH"' >> "$ZSHRC"
  echo "  ✅ Added ~/bin to PATH in .zshrc"
fi
export PATH="$HOME/bin:$PATH"

# 4 ── ngrok auth token ────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  🔑 ngrok Auth Token"
echo "════════════════════════════════════════"
echo ""
echo "  You need a FREE ngrok account to get a public URL."
echo "  → Sign up at: https://dashboard.ngrok.com/signup"
echo "  → After signing in: https://dashboard.ngrok.com/get-started/your-authtoken"
echo "  → Copy your authtoken, then paste it below."
echo ""
read -p "  Paste your ngrok authtoken here: " NGROK_TOKEN

if [ -z "$NGROK_TOKEN" ]; then
  echo "  ⚠️  No token entered — skipping. Run later: ngrok config add-authtoken YOUR_TOKEN"
else
  "$HOME/bin/ngrok" config add-authtoken "$NGROK_TOKEN"
  echo "  ✅ Auth token saved"
fi

# 5 ── Create a launch script for easy daily use ──────────
LAUNCH_SCRIPT="$HOME/bin/pulse-start"
cat > "$LAUNCH_SCRIPT" << 'EOF'
#!/bin/bash
# Start Pulse Media dashboard + ngrok tunnel
PROJECT="$HOME/PROJECT-A/pulse_media"

echo ""
echo "════════════════════════════════════════"
echo "  🚀 Starting Pulse Media Command Center"
echo "════════════════════════════════════════"

# Kill any existing server on port 8888
lsof -ti:8888 | xargs kill -9 2>/dev/null || true
sleep 1

# Start dashboard in background
cd "$PROJECT"
python3 dashboard/server.py &
SERVER_PID=$!
echo "  ✅ Dashboard started (PID $SERVER_PID)"
sleep 2

# Start ngrok tunnel
echo "  🌐 Starting ngrok tunnel..."
echo ""
$HOME/bin/ngrok http 8888
EOF
chmod +x "$LAUNCH_SCRIPT"

echo ""
echo "════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Every day, just run:"
echo "    pulse-start"
echo ""
echo "  ngrok will show your public URL."
echo "  Login: angad / PulseAdmin2024!"
echo "════════════════════════════════════════"
echo ""

# 6 ── Ask to start now ───────────────────────
read -p "  Start the dashboard + tunnel now? [Y/n]: " START_NOW
if [[ "$START_NOW" != "n" && "$START_NOW" != "N" ]]; then
  "$LAUNCH_SCRIPT"
fi
