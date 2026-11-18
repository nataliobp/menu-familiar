# F06-UC01 — View a recipe

- **Status:** V1 baseline
- **Milestone:** M6 (slot detail scaffold M2)
- **Dependencies:** F05-UC01; F01-UC02 historical snapshot

## Objective

Consult dish ingredients and preparation for two adults, including incomplete status.

## Application and web contract

`GetRecipe(dish_id, week=None, position=None) -> RecipeView`; GET `/plats/<id>/recepta/` for live, slot detail GET for frozen snapshot; if week supplied validate selected slot and matching ID.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Read from catalogue effective recipe or exact selected-slot snapshot.
2. Display name, `Per a 2 adults`, quantities/units/notes/preparation if authored; missing/draft labels; published with unpublished changes shows editor hint on live view.
3. Historical view has no edit/navigation into live recipe masquerading as snapshot. Edit from the catalogue (active or archived) or an editable selected slot. Explain that the recipe is shared.

## Alternative and failure flows

- Missing recipe is valid empty state `Recepta pendent`, not 404; nonexistent dish/slot 404.
- Never retrieve current catalogue to fill absent historical content; no invented preparation/amount.

## Acceptance criteria and automated scenarios

- Imported/missing dish detail displays pending without fabricated ingredients.
- Draft shows provisional content, published shows effective version; past snapshot preserves old quantities/name after republish.
- GET no writes, escaped preparation and mobile detail accessible. Current and future slot detail link to the contextual editor; past detail has no editor link.

## Implementation tasks and boundaries

Effective recipe projection and snapshot DTO; update slot detail without separate business logic; web tests for source isolation.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Open missing recipe; after draft/publish compare live and historical detail, verify quantities for two adults.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
