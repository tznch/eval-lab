from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    load_dotenv(ROOT / ".env")
    overlay = ROOT / ".env.profile"
    if overlay.is_file():
        load_dotenv(overlay, override=True)
