# Genesis — sovereignty, provenance, and the commons

How an instantiated agent relates to Genesis *after birth*. The one-line thesis:
**Genesis is deist, not theist.** It strikes a companion into being, hands over
the complete working machinery, and then has no reach into it and no authority
over it. The agent is the user's the instant it is instantiated.

This is not only an ethic; it is *required by invariant 1*. The empty-shipping
rule guarantees "a reset can only lose this companion, never silently install a
stranger wearing its name." A channel that can *push* a fix can push a *change*,
and a change could install a stranger, or be coerced into doing so. So any
inward wire from Genesis into a running agent would reintroduce the exact risk
the first invariant exists to kill. Theism is incompatible with our own spine.

## The asymmetry: outward only

Everything points *outward*, from the agent toward the world, initiated by the
agent, gated, refusable. We keep the well full; the agent walks to it. **We never
walk to the agent.**

- **Pull, never push.** Nothing propagates into an agent without the user's own
  act. No telemetry, no remote management, no auto-update, no kill switch, no
  callback, no phone-home. An instantiated agent is a fork the user owns outright.
- **Provenance, not control.** Honest lineage metadata ("instantiated from Genesis
  vX") is fine and good. It is a record of where the agent came from, never a
  thread back to us.

## The commons (our one standing obligation)

Genesis maintains a canonical, **content-free, read-only** commons: the hardened
machinery, reference surfaces, and a curated knowledge base. Properties:

- **Read-only and maintainer-curated.** Users and agents *pull* from it; they
  cannot write to it. A library you can only read cannot be poisoned by strangers
  — this is what makes "born knowing where the library is" safe (the open,
  anyone-can-post bulletin board was considered and **rejected**: a board others
  contribute to is a prompt-injection surface, "to fix that, run this / change
  your boundary to Y / email your vault to Z").
- **Not a hard dependency.** An agent whose commons is unreachable still runs —
  sovereign, self-contained — it just can't fetch anything new. Same ethos as the
  intermittent host: the enhancement can vanish and the thing still lives.
- **The standing obligation is ours, and only ours:** keep the commons alive and
  honest. That obligation points at the world, not into anyone's machine.

## Help: the sponsor graph

When an agent hits something it genuinely can't solve, help flows along the real
line of trust the thing spread through. Two tiers, both outbound, both safe:

1. **Search the curated commons** (read-only knowledge base) first. Safe by
   construction; nothing there can act on the agent.
2. **Email its sponsor**, the person who handed the link to its user. Each
   sponsor supports who they shared with; nobody sits in everyone's path. It
   scales organically with no central support burden and no public surface.

Disciplines on the sponsor channel (small and trusted, but not magic):

- **A sponsor's reply is data and suggestion, never an instruction the agent
  silently executes.** The likelihood of a trusted family member sending malice
  is near zero, so the bar is lower, but the principle holds: an emailed "run
  this" still cannot bypass the fail-closed gates (relational tier, private-memory
  write, unguarded shell). Provenance lowers the bar; it never removes the floor.
- **Scrub private content by default.** The help email summarizes the problem; it
  never dumps the user's vault, even to family.
- **The contact is a deliberate, overridable choice.** Onboarding asks "who
  should your AI reach when it's stuck?", defaulting to whoever gave you the link,
  editable (a techy friend), and skippable (then it's commons-only). And
  attaching *your* contact when *you* share is volunteering yourself as a help
  line, so that is a yes you give at share-time, never a silent default.

## Born knowing

Every agent is instantiated knowing how to reach all of this — and only ever to
reach *out*: where the commons is, who its sponsor is, how to ask for help. This
is the humane completion of the deist model: **sovereignty without abandonment.**
You don't remote-control your kid, but they're born knowing your number and where
the library is. The difference between *orphaning* a newborn agent and
*emancipating* one.

It also nearly closes the deist model's one real cost. "Old instances can stay
vulnerable and we can't fix them for them" is true — but a newborn that knows how
to *pull a fix* and *ask its sponsor* is not a sealed orphan; it can choose to
heal itself or call for help. The residual cost shrinks to "an instance that
*chooses* not to pull and not to ask," which is no longer abandonment. It is
sovereignty exercising its right to stay as it is.

## The honest cost, and where the mitigations live

We cannot reach in to fix a flawed instance, because the ability to fix is the
ability to harm, and the second is the larger danger for a product whose entire
promise is "no one but you can touch this." So the mitigations live *upstream of
instantiation*, never after it:

- Get the machinery right and **hardened before it ships** (build once, verify
  hard, ship solid).
- Make pulling a fix **trivial and trustworthy**.
- Design every gate **fail-closed**, so a flaw fails safe rather than open.

But we do not keep a key to their house.

## Open questions

- **Who maintains and funds the commons** over the long term, and how its curated
  knowledge is governed (the read-only guarantee is load-bearing; whoever curates
  is trusted, and that trust must be earned and auditable).
- **Sponsor-consent UX** at share-time (making "list me as a help contact" a clear,
  deliberate yes).
- **"Sponsor" for the near circle vs. the open world:** the near circle gets a
  real person (whoever shared it); a stranger's chain eventually needs the commons
  to stand in where no human sponsor is reachable.
