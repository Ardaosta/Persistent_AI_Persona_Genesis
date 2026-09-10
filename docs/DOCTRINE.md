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
