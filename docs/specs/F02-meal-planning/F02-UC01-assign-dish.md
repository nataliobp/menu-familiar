# F02-UC01 — Assign a dish to an empty slot

- **Status:** V1 baseline
- **Milestone:** M2
- **Dependencies:** F01-UC01–02; M0 import; basic F03-UC03

## Objective

Choose an existing active dish to fill a pending meal.

## Application and web contract

`AssignDish(week, position, dish_id, expected_version)` -> updated menu; POST slot `/assign/`. Slot pending; week editable; dish active, with any category or meal preference. Version 0 starts a missing week atomically.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open pending slot, show the suggested category when set and allow browsing all candidates; tap a dish to submit the selection and version.
2. Inside transaction check week/editability/version and pending state; load active dish, create snapshot, call aggregate assign, clear prior undo if changed.
3. Save; PRG displays selected name immediately. Reconcile shopping if available M7.

## Alternative and failure flows

- Unknown/archived dish, skipped/occupied slot, stale version: no write; archived between display and click must fail.
- No match to category/preference still allowed; repeated dish across slots allowed. Cancel no mutation.

## Acceptance criteria and automated scenarios

- Assign any ordinary/special or opposite-preference dish to pending; selected snapshot and version persist.
- Assign same dish to another slot succeeds; unrelated 13 slots unchanged.
- POST for archived, historical, occupied or stale request rejected; direct GET cannot assign.

## Implementation tasks and boundaries

Domain assign enforces state; application snapshot active dish via repository, CAS save; web form validates IDs; add test hooks for M7 reconciliation.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Choose a dish from all list for Monday lunch, verify slot survives reload. Assign same dish to dinner and verify both persist.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
