# F03-UC03 — Browse all dishes for a slot

- **Status:** V1 baseline
- **Milestone:** M2 first picker slice
- **Dependencies:** M0; F01-UC01–02

## Objective

Select any active catalogue dish independently of template or meal preference.

## Application and web contract

`BrowseAllSlotDishes(week, position, q=None)` uses GetDishRecommendations mode=all; GET picker `mode=all`. Early M2 stable ID ordering before later ranking slice.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open unfiltered picker (M2 initial default), or press `Mostra tots els plats` from suggestions; clear category but retain or explicitly clear search.
2. List all active candidates, once per dish; after ranking introduced apply full ordering even without category filter.
3. Selecting invokes assign/replace POST, not GET; show cancel and return to suggestion filter.

## Alternative and failure flows

- Empty catalogue: useful empty state, no mandatory creation; offer catalogue link when M5 exists.
- Archived not selectable; no restrictions by category, preference or special flag.

## Acceptance criteria and automated scenarios

- All active dishes listed once regardless of membership or preference; opposite meal and special can be chosen.
- After rank implementation mode all preserves full precedence; switching filter leaves persisted template/slot suggestion unchanged.
- GET/cancel does not mutate menu; no-results state clear.

## Implementation tasks and boundaries

Implement base CandidateView + picker template before advanced filtering; reuse for ReplaceDish; unit/integration/web query tests.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Open a pending slot; verify all dishes (synthetic catalogue), pick one not matching suggestion. Return to suggested view and check template unchanged.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
