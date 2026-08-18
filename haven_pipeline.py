#!/usr/bin/env python3
"""
Haven Pipeline
Main orchestrator. Generates visual loop, processes audio, assembles final video.

Usage:
    python3 haven_pipeline.py
    python3 haven_pipeline.py --audio music/track_2026-08-16.mp3
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
from datetime import datetime
from typing import Any

import haven_music_gen
from config import load_config, save_config
from haven_audio_qa import validate_audio_file
from haven_control import complete_render_qa, ensure_project_dirs, load_record, record_asset, record_audio_qa, transition
from logger import get_logger

logger = get_logger("pipeline")
Config = dict[str, Any]


def check_ffmpeg() -> bool:
    """Check if ffmpeg is installed."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5, check=False)
        if result.returncode == 0:
            logger.info("FFmpeg found: %s", result.stdout.splitlines()[0])
            return True
    except FileNotFoundError:
        pass

    logger.error("FFmpeg not found. Install it with 'brew install ffmpeg'.")
    return False



def find_audio_file(config: Config) -> str | None:
    """Find the audio file for today."""
    date = config.get("date", datetime.now().strftime("%Y-%m-%d"))

    candidates = [
        f"music/track_{date}.mp3",
        f"music/track_{date}.wav",
        f"music/track_{date}.m4a",
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    audio_files: list[str] = []
    for ext in ["*.mp3", "*.wav", "*.m4a", "*.flac"]:
        audio_files.extend(glob.glob(f"music/{ext}"))

    if audio_files:
        audio_files.sort(key=os.path.getmtime, reverse=True)
        logger.warning("Using most recent audio file: %s", audio_files[0])
        return audio_files[0]

    return None



def get_media_duration(path: str) -> float:
    """Get media duration in seconds using ffprobe."""
    try:
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
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as error:
        logger.warning("Could not detect media duration for %s: %s", path, error)

    return 0.0



def loop_audio(audio_path: str, target_duration: int, output_path: str) -> bool:
    """Loop audio to target duration using ffmpeg."""
    logger.info("Looping audio to %ss", target_duration)

    audio_duration = get_media_duration(audio_path)
    if audio_duration <= 0:
        logger.warning("Could not read source duration, using 180s fallback for %s", audio_path)
        audio_duration = 180.0

    logger.info("Source audio duration: %.1fs", audio_duration)

    if audio_duration >= target_duration:
        cmd = ["ffmpeg", "-y", "-i", audio_path, "-t", str(target_duration), "-c", "copy", output_path]
    else:
        loops_needed = int(target_duration / audio_duration) + 1
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            str(loops_needed),
            "-i",
            audio_path,
            "-af",
            f"afade=t=in:st=0:d=2,afade=t=out:st={target_duration - 3}:d=3",
            "-t",
            str(target_duration),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("Audio processing failed: %s", result.stderr.strip() or "unknown ffmpeg error")
        return False

    logger.info("Audio looped: %s", output_path)
    return True



def generate_visual_loop(config: Config, output_path: str) -> bool:
    """Generate the visual loop using haven_visuals."""
    logger.info("Generating visual loop")

    from haven_visuals import HavenVisuals

    haven = HavenVisuals(
        width=config.get("width", 1920),
        height=config.get("height", 1080),
        fps=config.get("fps", 24),
        duration=config.get("visual_duration", 10),
        seed=config.get("seed", 42),
    )

    haven.render_video(
        output_path,
        canvas_color=config.get("canvas_color", "#08080c"),
        line_color=config.get("line_color", "#7dd3c4"),
    )

    return os.path.exists(output_path)



def assemble_video(visual_path: str, audio_path: str, output_path: str, target_duration: int) -> bool:
    """Combine visual loop and extended audio into the final video."""
    logger.info("Assembling final video")

    visual_duration = get_media_duration(visual_path) or 10
    loops_needed = int(target_duration / visual_duration) + 2

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        str(loops_needed),
        "-i",
        visual_path,
        "-i",
        audio_path,
        "-shortest",
        "-t",
        str(target_duration),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]

    logger.info("Rendering final video. This may take a few minutes.")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("Video assembly failed: %s", (result.stderr or "")[-500:])
        return False

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info("Final video created: %s (%.1f MB)", output_path, size_mb)
    return True



def generate_thumbnail(config: Config, output_path: str) -> bool:
    """Generate a thumbnail."""
    logger.info("Generating thumbnail")

    from haven_thumbnail import HavenThumbnail

    generator = HavenThumbnail()
    generator.generate(
        title=config.get("title", "Ambient Music"),
        duration_text=f"{config.get('target_duration_hours', 3)} HOURS",
        canvas_color=config.get("canvas_color", "#08080c"),
        line_color=config.get("line_color", "#7dd3c4"),
        seed=config.get("seed", 42),
        output_path=output_path,
    )

    return os.path.exists(output_path)



def mark_failed(content_id: str | None, event: str, reason: str) -> None:
    if not content_id:
        return
    try:
        transition(content_id, "failed", event, reason=reason)
    except Exception:
        logger.exception("Could not mark record %s as failed", content_id)



