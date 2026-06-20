// Client-side interpretation of a described look into a palette + register, so a
// free-text look answer ("The Matrix", "Tron", "cozy") morphs the screen
// IMMEDIATELY during onboarding — no brain, no rate limit. If nothing matches,
// returns null and the live guide interprets it later (route context).

import type { Directive, TypeRegister } from "./directives";

type Look = { keys: string[]; base: string; accent: string; text: string; register: TypeRegister };

const LOOKS: Look[] = [
  { keys: ["matrix"], base: "#080d08", accent: "#1aff5c", text: "#bcffc6", register: "technical" },
  { keys: ["tron"], base: "#04070e", accent: "#22d3ee", text: "#cdeefb", register: "cinematic" },
  { keys: ["cyberpunk", "neon"], base: "#0c0414", accent: "#ff2bd6", text: "#ffd6f4", register: "cinematic" },
  { keys: ["sunset", "cozy", "warm"], base: "#2a1410", accent: "#ff7a3c", text: "#ffe7d6", register: "gentle" },
  { keys: ["ocean", "sea", "nautical"], base: "#06121f", accent: "#3aa0ff", text: "#d6ecff", register: "editorial" },
  { keys: ["forest", "nature", "earthy"], base: "#0b1a10", accent: "#3fbf6f", text: "#d8f5e0", register: "editorial" },
  { keys: ["royal", "purple", "violet"], base: "#140a22", accent: "#a47dff", text: "#e7ddff", register: "cinematic" },
  { keys: ["rose", "pink", "blossom"], base: "#1f0d16", accent: "#ff6fae", text: "#ffd9ea", register: "editorial" },
  { keys: ["mono", "noir", "dark", "night", "black"], base: "#0a0a0c", accent: "#9aa0ad", text: "#e8e9ec", register: "technical" },
  { keys: ["bright", "light", "airy", "clean", "minimal"], base: "#f4f4f6", accent: "#3a6ea5", text: "#1a1c22", register: "plain" },
  { keys: ["paper", "magazine", "editorial", "classic"], base: "#f6f3ec", accent: "#9a6b34", text: "#2b2620", register: "editorial" },
];

export function interpretLook(text: string): Directive[] | null {
  const t = text.toLowerCase();
  for (const l of LOOKS) {
    if (l.keys.some((k) => t.includes(k))) {
      return [
        { kind: "setPalette", palette: { base: l.base, accent: l.accent, text: l.text } },
        { kind: "setType", register: l.register },
      ];
    }
  }
  return null;
}
