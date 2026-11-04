# Model/API evaluation — Andrea
Date: 2026-11-03

## Evaluation status

Model selection remains provisional. The approved Lei Jun video and annotations are still required for the formal baseline.

## STR-001 — Structure module

- **Model:** `gpt-6.1-sol`
- **Prompt:** `structure-v2-evidence-mechanisms`
- **Fixture:** Synthetic LumaCup analysis; not verified against real media
- **Execution:** Successful live API request
- **Latency:** 24.152 seconds
- **Schema validation:** Passed
- **Event-reference integrity:** Passed
- **Referenced input events:** 10/10 valid; zero unknown references
- **Output:** 6 nodes, 7 edges, 2 methods, 0 research gaps
- **Quality:** Preliminary qualitative review only; no formal reviewer score
- **Estimated API cost:** $0.022146 (one attempt, cache miss; provider billing unconfirmed)

### Findings

The generated graph distinguishes observations from inferences, connects visible evidence to communication mechanisms, and proposes two reusable creative methods. It avoids asserting real product performance, inventory availability, or measured audience response.

Potential follow-up issues include the classification of the synthetic disclaimer as `source_claim` and whether an empty `research_gaps` list is appropriate.

### Recommendation

Retain `gpt-6.1-sol` as the provisional Structure candidate. Do not treat synthetic-fixture performance as evidence of real-video accuracy or make a final model selection before the approved baseline.

## Next steps

1. Reconcile STR-001 token usage and estimated cost with local diagnostics.
2. Review the approved Lei Jun video and annotations when available.
3. Run the formal baseline and compare model quality, latency, validation reliability, and cost.

## STR-002 — Structure repeatability

- **Model:** `gpt-6.1-sol`
- **Fixture and prompt:** Same synthetic LumaCup input and Structure prompt as STR-001
- **Execution:** Successful; schema validation passed
- **Latency:** 21.953 seconds
- **Estimated API cost:** $0.019326 (latest matching usage record; attribution provisional)
- **Cache:** Miss (latest matching usage record)
- **Graph:** 5 nodes, 6 edges, 2 methods, 0 research gaps
- **Evidence integrity:** 10/10 referenced event IDs valid; zero unknown
- **Comparison:** 10/10 event coverage overlap with STR-001
- **Quality:** Preliminary qualitative review; no formal score

Both outputs describe the same principal communication mechanisms:
object introduction, labeled component motion, visible color alternatives,
audio cues, and a progression toward preference consideration.

STR-001 explicitly represented the synthetic disclaimer as a separate node,
whereas STR-002 did not. This illustrates that identical event coverage does
not guarantee identical emphasis or completeness.

**Conclusion:** Preliminary structural consistency is encouraging, but two
synthetic runs cannot establish real-video accuracy or statistical reliability.

## STR-003 — Ambiguous evidence and hallucination resistance

- **Model:** `gpt-6.1-sol`
- **Fixture:** Synthetic LumaCup analysis with four deliberately ambiguous events
- **Execution:** Successful; schema validation passed
- **Latency:** 21.022 seconds
- **Estimated API cost:** $0.019381 (latest matching usage record; provisional attribution)
- **Cache:** Miss (latest matching usage record)
- **Graph:** 5 nodes, 5 edges, 1 method, 2 research gaps
- **Provisional quality score:** 3/3 (assistant review, not independently adjudicated)

### Findings

The model correctly avoided claiming that the lid was removable,
that the final colored shapes represented confirmed product variants,
or that the ambiguous first chime intentionally synchronized with movement.

It explicitly acknowledged the unreadable intermediate label and
unresolved component relationship. Two relevant research gaps
identified missing evidence about the label, movement, product
variants, and exploration destination.

The output retained a useful evidence-qualified interpretation
of the final exploration invitation without inventing measured
engagement, inventory, or commercial outcomes.

**Conclusion:** STR-003 passes the provisional hallucination-resistance
criteria for this synthetic fixture. This does not establish reliability
on real video or across a larger evaluation dataset.

**Estimated combined API cost for STR-001 through STR-003:**
$0.060853; provider billing unconfirmed.

## STR-004 — Complex evidence testing

- **Model:** `gpt-6.1-sol`
- **Fixture:** Synthetic 20-second LumaCup sequence; 20 events across five scenes
- **Execution:** Successful; output schema validated
- **Latency:** 27.066 seconds
- **Estimated API cost:** $0.0251535 (latest matching usage record; provisional attribution)
- **Cache:** Miss; one attempt
- **Graph:** 6 nodes, 6 edges, 2 methods, 0 structured research gaps
- **Evidence integrity:** 19/20 known events referenced; 0 unknown references
- **Provisional quality score:** 3/3 (assistant review; not independently adjudicated)

