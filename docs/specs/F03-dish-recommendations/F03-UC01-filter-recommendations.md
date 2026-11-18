# F03-UC01 — Find dishes by category and rank

- **Status:** V1 baseline
- **Milestone:** M2; M3 cross-week recency
- **Dependencies:** F03-UC03, F01-UC01–02; M0 catalogue; F02 assignment for recency

## Objective

Show context-relevant suggestions without restricting what can be chosen.

## Application and web contract

`GetDishRecommendations(week, position, category_key=None, query=None, filter_mode="suggested") -> PickerView`; GET `/triar/`. Suggested category default if set, category user override, mode all removes filter; picker action assign/replace and version.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Load slot (editable), category suggestion. Fetch active candidates where any membership matches effective filter; deduplicate by ID.
2. Optional name search conjunctive with filter. Obtain latest date by dish from persisted selected occurrences (M2 current only, M3 all weeks); rank ordinary/special, preferred/both vs other, never/oldest/newest, stable ID.
3. Render ordered list and category labels; allow all/search recovery. No write.

## Alternative and failure flows

- Unknown category -> validation not empty fake results; no matches -> clear filter/show all.
- No suggestion -> all; archived excluded. Future planned date counts per D06; not based on creation time.

## Acceptance criteria and automated scenarios

- Synthetic multi-member dish appears exactly once in each matching category, not unrelated; both equals preferred.
- Rank test spans all four occasion/preference tiers and never/older/newer/ties; ordinary opposite dominates special preferred.
- In M2 test removal, replacement and repeated occurrences. In M3 test future dates and in M4 move and undo. Test archive exclusion in M5. Each mutation must affect max date immediately.

## Implementation tasks and boundaries

Add pure rank_dishes with table-driven tests; adapter membership query distinct; latest_planned_dates batch projection, no N+1; M2 build unfiltered first and extend incrementally.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Choose a suggested category; inspect list and order with demo catalogue, switch category, choose dish outside original suggestion using all.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
