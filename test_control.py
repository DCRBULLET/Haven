import haven_control
import haven_pipeline
from haven_audio_qa import AudioQAMetadata, AudioQAResult


def test_brief_lifecycle_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(haven_control, "STORE", tmp_path / "records")
    record = haven_control.create_brief({"title": "Focus Test", "activity": "Coding"})
    assert record["status"] == "awaiting_review"
    assert haven_control.load_record(record["id"])["brief"]["title"] == "Focus Test"

    haven_control.transition(record["id"], "approved", "brief_approved")
    updated = haven_control.add_metrics(record["id"], {"views": 123, "click_through_rate": 4.2, "ignored": "no"})
    assert updated["status"] == "approved"
    assert updated["metrics"][-1]["views"] == 123
    assert "ignored" not in updated["metrics"][-1]


def test_invalid_lifecycle_transition_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(haven_control, "STORE", tmp_path / "records")
    record = haven_control.create_brief({})
    try:
        haven_control.transition(record["id"], "published")
    except ValueError as error:
        assert "Cannot move" in str(error)
    else:
        raise AssertionError("A brief must not be publishable without review and QA.")


def test_record_nonmedia_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(haven_control, "STORE", tmp_path / "records")
    asset = tmp_path / "thumbnail.jpg"
    asset.write_bytes(b"thumbnail")
    record = haven_control.create_brief({})
    updated = haven_control.record_asset(record["id"], "thumbnail", str(asset))
    assert updated["assets"]["thumbnail"]["bytes"] == len(b"thumbnail")



def test_record_audio_qa(tmp_path, monkeypatch):
    monkeypatch.setattr(haven_control, "STORE", tmp_path / "records")
    record = haven_control.create_brief({})
    qa = AudioQAResult(
        passed=True,
        checks={"lufs_within_range": True},
        measured_values={"integrated_lufs": -16.0},
        policy_id="haven-audio-prod-v1",
        policy_version="1",
        policy_hash="abc123",
        metadata=AudioQAMetadata(
            duration_seconds=180.0,
            integrated_lufs=-16.0,
            silence_percent=0.0,
            true_peak_dbtp=-1.2,
            clipping_percent=0.0,
            expected_duration_seconds=180.0,
        ),
    )

    updated = haven_control.record_audio_qa(record["id"], qa.to_dict())

    assert updated["audio_qa"]["passed"] is True
    assert updated["audio_qa"]["metadata"]["integrated_lufs"] == -16.0


def test_prepare_record_for_render_requires_approved_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(haven_control, "STORE", tmp_path / "records")
    record = haven_control.create_brief({})
    monkeypatch.setattr(haven_pipeline, "record_asset", lambda *args, **kwargs: None)

    try:
        haven_pipeline.prepare_record_for_render(record["id"], "music/example.wav")
    except RuntimeError as error:
        assert "must be approved" in str(error)
    else:
        raise AssertionError("Pipeline should not render an unapproved brief.")


def test_prepare_record_for_render_advances_to_rendering(tmp_path, monkeypatch):
    monkeypatch.setattr(haven_control, "STORE", tmp_path / "records")
    record = haven_control.create_brief({})
    haven_control.transition(record["id"], "approved", "brief_approved")

    calls = []

    def fake_record_asset(*args, **kwargs):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr(haven_pipeline, "record_asset", fake_record_asset)
    haven_pipeline.prepare_record_for_render(record["id"], "music/example.wav")

    updated = haven_control.load_record(record["id"])
    assert updated["status"] == "rendering"
    assert calls



def test_pipeline_stops_when_audio_qa_fails(monkeypatch):
    monkeypatch.setattr("sys.argv", ["haven_pipeline.py"])
    monkeypatch.setattr(haven_pipeline, "check_ffmpeg", lambda: True)
    monkeypatch.setattr(
        haven_pipeline,
        "load_config",
        lambda: {"music_duration_seconds": 180, "target_duration_hours": 1, "audio_file": "music/example.wav"},
    )
    monkeypatch.setattr(haven_pipeline, "save_config", lambda config: None)
    monkeypatch.setattr(haven_pipeline, "ensure_project_dirs", lambda: None)
    monkeypatch.setattr(haven_pipeline, "find_audio_file", lambda config: "music/example.wav")
    monkeypatch.setattr(haven_pipeline.os.path, "exists", lambda path: True)

    class FailedQA:
        passed = False
        checks = {"lufs_within_range": False}

        @staticmethod
        def to_dict():
            return {"passed": False, "checks": {"lufs_within_range": False}}

    markers = {"visual_started": False}
    failed_calls = []

    monkeypatch.setattr(haven_pipeline, "validate_audio_file", lambda path, expected: FailedQA())
    monkeypatch.setattr(haven_pipeline, "generate_visual_loop", lambda config, path: markers.__setitem__("visual_started", True))
    monkeypatch.setattr(haven_pipeline, "mark_failed", lambda content_id, event, reason: failed_calls.append((content_id, event, reason)))

    result = haven_pipeline.main()

    assert result == 1
    assert markers["visual_started"] is False
    assert failed_calls == [(None, "audio_qa_failed", "lufs_within_range")]
