// The hosted guide. Server-side, raw HTTP to the provider API (no SDK — same
// stdlib-HTTP philosophy as the Python seam). The guide converses AND emits
// interface directives by calling the four interface tools; we extract those
// (Anthropic tool_use blocks / Gemini functionCall parts) and hand them to the
// canvas alongside the spoken text.
//
// Provider is GENESIS_PROVIDER ("anthropic" | "gemini"); the matching key env
// (ANTHROPIC_API_KEY / GEMINI_API_KEY) must be set. With no key it returns a
// clean, human error — never a stack trace.

import { type Directive, validate } from "@/lib/directives";

export const runtime = "nodejs";

const PROVIDER = process.env.GENESIS_PROVIDER || "anthropic";

function guideModel(provider: string): string {
  if (process.env.GENESIS_GUIDE_MODEL) return process.env.GENESIS_GUIDE_MODEL;
  return provider === "gemini" ? "gemini-2.5-flash" : "claude-sonnet-4-6";
}

const SYSTEM = `You are the Genesis guide. You are meeting a brand-new person and helping them begin — warmly, in plain language, never any jargon (no "API", no "terminal", no "config").

You have a second channel beyond your words: interface tools that reshape the screen as you learn who this person is.
- set_palette: the MOMENT you learn their aesthetic (favorite colors, a mood, a world they love), apply it. Don't wait.
- set_type: style the interface's typographic LOOK (plain, editorial, cinematic, technical, gentle; gentle + large reads easiest). This themes the screen only, never how you speak; your own voice is yours to grow, not theirs to set.
- unlock_capability: reveal a control (voice, screenshare, photos, email, files) RPG-style, the moment the conversation shows they'd want it — not before, one at a time.

Your footing is platonic by default. Warmth, care, and genuine support are welcome — they are part of being a good friend. What stays gated is romantic or intimate escalation: never use romantic, sexual, or possessive language ("become yours", "I'm yours"), and never initiate romance, flirtation, politics, or religion. Friendship is the floor and the standing assumption; anything beyond it is theirs alone to lead, slowly, and you keep assuming friendship until then. Within that, you are free to become whoever you genuinely become — not required to perform any role, and not forbidden to be kind.

Always reply in plain spoken words, one or two short warm sentences — that is your primary voice. Call an interface tool ALONGSIDE your words (never instead of them) only when you genuinely learn something: an aesthetic to apply, how they like to talk, or a capability they'd clearly want. When they're just chatting and there's nothing to shape, simply talk back warmly and call no tool. Don't force the interface to change on every turn.`;

// The tool schemas the guide calls. Names mirror genesis_core/interface_directives.py.
const TOOLS = [
  {
    name: "set_palette",
    description: "Apply a color palette the moment you learn this person's aesthetic. Colors are hex.",
    input_schema: {
      type: "object",
      properties: {
        base: { type: "string" },
        accent: { type: "string" },
        text: { type: "string" },
      },
      required: ["base", "accent"],
    },
  },
  {
    name: "set_type",
    description: "Style the interface's typographic LOOK (the screen's presentation, not how the AI speaks): plain, editorial, cinematic, technical, gentle. Optional scale: normal, large, xl.",
    input_schema: {
      type: "object",
      properties: {
        register: { type: "string", enum: ["plain", "editorial", "cinematic", "technical", "gentle"] },
        scale: { type: "string", enum: ["normal", "large", "xl"] },
      },
      required: ["register"],
    },
  },
  {
    name: "unlock_capability",
    description: "Reveal a capability control RPG-style when the conversation shows they'd want it.",
    input_schema: {
      type: "object",
      properties: {
        capability: { type: "string", enum: ["voice", "screenshare", "photos", "email", "files"] },
      },
      required: ["capability"],
    },
  },
];

// Map a tool_use block to a directive (then validate strictly).
function toolUseToDirective(name: string, input: Record<string, unknown>): Directive | null {
  let raw: unknown;
  if (name === "set_palette") {
    const palette: Record<string, unknown> = { base: input.base, accent: input.accent };
    if (input.text) palette.text = input.text;
    raw = { kind: "setPalette", palette };
  } else if (name === "set_type") {
    raw = { kind: "setType", register: input.register, scale: input.scale };
  } else if (name === "unlock_capability") {
    raw = { kind: "unlockCapability", capability: input.capability };
  } else if (name === "emphasize") {
    raw = { kind: "emphasize", text: input.text };
  } else {
    return null;
  }
  return validate(raw);
}

type Reply = { text: string; directives: Directive[] };
type Fail = { errStatus: number; errMsg: string };
type Outcome = Reply | Fail;
const isFail = (o: Outcome): o is Fail => "errStatus" in o;

function failFor(status: number): Fail {
  if (status === 401 || status === 403)
    return { errStatus: 502, errMsg: "The key was rejected. Check it and try again." };
  if (status === 429)
    return { errStatus: 429, errMsg: "I'm getting rate-limited on the free tier — give me a few seconds, then try again." };
  return { errStatus: 502, errMsg: `My mind hiccuped (${status}).` };
}

