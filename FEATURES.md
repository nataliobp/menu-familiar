# Features and use cases

The V1 inventory defines seven features and 30 stable use-case IDs. The [detailed specifications](docs/specs/README.md#use-case-index) define behavior and acceptance for every ID. The [roadmap](ROADMAP.md) assigns delivery milestones.

## F01 — Weekly Menu

- **F01-UC01:** Create an editable weekly menu atomically on its first valid change.
- **F01-UC02:** View and return to a persisted weekly menu.
- **F01-UC03:** Navigate between weekly menus.

## F02 — Meal Planning

- **F02-UC01:** Assign a dish to an empty slot.
- **F02-UC02:** Replace the dish in an occupied slot.
- **F02-UC03:** Remove a dish from a slot.
- **F02-UC04:** Mark a slot as skipped or return it to pending.
- **F02-UC05:** Move a dish to an empty slot.
- **F02-UC06:** Exchange dishes between occupied slots.
- **F02-UC07:** Undo the latest eligible move or exchange.

## F03 — Dish Recommendations

- **F03-UC01:** Find dishes for a meal slot by category.
- **F03-UC02:** Search for dishes for a meal slot.
- **F03-UC03:** Browse and select dishes for a meal slot without a category filter.

## F04 — Weekly Template

- **F04-UC01:** View the reusable weekly template.
- **F04-UC02:** Set or change a slot's suggested category.
- **F04-UC03:** Leave a template slot without a suggested category.

## F05 — Dish Catalogue

- **F05-UC01:** Browse the dish catalogue.
- **F05-UC02:** Search the dish catalogue.
- **F05-UC03:** Create a dish.
- **F05-UC04:** Edit a dish.
- **F05-UC05:** Archive a dish.
- **F05-UC06:** Restore an archived dish.

## F06 — Recipe Management

- **F06-UC01:** View a recipe.
- **F06-UC02:** Create or edit recipe information.
- **F06-UC03:** Save a recipe draft.
- **F06-UC04:** Publish a recipe.

## F07 — Weekly Ingredient Reminder

- **F07-UC01:** View the dated week's ingredient reminder, with totals for selected dishes and notices for incomplete or provisional data.
- **F07-UC02–04:** Retired in V2.5. Historical persistence is retained. See the [current F07 contract](docs/specs/V2.5-SHOPPING-REMINDER.md).

## Business rules and technical tasks

Rules apply across use cases rather than forming separate user goals. In particular, `SPEC.md` governs week editability and historical preservation, live template suggestions, slot states, selection ordering, atomic moves and undo, recipe changes, and ingredient projection and historical preservation. The initial CSV import is a technical prerequisite, not a catalogue use case. Implementation and verification tasks are planned in the relevant milestone.
