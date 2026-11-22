# F07-UC01 — Generate and view the weekly shopping list

> Historical V1 contract, superseded by the [V2.5 ingredient reminder](../V2.5-SHOPPING-REMINDER.md).

- **Status:** V1 baseline
- **Milestone:** M7
- **Dependencies:** F01–F04 implemented; F06-UC01–04; M4 atomic writes

## Objective

See aggregated ingredients and honest coverage for a selected week.

## Application and web contract

`GetShoppingList(week) -> ShoppingView`; GET `/compra/<week>/`; version pair `(menu_version, overlay_version or 0)`, base rows, overrides/manual/orphans, coverage and editability.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Load week snapshots, aggregate every selected occurrence in pure Decimal function; canonical ingredient+unit family key, exact conversions, taste separate.
2. Overlay matching adjustments/checks, display manual separate and orphan review. Report pending slots and missing/draft per occurrence; skipped no contribution.
3. Read-only historical projection from frozen values; absent week show plan/create link (not extras until week exists). No state initialization on GET.

## Alternative and failure flows

- Incompatible units separate; unquantified not zero; no missing data inferred.
- DB/projection failure not fake empty list. Empty existing week supports extras; all skipped intentionally empty.

## Acceptance criteria and automated scenarios

- Synthetic quantities 160g+0.18kg -> 340g; repeated occurrence adds 160g; count and weight separate; taste no number.
- No selected dishes/pending/draft/missing/skipped combinations show accurate coverage; manual rows independent.
- Plan/recipe update recalculates base and preserves applicable overlays atomically; past list unchanged after later edits.

## Implementation tasks and boundaries

Add ShoppingListState, aggregate_ingredients/reconcile helpers, read DTO/template, overlay migrations; integrate all earlier plan/effective-recipe writes; exact arithmetic and transaction tests.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Plan two synthetic recipes, inspect converted totals, repeat one, remove one, inspect coverage and compare past list.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
