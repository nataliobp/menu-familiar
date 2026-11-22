# F04-UC02 — Set or change a template category

- **Status:** V1 baseline
- **Milestone:** M1
- **Dependencies:** F04-UC01

## Objective

Assign one category suggestion to a position or replace previous suggestion.

## Application and web contract

`SetTemplateCategory(position, category_key, expected_version)`; GET editor/POST `/plantilla/<day>/<meal>/`; nonnull known category.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Tap position, tap one of the 13 categories to save immediately.
2. Validate position/category and current version; update one suggestion only, preserve other 13; no-op same value.
3. Commit then display `Plantilla actualitzada`. No existing week mutations.

## Alternative and failure flows

- Unknown/multiple category, invalid position/expired version: reject; preserve form choice on conflict.
- Cancel no change; category labels are advisory only.

## Acceptance criteria and automated scenarios

- Set lunch suggestion then change to B; reload retains B, other positions identical.
- Save same value no version bump; stale tab cannot overwrite newer edit.
- Empty slots in existing and virtual editable weeks show the latest hint on the next render. Selected, skipped and historical slots do not show a live hint.

## Implementation tasks and boundaries

Aggregate set_suggestion + CAS repository; choice form with category keys and translated labels; unit/integration tests.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Set Monday lunch, change it, refresh from another tab. Verify unrelated slots unchanged.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
