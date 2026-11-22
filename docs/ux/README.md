# Family Menu V1 — visual design handoff

**Status:** consolidated V1 visual reference. Use the [V2.2 product corrections](../specs/V2.1-V2.2.md) for current interaction behavior. This package replaces both legacy Spanish mockup boards. Do not use the old mockups or their JSON state files for implementation. No family data is required to review this deliverable.

## Contents

- `index.html`: self-contained offline design review board, grouped visual wall and interactive prototype. Open in an ordinary desktop browser (JavaScript enabled), then use the on-screen device switch. No dependencies, network requests, images or external fonts. The visual wall renders one independent preview per state when its group is expanded. The free prototype starts from a deterministic fictitious dataset. Changes remain in memory until reset/reload; they do not reach the server or survive reload.
- `STATE-MATRIX.md`: all 74 states with expected interactions and references to all 30 use cases.
- `states.json`: same inventory in machine-readable form. Titles and example copy are in standard Catalan.
- `VALIDATION.md`: checks performed and explicit limitations.

## Review and implementation

Read `../specs/05-web-ux.md` first. The board is the visual reference for the product; the approved domain rules, API/use-case contracts and security/transaction requirements remain normative. If a visual example conflicts, record and resolve the difference before implementation. Do not copy board controls, demo dataset, example date, injected error controls or in-memory JavaScript business logic into production. X02 demonstrates review of current and typed values before resubmission; X05 injects a failed first save while preserving the form. Unknown draft amounts and the editable-slot recipe entry point are demonstrated. The real implementation remains Django, DDD and ports/adapters as specified. Keep semantic templates, local CSS, minimal progressively enhanced JS, server-side validation and persistence. Reuse visual hierarchy, spacing, colors and interaction patterns where appropriate rather than transcribing the whole prototype source.

Design constraints: four product destinations, landscape left navigation, portrait bottom navigation, minimal card actions, no hard category/meal eligibility restriction, no images or access management, no other home modules. Show historical weeks without write controls. The seeded dataset is fictional (19 example dishes, not a mock import of 57 private records). Quantities and recipes are solely illustrative. Demo time is fixed to 18 November 2026, with Monday 16 November as current week; real time comes from the application clock. The application layout is responsive; board navigation and thumbnail scales are review tooling only.

For review: use the index to select states, switch between 800×480 / 1024×600 landscape and 390×780 / 360×780 portrait, open the grouped visual wall and inspect representative flows. The loading, failure, conflict and historical-write-denial cases are simulated presentation states, not evidence of real HTTP errors, concurrency safety or rollback. Browser refresh of an example resets it. Verify actual behavior with the production automated tests and owner QA after implementation.

This directory may be committed as documentation after reviewing the staged diff. Keep the original mockups, actual catalogue, personal recipes, DB, env files and backups out of Git. Do not include this review board in the app's runtime static files or route it as a product page.
