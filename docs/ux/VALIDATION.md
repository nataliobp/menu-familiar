# Prototype validation

## Consolidated V1 checks

- Parsed the embedded JavaScript and rendered all 74 initial states in Node with a minimal DOM stub. The embedded and JSON inventories and the Markdown matrix agree on IDs, copy and both directions of use-case coverage.
- Exercised accent-insensitive picker and catalogue searches, editable and historical recipe entry points, saving unknown draft quantities and rejecting publication, provisional shopping, skipped-slot reactivation and confirmed move with undo, related and unrelated refreshes, future recency, retained checks with updated quantities, exact quantity bounds, stale-form comparison, and the simulated fail-then-retry flow.
- Browser visual geometry, focus behavior and device checks were not rerun on this revision. A stub does not verify those properties. The board also cannot establish Django fallback behavior, HTTP status codes, concurrency, transactions or production persistence.

## Earlier browser evidence

- 74/74 scenario initial states loaded and rendered in Chromium in the 800×480 CSS viewport without JavaScript page exceptions or body-level horizontal overflow.
- 10 representative states (M01, M04, M07, T01, P01, D04, R03, C01, C06, X02) checked at 800×480, 1024×600, 390×780 and 360×780 (40 layout checks). No observed page/main/dialog-body horizontal overflow; the tested weekly and template grids fit vertically on landscape previews.
- Visual inspection of the review board, landscape weekly menu, and portrait weekly menu.
- 11 groups of Playwright interaction checks passed: assignment outside suggestion/replacement/removal, skip/reactivation, swap/move to omitted/undo, invalidation after subsequent edit, template snapshot plus future/past weeks, create dish/recipe validation/draft/publication/archive/restore, manual shopping/checks/adjustment/reset/removal, orphan discard, simulated conflict recovery, dirty-form handling, board state/device selection and grouped visual wall.
- Stable state IDs and traceability checked against all 30 specification filenames.

Limitations: the browser sandbox blocked navigation to both file:// and loopback HTTP URLs. The checks ran by loading HTML directly into Chromium, and the embedded preview/mural ran via `srcdoc`. Navigation through external full-size/new-tab links and opening a downloaded local file were not directly tested. The real devices, browser/device accessibility, language review, manual product acceptance, Django backend, data persistence, network failures, HTTP transactions, security and concurrency have not been certified. No production data or server were used. These checks are representative rather than exhaustive interaction coverage across every state/device combination. The prototype uses simplified in-memory JavaScript, not the normative persistence, Decimal arithmetic or transaction implementation. Browser and device checks on the consolidated revision and owner acceptance remain pending.
