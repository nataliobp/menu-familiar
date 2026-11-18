# F02-UC03 — Remove a dish from a slot

- **Status:** V1 baseline
- **Milestone:** M2
- **Dependencies:** F02-UC01

## Objective

Clear a selected meal so it can be planned later.

## Application and web contract

`RemoveDish(week, position, expected_version)`; POST `/remove/`. Requires selected in editable week; sets pending and null snapshot, preserves suggestion.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Choose `Retira el plat` from selected actions.
2. Validate version and selected state; remove snapshot, set pending, invalidate prior undo; update recency and reconcile.
3. Return pending picker affordance; no deletion of dish/catalogue recipe.

## Alternative and failure flows

- Past/stale/invalid transition rejected. Already pending retry may report no-op only if same current version; skipped is not removal.
- Cancel confirmation or leave detail changes nothing.

## Acceptance criteria and automated scenarios

- Remove selected dish -> pending/no snapshot; category label unchanged; catalogue unchanged.
- If A exists elsewhere, latest date recalculated from remaining occurrences; absent entirely becomes never-planned.
- M7 removes contribution, preserves manual products and orphan adjustments. Stale/past cannot remove.

## Implementation tasks and boundaries

Add simple aggregate remove method and shared planning mutation transaction. Tests for slot state and recency query.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Remove from a populated slot, check `Tria un plat`; choose new dish. Verify it is not marked `Omès`.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
