# F05-UC06 — Restore an archived dish

- **Status:** V1 baseline
- **Milestone:** M5
- **Dependencies:** F05-UC05

## Objective

Make previously archived catalogue entry selectable again.

## Application and web contract

`RestoreDish(dish_id, expected_version)`; POST `/plats/<id>/restore/`; flag false only.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open archived detail, press `Restaura el plat`.
2. Validate version, restore same ID/metadata/recipe; commit and redirect detail/active list.
3. Recommendation ranking uses persisted historical occurrences of same ID.

## Alternative and failure flows

- Already active no-op; missing/stale rejected; do not create duplicate or reset recency.

## Acceptance criteria and automated scenarios

- Restore archived dish retains ID, memberships and recipe; selectable again under correct categories and ranking.
- Historic slots unchanged, no extra dish row.

## Implementation tasks and boundaries

Reuse catalogue mutation pattern; tests verify identity and archived filter.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Restore previously archived dish; locate in normal catalogue and assign to pending slot.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
