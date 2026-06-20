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
  nextQuestion,
  shouldStop,
} from "@/lib/interview";
import { interpretLook } from "@/lib/looks";
import { PERSONAS, type Step } from "@/lib/personas";
import { makeSeed } from "@/lib/seed";
import { CAP_LABELS, CapabilityIcon } from "./CapabilityIcon";
import TakeItHome from "./TakeItHome";

type Line = { text: string; emph?: boolean; key: number };
type Ask = { prompt: string; record: string; choices: Choice[]; index: number; freeText?: FreeText; interview?: Question };

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
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const intake = useRef<Record<string, string>>({});
  const runBeatRef = useRef<(i: number) => void>(() => {});
  const interviewModel = useRef<UserModel>(emptyModel());
  const showQRef = useRef<(i: number) => void>(() => {});
  const firstLive = useRef(true);

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
        if (!d) continue; // strict gate — malformed never reaches the screen
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
      const q = shouldStop(m) ? null : nextQuestion(m);
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
    [pushLine],
  );
  showQRef.current = showInterviewQuestion;

  const clearFree = useCallback(() => {
    setFreeOpen(false);
    setFreeDraft("");
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
      timers.current.push(setTimeout(() => runBeatRef.current(a.index + 1), 450));
    },
    [pushLine, runDirectives, clearFree],
  );

  // Free-text escape: record the user's own words instead of a card.
  const submitFree = useCallback(
    (a: Ask) => {
      const text = freeDraft.trim();
      if (!text) return;
      pushLine(text);
      intake.current[a.record] = text;
      // A described look morphs the screen right now (client-side, no brain). If
      // it isn't a recognized vibe, the live guide interprets it later.
      if (a.record === "look") {
        const ds = interpretLook(text);
        if (ds) runDirectives(ds);
      }
      setAsk(null);
      clearFree();
      timers.current.push(setTimeout(() => runBeatRef.current(a.index + 1), 550));
    },
    [freeDraft, pushLine, clearFree, runDirectives],
  );

  const restart = useCallback(() => {
    reset();
    intake.current = {};
    interviewModel.current = emptyModel();
    firstLive.current = true;
    setObDone(false);
    setStatus("listening");
    timers.current.push(setTimeout(() => runBeatRef.current(0), 300));
  }, [reset]);

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

  // The seed that the take-it-home command carries: archetype + machinery from
  // the interview, plus the chosen look. Conditions only — never personality.
  const buildSeed = useCallback(() => {
    let archetype: Record<string, unknown> = {};
    let machinery: Record<string, unknown> = {};
    try {
      if (intake.current.interview) archetype = JSON.parse(intake.current.interview);
    } catch {}
    try {
      if (intake.current.machinery) machinery = JSON.parse(intake.current.machinery);
    } catch {}
    // The brain choice maps to runtime mode + provider. Claude = Mode B (Claude
    // Code is the brain); anything else = Mode A on the free Gemini path.
    const claude = intake.current.brain === "claude";
    return makeSeed({
      archetype,
      machinery,
      look: intake.current.look ?? null,
      provider: claude ? "anthropic" : "gemini",
      mode: claude ? "claude-code" : "agent",
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

  useEffect(() => {
    restart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div ref={rootRef} className="canvas">
      <div className="devbar">
        <span className="tag">preview:</span>
        {PERSONAS.map((p) => (
          <button key={p.id} onClick={() => runPersona(p.steps)} title={p.hint}>
            {p.label}
          </button>
        ))}
        <button onClick={restart}>restart</button>
      </div>

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
            </div>
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
          {obDone && (
            <>
              <div className="composer">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="type here…"
                  aria-label="Message your AI"
                />
                <button className="send" onClick={send}>
                  Send
                </button>
              </div>
              <TakeItHome seed={buildSeed()} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
