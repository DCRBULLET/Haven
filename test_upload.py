from haven_upload import build_video_body


def test_upload_body_is_private_and_disclosed_by_default():
    body = build_video_body({"title": "Test", "description": "Ambient music"})
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["containsSyntheticMedia"] is True
    assert "AI assistance" in body["snippet"]["description"]


def test_upload_body_requires_explicit_public_choice():
    assert build_video_body({}, "public")["status"]["privacyStatus"] == "public"
