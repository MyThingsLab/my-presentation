# my-presentation — agent instructions

You are developing **my-presentation**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** given a talk issue labeled `my-presentation` (topic, audience,
  target length), drafts a slide-by-slide outline with speaker notes, then
  hands that structure to MyTypster to render a `.typ` slide deck and compile
  it to PDF.
- **The single Engine call:** one per run — "given this topic, audience, and
  target length, draft a slide-by-slide outline with speaker notes." Input:
  the issue title + body, `context = {"issue": N, "target_slides": int |
  None}`. Output: `{"slides": [{"title", "bullets", "speaker_notes"}],
  "est_duration_min": int}`. Against `NoopEngine`, degrades to one slide
  titled from the issue with the body split into bullets and empty speaker
  notes — honest stub.
- **Invariants / rules:**
  - **Deterministic truncation.** If a `target_slides` was given (via
    `--slides` or parsed from free-text in the issue body) and the reply has
    more slides than that, truncate to the first N — never trust the
    model's own slide count.
  - **CLI hand-off, not a package dependency.** This tool does not import
    `mytypster`; it shells out to the installed `mytypster` CLI
    (`mytypster draft --kind presentation --from-json ... --json`) for the
    actual render-and-compile step. This keeps the two tool repos decoupled
    at the code level — only `my-things-core` is a shared dependency.
  - One side effect of its own: an issue comment rendering the full outline
    (title/bullets/speaker notes per slide), posted **regardless** of
    whether the deck compiles — the narrative review doesn't depend on
    compilation succeeding. Routed through `Policy` (`Guard` default).
    Everything else (Workspace, PR, compile gate) is MyTypster's own side
    effect, passed through unchanged. **Never merges.**
  - Ledger `kind=presentation`, `outcome=success|compile_failed|failure` —
    `compile_failed` passes through MyTypster's own outcome unchanged.
- **Backlog label:** `my-presentation`
