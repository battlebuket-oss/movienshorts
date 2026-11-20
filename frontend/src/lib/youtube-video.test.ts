import { describe, expect, it } from "vitest";
import {
  extractYouTubeVideoId,
  getYouTubeThumbnailUrl,
} from "./youtube-video";

const VIDEO_ID = "VZqAPdUvqnQ";

describe("extractYouTubeVideoId", () => {
  it.each([
    [`https://www.youtube.com/watch?v=${VIDEO_ID}&feature=share`, VIDEO_ID],
    [`https://youtu.be/${VIDEO_ID}?si=abc123`, VIDEO_ID],
    [`https://www.youtube.com/live/${VIDEO_ID}?si=abc123`, VIDEO_ID],
    [`https://youtube.com/shorts/${VIDEO_ID}`, VIDEO_ID],
    [`https://www.youtube.com/embed/${VIDEO_ID}`, VIDEO_ID],
    [`https://m.youtube.com/v/${VIDEO_ID}`, VIDEO_ID],
  ])("extracts IDs from supported URL %s", (url, expected) => {
    expect(extractYouTubeVideoId(url)).toBe(expected);
  });

  it.each([
    "",
    "not a URL",
    "https://youtube.com.evil.example/watch?v=VZqAPdUvqnQ",
    "https://example.com/watch?v=VZqAPdUvqnQ",
    "https://www.youtube.com/watch?v=too-short",
    "https://www.youtube.com/channel/UC1234567890",
  ])("rejects unsupported input %s", (url) => {
    expect(extractYouTubeVideoId(url)).toBeNull();
  });
});

describe("getYouTubeThumbnailUrl", () => {
  it("returns the standard high-quality thumbnail for a valid video", () => {
    expect(getYouTubeThumbnailUrl(`https://www.youtube.com/live/${VIDEO_ID}`)).toBe(
      `https://i.ytimg.com/vi/${VIDEO_ID}/hqdefault.jpg`,
    );
  });

  it("returns null for unsupported URLs", () => {
    expect(getYouTubeThumbnailUrl("https://example.com/video")).toBeNull();
  });
});
