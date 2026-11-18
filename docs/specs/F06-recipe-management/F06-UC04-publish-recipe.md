# F06-UC04 — Publish a complete recipe

- **Status:** V1 baseline
- **Milestone:** M6
- **Dependencies:** F06-UC03

## Objective

Make an authored complete recipe effective for current/future planning and shopping.

## Application and web contract

`PublishRecipe(dish_id, recipe_data, expected_version, slot_context=None)`; POST `/recepta/publish/`; validate full editor data (not necessarily prior draft saved), nonblank preparation, at least one line, and every line quantified or explicitly al gust. Unknown amounts block publication. Accept catalogue and editable-slot origins.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Validate all fields and completeness; publish immutable copy as effective, clear working draft (or identical no-op when no pending draft).
2. Atomically save dish version/recipe plus refresh all current/future selected snapshots; M7 reconcile affected lists. Historical snapshots untouched.
3. Show `Recepta publicada` and effective ingredients. Later edits create/modify draft without replacing publication until next publish.

## Alternative and failure flows

- Incomplete/invalid -> field errors, keep form and existing publication.
- Stale/past-boundary/fan-out error -> no partial publication; no image requirement.

## Acceptance criteria and automated scenarios

- Publish invalid no prep/no ingredient rejected; unknown quantity rejected; valid quantified and explicitly al gust lines accepted.
- Publish updates all selected current/future occurrences and draft becomes published; past old version unchanged.
- Publish second revision after draft changes: effective changes only then; injected failure updating another week rolls everything back.

## Implementation tasks and boundaries

Pure publish completeness rule; immutable RecipeContent; transaction + CAS across dish and weeks; test effective-vs-draft and historical isolation.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Publish incomplete then correct and publish demo recipe; compare current/future and past snapshots and shopping after M7.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
