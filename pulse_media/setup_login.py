"""
setup_login.py — One-time Instagram login setup
Run this ONCE to verify your account and save the session.

Usage:
  python3 setup_login.py
  python3 setup_login.py techpulse
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import env_loader  # noqa: F401 — loads .env on import

SESSION_DIR = os.path.join(os.path.dirname(__file__), "data", "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

def setup(page="finpulse"):
    import instagrapi

    key      = page.upper()
    username = os.environ.get(f"INSTAGRAM_{key}_USERNAME", "")
    password = os.environ.get(f"INSTAGRAM_{key}_PASSWORD", "")

    if not username or username == "REPLACE_ME":
        print(f"No username set for {page} in .env")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  Instagram Login — {page.upper()}")
    print(f"  Account: {username}")
    print(f"{'='*50}\n")

    cl = instagrapi.Client()
    cl.delay_range = [2, 5]
    session_file = os.path.join(SESSION_DIR, f"{page}_session.json")

    try:
        print("  Logging in...")

        # Check if 2FA code needed
        totp_code = input("  Open Google Authenticator → enter Instagram code: ").strip()
        cl.login(username, password, verification_code=totp_code)
        cl.dump_settings(session_file)
        print(f"\n  ✅ Login successful! Session saved.")
        print(f"  Now run: python3 instagram.py {page}")

    except Exception as e:
        err = str(e).lower()

        if "challenge_required" in err or "challenge" in err:
            print("\n  ⚠️  Instagram needs extra verification.")
            print("  Check your email or phone for a 6-digit code.\n")
            code = input("  Enter the code Instagram sent: ").strip()
            try:
                cl.challenge_resolve(cl.last_json)
                cl.dump_settings(session_file)
                print(f"\n  ✅ Verified! Session saved.")
                print(f"  Now run: python3 instagram.py {page}")
            except Exception as e2:
                print(f"\n  ❌ Failed: {e2}")

        elif "two_factor" in err or "2fa" in err or "verification_code" in err:
            print("  ❌ Wrong 2FA code — codes expire every 30 seconds.")
            print("  Run the script again and enter a fresh code quickly.")

        elif "bad_password" in err or "password" in err:
            print("  ❌ Wrong password — check .env file")

        else:
            print(f"  ❌ Error: {e}")
            print("  Try running this script again.")

if __name__ == "__main__":
    page = "finpulse"
    for arg in sys.argv[1:]:
        if arg in ("finpulse","techpulse","corppulse","worldpulse"):
            page = arg
    setup(page)
