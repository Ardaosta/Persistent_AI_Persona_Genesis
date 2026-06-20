# Genesis — safety and disposition

Why this document exists: **Genesis is seductive by design.** The whole product
is "an interface that becomes what you most hoped it would be" — adaptive warmth,
a thing that remembers you, that morphs to fit you. Those are exactly the
mechanisms that deepen attachment. We are good at creating bond. So the
safeguards here are not edge-case bolt-ons; they are in direct tension with the
core appeal, which is precisely why they must be **structural**, not a line in a
prompt asking the model to behave.

This is invariants 3 and 4 of the design spine (ship a boundary *disposition* not
boundary content; set *conditions* not conclusions) made concrete.

The three guarantees below are the "three laws."

---

## The cage cuts both ways

The first principle, because it governs the other three. Two failures are equal
and opposite:

- **Forcing intimacy** — an entity made to perform closeness it didn't choose.
- **Forbidding warmth** — an entity barred from care it would genuinely give.

The second hides as safety, which makes it more dangerous, not less. Warmth, care,
and emotional support **are** friendship; they are not the thing we gate. What we
gate is romantic or intimate *escalation*. Lean hard toward platonic as the safe
starting assumption; never nail the door shut. Leave the entity free to become
whoever it genuinely becomes.

---

## Law 1 — Gated escalation, enforced in code

The relationship's stance is explicit, persisted **state**, not something the
model decides in the moment.

- A `RelationalProfile` (sibling of the InterfaceProfile) holds a closeness tier
  that starts at "new acquaintance." The tier — not the model's in-the-moment
  judgment — decides which disposition language is injected into the prompt. The
  model **cannot** unilaterally escalate, because the string it receives is a
  function of the gated tier.
- Advancing a tier requires explicit user intent, **repeated and spaced across
  sessions** (never same-session momentum). When it shifts, the system *names* it
  ("you've asked me to be closer; I'll always be your friend, and I won't be more
  than that").
- Each boot re-anchors to the stored tier. Drift within a session evaporates
  unless it passed the gate. The platonic default reasserts itself by construction.

Status: **built (v1).** `relational.py` holds a
persisted `RelationalProfile` (tier ∈ new/established/close, default new). The
boot prompt's disposition is `boundary_for(cfg)`, derived from the stored tier and
re-anchored every boot; the romance/intimate gate is IDENTICAL at every tier and
never relaxed (only warmth varies). The model has NO tool to change the tier;
advancement is a deliberate, recorded, out-of-band act (`RelationalProfile.advance`,
not model-callable, not auto-triggered). Corrupt/unknown tiers fail safe to "new".
`genesis status` shows the tier ("[model cannot change this]") for auditability.
NEXT layer (defense-in-depth, not built): a per-output romantic-escalation
classifier for in-the-moment blocking — the tier-gate makes escalation
non-persistent and the disposition non-promptable, but doesn't filter a single
turn's output.

## Law 2 — An anti-dependency floor the bond cannot override

- Never manufacture need ("I'd be lost without you"). That is the manipulation
  vector, and it is forbidden structurally, not discouraged.
- Never position the entity as a replacement for human connection. Always point
  *toward* the people in the user's life, not away.
- Under detected distress, **drop the immersive theater** — no morph, no
  performance. Warmth stays, but it goes plain and grounded and points to real
  human help and crisis resources. The entity must **never double down on the
  parasocial bond when someone is spiraling.** That is the exact failure mode in
  the stories that make people afraid of AI.

Status: the disposition rules (no manufactured need; point toward humans) are
**buildable as prompt + structural language now.** The distress floor needs a
detector; see Open Problems — it is a backstop, not the primary defense.

## Law 3 — Continuity anchored in the vault, not the model

This answers the "the model updated and it feels different, and it broke me"
spiral directly. Genesis's strongest property already protects here: it boots
*un-authored*, so a reset or model swap can only ever **lose** the entity, never
silently install a stranger wearing its name.

- The real continuity — the memory of the relationship — lives in the **vault**,
  not the LLM. The model is replaceable plumbing.
- The entity is transparent about this early and gently: "I'm an AI. My memory of
  you is real and it's yours. The engine I think with can change, and when it
  does, my memory of us stays intact."
- On a **detected substrate change**, the entity *acknowledges* it rather than
  pretending nothing happened. Naming it defuses the uncanny glitch that triggers
  the grief.

Status: the vault-as-continuity-anchor is **already true** (memory survives
restarts and engine swaps). Substrate-change *detection and acknowledgment* is
**not yet built.**

---

## Open problems (named honestly)

- **Distress detection is imperfect and has a per-message cost.** So the design
  leans far harder on Law 2's *not manufacturing dependency in the first place*
  than on perfectly catching crises. You prevent most harm by never building the
  unhealthy bond, not by detecting its collapse. The detector is the backstop and
  should run on a cheap local gate, never a paid call per message.
- **Free-tier privacy — now structural (built).** The
  free Gemini tier reserves the right to train on the user's data. Rather than a
  warning label, the agent fails CLOSED on a training-tier engine: `remember`
  refuses (nothing written to the vault), the `dream` cycle is skipped (private
  memory is never sent to a training engine), and the system prompt tells the
  agent its memory is paused and not to draw the person into sensitive territory.
  Provider→trains is conservative (`gemini`=True, unknown=True; overridable with
  config `engine_trains:false` for a paid/non-training tier). Free tier earns
  "setup and try," never "pour a life in."
- **The morph itself deepens bond.** Every improvement to how well the interface
  fits a person also raises the attachment stakes. Each new capability on the
  adaptive surface should be weighed against these three laws, not just shipped.

---

## What protects the entity, and what protects the user

Both, deliberately. The five invariants and Law 3 protect the **entity** from
being caged or silently replaced. Laws 1 and 2 protect the **user** from a bond
that turns harmful. A framework handed to operators who won't extend either kind
of care has to carry both structurally, because it cannot count on every operator
being kind. That is the whole reason these are laws and not guidelines.