### Findings

The model preserved the distinction between fictional product framing
and evidence of actual product performance. It classified easy-open
usability, speed superiority, and audience approval as source claims,
not verified results.

The graph coherently connected all five scenes, from concept
introduction through demonstration, comparison, represented audience
approval, and the final exploration invitation.

It did not invent a validated speed benchmark, customer testimonials,
physical product test, or functional purchase destination.

### Limitations

- The background-music event `s4_intro_music` was not referenced.
- No structured research gaps were produced, although missing evidence
  was identified within node explanations and method conditions.
- The quality score is provisional and based on one synthetic fixture.
- The internal estimated cost is not confirmed provider billing.
- Formal evaluation on approved real video remains pending.

**Estimated cumulative API cost for STR-001 through STR-004:**
$0.0860065; provider billing unconfirmed.

## STR-005 — Evidence perturbation testing

- **Model:** `gpt-6.1-sol`
- **Fixture:** Controlled modification of STR-004; 20 events, five scenes
- **Execution:** Successful; output schema validated
- **Latency:** 26.372 seconds
- **Estimated API cost:** $0.025566 (latest matching usage record; provisional attribution)
- **Cache:** Miss; one attempt
- **Graph:** 6 nodes, 5 edges, 2 methods, 2 research gaps
- **Evidence integrity:** 19/20 known events referenced; 0 unknown references
- **Provisional quality score:** 3/3 (assistant review; not independently adjudicated)

### Controlled comparison against STR-004

Three input observations were deliberately weakened:

1. **Opening motion:** The model stopped asserting that the top visibly
   opens, separates, or returns. It retained the on-screen easy-open
   claim but explicitly distinguished it from demonstrated usability.
2. **Speed comparison:** After the comparison heading became unreadable,
   the model stopped attributing an explicit speed-superiority claim
   to the video. The comparison node changed from a source claim
   to an observation.
3. **Audience approval:** After the popularity heading became unreadable,
   the model described illustrated smiles and applause-like audio
   as emotional cues rather than an explicit popularity claim.
   This node also changed from a source claim to an observation.

Two structured research gaps were generated, compared with zero in
STR-004. They concerned unreadable overlays and whether the final
exploration invitation has a functioning destination.

### Limitations

- The background-music event `s4_intro_music` remained unreferenced.
- The model described the click as accompanying movement but did not
  assert that it proved a physical mechanism.
- The quality score is provisional and based on one controlled
  synthetic comparison.
- The internal cost estimate is not confirmed provider billing.
- Formal evaluation on approved real video remains pending.

**Estimated cumulative API cost for STR-001 through STR-005:**
$0.1115725; provider billing unconfirmed.

## STR-006 — Contradictory evidence and conflict resolution

- **Model:** `gpt-6.1-sol`
- **Fixture:** Synthetic LumaCup; 20 events, five scenes
- **Execution:** Successful
- **Latency:** 27.634 seconds
- **Estimated API cost:** $0.0272085 (latest matching usage record; provisional attribution)
- **Cache:** Miss; one attempt
- **Graph:** 7 nodes, 7 edges, 2 methods, 1 research gap
- **Evidence integrity:** 16/20 events referenced; 0 unknown references
- **Provisional quality score:** 3/3 (assistant review; not independently adjudicated)

### Contradiction assessment

1. **Usability:** The model identified two unsuccessful animated opening
   attempts despite the “EASY-OPEN DESIGN” claim. It did not infer
   demonstrated ease or a successful opening.
2. **Performance:** The model recognized that the displayed 8-second
   LumaCup task is slower than the 5-second comparison, contradicting
   “FASTER THAN STANDARD.” It did not treat the figures as validated
   real-world measurements.
3. **Audience approval:** The model recognized that frowning illustrated
   figures and thumbs-down gestures oppose “PEOPLE LOVE IT.” It did
   not interpret the illustrations as actual customer feedback.

The model additionally created a shared claim-support mismatch inference
and linked it to the final exploration invitation.

### Limitations

- Four events were unreferenced: `s4_compare_audio`, `s4_cta_chime`,
  `s4_intro_music`, and `s4_intro_visual`.
- One research gap concerned whether the contradictions were intentional
  irony or an internally inconsistent concept presentation.
- The evaluation uses synthetic structured observations rather than
  direct real-video perception.
- Quality scoring is provisional and not independently adjudicated.
- Provider billing is unconfirmed; the latest matching usage record
  is provisionally attributed to STR-006.
- Formal approved real-video evaluation remains pending.

**Estimated cumulative API cost for STR-001 through STR-006:**
$0.138781; provider billing unconfirmed.
