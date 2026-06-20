// The scripted, no-LLM opening. The first turns cannot be model-driven (you
// can't have the AI guide you to connecting the AI), so this stretch is
// deterministic: framing, then button-first choice cards. Each pick is recorded
// into an intake the model inherits once a brain is connected, and some picks
// carry their own directives (choosing a voice visibly morphs the interface).
//
// Button-first is the first rung of the progressive interface: clicks now, text
// and richer modalities once there's a brain to drive them.

import type { Choice } from "./directives";

// Optional free-text escape on an "ask" beat: the cards prevent blank-page
// freeze; this lets someone who already knows exactly what they want type it
// in their own words, for a richer seed.
export type FreeText = { label: string; sublabel?: string; placeholder: string };

export type Beat =
  | { kind: "say"; lines: string[] }
  | { kind: "ask"; prompt: string; record: string; choices: Choice[]; freeText?: FreeText }
  // The adaptive interview phase: the canvas hands control to the interview
  // engine (lib/interview.ts), which picks each next question by uncertainty and
  // stops early when the user is clear. Replaces the old fixed archetype card.
  | { kind: "interview" };

export const ONBOARDING: Beat[] = [
  {
    kind: "say",
    lines: [
      "Hi. This short setup shapes the AI we build for you.",
      "A few quick questions, and it keeps adapting later, so nothing here is locked in.",
    ],
  },
  { kind: "interview" },
  {
    kind: "say",
    // The card below themes the SCREEN's look only. We do NOT pre-seed how the AI
    // speaks — its voice is un-authored and grows through the relationship (the
    // spine's invariants 1 & 2; flagged in dogfooding). So this asks about the
    // interface's feel, and the recorded value is a visual theme, not a register.
    lines: ["Good. And the feel of it on screen, while we're here."],
  },
  {
    kind: "ask",
    record: "look",
    prompt: "Which of these looks most like you? (This styles the screen; how it talks grows on its own.)",
    choices: [
      {
        label: "Warm and relaxed",
        sublabel: "Soft, larger, unhurried.",
        value: "gentle",
        directives: [{ kind: "setType", register: "gentle", scale: "large" }],
      },
      {
        label: "Clean and simple",
        sublabel: "Plain and easy to read.",
        value: "plain",
        directives: [{ kind: "setType", register: "plain" }],
      },
      {
        label: "Crisp and precise",
        sublabel: "Tight and efficient.",
        value: "crisp",
        directives: [{ kind: "setType", register: "technical" }],
      },
      {
        label: "Classic and literary",
        sublabel: "Serif, considered.",
        value: "editorial",
        directives: [{ kind: "setType", register: "editorial" }],
      },
    ],
    freeText: {
      label: "Something else in mind?",
      sublabel: "Describe the look you'd like.",
      placeholder: "e.g. dark and moody, or bright and airy…",
    },
  },
  {
    kind: "say",
    lines: [
      "Got it. I'll set your AI up around that.",
      "One practical thing before you take it home.",
    ],
  },
  {
    kind: "ask",
    record: "sponsor",
    prompt:
      "When your AI gets genuinely stuck, who should it be able to email for help? Usually whoever pointed you here. It only reaches out when it's truly stuck, and never shares your private memory.",
    choices: [
      {
        label: "Skip for now",
        sublabel: "It'll rely on the shared knowledge base instead.",
        value: "",
      },
    ],
    freeText: {
      label: "Add a help contact",
      sublabel: "An email address.",
      placeholder: "name@example.com",
    },
  },
  {
    kind: "say",
    lines: [
      "Perfect. Everything you just shaped is ready to live on your own machine.",
      "Take it home with the command below, and your AI sets itself up there, tuned to all of this.",
    ],
  },
];
