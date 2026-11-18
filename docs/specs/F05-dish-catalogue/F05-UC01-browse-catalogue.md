# F05-UC01 — Browse the dish catalogue

- **Status:** V1 baseline
- **Milestone:** M5
- **Dependencies:** M0 import; F03 basic catalogue projection

## Objective

View the catalogue, including clear recipe and archived status.

## Application and web contract

`BrowseCatalogue(category_key=None, archived=False, q=None) -> CatalogueView`; GET `/plats/`. Default active, optional category any membership, archived-only view; stable name casefold then ID sorting (not picker ranking).

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open Plats, see active dish names, categories, preference/special badge and recipe status.
2. Filter category or select `Arxivats`; click dish detail with recipe link when built.
3. No duplicate rows; create action available, empty state for no archived/no category matches.

## Alternative and failure flows

- Invalid category/filter rejected; missing records not fabricated; no direct deletion.
- Do not expose database internals or private data in logs/public fixtures.

## Acceptance criteria and automated scenarios

- Synthetic active dishes appear once and categories shown, archived tab separate; category union filter works.
- List and details GET unchanged DB; long names readable on mobile/tablet.

## Implementation tasks and boundaries

Read projection from DishRepository, category options; server templates; use existing picker query normalization without sharing temporal rank.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Browse catalogue, filter a category, inspect one selected dish and archived tab; check no duplicates.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
