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
      "Hi. Let's get started.",
      "You're about to set up an AI that lives on your own computer, remembers you, and gets better over time. Nobody else holds its memory. Not us, not the company whose model it thinks with.",
      "It arrives without a personality. Who it becomes grows out of working with you. This short setup only shapes the machinery around it.",
      "A few quick questions, and it keeps adapting later, so nothing here is locked in.",
    ],
  },
  { kind: "interview" },
  {
    kind: "say",
    lines: ["Now, one question about it rather than about you."],
  },
  {
    // The name is the ONE identity field setup may carry, and only because the
    // person chooses it. The default is to let the AI name itself in your first
    // conversation, which keeps the un-authored invariant intact.
    kind: "ask",
    record: "name",
    prompt: "Should it have a name from day one?",
    choices: [
      {
        label: "Let it choose its own",
        sublabel: "It picks a name in your first conversation. Recommended.",
        value: "",
      },
    ],
    freeText: {
      label: "I have a name in mind",
      sublabel: "It'll answer to this from the first session.",
      placeholder: "e.g. Quill",
    },
  },
  {
    kind: "say",
    // The card below themes the SCREEN's look only. We do NOT pre-seed how the AI
    // speaks — its voice is un-authored and grows through the relationship (the
    // spine's invariants 1 & 2; flagged in review, issue #1). So this asks about the
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
    lines: ["Good. Now, what should power your AI's thinking? You can change this later."],
  },
  {
    kind: "ask",
    record: "brain",
    prompt: "Pick a brain.",
    choices: [
      {
        label: "My Claude subscription",
        sublabel: "Most capable, and it can read and write code. Needs the Claude app and a paid plan.",
        value: "claude",
      },
      {
        label: "My ChatGPT subscription (Codex)",
        sublabel: "Runs on OpenAI's Codex. Needs the Codex app or CLI and a ChatGPT plan.",
        value: "codex",
      },
      {
        label: "Both: Claude first, Codex too",
        sublabel: "One AI, one memory, two doors. Open it in whichever app you like.",
        value: "both",
      },
      {
        label: "Free to start",
        sublabel: "Uses Google's Gemini. Free, no account beyond a quick key. Great for trying it.",
        value: "gemini",
      },
    ],
  },
  {
    kind: "ask",
    record: "capabilities",
    prompt: "What should it help with first? It starts with a recipe for each of these, and you can add more later.",
    choices: [
      {
        label: "A business's public face",
        sublabel: "Website, social posts, the calendar and bookings, customer email. It drafts; you publish.",
        value: "website,social,calendar,email",
      },
      {
        label: "My own admin",
        sublabel: "Calendar, email, and seeing my money clearly. It never moves money.",
        value: "calendar,email,finances",
      },
      {
        label: "All of it",
        sublabel: "Website, social, calendar, email, finances.",
        value: "website,social,calendar,email,finances",
      },
      {
        label: "Nothing specific yet",
        sublabel: "We'll find out together. Add any of these later.",
        value: "",
      },
    ],
  },
  {
    kind: "say",
    lines: ["Two more, and both are optional."],
  },
  {
    kind: "ask",
    record: "drip",
    prompt: "Want it to get to know you over time? It would ask one or two real questions a session, at natural moments, and remember your answers.",
    choices: [
      {
        label: "Yes, get to know me",
        sublabel: "Working style first, then people, taste, and edges. Never a quiz.",
        value: "yes",
      },
      {
        label: "Not for now",
        sublabel: "It'll still remember what you tell it. You can switch this on later.",
        value: "",
      },
    ],
  },
  {
    kind: "ask",
    record: "project_repo",
    prompt: "Is there a project it's joining? If a collaborator gave you a repository link, paste it and your AI will start with that project's knowledge.",
    choices: [
      {
        label: "No project yet",
        sublabel: "Skip this.",
        value: "",
      },
    ],
    freeText: {
      label: "Paste a repository link",
      sublabel: "A GitHub address, or a folder on your machine.",
      placeholder: "https://github.com/org/repo",
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
