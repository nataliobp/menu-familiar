# F01-UC01 — Create a weekly menu

- **Status:** V1 baseline
- **Milestone:** M2; extend in M3
- **Dependencies:** F04-UC01–03; M0 catalogue/category foundation; F01-UC02 read model (develop together)

## Objective

Create an independent plan for an explicit week from the current reusable template.

## Application and web contract

`CreateWeeklyMenu(week: date) -> WeeklyMenuView`; POST `/menu/<week>/create/`. Input Monday ISO date; clock supplies current Monday. Create is idempotent by week key. In M2 expose current week only; M3 permits future.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Validate date and editability; load template with exactly 14 positions.
2. If menu already exists return it unchanged (do not reset or recopy suggestions). Otherwise instantiate `WeeklyMenu.from_template` with all positions pending, copy category keys and display labels, no dish snapshots, version 1.
3. Persist menu and its 14 slots in one transaction with shopping projection version 1. Redirect to specific week; show creation confirmation. GET alone never creates.

## Alternative and failure flows

- Malformed date/non-Monday: reject; absent past week: read-only, no create.
- Concurrent duplicate create: uniqueness resolves to a single unchanged menu, reload after rollback if needed. Template/slot persistence error rolls back whole creation.

## Acceptance criteria and automated scenarios

- Given a template with 14 positions and one suggested category, when a new current week is created, then exactly 14 pending slots and copied suggestion values persist, zero dishes.
- Changing template afterwards leaves created menu unchanged; repeating create after assignment preserves assignment/version.
- Creating future week in M3 succeeds; creating missing past or non-Monday fails; injected child-write failure leaves no week or slots.

## Implementation tasks and boundaries

Add WeekStart/SlotState/MenuSlot/WeeklyMenu aggregate and init method, repository insert with unique key, projection DTO, migration. No history singleton. Integration test transaction rollback and duplicate create.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Open the current missing week, select `Crea el menú`, refresh; check all 14 empty slots. Change template and return: the original labels remain.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
