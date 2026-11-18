# F01-UC03 — Navigate between weekly menus

- **Status:** V1 baseline
- **Milestone:** M3
- **Dependencies:** F01-UC01–02, F02-UC01–04, F03-UC01–03

## Objective

Navigate independently saved past/current/future weeks and create future menus as desired.

## Application and web contract

`NavigateWeeklyMenu(week, direction: previous|next|current)` -> target WeekStart; reuse GetWeeklyMenu. Date links GET; previous/next ±7 days, current = clock current Monday; ISO week label display only.

Shared rules: [domain](../02-domain-model.md), [application ports](../03-application-contracts.md), [persistence](../04-persistence.md), [UX](../05-web-ux.md), [tests](../06-testing.md). Applicable security, editability, snapshot, transaction and version rules are mandatory. No images or login. All visible text Catalan.

## Main scenario and postconditions

1. Use previous/next or return `Avui`. Load target by date; missing past shows empty read-only state; missing future/current offers create.
2. No data copied between existing weeks; create uses current template only. Keep selected week in links to shopping and picker.
3. Apply historic guard in all POST actions, including earlier cases and later shopping; recency query spans persisted weeks.

## Alternative and failure flows

- Year/week boundary and DST use local date, no naive UTC rollover.
- No mutation on week navigation; stale open page becoming historical cannot write.

## Acceptance criteria and automated scenarios

- Given Sunday then local Monday, the former current week becomes past; earlier day within current week editable.
- Navigate across December/January and absent weeks; no accidental DB rows, ISO Monday identities distinct.
- Attempt direct past write for each implemented command -> reject, DB unchanged; create future and return current retains independent selections.

## Implementation tasks and boundaries

Extend Clock date policy, date routes, read-only guards, latest-planned query across all weeks. Tests frozen Europe/Madrid calendar including boundary.

Add tests at the layer owning the rule, real SQLite integration tests for persistence/atomicity, and web tests for user-facing behavior. Use synthetic fixtures. No product scope beyond this case and shared prerequisites.

## Manual QA

Move previous/next several times, create future, return `Avui`; confirm past has read-only label and no create for missing past.

Record owner QA status as pending until performed; automated execution must not claim manual approval.
