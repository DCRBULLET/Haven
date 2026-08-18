#!/usr/bin/env python3
"""Create a LocalMusic AI prompt plus Haven's video metadata."""
import argparse
import random
from datetime import datetime
from config import ACTIVITIES, GENRES, MOODS, format_duration, get_palette_by_mood, save_config
from haven_control import create_brief

def generate_daily_prompts(mood_override=None, activity_override=None, duration_hours=3):
    mood = mood_override or random.choice(MOODS)
    genre = random.choice(GENRES)
    activity = activity_override or random.choice(ACTIVITIES)
    palette = get_palette_by_mood(mood)
    music_prompt = (
        f"Instrumental {mood.lower()} {genre.lower()} ambient music for {activity.lower()}. "
        "Slow evolving textures, seamless gentle ending, no vocals, no spoken words."
    )
    duration = format_duration(duration_hours)
    title = f"{duration} of {mood} {genre} for {activity}"
    return {
        "date": datetime.now().strftime("%Y-%m-%d"), "mood": mood, "genre": genre,
        "activity": activity, "canvas_color": palette["canvas"], "line_color": palette["lines"],
        "music_prompt": music_prompt, "title": title,
        "description": f"🎧 {title}\n\nAmbient music for {activity.lower()}, deep work, and relaxation.\n\nThis music was created with LocalMusic AI.\n\n#ambientmusic #focusmusic #{activity.lower()}music",
        "tags": ["ambient music", "focus music", "study music", "deep work music", f"{genre.lower()} ambient"],
        "target_duration_hours": duration_hours, "seed": random.randint(0, 999999),
        "visual_duration": 10, "fps": 24, "width": 1920, "height": 1080,
        "audio_file": "", "music_duration_seconds": 180,
    }

def main():
    parser = argparse.ArgumentParser(description="Create a Haven production plan")
    parser.add_argument("--mood")
    parser.add_argument("--activity")
    parser.add_argument("--duration", type=int, default=3)
    args = parser.parse_args()
    plan = generate_daily_prompts(args.mood, args.activity, args.duration)
    record = create_brief(plan)
    plan["content_id"] = record["id"]
    save_config(plan)
    print(f"Created plan: {plan['title']}\n\nLocalMusic AI prompt:\n{plan['music_prompt']}")

if __name__ == "__main__":
    main()
