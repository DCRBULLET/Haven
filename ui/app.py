import os
import subprocess
import sys

import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
from config import get_localmusic_key, load_config, save_config, save_localmusic_key
from haven_control import add_metrics, create_brief, load_record, record_asset, transition
from haven_music_gen import generate_music
from haven_prompt import generate_daily_prompts

st.set_page_config(page_title="Haven", page_icon="🌌", layout="wide")
st.title("🌌 Haven")
st.caption("Create ambient music with LocalMusic AI, then build a finished YouTube video.")

with st.sidebar:
    st.subheader("LocalMusic AI")
    if get_localmusic_key():
        st.success("Connected")
    else:
        st.warning("Not connected")
    with st.expander("Connect or replace key"):
        key = st.text_input("LocalMusic AI API key", type="password")
        if st.button("Save key"):
            if key.strip():
                save_localmusic_key(key)
                st.success("Connected. Your key stays in a private file on this Mac.")
                st.rerun()
            else:
                st.error("Paste your API key first.")

config = load_config()
if config and "music_prompt" not in config:
    config = generate_daily_prompts(
        mood_override=config.get("mood"),
        activity_override=config.get("activity"),
        duration_hours=config.get("target_duration_hours", 3),
    )
    save_config(config)
if config and not config.get("content_id"):
    record = create_brief(config)
    config["content_id"] = record["id"]
    save_config(config)
if not config:
    st.info("Start by creating today’s music and video plan.")
    if st.button("Create today’s plan", type="primary"):
        config = generate_daily_prompts()
        record = create_brief(config)
        config["content_id"] = record["id"]
        save_config(config)
        st.rerun()
    st.stop()

record = load_record(config["content_id"])
status = record["status"]
st.caption(f"Production status: **{status.replace('_', ' ')}** · ID {record['id'][:8]}")

if status == "awaiting_review":
    if st.button("Approve this production brief", type="primary"):
        transition(record["id"], "approved", "brief_approved")
        st.rerun()
elif status == "ready_for_review":
    if st.button("Approve publication package", type="primary"):
        transition(record["id"], "approved_for_upload", "publication_package_approved")
        st.rerun()

left, right = st.columns(2)
with left:
    st.subheader("Today’s sound")
    st.write(f"**{config['mood']} · {config['genre']} · {config['activity']}**")
    st.text_area("LocalMusic AI prompt", config["music_prompt"], height=130, disabled=True)
    if st.button("Generate music", type="primary", disabled=not bool(get_localmusic_key()) or status not in {"approved", "music_ready"}):
        with st.spinner("LocalMusic AI is composing your track…"):
            try:
                track = generate_music(config["music_prompt"], config.get("music_duration_seconds", 180))
                config["audio_file"] = track
                save_config(config)
                record_asset(record["id"], "audio", track)
                transition(record["id"], "music_ready", "music_generated")
                st.success("Track generated.")
                st.audio(track)
            except RuntimeError as error:
                st.error(str(error))

with right:
    st.subheader("Your video")
    st.write(config["title"])
    st.caption(f"{config['target_duration_hours']} hours · {config['canvas_color']} canvas · {config['line_color']} lines")
    if config.get("audio_file") and os.path.exists(config["audio_file"]):
        st.success("Music is ready")
        st.audio(config["audio_file"])
    else:
        st.info("Generate music to continue.")
    if st.button("Build video", disabled=not bool(config.get("audio_file")) or status not in {"music_ready", "failed"}):
        with st.spinner("Building video — this can take several minutes…"):
            result = subprocess.run(["python3", "haven_pipeline.py"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            if result.returncode == 0:
                st.success("Video built and passed render QA. Approve its publication package before uploading privately.")
            else:
                st.error(result.stdout or result.stderr)

st.divider()
st.subheader("Performance observation")
with st.form("metrics"):
    metric_left, metric_right = st.columns(2)
    with metric_left:
        views = st.number_input("Views", min_value=0, step=1)
        ctr = st.number_input("Click-through rate (%)", min_value=0.0, max_value=100.0, step=0.1)
    with metric_right:
        average_duration = st.number_input("Average view duration (seconds)", min_value=0.0, step=1.0)
        subscribers = st.number_input("Subscribers gained", min_value=0, step=1)
    notes = st.text_input("What did viewers respond to?")
    if st.form_submit_button("Save observation"):
        add_metrics(record["id"], {
            "views": views, "click_through_rate": ctr,
            "average_view_duration_seconds": average_duration,
            "subscribers_gained": subscribers, "notes": notes,
        })
        st.success("Performance observation saved to this content record.")

if st.button("Create a new plan"):
    next_config = generate_daily_prompts()
    next_record = create_brief(next_config)
    next_config["content_id"] = next_record["id"]
    save_config(next_config)
    st.rerun()
