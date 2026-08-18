from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from logger import get_logger

logger = get_logger("audio_qa")

_LOUDNORM_JSON_RE = re.compile(r"\{\s*\"input_i\".*?\}", re.DOTALL)
_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")


class AudioQAError(RuntimeError):
    """Raised when Haven cannot measure or validate an audio artifact."""


@dataclass(frozen=True)
class AudioQAPolicy:
    policy_id: str
    version: str
    lufs_min: float
    lufs_max: float
    silence_max_percent: float
    true_peak_max_dbtp: float
    clipping_max_percent: float
    duration_tolerance_seconds: int


AUDIO_QA_POLICY = AudioQAPolicy(
    policy_id="haven-audio-prod-v1",
    version="1",
    lufs_min=-24.0,
    lufs_max=-10.0,
    silence_max_percent=5.0,
    true_peak_max_dbtp=-1.0,
    clipping_max_percent=0.0,
    duration_tolerance_seconds=15,
)


def _policy_hash() -> str:
    payload = json.dumps(asdict(AUDIO_QA_POLICY), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


AUDIO_QA_POLICY_HASH = _policy_hash()


@dataclass(frozen=True)
class AudioQAMetadata:
    duration_seconds: float
    integrated_lufs: float
    silence_percent: float
    true_peak_dbtp: float
    clipping_percent: float
    expected_duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AudioQAResult:
    passed: bool
    checks: dict[str, bool]
    measured_values: dict[str, float]
    policy_id: str
    policy_version: str
    policy_hash: str
    metadata: AudioQAMetadata

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["metadata"] = self.metadata.to_dict()
        return result


def validate_audio_file(path: str, expected_duration_seconds: float | None = None) -> AudioQAResult:
    """Measure source audio and validate it against Haven's production policy."""
    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {path}")

    duration_seconds = _probe_duration(path)
    integrated_lufs, true_peak_dbtp = _measure_loudness(path)
    silence_percent = _measure_silence_percent(path, duration_seconds)
    clipping_percent = _measure_clipping_percent(path)

    metadata = AudioQAMetadata(
        duration_seconds=duration_seconds,
        integrated_lufs=integrated_lufs,
        silence_percent=silence_percent,
        true_peak_dbtp=true_peak_dbtp,
        clipping_percent=clipping_percent,
        expected_duration_seconds=float(expected_duration_seconds) if expected_duration_seconds else None,
    )
    _validate_metadata(metadata)

    checks = {
        "lufs_within_range": AUDIO_QA_POLICY.lufs_min <= metadata.integrated_lufs <= AUDIO_QA_POLICY.lufs_max,
        "silence_within_limit": metadata.silence_percent <= AUDIO_QA_POLICY.silence_max_percent,
        "true_peak_within_limit": metadata.true_peak_dbtp <= AUDIO_QA_POLICY.true_peak_max_dbtp,
        "clipping_within_limit": metadata.clipping_percent <= AUDIO_QA_POLICY.clipping_max_percent,
        "duration_within_tolerance": _duration_within_tolerance(metadata),
    }
    measured_values = {
        "duration_seconds": metadata.duration_seconds,
        "integrated_lufs": metadata.integrated_lufs,
        "silence_percent": metadata.silence_percent,
        "true_peak_dbtp": metadata.true_peak_dbtp,
        "clipping_percent": metadata.clipping_percent,
    }
    result = AudioQAResult(
        passed=all(checks.values()),
        checks=checks,
        measured_values=measured_values,
        policy_id=AUDIO_QA_POLICY.policy_id,
        policy_version=AUDIO_QA_POLICY.version,
        policy_hash=AUDIO_QA_POLICY_HASH,
        metadata=metadata,
    )
    logger.info(
        "Audio QA %s for %s | LUFS %.2f | silence %.2f%% | true peak %.2f dBTP | clipping %.4f%%",
        "passed" if result.passed else "failed",
        path,
        metadata.integrated_lufs,
        metadata.silence_percent,
        metadata.true_peak_dbtp,
        metadata.clipping_percent,
    )
    return result


def _validate_metadata(metadata: AudioQAMetadata) -> None:
    values = {
        "duration_seconds": metadata.duration_seconds,
        "integrated_lufs": metadata.integrated_lufs,
        "silence_percent": metadata.silence_percent,
        "true_peak_dbtp": metadata.true_peak_dbtp,
        "clipping_percent": metadata.clipping_percent,
    }
    for name, value in values.items():
        if not math.isfinite(value):
            raise AudioQAError(f"Audio QA measurement is not finite: {name}={value}")
    if metadata.duration_seconds <= 0:
        raise AudioQAError("Audio QA duration must be greater than zero")
    if metadata.silence_percent < 0 or metadata.clipping_percent < 0:
        raise AudioQAError("Audio QA percentages must not be negative")


def _duration_within_tolerance(metadata: AudioQAMetadata) -> bool:
    if metadata.expected_duration_seconds is None:
        return True
    return abs(metadata.duration_seconds - metadata.expected_duration_seconds) <= AUDIO_QA_POLICY.duration_tolerance_seconds


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise AudioQAError(result.stderr.strip() or f"ffprobe failed while reading {path}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise AudioQAError(f"ffprobe returned an invalid duration for {path}") from exc


def _measure_loudness(path: str) -> tuple[float, float]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            path,
            "-af",
            "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise AudioQAError(result.stderr.strip() or f"ffmpeg loudnorm failed for {path}")

    matches = _LOUDNORM_JSON_RE.findall(result.stderr)
    if not matches:
        raise AudioQAError(f"Could not parse loudness metrics for {path}")

    payload = json.loads(matches[-1])
    try:
        integrated_lufs = float(payload["input_i"])
        true_peak_dbtp = float(payload["input_tp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AudioQAError(f"Loudness metrics were incomplete for {path}") from exc
    return integrated_lufs, true_peak_dbtp


def _measure_silence_percent(path: str, duration_seconds: float) -> float:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            path,
            "-af",
            "silencedetect=n=-45dB:d=0.5",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise AudioQAError(result.stderr.strip() or f"ffmpeg silencedetect failed for {path}")

    silence_total = 0.0
    open_start: float | None = None
    for line in result.stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            open_start = float(start_match.group(1))
        end_match = _SILENCE_END_RE.search(line)
        if end_match:
            silence_total += float(end_match.group(2))
            open_start = None
    if open_start is not None:
        silence_total += max(0.0, duration_seconds - open_start)
    if duration_seconds <= 0:
        return 0.0
    return min(100.0, max(0.0, (silence_total / duration_seconds) * 100.0))


def _measure_clipping_percent(path: str) -> float:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-f", "f32le", "-"],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise AudioQAError(stderr.strip() or f"ffmpeg decode failed for {path}")

    samples = np.frombuffer(result.stdout, dtype=np.float32)
    if samples.size == 0:
        raise AudioQAError(f"No PCM samples were decoded for {path}")

    clipped_samples = int(np.count_nonzero(np.abs(samples) >= 0.9999))
    return (clipped_samples / samples.size) * 100.0
