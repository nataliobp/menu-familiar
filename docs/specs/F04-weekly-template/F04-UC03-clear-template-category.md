# F04-UC03 — Leave a template slot free

- **Status:** V1 baseline
- **Milestone:** M1
- **Dependencies:** F04-UC02

## Objective

Remove the suggested category without skipping a meal.

## Application and web contract

`ClearTemplateCategory(position, expected_version)`; same template form nullable category choice `Lliure` (empty value normalized to None).

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Select `Lliure`, save; clear category on target slot only.
2. Persist; show free label. Future week copies null suggestion and picker defaults to all.
3. Existing menu remains untouched; slot in template has no pending/selected/skipped state.

## Alternative and failure flows

- Already free no-op; invalid/stale rejected; no category deletion.

## Acceptance criteria and automated scenarios

- Clear previously set slot; null stored, `Lliure` displayed; all 14 positions remain.
- At M2, a new week from a free slot starts pending with no filter; existing copied labels unaffected.

## Implementation tasks and boundaries

Reuse template view/form and separate clear domain intent; test null choice and no-op.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Clear saved category, reload and verify `Lliure` not `Omès`.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
