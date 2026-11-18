# F07-UC04 — Check or uncheck a shopping item

- **Status:** V1 baseline
- **Milestone:** M7
- **Dependencies:** F07-UC01–03

## Objective

Persist purchase progress across refreshes and devices.

## Application and web contract

`SetShoppingItemChecked(week,item_ref,checked: bool,expected_version)`; POST `/checked/`; item_ref tagged generated key or manual ID, not arbitrary label; composite version.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Tap checkbox; submit explicit desired boolean and version; persist matching overlay or update manual row.
2. Re-render truthful checked state after commit; use lightweight JS optionally, accessible form fallback.
3. Same key retains checked on recalc even if amount changes. Disappearing unadjusted generated row loses check; orphan adjusted row unchecked; returning row unchecked.

## Alternative and failure flows

- Stale list after menu version change -> conflict, refresh; no blind toggles. Unknown/cross-week ref, orphan or past write rejected.
- Same desired value with current version no-op; network failure no false success.

## Acceptance criteria and automated scenarios

- Check generated and manual separately, reload/other device sees both; explicit uncheck persists.
- Matching generated key survives recalc with the new calculated amount visible, removed key loses check and reappearance unchecked; manual check survives menu changes.
- Stale checkbox request cannot overwrite newer state; past read-only frozen.

## Implementation tasks and boundaries

State domain set_checked, key/ID validation, CAS; web CSRF and checkbox accessible labels; test repeated requests and overlay cleanup.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Check generated/manual rows on mobile, reload from tablet, change menu and verify applicable check retention.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
