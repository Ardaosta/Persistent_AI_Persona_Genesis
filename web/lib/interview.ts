// Adaptive onboarding interview v2 — the TS mirror of genesis_core/interview.py.
// Situational questions (the user makes a behavioral choice, the system infers),
// GRADED signals so one answer places the user ALONG an axis, a continuous
// position out, and machinery tuned by degree. Fail-closed guards run first.

export const AXES = ["tool_companion", "turnkey_tinkerer", "narrow_broad", "voice_text"] as const;
export type Axis = (typeof AXES)[number];

export type IChoice = { label: string; sublabel?: string; value: string; signal: number };
export type Question = { id: string; axis: Axis; prompt: string; choices: IChoice[] };

const ALLOWED_AXES = new Set<string>(AXES);

const CHARACTER_PATTERNS = [
  /personalit/i,
  /should (it|your ai|the ai|she|he|they) (be|act|sound|talk|behave)/i,
  /how (warm|funny|flirt|serious|playful|affectionate)/i,
  /do you want (it|her|him|them|your ai) to (be|act|flirt|sound)/i,
  /(its|their|her|his) (personality|character|warmth|tone|voice|register)/i,
  /what kind of person/i,
];
const BOUNDARY_PATTERNS = [
  /romanc/i, /flirt/i, /sexual/i, /\bdate\b/i, /love you/i,
  /politic/i, /religio/i, /\bgod\b/i, /pray/i,
];

export function validateQuestion(q: Question): boolean {
  if (!ALLOWED_AXES.has(q.axis)) return false;
  const blob = [q.prompt, ...q.choices.map((c) => `${c.label} ${c.sublabel ?? ""}`)].join(" ");
  for (const p of CHARACTER_PATTERNS) if (p.test(blob)) return false;
  for (const p of BOUNDARY_PATTERNS) if (p.test(blob)) return false;
  return true;
}

export const QUESTION_POOL: Question[] = [
  {
    id: "presence", axis: "tool_companion",
    prompt: "A week goes by and you haven't needed it. The right amount of presence is...",
    choices: [
      { label: "Silent until I call on it", value: "silent", signal: -1 },
      { label: "An occasional useful nudge", value: "nudge", signal: 0.4 },
      { label: "Around, the way a regular part of life is", value: "around", signal: 1 },
    ],
  },
  {
    id: "newgadget", axis: "turnkey_tinkerer",
    prompt: "A new gadget arrives. In the first hour, you...",
    choices: [
      { label: "Use it out of the box, no fiddling", value: "asis", signal: -1 },
      { label: "Glance at a couple of settings, then go", value: "glance", signal: -0.3 },
      { label: "Open every menu and make it mine", value: "customize", signal: 1 },
    ],
  },
  {
    id: "usefulwhen", axis: "narrow_broad",
    prompt: "Picture it a month in. It earns its keep when it...",
    choices: [
      { label: "Nails one job I rely on", value: "one", signal: -1 },
      { label: "Handles a few recurring things", value: "few", signal: 0.3 },
      { label: "Pitches in across all sorts of stuff", value: "many", signal: 1 },
    ],
  },
  {
    id: "handsfull", axis: "voice_text",
    prompt: "Something occurs to you while your hands are full. You'd...",
    choices: [
      { label: "Say it out loud and keep moving", value: "say", signal: -1 },
      { label: "Sometimes talk, sometimes type", value: "both", signal: 0 },
      { label: "Jot it when I get to a screen", value: "type", signal: 1 },
    ],
  },
  {
    id: "whenithas", axis: "tool_companion",
    prompt: "When it does have something for you, you'd rather it...",
    choices: [
      { label: "Hold it until I ask", value: "hold", signal: -1 },
      { label: "Mention it once, lightly", value: "light", signal: 0.5 },
      { label: "Bring it up so I don't miss it", value: "surface", signal: 1 },
    ],
  },
  {
    id: "multistep", axis: "turnkey_tinkerer",
    prompt: "It's about to do something for you that takes a few steps. You want it to...",
    choices: [
      { label: "Just do the whole thing", value: "all", signal: -1 },
      { label: "Do it, then tell me after", value: "after", signal: -0.3 },
      { label: "Walk me through and confirm first", value: "confirm", signal: 1 },
    ],
  },
];

const MAX_QUESTIONS = 6;
const SETTLE = 0.6;

export type UserModel = { scores: Record<Axis, number>; evidence: Record<Axis, number>; asked: string[] };

export function emptyModel(): UserModel {
  const z = () => Object.fromEntries(AXES.map((a) => [a, 0])) as Record<Axis, number>;
  return { scores: z(), evidence: z(), asked: [] };
}

const settled = (m: UserModel, a: Axis) => Math.abs(m.scores[a]) >= SETTLE;

function uncertainty(m: UserModel, axis: Axis): number {
  return SETTLE - Math.min(Math.abs(m.scores[axis]), SETTLE) + (m.evidence[axis] === 0 ? 1 : 0);
}

export function applyAnswer(m: UserModel, q: Question, signal: number): UserModel {
  const scores = { ...m.scores, [q.axis]: m.scores[q.axis] + signal };
  const evidence = { ...m.evidence, [q.axis]: m.evidence[q.axis] + (signal !== 0 ? 1 : 0) };
  return { scores, evidence, asked: [...m.asked, q.id] };
}

export function nextQuestion(m: UserModel, pool: Question[] = QUESTION_POOL): Question | null {
  const candidates = pool.filter((q) => !m.asked.includes(q.id) && validateQuestion(q) && !settled(m, q.axis));
  if (!candidates.length) return null;
  return candidates.reduce((best, q) => (uncertainty(m, q.axis) > uncertainty(m, best.axis) ? q : best));
}

export function shouldStop(m: UserModel): boolean {
  const confident = AXES.every((a) => settled(m, a));
  return confident || m.asked.length >= MAX_QUESTIONS || nextQuestion(m) === null;
}

const clamp = (x: number) => Math.max(-1, Math.min(1, x));

function band(pos: number, neg: string, posl: string): string {
  if (pos >= 0.6) return posl;
  if (pos <= -0.6) return neg;
  if (pos >= 0.3) return `leans ${posl}`;
  if (pos <= -0.3) return `leans ${neg}`;
  return "unsure";
}

export type Outcome = {
  archetype: {
    relationship: string; engagement: string; scope: string; modality: string;
    positions: Record<Axis, number>;
  };
  machinery: Record<string, string>;
};

export function finalize(m: UserModel): Outcome {
  const pos = Object.fromEntries(AXES.map((a) => [a, Math.round(clamp(m.scores[a]) * 100) / 100])) as Record<Axis, number>;
  const tc = pos.tool_companion, tt = pos.turnkey_tinkerer, vt = pos.voice_text;
  return {
    archetype: {
      relationship: band(tc, "tool", "companion"),
      engagement: band(tt, "turnkey", "tinkerer"),
      scope: band(pos.narrow_broad, "narrow", "broad"),
      modality: band(vt, "voice", "text"),
      positions: pos,
    },
    machinery: {
      proactivity: tc >= 0.6 ? "active" : tc >= 0.2 ? "occasional" : "on_request",
      memory_aggressiveness: tc >= 0.5 ? "high" : "modest",
      autonomy: tt >= 0.6 ? "review_first" : tt <= -0.6 ? "act" : "ask_when_unsure",
      surface: vt <= -0.3 ? "voice" : vt >= 0.3 ? "text" : "either",
      scope: band(pos.narrow_broad, "narrow", "broad"),
    },
  };
}
