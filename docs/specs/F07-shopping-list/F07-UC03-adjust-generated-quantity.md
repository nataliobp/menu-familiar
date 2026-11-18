# F07-UC03 — Adjust and reset generated quantities

- **Status:** V1 baseline
- **Milestone:** M7
- **Dependencies:** F07-UC01–02

## Objective

Override an expected shopping amount without altering a recipe; preserve reviewable adjustments.

## Application and web contract

`AdjustGeneratedItem(week,key,amount,expected_version)`; `ResetGeneratedAdjustment(week,key,expected_version)`; POST `/adjust/` or `/reset/`; canonical key and absolute amount in displayed canonical unit.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Select existing quantified generated row, show base and override field; validate exact positive amount and version. Store absolute override with last base/name.
2. Reset matching row removes override (retains applicable check), base becomes effective. If generated key disappears after menu/recipe change, reconcile keeps override visible in orphan section with previous amount and name; reset orphan explicitly drops it.
3. If key returns, restore override automatically, checked false; manual rows unaffected.

## Alternative and failure flows

- Taste row cannot receive numeric override; unknown key not a valid adjustment; stale/historical rejected.
- Do not auto-convert orphan to manual item or discard adjustment. An override equal to the current base clears an existing override or is a no-op when none exists. Preserve the matching check. Use the full canonical quantity bound.

## Acceptance criteria and automated scenarios

- Override base 340g to 500g, change recipe base to 360g; override still 500g, base 360g visible. Reset shows 360g.
- Remove last generated occurrence -> orphan retains 500g; return key restores override; reset orphan discards explicitly.
- Invalid negative/zero, taste, stale version rejected; underlying recipe unchanged.

## Implementation tasks and boundaries

ShoppingState adjust/reset/reconcile, stable key validation and overlay schema; integration test reapplication after disappearance; composite version checks.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Adjust a synthetic ingredient, change planned dishes until row disappears, review orphan, re-add then reset. Verify recipe untouched.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
