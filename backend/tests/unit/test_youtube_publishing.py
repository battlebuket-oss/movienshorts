import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes.youtube import (
    OAUTH_SCOPES,
    _get_acknowledged_upload_offset,
    _require_upload_rights_confirmation,
    _upload_resumable_media,
    _validate_upload_metadata,
    YouTubeUploadRequest,
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


def test_upload_metadata_accepts_unicode_description_within_character_limit():
    _validate_upload_metadata("A Short", "🔥" * 5000, "private")


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


def test_upload_requires_explicit_rights_confirmation():
    with pytest.raises(HTTPException) as exc:
        _require_upload_rights_confirmation(False)
    assert exc.value.status_code == 403


def test_upload_accepts_explicit_rights_confirmation():
    _require_upload_rights_confirmation(True)



def test_acknowledged_upload_offset_from_range_header():
    assert _get_acknowledged_upload_offset("bytes=0-1048575", 2_000_000) == 1_048_576


def test_acknowledged_upload_offset_without_range_restarts_at_zero():
    assert _get_acknowledged_upload_offset(None, 2_000_000) == 0


@pytest.mark.parametrize(
    ("range_header", "file_size"),
    [
        ("0-100", 1000),
        ("bytes=20-100", 1000),
        ("bytes=0-2000", 1000),
    ],
)
def test_invalid_acknowledged_upload_range_is_rejected(range_header, file_size):
    with pytest.raises(HTTPException):
        _get_acknowledged_upload_offset(range_header, file_size)


@pytest.mark.asyncio
async def test_resumable_upload_continues_from_acknowledged_byte(tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"abcdefghi")
    received_ranges = []
    received_chunks = []

    async def handler(request: httpx.Request) -> httpx.Response:
        received_ranges.append(request.headers.get("content-range"))
        received_chunks.append(request.content)
        if len(received_ranges) == 1:
            return httpx.Response(308, headers={"Range": "bytes=0-2"})
        return httpx.Response(201, json={"id": "uploaded-video-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await _upload_resumable_media(
            client,
            "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test",
            video_path,
            "access-token",
            video_path.stat().st_size,
        )

    assert response.status_code == 201
    assert received_ranges == ["bytes 0-8/9", "bytes 3-8/9"]
    assert received_chunks == [b"abcdefghi", b"defghi"]



def test_upload_payload_requires_a_strict_boolean_rights_confirmation():
    valid = YouTubeUploadRequest(
        clip_id="clip-id",
        title="A Short",
        rights_confirmed=True,
    )
    assert valid.rights_confirmed is True

    with pytest.raises(ValidationError):
        YouTubeUploadRequest(
            clip_id="clip-id",
            title="A Short",
            rights_confirmed="true",
        )
