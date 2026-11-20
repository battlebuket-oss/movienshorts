from fastapi import HTTPException
import pytest

from src.api.routes.youtube import (
    OAUTH_SCOPES,
    _validate_upload_metadata,
    build_oauth_url,
)


def test_oauth_url_requests_offline_access_and_csrf_state():
    url = build_oauth_url("client-id", "https://example.com/api/youtube/callback", "state-value")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "access_type=offline" in url
    assert "state=state-value" in url
    assert "youtube.upload" in url
    assert "youtube.readonly" in url


def test_youtube_scopes_are_limited_to_channel_read_and_upload():
    assert OAUTH_SCOPES == (
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    )


def test_upload_metadata_accepts_valid_private_video():
    _validate_upload_metadata("My first Short", "Description", "private")


@pytest.mark.parametrize(
    ("title", "description", "privacy"),
    [
        ("   ", "", "private"),
        ("x" * 101, "", "private"),
        ("A valid title", "x" * 5001, "private"),
        ("A valid title", "", "friends"),
    ],
)
def test_upload_metadata_rejects_invalid_values(title, description, privacy):
    with pytest.raises(HTTPException):
        _validate_upload_metadata(title, description, privacy)
