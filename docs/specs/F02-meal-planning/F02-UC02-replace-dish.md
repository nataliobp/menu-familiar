# F02-UC02 — Replace the dish in an occupied slot

- **Status:** V1 baseline
- **Milestone:** M2
- **Dependencies:** F02-UC01; F03-UC03

## Objective

Change the dish without moving it or overwriting unrelated meals.

## Application and web contract

`ReplaceDish(week, position, dish_id, expected_version)`; POST slot `/replace/`; requires selected slot, active replacement. Same dish ID and current snapshot = no-op.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Open selected detail, choose `Canvia el plat`; show same picker with original retained until save.
2. Validate active replacement and version; replace snapshot only, preserve suggestion/position/state selected; invalidate undo on actual change.
3. Commit and return updated week/detail; next rank query sees removed/added occurrences; M7 reconcile.

## Alternative and failure flows

- Cancel leaves original; invalid replacement/selection stale or past denied; no need to confirm category mismatch.
- If original is archived, replacement with active dish allowed. Re-select same current ID no-op.

## Acceptance criteria and automated scenarios

- Replace A with B in one slot; slot stays selected and suggestion unchanged, unrelated slots same.
- Cancel and same dish do not mutate or invalidate undo; archive/stale new dish rejected.
- Recency drops A occurrence and includes B; M7 list updates while manual items and matching overlays survive.

## Implementation tasks and boundaries

Reuse selection picker and snapshot factory; explicit ReplaceDish domain transition, not clear+assign separate writes. Tests inspect pre/post snapshot and list.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Open Monday selected dish, replace with another, cancel once and verify original persists, then save and refresh.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
