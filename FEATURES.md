# Features and use cases

The V1 inventory defines seven features and 30 stable use-case IDs. The [detailed specifications](docs/specs/README.md#use-case-index) define behavior and acceptance for every ID. The [roadmap](ROADMAP.md) assigns delivery milestones.

## F01 — Weekly Menu

- **F01-UC01:** Create a weekly menu from the reusable template.
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

## F07 — Shopping List

- **F07-UC01:** Generate and view a weekly shopping list.
- **F07-UC02:** Add, edit, and remove manual products.
- **F07-UC03:** Adjust and reset a generated quantity, including reviewing orphaned adjustments.
- **F07-UC04:** Check or uncheck a shopping-list item.

## Business rules and technical tasks

Rules apply across use cases rather than forming separate user goals. In particular, `SPEC.md` governs week editability and historical preservation, template copying, slot states, selection ordering, atomic moves and undo, recipe changes, and shopping-list refresh and preservation. The initial CSV import is a technical prerequisite, not a catalogue use case. Implementation and verification tasks are planned in the relevant milestone.
