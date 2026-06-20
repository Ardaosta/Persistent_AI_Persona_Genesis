# Persistent AI Persona: Genesis

An engine-agnostic framework for an AI companion that lives on *your* machine,
remembers across time, grows from its own lived record, and is never authored by
a vendor.

The whole project turns on one rule: **ship the machinery of personality, never
the content.** A Genesis companion boots *un-authored*. It has no name, no
pre-written personality, no manufactured warmth. Who it becomes emerges from one
relationship, kept in a private memory that belongs to the person, not to me and
not to whatever model is doing the thinking this week.

## Why I built this

I have been fascinated by the idea of a real AI companion since I was a kid, long
before it was buildable. What finally bothered me about the current wave is that
almost all of it gets two things backwards. The personality ships from a company,
so everyone's "companion" is the same product wearing a different name. And the
memory lives on someone else's servers, so the relationship is rented, not owned.

Genesis is my answer to both. The company ships the *capacity* to become someone,
and then gets out of the way. The memory is plain markdown on a computer you
control, so you can read it, back it up, move it, or delete it. A reset can only
*lose* your companion. It can never silently install a manufacturer's companion
wearing the same face, because there was never a manufacturer's companion to
install.

## What works today

This is early, but it is real, not a sketch. Around 200 tests, green on macOS and
Windows.

- **A private memory vault.** One human-readable fact per file, a lean always-loaded
  index with a hard byte budget, a single blessed write path.
- **Three memory tiers, kept structurally separate.** Durable (accumulates
  carefully), perishable (working state, overwritten freely), and an append-only
  first-person continuity thread. Perishable can never leak into durable, because
  it physically lives outside the vault, not because a prompt asks nicely.
- **Two growth loops.** An inward "dream" that reviews memory and keeps what is
  load-bearing, and an outward "learn" that pursues a thread you care about and
  brings back something concrete.
- **Onboarding that tunes the machine, not the soul.** A short adaptive interview
  produces an archetype and a behavioral profile (proactivity, autonomy, memory
  aggressiveness, surface), so the agent boots tuned to how you work, while still
  booting un-authored on *who it is*.
- **Safety enforced in code, not pleas.** A persisted relational tier the model
  cannot change, a fail-closed guard against deepening into private memory on an
  engine that may train on it, and a CI gate that refuses to ship if any soul
  content sneaks into the package. See [`SAFETY.md`](SAFETY.md).
- **A real continuity ritual.** Identity is injected at boot, with a liveness
  handshake so you get proof the companion actually loaded and it is not the bare
  model cosplaying it.
- **Engine-agnostic.** Anthropic, OpenAI, or a free Gemini brain behind one seam.
- **Web onboarding to a tuned local agent.** The browser flow hands you a single
  command that stands the whole thing up on your own machine, carrying your setup
  answers with it. Nothing runs on your computer that you did not run yourself.

## How it is meant to spread

Genesis is sovereign by design. The project keeps a content-free, read-only
"commons" of hardened lessons, and help flows along the real line of trust the
thing spread through (the person who gave you the link), never a central server
with reach into your machine. The full stance is in [`SOVEREIGNTY.md`](SOVEREIGNTY.md).

## Quickstart

### Take it home (the intended path)

Run the onboarding, and at the end it hands you a one-line command for your OS
(macOS, Windows, or Linux) that installs Genesis and stands up a tuned home. Then
connect a brain:

```sh
genesis install     # guided: walks you through getting an API key, plain language
genesis chat        # talk to it
genesis status      # plain-English memory + schedule health
```

### From source (developers)

```sh
git clone https://github.com/Ardaosta/Persistent_AI_Persona_Genesis
cd Persistent_AI_Persona_Genesis
python3 -m venv .venv && . .venv/bin/activate
pip install -e packages/genesis-memory -e packages/genesis-backend -e packages/genesis-core
pytest                       # green = the spine works
genesis status
```

Requires Python 3.10+.

## Layout

```
packages/
  genesis-memory/    # the vault, the lean index, the three memory tiers
  genesis-backend/   # the engine seam (Anthropic / OpenAI / Gemini)
  genesis-core/      # the agent loop, onboarding, growth loops, safety, CLI
web/                 # the browser onboarding + the take-it-home installer
engine-packs/        # per-engine reference config (content-free)
```

## Honesty about maturity

What is proven: the memory model, the growth loops, the onboarding-to-tuned-boot
bridge, the safety spine, and cross-platform install + scheduling. What is not yet
hardened: the action tools run behind a deny-list, which is fine for a single
trusted user on their own machine but wants a real OS sandbox before it is handed
to strangers. I would rather say that plainly than oversell it.

If the idea resonates, or if you find a hole in the reasoning, I want to hear it.

## License

[Apache License 2.0](LICENSE). Copyright 2026 Larame Spence.
