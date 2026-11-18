# F02-UC07 — Undo the latest eligible movement

- **Status:** V1 baseline
- **Milestone:** M4
- **Dependencies:** F02-UC05–06

## Objective

Restore exact previous slot pair after latest move or exchange, once.

## Application and web contract

`UndoPlanningChange(week, expected_version)`; POST `/undo/`; same editable week; eligible UndoRecord whose version/state still matches. No timed expiry within editable week.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Show `Desfés` while eligible; submit current version.
2. Check prior record and affected slot integrity; restore both prior states/snapshots, preserve positions/suggestions, remove undo record, update version.
3. Commit pair and shopping/recency effects together; hide undo.

## Alternative and failure flows

- No record, stale version, past week, intervening planning edit or affected snapshot refresh: reject/no change.
- Unrelated snapshot refreshes preserve undo and rebase its eligible version. Other nonplanning edits leave it intact. Failure rolls back.

## Acceptance criteria and automated scenarios

- Undo move into pending restores original selected/pending, into skipped restores skipped; swap undo restores both.
- Reload before undo works; second undo unavailable; subsequent successful planning edit invalidates prior undo.
- A snapshot edit affecting either position invalidates undo, an unrelated refresh preserves it, and rollover blocks historical writes; forced failure rollback restores record and state.

## Implementation tasks and boundaries

UndoRecord persisted on WeeklyMenu; compare eligible version and state; if unrelated snapshot refresh increments menu version, rebase eligible version atomically. Tests cover no-op and conflict.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Move then undo after refresh; repeat swap, change a third slot and verify old undo no longer available.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
