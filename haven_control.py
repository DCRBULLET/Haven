"""Lightweight production control for Haven.

Haven intentionally keeps its system of record local and human-readable. Each
content brief has a durable record containing its assets, QA result, publishing
status, provenance, and manually entered performance observations.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from logger import get_logger

logger = get_logger("control")

ROOT = Path(__file__).resolve().parent
STORE = ROOT / ".haven" / "records"
VALID_STATUSES = {
    "draft",
    "awaiting_review",
    "approved",
    "music_ready",
    "rendering",
    "ready_for_review",
    "approved_for_upload",
    "uploaded_private",
    "published",
    "failed",
}
ALLOWED_TRANSITIONS = {
    "draft": {"awaiting_review", "failed"},
    "awaiting_review": {"approved", "failed"},
    "approved": {"music_ready", "rendering", "failed"},
    "music_ready": {"music_ready", "rendering", "failed"},
    "rendering": {"ready_for_review", "failed"},
    "ready_for_review": {"approved_for_upload", "rendering", "failed"},
    "approved_for_upload": {"uploaded_private", "published", "failed"},
    "uploaded_private": {"published", "uploaded_private"},
    "published": {"published"},
    "failed": {"approved", "music_ready", "rendering", "failed"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()



def ensure_project_dirs() -> None:
    for directory in (ROOT / "music", ROOT / "visuals", ROOT / "output", ROOT / "thumbs", STORE):
        directory.mkdir(parents=True, exist_ok=True)



def _path(content_id: str) -> Path:
    return STORE / f"{content_id}.json"



def _write(record: Dict[str, Any]) -> Dict[str, Any]:
    ensure_project_dirs()
    record["updated_at"] = _now()
    destination = _path(record["id"])
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return record



def create_brief(config: Dict[str, Any]) -> Dict[str, Any]:
    """Create a reviewable brief from Haven's plan configuration."""
    ensure_project_dirs()
    content_id = str(uuid4())
    record = {
        "id": content_id,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "awaiting_review",
        "brief": {
            "title": config.get("title", "Ambient Music"),
            "audience": config.get("activity", "Focus"),
            "mood": config.get("mood", "Ambient"),
            "genre": config.get("genre", "Ambient"),
            "music_prompt": config.get("music_prompt", ""),
            "target_duration_hours": config.get("target_duration_hours", 3),
            "visual_direction": {
                "canvas_color": config.get("canvas_color"),
                "line_color": config.get("line_color"),
            },
            "metadata": {
                "description": config.get("description", ""),
                "tags": config.get("tags", []),
            },
        },
        "assets": {},
        "qa": {},
        "audio_qa": {},
        "publication": {"privacy_status": "private", "ai_disclosure": True},
        "metrics": [],
        "events": [{"at": _now(), "event": "brief_created"}],
    }
    logger.info("Created brief %s", content_id)
    return _write(record)



def load_record(content_id: str) -> Dict[str, Any]:
    path = _path(content_id)
    if not path.exists():
        logger.warning("Attempted to load missing record %s", content_id)
        raise FileNotFoundError(f"No Haven content record exists for {content_id}")
    return json.loads(path.read_text(encoding="utf-8"))



def transition(content_id: str, status: str, event: Optional[str] = None, **details: Any) -> Dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown Haven status: {status}")
    record = load_record(content_id)
    current_status = record["status"]
    if status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError(f"Cannot move Haven content from '{current_status}' to '{status}'.")
    record["status"] = status
    entry = {"at": _now(), "event": event or f"status_{status}"}
    entry.update({key: value for key, value in details.items() if value is not None})
    record.setdefault("events", []).append(entry)
    logger.info("Transitioned %s from %s to %s", content_id, current_status, status)
    return _write(record)



