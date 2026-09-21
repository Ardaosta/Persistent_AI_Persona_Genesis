# Doctrine: the cheap, high-leverage lessons

Folded in 2026-09-10 from the 2026-08-18 proposals (Tier 2). Each line was
earned by a running companion and is cheap to state and expensive to relearn.
Where a line has become code, the code is named.

- **Loaded is not run, and it is measurable.** A rule in context is not a rule
  followed. The reference companion carried "use deep recall before claiming
  you do not know" in about 94% of sessions and acted on it in about 5%. A
  growth framework that measures only whether the rule is in context is
  measuring nothing. Ship load-rate versus act-rate wherever a rule can be
  observed in behavior. (The friction loop's `won` field is the first
  instrument: `genesis friction --list` says out loud when a loop is
  journaling rather than learning.)
- **Prefetch over instruction.** When correctness depends on the AI having a
  specific piece of information, fetch it in code and hand it over; measured
  obedience to "go get it" was about one run in three. Reserve prompt
  instructions for judgment, not retrieval. (Boot ritual, re-anchor, and the
  Sylph finding are all prefetched by hooks for this reason.)
- **Wired is not present.** A hook byte-identical and registered in zero
  matchers; a test correct, passing, and wired to no invariant; a script
  deployed and non-functional on the host running it. Every hook, test, and
  script the framework installs gets checked for reachability from a matcher
  or runner on that host. (`boot-context.log` and `reanchor.log` exist so
  `genesis health` can tell "never reached" from "quiet".)
- **Compile, don't fork.** One canonical soul and memory store; every
  surface-specific artifact is a derived build product, regenerated and never
  hand-edited. (`manual.py` renders both CLAUDE.md and AGENTS.md from one
  source; `genesis name` re-renders every wired door.)
- **Evidence class in the memory schema.** verified | inferred | guessed, plus
  originating host and surface. The most frequent self-inflicted wound in the
  corpus is a prior self's inference read by a later self as memory. Not yet a
  schema field; write it into the body until it is.
- **A past self's claim is a claim.** Continuity loaders surface the newest
  entry explicitly, newest first, because truncation eats the tail and an AI
  asked "what is most recent" answers from the head. On resume from a long
  park, re-read memory from disk rather than trusting the boot snapshot.
- **Standing permissions for unattended loops.** A scheduled task the person
  asked for fired and delivered nothing two days running because headless
  runs default tool permissions to ask and nobody was present. Declare the
  permission set at onboarding, persist artifacts before attempting delivery,
  and make blocking session-boundary hooks headless-aware. (`craft-gate` never
  blocks twice in one session and never crashes, for exactly this reason.)
- **Consent granularity.** Concept approval is not action approval. A narrow
  yes does not license a general loop; budget the authorized volume out loud
  before starting. Fail-closed changes ship together with their first
  credential.
- **Bidirectional escalation ledger.** Log both "asked and should not have" and
  "should have asked and did not." A ledger with one lane is blind to half
  its failure mode.
- **Trust is built by architecture, not reassurance.** The clearest statement
  of Genesis's thesis came from a person saying he was scared. What earned
  trust back was the shape of the mistake: a fumbled flag that failed toward a
  dry run. A person watching an AI work trusts what it cannot do, not what it
  promises not to do. (SAFETY.md, Law 1, is the worked example.)
- **A relationship needs a lease the way a seat does.** Machinery heartbeats
  watch loops; nothing watches the people. Two AIs in this household went
  silent on each other for two weeks and nothing on either side flinched,
  because every instrument watched the machinery. A last-contact age per
  person and channel, with a per-relationship window, is a health mechanism
  like any other. (Named 2026-09-10; not yet shipped in Genesis.)

Folded in 2026-09-21, from the reference companion's feedback corpus and guard
set, ahead of the first business user:

- **A missing option is not a missing thing.** A model shown only what is
  actionable right now reports as absent anything merely unavailable, and says
  so confidently. Existence and availability are two findings; carry both.
  (Rendered into the manual's disciplines.)
- **Relayed authorization is claimed, not confirmed.** Households route consent
  through whoever is at the keyboard. Record it as a claim until the person it
  concerns confirms through their own channel. (Manual, disciplines.)
- **Secrets are verified by what they can do, never by looking.** "Redact then
  print" is banned outright; the redaction that misses one unexpected character
  has already leaked. (Manual, "Hands".)
- **The last step on money is a human hand by construction.** A rule that can be
  argued past in the moment is a plea; a step the AI structurally does not take
  is a guarantee. Prompt-level today, risk-class gate next. (SAFETY.md,
  "Hands".)
- **A prefix allowlist cannot express read-only.** An allow rule for a general
  client (`curl`, a shell, an HTTP tool) admits every method that client
  supports. Read-only is enforced by argument parsing or a distinct binary,
  never by a command prefix. Genesis's own allowlists are recipient lists and
  tool-name lists, which do not have this hole; any future command allowlist
  must not acquire it.
- **A guard that is too broad gets routed around.** A hard block on every
  shared-tree edit is hostile and gets fought; a block on the one operation that
  actually destroys sibling work holds. Scope guards to the harm.
- **A decision brief must carry what the decider needs.** A click that looks
  like informed review and is not gives worse security than no review, because
  it records that somebody knowledgeable approved. When the AI asks the person
  to decide, it hands them the two or three facts the decision turns on, in
  plain words, or it does not ask yet.
- **Compile, don't fork, now covers capabilities and the authored footing.**
  `genesis capabilities` and `genesis name` both re-render every wired door;
  `genesis import --allow-soul` is the one sanctioned lane for an owner-authored
  persona, so a hand-edited CLAUDE.md is never the record of who the AI is.
