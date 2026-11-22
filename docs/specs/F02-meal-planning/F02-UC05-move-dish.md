# F02-UC05 — Move a dish to another slot

- **Status:** V1 baseline
- **Milestone:** M4
- **Dependencies:** F02-UC01–04; F01-UC03

## Objective

Move selected dish to a pending or explicitly confirmed skipped slot in the same editable week.

## Application and web contract

`MoveDish(week, source: SlotPosition, destination: SlotPosition, expected_version, confirm_skipped=False)`; POST `/move/`. Source selected, dest pending/skipped, distinct positions.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open selected detail, `Mou o intercanvia`, choose destination; skipped target shows confirm with server-checked flag.
2. Domain copies selected snapshot to destination, source pending/null. A newly pending source shows the current suggestion for its position. Capture exact before/after pair and eligible version for undo.
3. One transaction saves both slots/undo and M7 reconciliation; return new week and undo availability.

## Alternative and failure flows

- Occupied target requires exchange, not overwrite. Same position/cancel no-op; cross-week invalid.
- Without skipped confirmation reject safely. Stale/past rejected; failure between writes rolls back both.

## Acceptance criteria and automated scenarios

- Move A from Monday lunch to Thursday dinner: exactly one A, origin pending, destination selected; labels unchanged.
- Confirmed skipped destination selected; cancel/unconfirmed leaves both states unchanged.
- Injected persistence failure after first child write leaves both originals and old undo intact; recency updates and M7 total unchanged.

## Implementation tasks and boundaries

WeeklyMenu.move, UndoRecord capture, transaction + CAS; two-tap web destination picker, no drag dependency; integration failure injection.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Two taps move to pending and to skipped (cancel then confirm). Reload; check original pending and undo visible.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
