# Remaining workspace implementation package

Read `docs/orchestration/DECISIONS.md`, current AGENTS.md, architecture/interfaces, the M2 report and the seven preserved M2 specifications. This package implements the confirmed post-M2 discussion; it does not replace M2 or the master-transfer archive.

Read in order: 01_PRD.md, 02_UIUX.md, 03_Contract_Impact.md, 04_Acceptance.md, 05_Implementation.md, 06_Integration_Summary.md. The coordinator is responsible for integration and final verification.

Current implementation source is PR #4 plus master transfer, not old main. Runtime dependencies, local databases/media and secrets do not travel through Git. No paid provider call or public hosting is required for the offline demo.
