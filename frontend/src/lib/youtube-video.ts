const YOUTUBE_VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "m.youtube.com",
  "music.youtube.com",
  "youtu.be",
]);

/**
 * Extract a YouTube video ID from supported watch, short, live, and embed URLs.
 * Accepts only known YouTube hostnames so lookalike domains are rejected.
 */
export function extractYouTubeVideoId(value: string): string | null {
  const input = value.trim();
  if (!input) return null;

  try {
    const parsed = new URL(input);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    if (!YOUTUBE_HOSTS.has(host)) return null;

    const pathParts = parsed.pathname.split("/").filter(Boolean);
    const candidate =
      host === "youtu.be"
        ? pathParts[0]
        : parsed.pathname === "/watch"
          ? parsed.searchParams.get("v")
          : ["embed", "shorts", "live", "v"].includes(pathParts[0] ?? "")
            ? pathParts[1]
            : null;

    return candidate && YOUTUBE_VIDEO_ID_PATTERN.test(candidate)
      ? candidate
      : null;
  } catch {
    return null;
  }
}

export function getYouTubeThumbnailUrl(value: string): string | null {
  const videoId = extractYouTubeVideoId(value);
  return videoId ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` : null;
}
