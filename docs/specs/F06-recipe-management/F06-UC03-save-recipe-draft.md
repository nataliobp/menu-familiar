# F06-UC03 — Save a recipe draft

- **Status:** V1 baseline
- **Milestone:** M6
- **Dependencies:** F06-UC02

## Objective

Save partial authored recipe without falsely declaring it complete.

## Application and web contract

`SaveRecipeDraft(dish_id, recipe_data, expected_version, slot_context=None)`; POST `/recepta/draft/`; structural validation only; prep can be blank and named lines can have unknown quantities. Invalid entered quantities still fail. Use the matching catalogue or editable-slot route.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Validate source form, build RecipeContent; if no published revision exists, this draft is effective provisional content, else keep published effective.
2. Save draft under dish aggregate version; canonical ingredient identity resolution. If effective snapshot changes, refresh current/future selected slots and M7 reconcile; past frozen.
3. Commit then indicate `Esborrany desat`, completeness status and edit link.

## Alternative and failure flows

- Invalid line/unknown dish/stale version returns without partial save.
- Identical draft no-op; failure during fan-out rolls back all. No recipe generated from dish name.

## Acceptance criteria and automated scenarios

- Save named unknown-quantity lines and valid known amounts and reopen with both intact. An effective first draft contributes only its known quantities and explicit al gust items, with an incomplete warning when M7 is available.
- With existing publication, updating draft preserves effective published snapshot/list; past never updated.
- Validation error preserves input; multiweek failure rollback.

## Implementation tasks and boundaries

RecipeRecord draft codec, versioned Dish aggregate, resolve ingredient label/key consistently; snapshot refresh helper runs only if effective content/status changes.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Save partial demo prep/ingredients, reopen, verify status. After published revision, edit draft and verify effective quantities unchanged.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
