# F05-UC02 — Search the catalogue

- **Status:** V1 baseline
- **Milestone:** M5
- **Dependencies:** F05-UC01

## Objective

Locate dishes by name with category/archived filters retained.

## Application and web contract

`SearchCatalogue(q, category_key=None, archived=False)` same read query; GET `/plats/?q=...`; case- and accent-insensitive substring per the shared domain normalization contract, max 200.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Submit search; keep selected filter/status. Render matching names sorted deterministic name+ID.
2. Show no results and clear filters; click detail.

## Alternative and failure flows

- Empty query shows catalogue; unknown filters validation; escape special input.

## Acceptance criteria and automated scenarios

- Mixed-case unaccented query matches composed and decomposed accented names; category+search and archived-only composition correct.
- No results clear recovers, no duplicate multi-category dish and no writes.

## Implementation tasks and boundaries

Reuse catalogue query and q validation; no separate redundant repository; web tests for search and display escaping.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Search existing and nonexistent names, clear and switch archived tab.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
