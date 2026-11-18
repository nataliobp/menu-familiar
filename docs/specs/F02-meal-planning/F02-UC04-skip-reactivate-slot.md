# F02-UC04 — Skip or reactivate a slot

- **Status:** V1 baseline
- **Milestone:** M2
- **Dependencies:** F02-UC01–03

## Objective

Mark an intentionally unplanned meal, or reopen it for planning.

## Application and web contract

`SetSlotSkipped(week, position, skipped: bool, expected_version, confirm_remove=False)`; POST `/skip/` or `/reactivate/`; explicit desired state, not blind toggle.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Pending slot can be skipped directly from picker/action; selected requires confirmation because dish is removed.
2. Skip sets skipped and clears selected snapshot if confirmed. Reactivate skipped -> pending, no prior dish resurrected.
3. Preserve suggestion; clear undo on changed state; skipped contributes neither ingredients nor pending warning. Show Catalan `Omès` and `Torna a planificar`.

## Alternative and failure flows

- Selected skip without confirmation: no write; cancel safe. Skipped assignment not allowed until explicit reactivation (or confirmed move).
- Repeated same desired state no-op when version current; stale/past denied.

## Acceptance criteria and automated scenarios

- Pending -> skipped -> pending across reload; labels and null dish correct.
- Selected skip requires confirmation; after confirmed, contribution gone; reactivation not restore dish.
- All skipped week has no pending-coverage warning; stale post does not overwrite a changed slot.

## Implementation tasks and boundaries

Add enum transitions, POST confirmation server-side and display state. Domain tests for full transition table; M7 coverage.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Skip pending, reactivate, assign a dish, attempt skip and cancel, then confirm. Check `Omès` versus pending.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
