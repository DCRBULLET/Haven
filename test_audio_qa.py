from haven_audio_qa import AUDIO_QA_POLICY_HASH, AudioQAMetadata, validate_audio_file


def test_validate_audio_file_passes_within_policy(monkeypatch):
    monkeypatch.setattr("haven_audio_qa.Path.exists", lambda self: True)
    monkeypatch.setattr("haven_audio_qa._probe_duration", lambda path: 180.0)
    monkeypatch.setattr("haven_audio_qa._measure_loudness", lambda path: (-16.2, -1.4))
    monkeypatch.setattr("haven_audio_qa._measure_silence_percent", lambda path, duration: 1.5)
    monkeypatch.setattr("haven_audio_qa._measure_clipping_percent", lambda path: 0.0)

    result = validate_audio_file("music/example.wav", expected_duration_seconds=180)

    assert result.passed is True
    assert all(result.checks.values())
    assert result.policy_hash == AUDIO_QA_POLICY_HASH
    assert result.metadata == AudioQAMetadata(
        duration_seconds=180.0,
        integrated_lufs=-16.2,
        silence_percent=1.5,
        true_peak_dbtp=-1.4,
        clipping_percent=0.0,
        expected_duration_seconds=180.0,
    )


def test_validate_audio_file_fails_outside_policy(monkeypatch):
    monkeypatch.setattr("haven_audio_qa.Path.exists", lambda self: True)
    monkeypatch.setattr("haven_audio_qa._probe_duration", lambda path: 180.0)
    monkeypatch.setattr("haven_audio_qa._measure_loudness", lambda path: (-8.0, -0.1))
    monkeypatch.setattr("haven_audio_qa._measure_silence_percent", lambda path, duration: 7.0)
    monkeypatch.setattr("haven_audio_qa._measure_clipping_percent", lambda path: 0.2)

    result = validate_audio_file("music/example.wav", expected_duration_seconds=120)

    assert result.passed is False
    assert result.checks["lufs_within_range"] is False
    assert result.checks["silence_within_limit"] is False
    assert result.checks["true_peak_within_limit"] is False
    assert result.checks["clipping_within_limit"] is False
    assert result.checks["duration_within_tolerance"] is False