def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def media_probe(path: str) -> Dict[str, Any]:
    """Return portable, non-destructive media facts using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe could not read the media")
    data = json.loads(result.stdout)
    stream_types = [stream.get("codec_type") for stream in data.get("streams", [])]
    return {
        "path": str(Path(path).resolve()),
        "bytes": Path(path).stat().st_size,
        "sha256": sha256_file(path),
        "duration_seconds": float(data["format"]["duration"]),
        "stream_types": stream_types,
        "codecs": [stream.get("codec_name") for stream in data.get("streams", [])],
    }



def record_asset(content_id: str, kind: str, path: str) -> Dict[str, Any]:
    record = load_record(content_id)
    asset = (
        media_probe(path)
        if kind in {"audio", "video"}
        else {
            "path": str(Path(path).resolve()),
            "bytes": Path(path).stat().st_size,
            "sha256": sha256_file(path),
        }
    )
    record.setdefault("assets", {})[kind] = asset
    record.setdefault("events", []).append({"at": _now(), "event": "asset_recorded", "kind": kind})
    logger.info("Recorded %s asset for %s: %s", kind, content_id, path)
    return _write(record)



def record_audio_qa(content_id: str, qa_result: Dict[str, Any]) -> Dict[str, Any]:
    record = load_record(content_id)
    record["audio_qa"] = qa_result
    record.setdefault("events", []).append(
        {"at": _now(), "event": "audio_qa_completed", "passed": qa_result.get("passed")}
    )
    logger.info("Recorded audio QA for %s. Passed=%s", content_id, qa_result.get("passed"))
    return _write(record)



def complete_render_qa(
    content_id: str,
    audio_path: str,
    video_path: str,
    thumbnail_path: str,
    expected_seconds: float,
) -> Dict[str, Any]:
    record = record_asset(content_id, "audio", audio_path)
    record_asset(content_id, "video", video_path)
    record_asset(content_id, "thumbnail", thumbnail_path)
    record = load_record(content_id)
    video = record["assets"]["video"]
    checks = {
        "video_has_audio": "audio" in video["stream_types"],
        "video_has_video": "video" in video["stream_types"],
        "duration_within_30_seconds": abs(video["duration_seconds"] - expected_seconds) <= 30,
        "thumbnail_present": Path(thumbnail_path).exists(),
    }
    record["qa"] = {"checked_at": _now(), "checks": checks, "passed": all(checks.values())}
    next_status = "ready_for_review" if record["qa"]["passed"] else "failed"
    if next_status not in ALLOWED_TRANSITIONS[record["status"]]:
        raise ValueError(f"Render QA cannot complete from '{record['status']}'.")
    record["status"] = next_status
    record.setdefault("events", []).append(
        {"at": _now(), "event": "render_qa_completed", "passed": record["qa"]["passed"]}
    )
    logger.info("Render QA completed for %s. Passed=%s", content_id, record["qa"]["passed"])
    return _write(record)



def record_upload(content_id: str, video_id: str, url: str, privacy_status: str) -> Dict[str, Any]:
    record = load_record(content_id)
    if privacy_status not in {"private", "public", "unlisted"}:
        raise ValueError("YouTube privacy status must be private, public, or unlisted.")
    next_status = "published" if privacy_status == "public" else "uploaded_private"
    if next_status not in ALLOWED_TRANSITIONS[record["status"]]:
        raise ValueError(f"Upload is not allowed while content is '{record['status']}'.")
    record["publication"].update(
        {
            "video_id": video_id,
            "url": url,
            "privacy_status": privacy_status,
            "uploaded_at": _now(),
        }
    )
    record["status"] = next_status
    record.setdefault("events", []).append(
        {"at": _now(), "event": "youtube_uploaded", "privacy_status": privacy_status}
    )
    logger.info("Recorded YouTube upload for %s: %s (%s)", content_id, video_id, privacy_status)
    return _write(record)



def add_metrics(content_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    record = load_record(content_id)
    allowed = {
        "views",
        "watch_time_seconds",
        "average_view_duration_seconds",
        "click_through_rate",
        "likes",
        "comments",
        "subscribers_gained",
        "notes",
    }
    observation = {key: value for key, value in metrics.items() if key in allowed and value not in (None, "")}
    observation["observed_at"] = _now()
    record.setdefault("metrics", []).append(observation)
    record.setdefault("events", []).append({"at": _now(), "event": "metrics_recorded"})
    logger.info("Recorded metrics for %s", content_id)
    return _write(record)
