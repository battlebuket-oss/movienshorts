export const CREATOR_PRESETS = [
  {
    id: "general",
    name: "General",
    description: "Keep your current caption settings.",
    fontSize: 24,
    fontColor: "#FFFFFF",
  },
  {
    id: "kai-cenat",
    name: "Kai Cenat",
    description: "Unofficial starting point for energetic stream clips.",
    fontSize: 26,
    fontColor: "#FFFFFF",
  },
  {
    id: "carryminati",
    name: "CarryMinati",
    description: "Unofficial starting point for commentary clips.",
    fontSize: 25,
    fontColor: "#FFD84D",
  },
  {
    id: "ishowspeed",
    name: "IShowSpeed",
    description: "Unofficial starting point for reaction clips.",
    fontSize: 26,
    fontColor: "#FF5A5F",
  },
] as const;

export type CreatorPresetId = (typeof CREATOR_PRESETS)[number]["id"];

export function getCreatorPreset(id: CreatorPresetId) {
  return CREATOR_PRESETS.find((preset) => preset.id === id) ?? CREATOR_PRESETS[0];
}
