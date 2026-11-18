# F05-UC03 — Create a dish

- **Status:** V1 baseline
- **Milestone:** M5
- **Dependencies:** F05-UC01; M0 taxonomy

## Objective

Add a dish without needing a completed recipe.

## Application and web contract

`CreateDish(dish_data: DishInput, creation_token) -> DishView`; GET/POST `/plats/new/`; fields name, primary, secondary set, meal preference, special; initial archived false, no recipe, version 1.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open `Nou plat`, enter Catalan name and category choices, preference and special flag.
2. Validate nonblank name and known category keys, no duplicate/primary repetition, allowed preference/bool. Create with fresh ID; do not assume unique name.
3. Commit then detail, recipe status pending; eligible immediately for picker.

## Alternative and failure flows

- Invalid inputs return field errors preserving entries; cancel no write. Retry the same validated payload and token after a lost response. A new token may create another dish with the same name.
- DB error rollback entire row/category associations.

## Acceptance criteria and automated scenarios

- Create active synthetic dish with secondary category, no recipe, version 1; appears in matching pickers.
- New auto ID does not collide with imported explicit IDs. Invalid categories/empty name do not create partial dish.

- Concurrent and lost-response retries with one token return the same ID. A changed payload with that token gets 409. A rolled-back write does not consume the token.

## Implementation tasks and boundaries

DishInput validator/domain constructor, insert repository and FK/membership transaction. Tests for auto sequence after import and field errors.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Create synthetic dish with two categories and no recipe; verify catalogue and selection. Try invalid form and cancel.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
