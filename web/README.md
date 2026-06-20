# Genesis — the web front door

The hosted guide. Share a URL; anyone can begin from there. As the guide learns
who it's talking to, the interface *becomes theirs* — palette, typographic
register, and capability controls all morph live (the adaptive surface).

## Layers

- **Layer 1 — directive protocol** (`packages/genesis-core/.../interface_directives.py`,
  mirrored in `lib/directives.ts`): the bounded vocabulary the guide speaks to the
  interface. Strictly validated; a malformed directive never reaches the screen.
- **Layer 2 — adaptive canvas** (`components/AdaptiveCanvas.tsx` + `app/globals.css`):
  the morphing surface. Palette/type flow through CSS variables so every change is
  an animated transition. Verifiable now via the `preview:` persona switcher (top
  right) — it drives the real canvas through the real directive path, no model needed.
- **Layer 3 — live wiring** (`app/api/chat/route.ts`): the guide is the real Claude
  adapter (raw HTTP, no SDK), emitting directives by calling the four interface
  tools. Complete, but live-pending a working `ANTHROPIC_API_KEY`.

## Run locally

    npm install
    npm run dev        # http://localhost:3000

The `preview:` buttons morph the canvas with no key. To make the typed conversation
live, set `ANTHROPIC_API_KEY` (and optionally `GENESIS_GUIDE_MODEL`).

## Deploy (Vercel)

Connected to your own GitHub account. Set the project root to `web/`, add
`ANTHROPIC_API_KEY` as an environment variable, and push — auto-deploys.

## Design decisions (2026-06-18)

- **Vocabulary now, generative seam later** — the model chooses among pre-designed
  mutations; the artistry lives in the canvas, the taste lives in the model.
- **Permanent surface** — the `InterfaceProfile` persists; what it becomes is the
  daily driver, not onboarding theater. (Persistence + web→local handoff are the
  next layers.)
