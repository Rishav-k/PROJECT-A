"""env_loader.py — loads pulse_media/.env once, shared by every entry point.

Usage: `import env_loader` before reading any os.environ value.
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
