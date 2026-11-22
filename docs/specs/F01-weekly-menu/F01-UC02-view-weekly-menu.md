# F01-UC02 — View a weekly menu

- **Status:** V1 baseline
- **Milestone:** M2; extend in M3
- **Dependencies:** M0, M1; F01-UC01 for persisted view

## Objective

Open current weekly plan or revisit a saved one without side effects.

## Application and web contract

`GetWeeklyMenu(week: date | None) -> WeeklyMenuView`; GET `/menu/` or `/menu/<week>/`. A missing editable week has 14 interactive positions, version 0, and no persisted slots. Existing DTO includes week, editable flag, version, state, names, suggestion, undo status.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Resolve default to current Monday; find persisted week or return preview.
2. Render seven days and two distinct meals, states and selected dish snapshot; show read-only when past.
3. Tapping an editable pending slot opens the picker and shows the live template hint before selection; selected detail opens exact snapshot; skipped opens reactivate action. Long text accessible in detail.

## Alternative and failure flows

- Unknown/malformed date: 404; missing past week show no menu without create.
- Unavailable DB: truthful 503, retry; never silently show blank week as if data absent.

## Acceptance criteria and automated scenarios

- GET current with no row renders 14 preview positions and leaves DB unchanged.
- Persisted selections and pending/skipped states survive refresh/restart; earlier current-week date slots remain editable.
- M2 verifies layout and read-only server guards. M3 verifies past navigation and no editing controls. M5 verifies frozen display after a catalogue rename. The normal tablet view shows all 14 slots without horizontal scrolling.

## Implementation tasks and boundaries

Query port returns DTO, not ORM; read snapshot, not live dish name. Render base and menu template; create dedicated missing-state markup. Web and browser tests.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Open menu on tablet and mobile, refresh/second tab. Verify `Dinar/Sopar`, `Pendent/Omès`, selected title, no extra meals or image slots.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
