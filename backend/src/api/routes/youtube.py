"""YouTube channel connection and explicit video publishing routes."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import aiofiles
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth_headers import resolve_authenticated_user_id
from ...config import get_config
from ...database import get_db
from ...runtime_settings import decrypt_setting_value, encrypt_setting_value

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/youtube", tags=["youtube"])

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)
MAX_VIDEO_UPLOAD_BYTES = 500 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=20, max_length=256)


class YouTubeUploadRequest(BaseModel):
    clip_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    privacy_status: Literal["private", "unlisted", "public"] = "private"
    rights_confirmed: bool = False


def build_oauth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Create a server-side OAuth authorization URL with offline refresh access."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def _require_upload_rights_confirmation(confirmed: bool) -> None:
    if confirmed is not True:
        raise HTTPException(
            status_code=403,
            detail="Confirm that you own this video or have permission from the rights holder to publish it.",
        )


def _get_acknowledged_upload_offset(range_header: str | None, file_size: int) -> int:
    """Return the first byte YouTube still needs after a 308 response."""
    if not range_header:
        return 0
    match = re.fullmatch(r"bytes=0-(\d+)", range_header.strip(), flags=re.IGNORECASE)
    if not match:
        raise HTTPException(status_code=502, detail="YouTube returned an invalid upload acknowledgement.")
    acknowledged_end = int(match.group(1))
    if acknowledged_end >= file_size:
        raise HTTPException(status_code=502, detail="YouTube returned an out-of-range upload acknowledgement.")
    return acknowledged_end + 1


async def _upload_resumable_media(
    client: httpx.AsyncClient,
    upload_url: str,
    video_path: Path,
    access_token: str,
    file_size: int,
) -> httpx.Response:
    """Transfer an MP4 in 8 MiB chunks and resume from YouTube's acknowledged byte."""
    chunk_size = 8 * 1024 * 1024  # Multiple of Google's required 256 KiB granularity.
    max_retries = 5
    offset = 0
    retries = 0

    async with aiofiles.open(video_path, "rb") as video_file:
        while offset < file_size:
            await video_file.seek(offset)
            chunk = await video_file.read(min(chunk_size, file_size - offset))
            if not chunk:
                raise HTTPException(status_code=500, detail="The generated video file ended unexpectedly.")

            end = offset + len(chunk) - 1
            try:
                response = await client.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {offset}-{end}/{file_size}",
                    },
                    content=chunk,
                )
            except httpx.HTTPError:
                response = None

            if response is not None and response.status_code in {200, 201}:
                return response

            if response is not None and response.status_code == 308:
                next_offset = _get_acknowledged_upload_offset(
                    response.headers.get("range"), file_size
                )
                if next_offset > offset:
                    offset = next_offset
                    retries = 0
                    continue
                retries += 1
            elif response is not None and response.status_code not in {500, 502, 503, 504}:
                logger.warning("YouTube chunk upload returned HTTP %s", response.status_code)
                raise HTTPException(status_code=502, detail="YouTube rejected a video upload chunk.")
            else:
                retries += 1

            if retries > max_retries:
                raise HTTPException(status_code=502, detail="The YouTube upload could not be resumed after repeated network errors.")

            await asyncio.sleep(min(2 ** (retries - 1), 8))

            # Probe after uncertain transfers; YouTube's Range header is authoritative.
            try:
                probe = await client.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Length": "0",
                        "Content-Range": f"bytes */{file_size}",
                    },
                    content=b"",
                )
            except httpx.HTTPError:
                continue

            if probe.status_code in {200, 201}:
                return probe
            if probe.status_code == 308:
                server_offset = _get_acknowledged_upload_offset(
                    probe.headers.get("range"), file_size
                )
                if server_offset > offset:
                    offset = server_offset
                    retries = 0
                continue
            if probe.status_code in {500, 502, 503, 504}:
                continue

            logger.warning("YouTube upload status probe returned HTTP %s", probe.status_code)
            raise HTTPException(status_code=502, detail="YouTube could not confirm the upload's resumable status.")

    raise HTTPException(status_code=502, detail="YouTube did not finalize the resumable video upload.")


def _validate_upload_metadata(title: str, description: str, privacy_status: str) -> None:
    if not title.strip():
        raise HTTPException(status_code=422, detail="A video title is required.")
    normalized_title = title.strip()
    if len(normalized_title) > 100:
        raise HTTPException(status_code=422, detail="YouTube titles must be 100 characters or fewer.")
    if len(description) > 5000:
        raise HTTPException(status_code=422, detail="YouTube descriptions must be 5,000 characters or fewer.")
    if privacy_status not in {"private", "unlisted", "public"}:
        raise HTTPException(status_code=422, detail="Choose private, unlisted, or public visibility.")


async def _get_user_id(request: Request, db: AsyncSession) -> str:
    return await resolve_authenticated_user_id(request, db, get_config())


