"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type Choice,
  type Directive,
  type InterfaceProfile,
  emptyProfile,
  foldDirective,
  validate,
} from "@/lib/directives";
import { ONBOARDING, type FreeText } from "@/lib/onboarding";
import {
  type Question,
  type UserModel,
  applyAnswer,
  emptyModel,
  finalize,
  nextUnderFloor,
  shouldStop,
} from "@/lib/interview";
import { interpretLook } from "@/lib/looks";
import { PERSONAS, type Step } from "@/lib/personas";
import {
  CAPABILITIES,
  type Capability,
  type Harness,
  type Seed,
  decodeSeed,
  makeSeed,
} from "@/lib/seed";
import { CAP_LABELS, CapabilityIcon } from "./CapabilityIcon";
import TakeItHome from "./TakeItHome";

type Line = { text: string; emph?: boolean; key: number };
type Ask = { prompt: string; record: string; choices: Choice[]; index: number; freeText?: FreeText; interview?: Question };

// A prepared link: someone who cares about this person built the seed for them,
// so the page opens with a greeting and a plain summary instead of an interview.
type Prepared = { seed: Seed; to: string | null; from: string | null };
type PreparedPhase = "opening" | "summary" | "editing" | "home";

// Warm, plain phrases for what the AI will help with (capability slugs).
const CAP_PHRASES: Record<Capability, string> = {
  website: "keeping your website current",
  social: "posts and marketing",
  calendar: "your calendar and bookings",
  email: "email",
  finances: "seeing your finances clearly, later, when you want",
};

