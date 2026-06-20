// Scripted transcripts for verifying the morph WITHOUT a live model.
// Each step is exactly what /api/chat will return at runtime: a line the guide
// says, plus the directives it emits in the same turn. This drives the REAL
// AdaptiveCanvas through the REAL directive path — only the source is canned.
// Layer 3 swaps this for the live Claude adapter; the canvas doesn't change.

import type { Directive } from "./directives";

export type Step = { say: string; directives: Directive[]; delayMs: number };
export type Persona = { id: string; label: string; hint: string; steps: Step[] };

export const PERSONAS: Persona[] = [
  {
    id: "dreamer",
    label: "A dreamer",
    hint: "deep, cinematic",
    steps: [
      { say: "Hello. Let's get started. Tell me anything to begin.", directives: [], delayMs: 0 },
      {
        say: "Deep blues and old science fiction — I can work with that. Let me set the mood.",
        directives: [{ kind: "setPalette", palette: { base: "#10243b", accent: "#2dd4bf", text: "#e6f1fb" } }],
        delayMs: 1400,
      },
      {
        say: "And I'll speak to you like the world is a little bit magic.",
        directives: [{ kind: "setType", register: "cinematic" }],
        delayMs: 1500,
      },
      {
        say: "You'd rather talk than type? Here.",
        directives: [{ kind: "unlockCapability", capability: "voice" }],
        delayMs: 1500,
      },
      {
        say: "And if you want me to see what you see —",
        directives: [
          { kind: "unlockCapability", capability: "screenshare" },
          { kind: "emphasize", text: "This space is yours." },
        ],
        delayMs: 1500,
      },
    ],
  },
  {
    id: "homemaker",
    label: "A homemaker",
    hint: "warm, calm, not techy",
    steps: [
      { say: "Hello. Let's get started. Tell me anything to begin.", directives: [], delayMs: 0 },
      {
        say: "Warm and simple, nothing fancy. That's easy.",
        directives: [{ kind: "setPalette", palette: { base: "#f4efe6", accent: "#b07a3c", text: "#3a2f22" } }],
        delayMs: 1400,
      },
      {
        say: "I'll keep everything plain and easy to read, no rush.",
        directives: [{ kind: "setType", register: "gentle", scale: "large" }],
        delayMs: 1500,
      },
      {
        say: "Hands busy? You can just talk to me.",
        directives: [{ kind: "unlockCapability", capability: "voice" }],
        delayMs: 1500,
      },
      {
        say: "And whenever you want to show me your workshop —",
        directives: [
          { kind: "unlockCapability", capability: "photos" },
          { kind: "emphasize", text: "Good to have you here." },
        ],
        delayMs: 1500,
      },
    ],
  },
];