def _oauth_config():
    config = get_config()
    if not config.youtube_oauth_client_id or not config.youtube_oauth_client_secret:
        raise HTTPException(
            status_code=503,
            detail="YouTube publishing is not configured yet. Add the Google OAuth client ID and secret to the server environment.",
        )
    if not config.youtube_oauth_redirect_uri:
        raise HTTPException(status_code=503, detail="The YouTube OAuth redirect URI is not configured.")
    return config


@router.get("/connect")
async def connect_youtube(request: Request, db: AsyncSession = Depends(get_db)):
    """Begin a one-time, user-bound OAuth flow."""
    user_id = await _get_user_id(request, db)
    config = _oauth_config()
    state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    await db.execute(
        text("DELETE FROM youtube_oauth_states WHERE expires_at <= NOW()")
    )

    await db.execute(
        text(
            """
            INSERT INTO youtube_oauth_states (state_hash, user_id, expires_at)
            VALUES (:state_hash, :user_id, :expires_at)
            """
        ),
        {"state_hash": state_hash, "user_id": user_id, "expires_at": expires_at},
    )
    await db.commit()

    return {
        "authorization_url": build_oauth_url(
            config.youtube_oauth_client_id,
            config.youtube_oauth_redirect_uri,
            state,
        )
    }


@router.post("/callback")
async def complete_youtube_oauth(
    payload: OAuthCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange the authorization code and store only an encrypted refresh token."""
    user_id = await _get_user_id(request, db)
    config = _oauth_config()
    state_hash = hashlib.sha256(payload.state.encode("utf-8")).hexdigest()

    state_result = await db.execute(
        text(
            """
            DELETE FROM youtube_oauth_states
            WHERE state_hash = :state_hash
              AND user_id = :user_id
              AND expires_at > NOW()
            RETURNING state_hash
            """
        ),
        {"state_hash": state_hash, "user_id": user_id},
    )
    if state_result.scalar_one_or_none() is None:
        await db.rollback()
        raise HTTPException(status_code=400, detail="YouTube authorization expired or could not be verified. Please connect again.")
    await db.commit()

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        try:
            token_response = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "code": payload.code,
                    "client_id": config.youtube_oauth_client_id,
                    "client_secret": config.youtube_oauth_client_secret,
                    "redirect_uri": config.youtube_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("Google OAuth token exchange failed for user %s", user_id)
            raise HTTPException(status_code=400, detail="Google could not complete YouTube authorization. Please try connecting again.")

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Google did not return an access token.")

        try:
            channel_response = await client.get(
                f"{YOUTUBE_API_BASE}/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            channel_response.raise_for_status()
            channel_data = channel_response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("Unable to retrieve the authorized YouTube channel for user %s", user_id)
            raise HTTPException(status_code=400, detail="Google authorization succeeded, but Movie Shorts could not read your YouTube channel.")

    channels = channel_data.get("items") or []
    if not channels or not channels[0].get("id"):
        raise HTTPException(status_code=400, detail="No YouTube channel was found for this Google account.")
    channel_id = str(channels[0]["id"])
    channel_title = str((channels[0].get("snippet") or {}).get("title") or "YouTube channel")[:255]

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        previous = await db.execute(
            text(
                """
                SELECT channel_id, refresh_token_encrypted
                FROM youtube_connections
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        previous_connection = previous.mappings().first()
        if not previous_connection or previous_connection["channel_id"] != channel_id:
            raise HTTPException(
                status_code=400,
                detail="Google did not return a new refresh token for this channel. Remove Movie Shorts from your Google Account's connected apps, then connect again.",
            )
        encrypted_refresh_token = previous_connection["refresh_token_encrypted"]
    else:
        encrypted_refresh_token = encrypt_setting_value(refresh_token)

    await db.execute(
        text(
            """
            INSERT INTO youtube_connections
                (user_id, channel_id, channel_title, refresh_token_encrypted, connected_at)
            VALUES
                (:user_id, :channel_id, :channel_title, :refresh_token_encrypted, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                channel_title = EXCLUDED.channel_title,
                refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                connected_at = NOW()
            """
        ),
        {
            "user_id": user_id,
            "channel_id": channel_id,
            "channel_title": channel_title,
            "refresh_token_encrypted": encrypted_refresh_token,
        },
    )
    await db.commit()
    return {"connected": True, "channel_id": channel_id, "channel_title": channel_title}


@router.get("/status")
async def youtube_connection_status(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _get_user_id(request, db)
    result = await db.execute(
        text(
            """
            SELECT channel_id, channel_title, connected_at
            FROM youtube_connections
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    )
    connection = result.mappings().first()
    if not connection:
        return {"connected": False, "channel": None}
    return {
        "connected": True,
        "channel": {
            "id": connection["channel_id"],
            "title": connection["channel_title"],
            "connected_at": connection["connected_at"].isoformat() if connection["connected_at"] else None,
        },
    }


@router.delete("/disconnect")
async def disconnect_youtube(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _get_user_id(request, db)
    result = await db.execute(
        text("SELECT refresh_token_encrypted FROM youtube_connections WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    encrypted = result.scalar_one_or_none()
    await db.execute(text("DELETE FROM youtube_connections WHERE user_id = :user_id"), {"user_id": user_id})
    await db.commit()

    if encrypted:
        try:
            refresh_token = decrypt_setting_value(encrypted)
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(REVOKE_ENDPOINT, data={"token": refresh_token})
        except Exception:
            logger.info("Local YouTube disconnect completed; remote token revocation could not be confirmed for user %s", user_id)

    return {"connected": False}


async def _get_access_token(db: AsyncSession, user_id: str, config) -> str:
    result = await db.execute(
        text("SELECT refresh_token_encrypted FROM youtube_connections WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    encrypted = result.scalar_one_or_none()
    if not encrypted:
        raise HTTPException(status_code=409, detail="Connect a YouTube channel before uploading.")
    try:
        refresh_token = decrypt_setting_value(encrypted)
    except Exception:
        logger.exception("Unable to decrypt the YouTube refresh token for user %s", user_id)
        raise HTTPException(status_code=503, detail="The saved YouTube connection cannot be read. Reconnect your channel.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "client_id": config.youtube_oauth_client_id,
                    "client_secret": config.youtube_oauth_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            access_token = response.json().get("access_token")
        except (httpx.HTTPError, ValueError):
            logger.warning("Unable to refresh YouTube access token for user %s", user_id)
            raise HTTPException(status_code=401, detail="Your YouTube connection expired or was revoked. Reconnect your channel.")
    if not access_token:
        raise HTTPException(status_code=401, detail="Google did not provide a usable YouTube access token. Reconnect your channel.")
    return access_token


@router.post("/upload")
async def upload_clip_to_youtube(
    payload: YouTubeUploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Upload one of the authenticated user's generated MP4 clips to YouTube."""
    user_id = await _get_user_id(request, db)
    config = _oauth_config()
    _validate_upload_metadata(payload.title, payload.description, payload.privacy_status)
    _require_upload_rights_confirmation(payload.rights_confirmed)

    clip_result = await db.execute(
        text(
            """
            SELECT gc.file_path, gc.filename
            FROM generated_clips AS gc
            INNER JOIN tasks AS t ON t.id = gc.task_id
            WHERE gc.id = :clip_id AND t.user_id = :user_id
            """
        ),
        {"clip_id": payload.clip_id, "user_id": user_id},
    )
    clip = clip_result.mappings().first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found.")
    try:
        video_path = Path(clip["file_path"]).resolve(strict=True)
    except (OSError, TypeError):
        raise HTTPException(status_code=404, detail="The generated video file is no longer available.")

    allowed_roots = [Path(config.temp_dir).resolve(), Path(config.output_dir).resolve()]
    if not any(video_path == root or root in video_path.parents for root in allowed_roots):
        raise HTTPException(status_code=400, detail="This file is outside Movie Shorts' managed video storage.")
    if not video_path.is_file() or video_path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only generated MP4 clips can be uploaded.")
    file_size = video_path.stat().st_size
    if file_size <= 0 or file_size > MAX_VIDEO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The clip must be between 1 byte and 500 MB to upload.")

    access_token = await _get_access_token(db, user_id, config)
    metadata = {
        "snippet": {
            "title": payload.title.strip(),
            "description": payload.description,
            "categoryId": "22",
        },
        "status": {"privacyStatus": payload.privacy_status},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(file_size),
        "X-Upload-Content-Type": "video/mp4",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=1800.0, write=1800.0, pool=30.0), follow_redirects=False) as client:
        try:
            init_response = await client.post(
                UPLOAD_ENDPOINT,
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers=headers,
                json=metadata,
            )
        except httpx.HTTPError:
            logger.exception("Could not initialize YouTube upload for user %s", user_id)
            raise HTTPException(status_code=502, detail="Could not start the YouTube upload. Please try again.")
        if init_response.status_code not in {200, 201}:
            logger.warning("YouTube upload initialization returned HTTP %s for user %s", init_response.status_code, user_id)
            raise HTTPException(status_code=502, detail="YouTube rejected the upload request. Check your channel permissions and try again.")

        upload_url = init_response.headers.get("location")
        if not upload_url or not upload_url.startswith("https://www.googleapis.com/upload/youtube/v3/videos?"):
            raise HTTPException(status_code=502, detail="YouTube did not return a valid resumable upload URL.")

        try:
            upload_response = await _upload_resumable_media(
                client,
                upload_url,
                video_path,
                access_token,
                file_size,
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("YouTube media transfer failed for user %s", user_id)
            raise HTTPException(status_code=502, detail="The video transfer to YouTube failed. Please retry.")

    if upload_response.status_code not in {200, 201}:
        logger.warning("YouTube media upload returned HTTP %s for user %s", upload_response.status_code, user_id)
        raise HTTPException(status_code=502, detail="YouTube could not finish processing the upload. Please retry.")
    try:
        uploaded_video = upload_response.json()
        video_id = uploaded_video["id"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=502, detail="YouTube completed the transfer but did not return a video ID.")

    return {
        "uploaded": True,
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "privacy_status": payload.privacy_status,
    }
