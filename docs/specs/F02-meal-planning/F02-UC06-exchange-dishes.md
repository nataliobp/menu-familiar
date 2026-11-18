# F02-UC06 — Exchange dishes between occupied slots

- **Status:** V1 baseline
- **Milestone:** M4
- **Dependencies:** F02-UC05

## Objective

Swap two selected dishes atomically without requiring them to match destination categories.

## Application and web contract

`ExchangeDishes(week, first, second, expected_version)`; POST `/exchange/`. Both selected and same editable week; distinct positions. Equal snapshots/same position no effective change.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Use move mode, select another occupied slot.
2. Swap exact dish snapshots, not suggestion/position. Record prior values and version for undo.
3. Persist both together, reconcile M7 (same totals) and update recency dates.

## Alternative and failure flows

- Pending/skipped target belongs to move; do not silently switch operation on stale UI.
- Same position/equal snapshots no-op; past/stale fail; rollback all on partial write error.

## Acceptance criteria and automated scenarios

- Swap A and B between different days/meal types; both selected, counts preserved and original suggestions unchanged.
- Opposite preference/category not blocked; archived existing selection movable.
- Injected partial-write failure leaves both unchanged; generated shopping totals and matching state unchanged; undo available.

## Implementation tasks and boundaries

Reuse movement UI and aggregate transaction; exchange explicit transition, not two independent replacements; test rollback and equal snapshots.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Swap two dishes of different categories; verify both labels and dishes, then reload. No dish lost or duplicated.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
