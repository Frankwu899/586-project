# Implementation ownership

Branch: `feat/integration/creative-workspace-demo`. Base: `dba985b20d0a012a7b1e90b174fe8b30c96b58eb`, containing PR #4 `243db859353abf5a8ccc70de2028ed0b706da70c` and PR #3 `da95ad3325a04b3b9f01cc7cb02a03af353208b5`.

Agents share a working directory. They use disjoint writes; only the coordinator commits and publishes. The coordinator owns integration decisions and reconciles contract changes. This is not six conflicting branches from old main.

| Owner | Exclusive write boundary |
|---|---|
| backend_core | models, storage, service, API, editor/migration modules, generated contracts, core backend tests |
| creative_backend | creative provider, sample creative adapters, creative tests; coordinate adapter entry point with core |
| workspace_shell | App, shared styles/UI, generic editor draft hook/registry and shell tests |
| reference_ui | AnalysisReview, VisualDetailsEditor, M5 components/styles/tests |
| directions_ui | Directions, direction-specific components/styles/tests |
| production_ui | Production, printable document/export components/styles/tests |
| coordinator | English decision/spec records, M9 evaluation guide, demo launcher/package, cross-module integration, browser regression, final review and Git |

Model/schema decisions precede generated frontend consumers. Core alone writes service/API; provider agent exposes a request-scoped language adapter. M7/M8 have one writer because they share Production. No agent edits another owner's file without a handoff. Existing M2 contracts and behavior are retained.
