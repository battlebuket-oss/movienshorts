# YouTube channel connection and publishing

Movie Shorts uses Google's server-side OAuth 2.0 flow. A user signs in on Google's consent screen; Movie Shorts never asks for or stores the user's Google password. The refresh token is encrypted in the Movie Shorts database and is scoped to that Movie Shorts user.

## 1. Configure Google Cloud

1. Open a Google Cloud project that you control.
2. Enable **YouTube Data API v3** for the project.
3. Configure the OAuth consent screen and add the accounts that are allowed to test the app while it is in testing mode.
4. In the OAuth Data Access settings, add the two scopes requested by Movie Shorts: `https://www.googleapis.com/auth/youtube.upload` and `https://www.googleapis.com/auth/youtube.readonly`.
5. Create an OAuth 2.0 Client ID with application type **Web application**.
6. Add the exact callback URL to **Authorized redirect URIs**:
   - Local development: http://localhost:3107/api/youtube/callback
   - Production: https://YOUR_APP_DOMAIN/api/youtube/callback
7. Copy the OAuth client ID and client secret. Keep the secret private.

**Testing mode note:** When the OAuth consent screen is External and its publishing status is Testing, add the Google account you will connect as a test user. Google states that test-user authorizations expire after seven days when non-basic scopes such as YouTube access are requested; the refresh token expires too. For ongoing use beyond testing, complete the OAuth app publishing and verification steps required for the requested scopes. See [Google's test-user guidance](https://support.google.com/cloud/answer/15549945) and [production readiness guidance](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).

Google's current authorization and API setup guides:
- [YouTube Data API authorization](https://developers.google.com/youtube/data/guides/authentication)
- [OAuth 2.0 for web server applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [YouTube video uploads](https://developers.google.com/youtube/data/guides/uploading_a_video)

## 2. Configure Movie Shorts

For local Docker development, add the following to the untracked .env file:

    YOUTUBE_CLIENT_ID=your-web-client-id
    YOUTUBE_CLIENT_SECRET=your-web-client-secret
    YOUTUBE_OAUTH_REDIRECT_URI=http://localhost:3107/api/youtube/callback
    APP_SETTINGS_ENCRYPTION_KEY=use-a-long-random-secret

For production, set the same variables in the private .env.production file or your hosting provider's secret manager. Set YOUTUBE_OAUTH_REDIRECT_URI to the exact HTTPS callback registered in Google Cloud. Do not use a NEXT_PUBLIC_ prefix for the client secret. Never commit either secret to Git.

The app uses the existing APP_SETTINGS_ENCRYPTION_KEY to encrypt refresh tokens at rest. Keep this key backed up securely: changing it without re-encrypting stored tokens will make existing channel connections unreadable, and users will need to reconnect.

Restart the backend after changing environment values:

    docker compose up -d --build backend

For production, use the production Compose file and its environment file as described in [production deployment](production-deployment.md).

## 3. Connect and upload

1. Sign in to Movie Shorts.
2. Open a completed task and find the **YouTube channel** panel.
3. Select **Connect YouTube** and choose the Google account that owns the intended YouTube channel.
4. Review the requested channel permissions and approve them.
5. Movie Shorts displays the connected channel name.
6. On a generated clip, select **Upload to YouTube**, edit the title/description, choose visibility, and explicitly confirm the upload.

Visibility defaults to **Private**. Unlisted or Public uploads require selecting that setting deliberately. Movie Shorts does not publish clips automatically. You can disconnect the channel from the channel panel; Movie Shorts deletes its local token and requests revocation from Google.

## Permissions and limits

The integration requests only:
- youtube.upload to upload videos to the authorized channel.
- youtube.readonly to identify and display the channel associated with the Google account.

The current uploader accepts a generated MP4 clip up to 500 MB. It sends the selected clip through YouTube's resumable upload endpoint. A successful response includes a link to the uploaded video.

Google OAuth publishing status affects who can authorize the app and how long refresh tokens last. An External app left in Testing is limited to listed test users, and refresh tokens for YouTube scopes expire after seven days. For broader use, publish the OAuth consent screen and complete any verification Google requires for the requested scopes. YouTube API quota, channel standing, file-size limits, and video processing checks still apply. Current YouTube `videos.insert` documentation states that uploads from unverified API projects are not restricted to Private visibility; an October 2026 YouTube API issue-tracker clarification confirms that the earlier private-only restriction was lifted.

**Content rights:** Upload only content you own or are authorized by the rights holder to publish. Connecting a channel does not grant rights to third-party footage, music, or livestreams.


Current policy references:
- [YouTube videos.insert API](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert)
- [Google OAuth refresh-token expiration](https://developers.google.com/identity/protocols/oauth2)
- [Google OAuth app publishing states](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)
- [YouTube API clarification on the former private-only upload restriction](https://issuetracker.google.com/issues/572863050)
