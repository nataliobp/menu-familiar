# F04-UC01 — View the weekly template

- **Status:** V1 baseline
- **Milestone:** M1
- **Dependencies:** M0 category seed/import

## Objective

Inspect the single reusable pattern of category suggestions.

## Application and web contract

`GetWeeklyTemplate() -> TemplateView`; GET `/plantilla/`, exactly 14 positions, nullable category, version and options. Singleton seeded blank; no GET initialization.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Load singleton and validate full positions; map labels from category repository.
2. Render seven days × Dinar/Sopar; unspecified `Lliure`; tap a slot to edit.
3. Responsive same weekly visual pattern; no historical templates, no dishes in template.

## Alternative and failure flows

- Missing/corrupt singleton is configuration/data error, not silently recreated on GET; 503/controlled error.
- No categories available -> seed/fixture verification error; no free-text category.

## Acceptance criteria and automated scenarios

- Fresh migration creates one template with 14 null suggestions; GET repeated no extra rows.
- All days/meal types visible, saved suggestions reload. Tablet all 14 accessible and mobile list no horizontal scroll.

## Implementation tasks and boundaries

Seed template migration; domain WeeklyTemplate positions invariant; template repository/read DTO; base navigation only available sections as slices delivered.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Open Plantilla on phone and tablet; verify 7 days, two meals and editable `Lliure` positions.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
