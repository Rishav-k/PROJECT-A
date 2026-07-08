"""
export_session.py — Export session file as base64 for GitHub Secrets
Run this whenever you need to update the FINPULSE_SESSION secret.

Usage:
  python3 export_session.py
"""
import base64, os

session_path = os.path.join(os.path.dirname(__file__), "data", "sessions", "finpulse_session.json")

if not os.path.exists(session_path):
    print("❌ Session file not found. Run setup_login.py first.")
else:
    with open(session_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    print("\n" + "="*60)
    print("FINPULSE_SESSION value for GitHub Secrets:")
    print("="*60)
    print(encoded)
    print("="*60)
    print("\nCopy the long string above → paste into GitHub Secret.")