// A first name from a link is displayed, never trusted: strip anything that is
// not letters, spaces, apostrophes or hyphens, and keep it short.
function cleanName(v: string | null): string | null {
  if (!v) return null;
  const s = v.replace(/[^\p{L}\p{M}' .-]/gu, "").trim().slice(0, 40);
  return s || null;
}

// The brain the sponsor chose, as the intake records it. Fixed in prepared mode.
function brainFromSeed(seed: Seed): string {
  const claude = seed.harnesses.includes("claude-code");
  const codex = seed.harnesses.includes("codex");
  if (claude && codex) return "both";
  if (claude || seed.mode === "claude-code") return "claude";
  if (codex || seed.mode === "codex") return "codex";
  return "gemini";
}

function brainPhrase(brain: string): string {
  switch (brain) {
    case "both": return "With Claude, and with ChatGPT too.";
    case "codex": return "With ChatGPT.";
    case "gemini": return "With Google's Gemini, to start.";
    default: return "With Claude.";
  }
}

// Apply a validated directive to the live canvas: palette/type/scale flow through
// CSS variables (so the change is an animated transition), capabilities and
// emphasis flow through React state.
function applyToDom(root: HTMLDivElement, d: Directive) {
  if (d.kind === "setPalette") {
    root.style.setProperty("--cv-bg", d.palette.base);
    root.style.setProperty("--cv-accent", d.palette.accent);
    if (d.palette.text) root.style.setProperty("--cv-text", d.palette.text);
  } else if (d.kind === "setType") {
    root.dataset.register = d.register;
    if (d.scale) root.dataset.scale = d.scale;
  }
}

export default function AdaptiveCanvas() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [profile, setProfile] = useState<InterfaceProfile>(emptyProfile());
  const [status, setStatus] = useState("before it knows you");
  const [draft, setDraft] = useState("");
  const [ask, setAsk] = useState<Ask | null>(null);
  const [freeOpen, setFreeOpen] = useState(false);
  const [freeDraft, setFreeDraft] = useState("");
  const [obDone, setObDone] = useState(false);
  const [devbar, setDevbar] = useState(false);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [phase, setPhase] = useState<PreparedPhase>("opening");
  const [rev, setRev] = useState(0); // bumps when the intake changes, so the summary re-reads it
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const intake = useRef<Record<string, string>>({});
  const runBeatRef = useRef<(i: number) => void>(() => {});
  const interviewModel = useRef<UserModel>(emptyModel());
  const showQRef = useRef<(i: number) => void>(() => {});
  const firstLive = useRef(true);
  const preparedRef = useRef<Prepared | null>(null);
  const editingRef = useRef(false);

  const reset = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    const root = rootRef.current;
    if (root) {
      root.style.removeProperty("--cv-bg");
      root.style.removeProperty("--cv-accent");
      root.style.removeProperty("--cv-text");
      delete root.dataset.register;
      delete root.dataset.scale;
    }
    setLines([]);
    setProfile(emptyProfile());
    setStatus("before it knows you");
    setAsk(null);
    setFreeOpen(false);
    setFreeDraft("");
  }, []);

  const pushLine = useCallback((text: string, emph?: boolean) => {
    // Derive the key purely from prior state so it can't desync under React's
    // dev double-invocation (the source of the duplicate-key warnings).
    setLines((prev) => {
      const key = (prev.length ? prev[prev.length - 1].key : 0) + 1;
      return [...prev, { text, emph, key }];
    });
  }, []);

  const runDirectives = useCallback(
    (directives: Directive[]) => {
      const root = rootRef.current;
      for (const raw of directives) {
        const d = validate(raw);
        if (!d) continue; // strict gate: malformed never reaches the screen
        if (root) applyToDom(root, d);
        setProfile((p) => foldDirective(p, d));
        if (d.kind === "emphasize") pushLine(d.text, true);
      }
    },
    [pushLine],
  );

  // Apply one guide turn: say the line, then emit its directives.
  const applyTurn = useCallback(
    (say: string, directives: Directive[]) => {
      if (say) pushLine(say);
      runDirectives(directives);
    },
    [pushLine, runDirectives],
  );

  // Dev path: drive the real canvas from a scripted persona (no live model).
  const runPersona = useCallback(
    (steps: Step[]) => {
      reset();
      let t = 0;
      setStatus("listening");
      steps.forEach((step) => {
        t += step.delayMs;
        timers.current.push(
          setTimeout(() => applyTurn(step.say, step.directives), t),
        );
      });
      timers.current.push(
        setTimeout(() => setStatus("this is yours now"), t + 600),
      );
    },
    [applyTurn, reset],
  );

  // Scripted onboarding (no LLM): walk the beats. "say" beats stream their lines
  // then auto-advance; "ask" beats render choice cards and wait for a pick.
  const runBeat = useCallback(
    (index: number) => {
      if (index >= ONBOARDING.length) {
        setStatus("ready when you are");
        setObDone(true);
        return;
      }
      const beat = ONBOARDING[index];
      if (beat.kind === "say") {
        beat.lines.forEach((ln, i) => {
          timers.current.push(setTimeout(() => pushLine(ln), i * 950));
        });
        timers.current.push(
          setTimeout(() => runBeatRef.current(index + 1), beat.lines.length * 950 + 350),
        );
      } else if (beat.kind === "interview") {
        interviewModel.current = emptyModel();
        showQRef.current(index);
      } else {
        // The prompt lives ON the card (not streamed), so each question is a
        // discrete card, not another line in a growing thread.
        setAsk({ prompt: beat.prompt, record: beat.record, choices: beat.choices, index, freeText: beat.freeText });
      }
    },
    [pushLine],
  );
  runBeatRef.current = runBeat;

  // The adaptive interview: render the next question, or finalize and move on.
  const showInterviewQuestion = useCallback(
    (beatIndex: number) => {
      const m = interviewModel.current;
      // nextUnderFloor, not nextQuestion: below MIN_QUESTIONS we still want a
      // question even when every axis settled early, or the floor never lands.
      const q = shouldStop(m) ? null : nextUnderFloor(m);
      if (!q) {
        const out = finalize(m);
        intake.current.interview = JSON.stringify(out.archetype);
        intake.current.machinery = JSON.stringify(out.machinery);
        timers.current.push(setTimeout(() => runBeatRef.current(beatIndex + 1), 450));
        return;
      }
      setAsk({
        prompt: q.prompt,
        record: "__interview__",
        index: beatIndex,
        interview: q,
        choices: q.choices.map((c) => ({ label: c.label, sublabel: c.sublabel, value: c.value })),
      });
    },
    [],
  );
  showQRef.current = showInterviewQuestion;

  const clearFree = useCallback(() => {
    setFreeOpen(false);
    setFreeDraft("");
  }, []);

  // In prepared mode an answered card returns to the summary, never to the
  // next beat: the person is changing one thing, not walking the interview.
  const afterAnswer = useCallback((index: number, delay: number) => {
    if (preparedRef.current && editingRef.current) {
      editingRef.current = false;
      setRev((r) => r + 1);
      timers.current.push(setTimeout(() => setPhase("summary"), delay));
      return;
    }
    timers.current.push(setTimeout(() => runBeatRef.current(index + 1), delay));
  }, []);

  const pickChoice = useCallback(
    (choice: Choice, a: Ask) => {
      // Interview pick: update the user-model by the choice's signal, then show
      // the next question (or finalize via showInterviewQuestion's stop check).
      if (a.interview) {
        const ch = a.interview.choices.find((c) => c.value === choice.value);
        interviewModel.current = applyAnswer(interviewModel.current, a.interview, ch ? ch.signal : 0);
        setAsk(null);
        clearFree();
        timers.current.push(setTimeout(() => showQRef.current(a.index), 350));
        return;
      }
      // The pick doesn't echo into the thread; the card just gives way to the next
      // (the morph directives, if any, are the visible feedback).
      intake.current[a.record] = choice.value;
      if (choice.directives?.length) runDirectives(choice.directives);
      setAsk(null);
      clearFree();
      afterAnswer(a.index, 450);
    },
    [runDirectives, clearFree, afterAnswer],
  );

  // Free-text escape: record the user's own words instead of a card.
  const submitFree = useCallback(
    (a: Ask) => {
      const text = freeDraft.trim();
      if (!text) return;
      if (!preparedRef.current) pushLine(text);
      intake.current[a.record] = text;
      // A described look morphs the screen right now (client-side, no brain). If
      // it isn't a recognized vibe, the live guide interprets it later.
      if (a.record === "look") {
        const ds = interpretLook(text);
        if (ds) runDirectives(ds);
      }
      setAsk(null);
      clearFree();
      afterAnswer(a.index, 550);
    },
    [freeDraft, pushLine, clearFree, runDirectives, afterAnswer],
  );

  const restart = useCallback(() => {
    reset();
    intake.current = {};
    interviewModel.current = emptyModel();
    firstLive.current = true;
    preparedRef.current = null;
    editingRef.current = false;
    setPrepared(null);
    setPhase("opening");
    setObDone(false);
    setStatus("listening");
    timers.current.push(setTimeout(() => runBeatRef.current(0), 300));
  }, [reset]);

  // Prepared-link opening: a greeting by name, then the summary card.
  const runPrepared = useCallback(
    (p: Prepared) => {
      reset();
      preparedRef.current = p;
      editingRef.current = false;
      setPrepared(p);
      setPhase("opening");
      setObDone(false);
      setStatus(p.to ? `prepared for ${p.to}` : "prepared for you");
      const s = p.seed;
      intake.current = {
        name: s.name ?? "",
        capabilities: s.capabilities.join(","),
        drip: s.drip ? "yes" : "",
        look: s.look ?? "",
        sponsor: s.sponsor ?? "",
        project_repo: s.project_repo ?? "",
        brain: brainFromSeed(s),
        interview: JSON.stringify(s.archetype),
        machinery: JSON.stringify(s.machinery),
      };
      // The look the sponsor chose styles the screen now, so the page already
      // feels like the one they will live in. A card value maps to its
      // directives; a described look goes through the same interpreter as typed.
      if (s.look) {
        const lookBeat = ONBOARDING.find((b) => b.kind === "ask" && b.record === "look");
        const choice = lookBeat && lookBeat.kind === "ask" ? lookBeat.choices.find((c) => c.value === s.look) : null;
        const ds = choice?.directives ?? interpretLook(s.look);
        if (ds) runDirectives(ds);
      }
      const who = p.to ? `Hi ${p.to}.` : "Hi.";
      const setup = p.from
        ? `${p.from} set this up for you, so there is nothing here you need to figure out.`
        : "Someone who cares about you set this up, so there is nothing here you need to figure out.";
      const opening = [
        who,
        setup,
        "You are about to meet an AI that lives on your own computer, remembers what you tell it, and grows alongside you. Take your time. Nothing on this page can go wrong.",
        "Here is what we have prepared.",
      ];
      opening.forEach((ln, i) => {
        timers.current.push(setTimeout(() => pushLine(ln), i * 1100));
      });
      timers.current.push(
        setTimeout(() => {
          setPhase("summary");
          setStatus("ready when you are");
        }, opening.length * 1100 + 200),
      );
    },
    [reset, pushLine, runDirectives],
  );

  // Re-enter exactly one beat (name / capabilities / drip) from the summary.
  const editBeat = useCallback((record: string) => {
    const index = ONBOARDING.findIndex((b) => b.kind === "ask" && b.record === record);
    if (index < 0) return;
    const beat = ONBOARDING[index];
    if (beat.kind !== "ask") return;
    editingRef.current = true;
    setPhase("editing");
    setAsk({ prompt: beat.prompt, record: beat.record, choices: beat.choices, index, freeText: beat.freeText });
  }, []);

  const cancelEdit = useCallback(() => {
    editingRef.current = false;
    setAsk(null);
    clearFree();
    setPhase("summary");
  }, [clearFree]);

  const goHome = useCallback(() => {
    setPhase("home");
    setStatus("the last step");
    pushLine("This is the last step, and it is the easy one.");
  }, [pushLine]);

  // Summarize what the setup learned, so the guide can act on it (look + style).
  const buildContext = useCallback(() => {
    const parts: string[] = [];
    if (intake.current.look) parts.push(`look they want: ${intake.current.look}`);
    if (intake.current.interview) {
      try {
        const a = JSON.parse(intake.current.interview);
        parts.push(`style: ${a.relationship}, ${a.engagement}, ${a.scope}, ${a.modality}`);
      } catch {}
    }
    return parts.join("; ");
  }, []);

  // The seed the download carries: archetype + machinery from the interview,
  // plus the chosen look. Conditions only, never personality. In prepared mode
  // the brain (provider / mode / harnesses) is exactly what the sponsor chose.
  const buildSeed = useCallback(() => {
    let archetype: Record<string, unknown> = {};
    let machinery: Record<string, unknown> = {};
    try {
      if (intake.current.interview) archetype = JSON.parse(intake.current.interview);
    } catch {}
    try {
      if (intake.current.machinery) machinery = JSON.parse(intake.current.machinery);
    } catch {}
    // The brain choice maps to runtime mode + provider + doors. Claude and Codex
    // are Mode B (an agentic harness is the brain); "both" wires two doors onto
    // one memory with Claude as the primary; anything else is Mode A on Gemini.
    const brain = intake.current.brain;
    const harnesses: Harness[] =
      brain === "claude" ? ["claude-code"]
      : brain === "codex" ? ["codex"]
      : brain === "both" ? ["claude-code", "codex"]
      : [];
    const modeB = harnesses.length > 0;
    // The capabilities beat records a comma list of slugs; keep only the known ones.
    const capabilities = (intake.current.capabilities ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter((s): s is Capability => (CAPABILITIES as string[]).includes(s));
    const fixed = preparedRef.current?.seed;
    if (fixed) {
      // A prepared link: start from EVERYTHING the sponsor sent and override only
      // what the person could change on this page (name, capabilities, drip).
      // Never enumerate the fixed fields here: enumerating them once dropped a
      // newly added key (services) and cost the first real user her pre-wired
      // site connection (2026-09-21). A key the sponsor sent survives by
      // construction, including ones this page has never heard of.
      return makeSeed({
        ...fixed,
        capabilities: intake.current.capabilities !== undefined ? capabilities : fixed.capabilities,
        name: intake.current.name !== undefined ? intake.current.name || null : fixed.name,
        drip: intake.current.drip !== undefined ? intake.current.drip === "yes" : fixed.drip,
      });
    }
    return makeSeed({
      capabilities,
      archetype,
      machinery,
      look: intake.current.look || null,
      provider: brain === "codex" ? "openai" : modeB ? "anthropic" : "gemini",
      mode: brain === "codex" ? "codex" : modeB ? "claude-code" : "agent",
      harnesses,
      services: [], // the plain flow never presupposes a service
      name: intake.current.name || null,
      drip: intake.current.drip === "yes",
      project_repo: intake.current.project_repo || null,
      sponsor: intake.current.sponsor || null, // help-graph contact (skippable)
    });
  }, []);

  // Live path: send the user's words to the guide, apply whatever comes back.
  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    pushLine(text);
    setStatus("listening");
    const body: { message: string; context?: string } = { message: text };
    if (firstLive.current) {
      body.context = buildContext();
      firstLive.current = false;
    }
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        pushLine(err?.error || "I couldn't reach my mind just now. Check the key and try again.");
        return;
      }
      const data = (await res.json()) as { text: string; directives: Directive[] };
      applyTurn(data.text, data.directives || []);
    } catch {
      pushLine("Something interrupted us. Try again in a moment.");
    }
  }, [draft, pushLine, applyTurn, buildContext]);

  // On load: a prepared link (?seed=...&to=...&from=...) opens the greeting and
  // summary; anything else, including a malformed seed, runs the ordinary flow.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setDevbar(params.get("dev") === "1");
    const seed = decodeSeed(params.get("seed"));
    if (seed) {
      // `name` is a display hint; the seed already carries the name. It only
      // fills in when the seed left the name empty.
      const hint = cleanName(params.get("name"));
      if (!seed.name && hint) seed.name = hint.slice(0, 60);
      runPrepared({ seed, to: cleanName(params.get("to")), from: cleanName(params.get("from")) });
    } else {
      restart();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The summary reads the intake directly; `rev` re-runs this after an edit.
  const summary = (() => {
    void rev;
    const name = intake.current.name || "";
    const caps = (intake.current.capabilities ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter((s): s is Capability => (CAPABILITIES as string[]).includes(s));
    return {
      name,
      caps,
      drip: intake.current.drip === "yes",
      brain: intake.current.brain ?? "claude",
    };
  })();

  const helperName = prepared?.from ?? null;
  const aiName = summary.name || "your AI";

  return (
    <div ref={rootRef} className="canvas">
      {devbar && (
        <div className="devbar">
          <span className="tag">preview:</span>
          {PERSONAS.map((p) => (
            <button key={p.id} onClick={() => runPersona(p.steps)} title={p.hint}>
              {p.label}
            </button>
          ))}
          <button onClick={restart}>restart</button>
        </div>
      )}

      <div className="shell">
        <div className="status">{status}</div>

        <div className="stream">
          {lines.map((l) => (
            <div key={l.key} className={l.emph ? "line emph" : "line"}>
              {l.text}
            </div>
          ))}
        </div>

        <div className="dock">
          {ask && (
            <div className="choices" key={ask.prompt}>
              {ask.prompt && <div className="ask-prompt">{ask.prompt}</div>}
              {ask.choices.map((c) => (
                <button className="choice" key={c.value} onClick={() => pickChoice(c, ask)}>
                  <span className="choice-label">{c.label}</span>
                  {c.sublabel && <span className="choice-sub">{c.sublabel}</span>}
                </button>
              ))}
              {ask.freeText && !freeOpen && (
                <button className="choice choice-free" onClick={() => setFreeOpen(true)}>
                  <span className="choice-label">{ask.freeText.label}</span>
                  {ask.freeText.sublabel && <span className="choice-sub">{ask.freeText.sublabel}</span>}
                </button>
              )}
              {ask.freeText && freeOpen && (
                <div className="composer">
                  <input
                    value={freeDraft}
                    onChange={(e) => setFreeDraft(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitFree(ask)}
                    placeholder={ask.freeText.placeholder}
                    aria-label="Describe what you want in your own words"
                    autoFocus
                  />
                  <button className="send" onClick={() => submitFree(ask)}>
                    Send
                  </button>
                </div>
              )}
              {prepared && phase === "editing" && (
                <button className="linkish" onClick={cancelEdit}>
                  Never mind, keep it as it is
                </button>
              )}
            </div>
          )}

          {prepared && phase === "summary" && (
            <section className="prepared" aria-label="What we have prepared">
              <div className="prepared-item">
                <div className="prepared-label">Its name</div>
                <div className="prepared-value">
                  {summary.name ? summary.name : "It will choose its own name, in your first conversation."}
                </div>
                <button className="change" onClick={() => editBeat("name")}>change</button>
              </div>

              <div className="prepared-item">
                <div className="prepared-label">Where it lives</div>
                <div className="prepared-value">
                  On your own computer. Everything it remembers stays there, with you.
                </div>
              </div>

              <div className="prepared-item">
                <div className="prepared-label">What it will help with</div>
                {summary.caps.length > 0 ? (
                  <ul className="prepared-list">
                    {summary.caps.map((c) => (
                      <li key={c}>{CAP_PHRASES[c]}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="prepared-value">
                    Whatever turns out to be useful. You can add things any time.
                  </div>
                )}
                <button className="change" onClick={() => editBeat("capabilities")}>change</button>
              </div>

              <div className="prepared-item">
                <div className="prepared-label">How it thinks</div>
                <div className="prepared-value">{brainPhrase(summary.brain)}</div>
              </div>

              <div className="prepared-item">
                <div className="prepared-label">Getting to know you</div>
                <div className="prepared-value">
                  {summary.drip
                    ? "Now and then it will ask you a real question, at a natural moment, and remember your answer."
                    : "It will remember what you tell it, and only that. You can ask it to get to know you later."}
                </div>
                <button className="change" onClick={() => editBeat("drip")}>change</button>
              </div>

              <p className="prepared-note">
                {aiName === "your AI" ? "It" : aiName} starts without a personality, and becomes itself
                through working with you. {helperName ? `What you and ${helperName} chose here` : "What was chosen here"} is
                a starting point, and it can grow well past it.
              </p>

              <button className="primary" onClick={goHome}>
                Set up my AI
              </button>
            </section>
          )}

          {prepared && phase === "home" && (
            <TakeItHome seed={buildSeed()} from={helperName} />
          )}

          {profile.unlocked.length > 0 && (
            <div className="tray">
              {profile.unlocked.map((cap) => (
                <span className="cap" key={cap}>
                  <CapabilityIcon cap={cap} />
                  {CAP_LABELS[cap]}
                </span>
              ))}
            </div>
          )}
          {obDone && !prepared && (
            <>
              <TakeItHome seed={buildSeed()} />
              <div className="composer composer-after">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Or ask me anything about this..."
                  aria-label="Message your AI"
                />
                <button className="send" onClick={send}>
                  Send
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