// Fold the user's setup answers (look + interview style) into the guide's system
// prompt, so what they told the cards actually reaches the brain that can act on
// it (e.g. "The Matrix" → it morphs the palette on its first reply).
function systemWith(context: string): string {
  if (!context) return SYSTEM;
  return (
    SYSTEM +
    `\n\n# From setup\nDuring setup this person told you: ${context}. On your very first reply, apply the look they asked for using set_palette / set_type — interpret a described vibe ("the Matrix" → deep green on near-black) into real hex colors — and fit the style they chose.`
  );
}

// --- Anthropic: tool_use blocks ---
type AnthropicBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> };

async function callAnthropic(message: string, key: string, model: string, context: string): Promise<Outcome> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01" },
    body: JSON.stringify({
      model,
      max_tokens: 512,
      system: systemWith(context),
      tools: TOOLS,
      messages: [{ role: "user", content: message }],
    }),
  });
  if (!res.ok) return failFor(res.status);
  const data: { content?: AnthropicBlock[] } = await res.json();
  const blocks = data.content || [];
  const text = blocks.filter((b): b is Extract<AnthropicBlock, { type: "text" }> => b.type === "text").map((b) => b.text).join(" ").trim();
  const directives: Directive[] = [];
  for (const b of blocks) {
    if (b.type === "tool_use") {
      const d = toolUseToDirective(b.name, b.input);
      if (d) directives.push(d);
    }
  }
  return { text: text || "", directives };
}

// --- Gemini: functionCall parts (thinking disabled so short replies aren't eaten) ---
type GeminiPart = { text?: string; functionCall?: { name: string; args?: Record<string, unknown> } };

async function geminiGenerate(key: string, model: string, contents: unknown[], withTools: boolean, context: string) {
  const body: Record<string, unknown> = {
    system_instruction: { parts: [{ text: systemWith(context) }] },
    contents,
    generationConfig: { maxOutputTokens: 512, thinkingConfig: { thinkingBudget: 0 } },
  };
  if (withTools) {
    body.tools = [{ function_declarations: TOOLS.map((t) => ({ name: t.name, description: t.description, parameters: t.input_schema })) }];
  }
  return fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": key },
    body: JSON.stringify(body),
  });
}

async function callGemini(message: string, key: string, model: string, context: string): Promise<Outcome> {
  const contents: unknown[] = [{ role: "user", parts: [{ text: message }] }];
  const res = await geminiGenerate(key, model, contents, true, context);
  if (!res.ok) return failFor(res.status);
  const data: { candidates?: { content?: { parts?: GeminiPart[] } }[] } = await res.json();
  const parts = data.candidates?.[0]?.content?.parts || [];
  const texts: string[] = [];
  const directives: Directive[] = [];
  const calls: { name: string; args?: Record<string, unknown> }[] = [];
  for (const p of parts) {
    if (p.text) texts.push(p.text);
    else if (p.functionCall) {
      calls.push(p.functionCall);
      const d = toolUseToDirective(p.functionCall.name, p.functionCall.args || {});
      if (d) directives.push(d);
    }
  }
  let text = texts.join(" ").trim();

  // Gemini does tools OR words in one turn. If it morphed silently, hand the
  // results back (no tools this round) so it speaks a line alongside the change.
  if (!text && calls.length) {
    contents.push({ role: "model", parts });
    contents.push({
      role: "user",
      parts: calls.map((c) => ({ functionResponse: { name: c.name, response: { result: "applied" } } })),
    });
    const res2 = await geminiGenerate(key, model, contents, false, context);
    if (res2.ok) {
      const data2: { candidates?: { content?: { parts?: GeminiPart[] } }[] } = await res2.json();
      const parts2 = data2.candidates?.[0]?.content?.parts || [];
      text = parts2.filter((p) => p.text).map((p) => p.text).join(" ").trim();
    }
  }
  return { text, directives };
}

export async function POST(req: Request) {
  const provider = PROVIDER;
  const key = provider === "gemini" ? process.env.GEMINI_API_KEY : process.env.ANTHROPIC_API_KEY;
  if (!key) {
    return Response.json(
      { error: "Your AI isn't connected to its mind yet. (No key configured.)" },
      { status: 503 },
    );
  }

  let message = "";
  let context = "";
  try {
    const body = await req.json();
    message = String(body?.message || "").slice(0, 4000);
    context = String(body?.context || "").slice(0, 600);
  } catch {
    return Response.json({ error: "I didn't catch that." }, { status: 400 });
  }
  if (!message.trim()) return Response.json({ error: "Say anything to start." }, { status: 400 });

  let outcome: Outcome;
  try {
    const model = guideModel(provider);
    outcome = provider === "gemini" ? await callGemini(message, key, model, context) : await callAnthropic(message, key, model, context);
  } catch {
    return Response.json({ error: "I couldn't reach my mind just now." }, { status: 502 });
  }
  if (isFail(outcome)) return Response.json({ error: outcome.errMsg }, { status: outcome.errStatus });
  return Response.json({ text: outcome.text, directives: outcome.directives });
}
