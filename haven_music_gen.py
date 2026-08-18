#!/usr/bin/env python3
"""Generate instrumental audio with LocalMusic AI's ACE Music API."""
import argparse
import base64
from datetime import datetime
from pathlib import Path

import requests

from config import LOCALMUSIC_API_URL, LOCALMUSIC_MODEL, get_localmusic_key

def _audio_bytes(response):
    message = response.get("choices", [{}])[0].get("message", {})
    audio_items = message.get("audio") or response.get("audio") or []
    if not audio_items:
        raise RuntimeError("LocalMusic AI returned no audio.")
    item = audio_items[0]
    value = item.get("audio_url", {}).get("url", "") if isinstance(item, dict) else ""
    value = value or (item.get("url", "") if isinstance(item, dict) else "")
    if not value:
        raise RuntimeError("LocalMusic AI returned an audio item without data.")
    return base64.b64decode(value.split(",", 1)[-1])

def generate_music(prompt, duration_seconds=180):
    key = get_localmusic_key()
    if not key:
        raise RuntimeError("Connect LocalMusic AI in the Haven dashboard first.")
    duration_seconds = max(10, min(int(duration_seconds), 600))
    payload = {
        "model": LOCALMUSIC_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["audio"], "stream": False, "task_type": "text2music",
        "thinking": True, "temperature": 0.85, "top_p": 0.9,
        "use_cot_caption": True, "use_cot_language": True, "use_cot_metas": True,
        "guidance_scale": 7.0,
        "audio_config": {"format": "wav", "instrumental": True, "duration": duration_seconds},
    }
    try:
        response = requests.post(
            f"{LOCALMUSIC_API_URL}/v1/chat/completions", json=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=600,
        )
        response.raise_for_status()
        audio = _audio_bytes(response.json())
    except requests.RequestException as error:
        details = getattr(error.response, "text", "") if getattr(error, "response", None) else str(error)
        raise RuntimeError(f"LocalMusic AI request failed: {details}") from error
    music_dir = Path(__file__).with_name("music")
    music_dir.mkdir(exist_ok=True)
    output = music_dir / f"localmusic_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.wav"
    output.write_bytes(audio)
    return str(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a LocalMusic AI track")
    parser.add_argument("prompt")
    parser.add_argument("--seconds", type=int, default=180)
    args = parser.parse_args()
    print(generate_music(args.prompt, args.seconds))
