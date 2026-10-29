# Backend harness integration brief — v0.7.6

**v0.7.6 skill specification; no backend implementation in this delivery.** Confirmed behavior is in
[DECISIONS.md](DECISIONS.md). The owner approved documentation, not deployment,
paid testing or fine-tuning. Frank owns the future shared-interface changes.

## What was actually inspected in v0.7.5

| Location | Current behavior | Integration implication |
| --- | --- | --- |
| `backend/app/structure_provider.py` | Embedded `GUIDANCE`, prompt version `structure-v2-evidence-mechanisms`; draft/research/feedback flows; evidence coverage guidance | Refactor or compose explicit skill loading; do not claim there was no guidance before this package. |
| `backend/app/structure_models.py` | Nodes/edges/methods/gaps, strict extra-field rejection; methods have explanation, node IDs and conditions | Semantic card requirements may fit existing text initially; new fields need versioned contracts, not prompt-only invention. |
| Structure provider/runtime | Exact evidence IDs; model leaves moments empty and server attaches source timing | Keep trustworthy timing and revision ownership on the server. |
| `backend/app/providers/creative.py` | `DirectionsContent` requires exactly two candidates; generation also checks two unique hook/narrative fingerprints | I5 cannot work by changing prompts alone. Update cardinality, adapter logic, downstream assumptions and UI for one/zero qualifying results. Semantic differentiation needs more than string uniqueness. |
| Creative provider | Product context, source citations, hypotheses and approval checks already exist | Reuse these boundaries; add professional method and explicit experimental-status persistence where needed. |
| `backend/app/models.py` and creative provider | Production output validates ordered times ending at target duration; invalid output can be rejected | Design a separate safe draft/issue representation for P5/P6; do not weaken the trusted production-ready schema to hide failure. |
| Storyboard row fields | Visual, dialogue, screen text, sound and timings are separate | Four-column display is a presentation requirement; preserve distinct semantic data under the hood. |
| Local client policy | No experiment-dollar cap; Cloud experiment guard retained | Do not revive the USD 3 local restriction through the harness. |

Historical interview documents contain old “not implemented” statements. The
current source above takes precedence for implementation facts. This package
does not assert that all new behavior already exists.

## Proposed request lifecycle

1. Resolve the module, task revision, language, immutable input snapshot and
   selected reference handoff. Check approval for production before any model call.
2. Assemble trusted instructions separately from untrusted evidence. Load the
   shared method and relevant module only; include context whose purpose is known.
3. Validate input sufficiency and modality coverage. Continue supported work with
   assumptions/limitations where allowed; do not invent missing product facts.
4. Generate against the selected, supported contract. The host assigns persistent
   identities, revision links, source timing and permission-controlled state.
5. Run cheap deterministic checks first. Then assess semantic quality using a
   calibrated review procedure. Which checks need another model call remains an
   engineering decision; avoid automatically doubling every operation's cost.
6. If a correctable defect remains, make at most one targeted quality-repair call
   for this module operation, addressing all known repairable defects together.
   This single-call interpretation is a proposed implementation of the agreed
   one-revision rule; never allocate a new loop per card, shot or critic.
7. Revalidate and apply the module-specific retention/draft policy. Persist the
   user-visible status, assumptions and issue markers with the artifact.
8. Render concise rationale and expose details on demand. Exports retain warnings,
   source versions, experimental flags and discussion-draft status.

Network retries and syntax-recovery behavior must be explicitly accounted for;
do not use them to evade the semantic revision bound. The baseline local launcher
uses zero automatic retries. Any future change needs documented attempt accounting.
Structure's initial draft and configured research synthesis are normal stages,
not permission for unlimited repairs. Repairs must not restart research or extend
a run past its deadline. Return completed portions when the configured bound ends.

## Proposed data needed beyond prose

Plan a versioned mapping for: artifact quality state; experimental status;
assumptions; issue location/severity; repair count; approval/source snapshots;
method prerequisites and limits; beat-to-shot relationships; resource requirements;
and proposed core-message changes awaiting confirmation. These are concepts,
not approved new JSON key names. Distinguish professional quality, feasibility,
user approval and demonstrated advertising effect; a single `ready` boolean
cannot safely stand for all four.

The backend must support a valid zero-method result and one-direction result.
For zero qualifying Ideas, return a typed outcome describing the gap rather than
creating fake direction content. A discussion draft can retain readable content
and issue locations without asserting valid references or production readiness.
Create migrations/contracts together with consumers; preserve historical projects
and exact approved revision checks. No global approval step for Structure is added.

## Proposed observability and versioning

Record the complete instruction dependency digest, app/provider/model versions,
input revisions and hash, research snapshot, language, stage times, cache state,
repair count, final status and known/unknown usage. Cache keys must change when
semantic instructions or relevant inputs change; do not reuse stale artifacts as
if they were produced under the new rules. Preserve old results and provenance.

No actual key, full private prompt or video should be dumped into telemetry.
Credential replacement and language switching must preserve operation safety.
Use the host's existing authentication, capability and account-limit handling.

## Suggested implementation order

1. Agree semantic output mappings and a safe draft result contract with Natalie
   and Belinda; lock a small development corpus with Haoyang.
2. Implement the loader/version record and shared evidence/context handling.
3. Integrate Structure rules and one-repair/zero-method behavior.
4. Integrate Ideas differentiation, flexible candidate count and experiments.
5. Integrate compact storyboard presentation plus separate production notes and
   safe draft status, target-duration decisions and experimental continuity.
6. Verify deterministic fixtures and a small manual rubric calibration before
   freezing a candidate for Andrea's formal model comparisons.

Keep ordinary software regression tests separate from model-quality evaluation.
The app's earlier 730-test result is historical, not validation of this new package.
Do not merge or deploy an implementation based on the documentation's approval.
