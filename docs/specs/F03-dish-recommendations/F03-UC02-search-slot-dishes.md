# F03-UC02 — Search dishes for a slot

- **Status:** V1 baseline
- **Milestone:** M2
- **Dependencies:** F03-UC01/03

## Objective

Find a dish by name in the current picker.

## Application and web contract

`SearchSlotDishes(week, position, q, category_key, filter_mode)` delegates GetDishRecommendations; GET picker `q` string max 200, no new service needed.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Type search or submit; case- and accent-insensitive substring matching per the domain normalization contract; empty q clears search.
2. Apply category filter if active plus same ranking, dedup and eligibility; preserve selected slot and picker action.
3. No results shows `No s’han trobat plats` and clear search/show all. Choose result normally (separate write case).

## Alternative and failure flows

- Malformed input handled; text escaped; no hidden category restriction after mode all.
- Cancel/back no writes or lost original replacement.

## Acceptance criteria and automated scenarios

- Query finds mixed-case matching synthetic names, not unrelated; accented and unaccented queries find both NFC and decomposed names without changing their display; category plus search intersection.
- Clearing returns ranked original list; no results recover; duplicate category membership no duplicates.
- Search does not create menu or alter slots.

## Implementation tasks and boundaries

Reuse same query and normalization helper; server-rendered GET form, optional debounce only with basic fallback. Web tests query escaping/context.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Search partial name, clear, search nonexistent, then choose `Mostra tots els plats` and select another.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
