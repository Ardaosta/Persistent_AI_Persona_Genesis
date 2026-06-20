# Connect a brain — the foolproof key flow (clocked 2026-06-19)

This is the exact, verified process for getting a **free Gemini brain** connected,
walked end-to-end on a real Google account. It is the spec for the
guided connect-a-brain step: whatever a human must do here, the guide explains in
plain language; whatever can be automated/validated, the guide does.

## The hard constraint

The agent **cannot** do this part *for* a brand-new user: signing into Google and
accepting Google's terms are human-only consent acts (and automating someone's
Google login is a phishing pattern, against ToS, and blocked by 2FA/CAPTCHA). So
the guide's job is to make the human steps unmissable and to do everything around
them: open the right page, explain the consent honestly, then validate and save
the pasted key. (The alternative that skips all of this is the starter-brain-on-
our-key path — still an open decision; see DESIGN/BETA.)

## The steps, as clocked

1. **Go to** `https://aistudio.google.com/apikey`.
2. **Sign in with Google** if not already. (The one account step. The user uses
   the Google login they already know.)
3. **A "Welcome to AI Studio" terms gate appears**, with an "Accept terms of
   service" button and links to the Gemini API Additional Terms, Starter Tier
   Additional Terms, the Privacy Policy, and the data-use terms. The user must
   click accept. **This is a human-only consent step.**
4. **Accepting the terms AUTO-CREATES a key** — a "Default Gemini API Key" in a
   "Default Gemini Project", Free tier, no billing. There is **no separate "Create
   API key" click** on first run; the accept *is* the creation. (One fewer step
   than expected.)
5. **Copy the key** via the copy button in the key's row.
6. **Paste it into the connect-a-brain field**, which validates it live and saves
   it locally (to the secrets dir, never the vault, never echoed anywhere).

## Findings that change how we build the guide

- **The data-training caveat is the headline.** The welcome screen states: prompts
  and responses "may be reviewed and used to train Google AI, so don't submit
  sensitive or personal information." For an intimate AI this conflicts with the
  privacy promise. The guide MUST surface this honestly, and for real users we
  likely want a non-training path (paid tier or a non-training provider) before
  trusting it with a life. The free tier is great for *setup and trying it*, not
  for pouring your private life into.
- **Key format changed.** New Google API keys are **`AQ.`-prefixed, ~53 chars**,
  NOT the legacy `AIza`/39-char format. Any "is this a key?" check must not
  hardcode `AIza`. (Accept `AQ.` and `AIza`; really, just try it and let the live
  validation decide.)
- **Validate with the API, not a regex.** `GET
  https://generativelanguage.googleapis.com/v1beta/models` with the key in the
  `x-goog-api-key` header returns the model list on a good key (HTTP 200). A tiny
  `generateContent` call confirms it can actually complete. **Key goes in the
  header, never the URL.**
- **Gemini 2.5 "thinking" gotcha.** gemini-2.5-flash defaults to dynamic thinking
  that silently consumes output tokens before any visible text. A small
  max_tokens then returns an EMPTY reply (finishReason MAX_TOKENS,
  thoughtsTokenCount > 0) — this broke `genesis doctor` until found. The adapter
  disables it (`generationConfig.thinkingConfig.thinkingBudget = 0`); also cheaper
  and lower-latency for a conversational companion.
- **Free-tier models available (verified):** gemini-2.5-flash, gemini-2.0-flash,
  gemini-flash-latest, gemini-flash-lite-latest, gemini-2.5-flash-lite,
  gemini-3-flash-preview, gemini-3.1-flash-lite, and more (50 models visible).
  `gemini-2.5-flash` and `gemini-flash-latest` are good safe defaults.

## The guide's voice (use this framing at the consent moment)

> "Let's get a brain connected for me. We can change it later, but this will let
> me set things up, and it won't cost you anything. I'll open a window for you in
> your browser. If you'll accept the terms — they say you plan to use Gemini as a
> developer, which is true even if all you ever use it for is to finish the setup
> we're doing right here — then copy the key it gives you and paste it back to me."

It defuses the scary "developer terms" honestly: you *are* a developer in the only
sense that matters here.

## Secrets handling (how the test key was captured)

Clipboard → file via `pbpaste > ~/.config/aimee/gemini_key`, `chmod 600`, and
**never echoed**. Validation prints only byte count / HTTP status / the model's
reply, never the key. The guide must do the same: the pasted key goes straight to
the local secrets file; it is never logged, never shown back, never put in a URL.