def ensure_record_can_render(content_id: str) -> str:
    record = load_record(content_id)
    status = record["status"]

    if status in {"awaiting_review", "draft"}:
        raise RuntimeError("The production brief must be approved before building the video.")
    if status in {"ready_for_review", "approved_for_upload", "uploaded_private", "published"}:
        raise RuntimeError(f"Cannot rebuild content that is already in '{status}'.")
    return status



def prepare_record_for_render(content_id: str, audio_path: str) -> None:
    status = ensure_record_can_render(content_id)

    if status in {"approved", "failed"}:
        transition(content_id, "music_ready", "music_asset_ready", audio_path=audio_path)
        status = "music_ready"

    if status == "music_ready":
        transition(content_id, "rendering", "video_render_started")
    elif status != "rendering":
        raise RuntimeError(f"Cannot start rendering while content is in '{status}'.")

    record_asset(content_id, "audio", audio_path)



def require_existing_artifact(path: str, label: str) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} does not exist: {path}")



def main() -> int:
    parser = argparse.ArgumentParser(description="Haven Pipeline")
    parser.add_argument("--audio", default=None, help="Path to audio file")
    parser.add_argument("--duration", type=int, default=None, help="Target duration in hours")
    parser.add_argument("--skip-visual", action="store_true", help="Skip visual generation")
    parser.add_argument("--skip-thumb", action="store_true", help="Skip thumbnail generation")
    args = parser.parse_args()

    logger.info("Starting Haven pipeline")
    ensure_project_dirs()

    if not check_ffmpeg():
        return 1

    try:
        config = load_config()
    except RuntimeError as error:
        logger.error("Could not load configuration: %s", error)
        return 1

    if args.duration:
        config["target_duration_hours"] = args.duration

    target_duration = int(config.get("target_duration_hours", 3) * 3600)
    date = config.get("date", datetime.now().strftime("%Y-%m-%d"))
    content_id = config.get("content_id")

    visual_path = f"visuals/loop_{date}.mp4"
    audio_looped_path = f"visuals/audio_{date}_looped.m4a"
    final_path = f"output/haven_{date}.mp4"
    thumb_path = f"thumbs/haven_{date}.jpg"

    try:
        audio_path = args.audio if args.audio else find_audio_file(config)
        if args.audio and not os.path.exists(args.audio):
            raise FileNotFoundError(f"Audio file does not exist: {args.audio}")

        if not audio_path:
            logger.info("No existing audio found. Generating a LocalMusic AI track.")
            audio_path = haven_music_gen.generate_music(
                config.get("music_prompt", "Instrumental ambient music, no vocals."),
                config.get("music_duration_seconds", 180),
            )

        require_existing_artifact(audio_path, "Audio file")
        config["audio_file"] = audio_path
        save_config(config)
        logger.info("Audio selected: %s", audio_path)

        if content_id:
            ensure_record_can_render(content_id)

        audio_qa = validate_audio_file(audio_path, config.get("music_duration_seconds"))
        logger.info("Audio QA checks: %s", audio_qa.checks)
        if content_id:
            record_audio_qa(content_id, audio_qa.to_dict())
        if not audio_qa.passed:
            failed_checks = ", ".join(name for name, passed in audio_qa.checks.items() if not passed)
            logger.error("Audio QA failed for %s: %s", audio_path, failed_checks or "unknown audio QA error")
            mark_failed(content_id, "audio_qa_failed", failed_checks or "Audio QA failed")
            return 1

        if content_id:
            prepare_record_for_render(content_id, audio_path)

        if args.skip_visual:
            logger.info("Skipping visual generation")
            require_existing_artifact(visual_path, "Visual loop")
        else:
            if not generate_visual_loop(config, visual_path):
                mark_failed(content_id, "visual_generation_failed", "Visual generation returned no output file.")
                return 1

        if not loop_audio(audio_path, target_duration, audio_looped_path):
            mark_failed(content_id, "audio_processing_failed", "ffmpeg failed while extending the audio track.")
            return 1

        if not assemble_video(visual_path, audio_looped_path, final_path, target_duration):
            mark_failed(content_id, "video_assembly_failed", "ffmpeg failed while assembling the final video.")
            return 1

        if args.skip_thumb:
            logger.info("Skipping thumbnail generation")
            require_existing_artifact(thumb_path, "Thumbnail")
        else:
            if not generate_thumbnail(config, thumb_path):
                mark_failed(content_id, "thumbnail_generation_failed", "Thumbnail generation returned no output file.")
                return 1

        logger.info("Haven pipeline complete")
        logger.info("Final video: %s", final_path)
        logger.info("Thumbnail: %s", thumb_path)

        if content_id:
            qa = complete_render_qa(content_id, audio_path, final_path, thumb_path, target_duration)
            logger.info("Render QA: %s", "passed" if qa["qa"]["passed"] else "failed")
            if not qa["qa"]["passed"]:
                return 1

        logger.info("Next step: review and upload privately with 'python3 haven_upload.py'")
        logger.info("Title: %s", config.get("title", "N/A"))
        return 0

    except Exception as error:
        logger.exception("Pipeline failed")
        mark_failed(content_id, "pipeline_failed", str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main() or 0)
