import { describe, expect, it } from "vitest";
import { CREATOR_PRESETS, getCreatorPreset } from "./creator-presets";

describe("creator presets", () => {
  it("provides the three requested creator presets plus a general option", () => {
    expect(CREATOR_PRESETS.map((preset) => preset.id)).toEqual([
      "general",
      "kai-cenat",
      "carryminati",
      "ishowspeed",
    ]);
  });

  it("returns stable, valid caption settings for every preset", () => {
    for (const preset of CREATOR_PRESETS) {
      expect(preset.fontSize).toBeGreaterThanOrEqual(18);
      expect(preset.fontSize).toBeLessThanOrEqual(48);
      expect(preset.fontColor).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it("falls back to the general preset for unknown runtime input", () => {
    expect(getCreatorPreset("not-a-real-preset" as never).id).toBe("general");
  });
});
