"""Shared Haven settings and LocalMusic AI credential helpers."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

PALETTES = {
    "deep_focus": {"canvas": "#08080c", "lines": "#4a90d9", "name": "Deep Focus"},
    "sleep": {"canvas": "#0a0808", "lines": "#8b7db3", "name": "Sleep"},
    "melancholy": {"canvas": "#080a08", "lines": "#c4a77d", "name": "Melancholy"},
    "meditation": {"canvas": "#080c0a", "lines": "#7dd3c4", "name": "Meditation"},
    "dark_intense": {"canvas": "#050505", "lines": "#d4574a", "name": "Dark Intense"},
    "flow_state": {"canvas": "#0c0808", "lines": "#e8a87c", "name": "Flow State"},
    "love": {"canvas": "#0a080a", "lines": "#d4a5a5", "name": "Love"},
    "thinking": {"canvas": "#08080a", "lines": "#a8b5c4", "name": "Thinking"},
}
MOODS = ["Focus", "Sleep", "Melancholy", "Meditation", "Intense", "Flow", "Love", "Thinking"]
GENRES = ["Ambient", "Cinematic", "Lofi", "Minimalist", "Electronic"]
ACTIVITIES = ["Coding", "Reading", "Sleeping", "Meditating", "Writing", "Walking"]

LOCALMUSIC_API_URL = "https://api.acemusic.ai"
LOCALMUSIC_MODEL = "acemusic/acestep-v15-turbo"
KEY_FILE = Path(__file__).with_name(".localmusic_api_key")
CONFIG_FILE = Path(__file__).with_name("haven_config.json")

def get_localmusic_key():
    return os.getenv("ACEMUSIC_API_KEY", "") or (KEY_FILE.read_text().strip() if KEY_FILE.exists() else "")

def save_localmusic_key(key):
    KEY_FILE.write_text(key.strip())
    os.chmod(KEY_FILE, 0o600)

def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError as error:
        raise RuntimeError("haven_config.json is invalid JSON; restore it from a backup or create a new plan.") from error
    if not isinstance(data, dict):
        raise RuntimeError("haven_config.json must contain a JSON object.")
    return data

def save_config(data):
    if not isinstance(data, dict):
        raise TypeError("Haven configuration must be a dictionary.")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_FILE.parent, delete=False) as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(CONFIG_FILE)

def get_palette_by_mood(mood):
    return PALETTES.get(mood.lower().replace(" ", "_"), PALETTES["deep_focus"])

def format_duration(hours):
    return "1 HOUR" if hours == 1 else f"{hours} HOURS"
