# F05-UC04 — Edit a dish

- **Status:** V1 baseline
- **Milestone:** M5
- **Dependencies:** F05-UC03; F01-UC03 history; F02 assignment

## Objective

Update catalogue metadata while preserving historical plans.

## Application and web contract

`EditDish(dish_id, dish_data, expected_version)`; GET/POST `/plats/<id>/edit/`. Metadata only; no identity/recipe/archive mutation in this command.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Load current values and version; validate edited name/categories/preference/occasion.
2. Inside transaction update dish via CAS; refresh snapshots for selected occurrences in current/future weeks only; preserve positions and suggestion labels; invalidate undo only if affected pair snapshot changed.
3. M7 reconcile if effective display/recipe projection affected; return detail.

## Alternative and failure flows

- Archived metadata editing allowed explicitly but still not selectable; missing/stale invalid no writes.
- Any multi-week fan-out failure rolls back dish and all affected weeks. No-op does not increment version.

## Acceptance criteria and automated scenarios

- Rename/change category of assigned dish: current/future display updated, past frozen; picker filters reflect new membership.
- Recipe status/content and old suggestions preserved; stale version rejected.
- Force failure while updating second week -> whole edit rolls back.

## Implementation tasks and boundaries

Dish metadata domain behavior, snapshot factory and RefreshEditableDishSnapshots helper; transaction over affected sorted weeks; integration fan-out/concurrency tests.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Edit synthetic assigned dish, compare current and future with historical detail, verify suggestion unchanged.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
