# F06-UC02 — Create or edit recipe information

- **Status:** V1 baseline
- **Milestone:** M6
- **Dependencies:** F06-UC01

## Objective

Enter preparation and structured ingredients for a dish, retaining typed values until explicit save.

## Application and web contract

`GetRecipeEditor(dish_id, slot_context=None)` / `ValidateRecipeInput(data: RecipeInput)`; GET the catalogue or slot-context recipe editor; returns draft if present, else published copy or blank; editor DTO includes dish version. Validation shared by draft/publish.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Render preparation textarea, ingredient rows (name, amount, unit, note, al gust). Add or remove rows locally or via the server-rendered form without persistence. Contextual editing requires the same selected dish in an editable slot.
2. Validate nonblank ingredient name, canonical identity, exact Decimal finite positive max precision, allowed unit or to-taste with no amount/unit. Empty untouched rows are omitted. A named draft line may have an unknown quantity with optional unit, or explicit al gust with neither amount nor unit. Other invalid partial lines are flagged.
3. Keep editor input on field error; dirty cancel warning; no storage until draft/publish.

## Alternative and failure flows

- Zero/negative/NaN/ambiguous number, a quantified line without unit, contradictory taste flags -> errors. Blank prep allowed draft only.
- A stale editor save preserves typed values for explicit reconciliation. Contextual POST rejects a changed slot or a week that has become past.

## Acceptance criteria and automated scenarios

- Open blank editor for missing recipe, published content copied for new draft, existing draft loaded first.
- Valid decimal comma normalizes exactly; invalid numeric/taste fields rejected with input preserved.
- Cancel and add/remove alone produce no DB writes with or without JavaScript. Verify shared recipe editing and safe return from both origins.

## Implementation tasks and boundaries

Input DTO + form/formset, pure validators in domain/application; local JS optional; no untrusted HTML or dynamic complexity. Shared commands below.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Enter two demo ingredients including `Al gust`; try invalid quantity, correct, cancel dirty edit; confirm no phantom saved data.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
