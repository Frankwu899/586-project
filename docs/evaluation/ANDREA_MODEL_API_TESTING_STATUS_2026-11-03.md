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
- **Cost:** Not yet reconciled with provider usage diagnostics

### Findings

The generated graph distinguishes observations from inferences, connects visible evidence to communication mechanisms, and proposes two reusable creative methods. It avoids asserting real product performance, inventory availability, or measured audience response.

Potential follow-up issues include the classification of the synthetic disclaimer as `source_claim` and whether an empty `research_gaps` list is appropriate.

### Recommendation

Retain `gpt-6.1-sol` as the provisional Structure candidate. Do not treat synthetic-fixture performance as evidence of real-video accuracy or make a final model selection before the approved baseline.

## Next steps

1. Reconcile STR-001 token usage and estimated cost with local diagnostics.
2. Review the approved Lei Jun video and annotations when available.
3. Run the formal baseline and compare model quality, latency, validation reliability, and cost.
