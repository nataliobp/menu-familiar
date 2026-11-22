# F07-UC02 — Add, edit and remove manual products

> Historical V1 contract, superseded by the [V2.5 ingredient reminder](../V2.5-SHOPPING-REMINDER.md).

- **Status:** V1 baseline
- **Milestone:** M7
- **Dependencies:** F07-UC01

## Objective

Maintain extras unrelated to generated recipe ingredients.

## Application and web contract

`AddManualItem(week,data,expected_version,creation_token)`; `EditManualItem(week,item_id,data,expected_version)`; `RemoveManualItem(week,item_id,expected_version)`; POST manual endpoints. Data name, optional quantity+unit; composite version.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Add with the creation receipt contract. Require a name and either a valid positive quantity with unit or neither. Persist independent stable ID; default unchecked.
2. Edit existing manual row for same week, preserve checked unless explicitly changed. Remove confirmed manual row only.
3. PRG list; base generation and other manual items untouched. Recalc never removes extras.

## Alternative and failure flows

- Unknown ID or cross-week ID denied; malformed amount/unit, historical and stale rejected.
- Do not merge manual with generated even same name; deleting a manual row cannot delete generated ingredient.

## Acceptance criteria and automated scenarios

- Add unquantified and quantified extras to empty existing week; reload retains IDs and amounts.
- Edit quantity/name, remove one, independent rows and checks preserved.
- Menu replacement/recalculation leaves manual extras intact; cross-week/past/stale posts do not mutate.

- Retry a lost response with the same token and payload and recover the original ID, even if the row was subsequently removed. Never resurrect a deleted row.

## Implementation tasks and boundaries

ManualShoppingItem domain validation, state repo lazy initialization only on write, CAS composite guard; web forms and integration tests.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Add two extras including one with same name as generated row, edit quantity, delete one, change menu and verify other persists.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
