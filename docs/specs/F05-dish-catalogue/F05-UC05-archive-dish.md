# F05-UC05 — Archive a dish

- **Status:** V1 baseline
- **Milestone:** M5
- **Dependencies:** F05-UC01, F02 planning

## Objective

Retire a dish from new selections without deleting its history or current assignments.

## Application and web contract

`ArchiveDish(dish_id, expected_version)`; POST `/plats/<id>/archive/`; explicit confirmation; sets archived true only.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. From detail press `Arxiva el plat`; explain existing menus retained and new selections unavailable.
2. Check current version, set flag, persist. No changes to slots/recipe/history; catalogue archived view includes it.
3. Picker excludes archived; assigned snapshot still editable by moving/removing/replacing with active dish.

## Alternative and failure flows

- Cancel unchanged; already archived no-op at current version; stale/missing rejected.
- No cascading deletion, no loss of generated shopping contributions.

## Acceptance criteria and automated scenarios

- Archive planned dish -> excluded from all pickers, active list; selected occurrences intact including history; recipe remains.
- M7 list totals unchanged; attempting assign forged ID rejected; restore possible.

## Implementation tasks and boundaries

Archive flag + CAS; query filters and application selection revalidation; no physical delete route/model action.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Archive assigned synthetic dish; confirm it disappears from picker but stays in plan, open archived list.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
