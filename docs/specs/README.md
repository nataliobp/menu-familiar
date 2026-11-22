# Family Menu — implementation specifications

**Status: consolidated V1 implementation baseline.** This corpus specifies seven features and 30 use cases for the existing repository. The [decision record](01-decisions.md) captures the approved product rules and cross-cutting technical defaults. Interface copy is Catalan and technical documentation is English.

The [V2.1–V2.2 supplement](V2.1-V2.2.md) takes precedence over the detailed V1 use-case contracts for the V2.2 changes. The original M0–M8 delivery plan and UX mockups remain V1 references. See the [V2.3–V2.4 operations guide](V2.3-V2.4.md) for the private recipe import and media lifecycle. [V2.5 supersedes V1 F07](V2.5-SHOPPING-REMINDER.md) with the read-only weekly ingredient reminder.

## Reading order and authority

1. Root instructions and summaries govern project scope, workflow and architectural boundaries. The detailed V1 contracts below define behavior, implementation and acceptance for that same baseline. Legacy specifications and mockups are superseded.
2. Documents 02–08 are the shared V1 contracts. Read the relevant case with its shared contract and applicable V2 supplements.
3. Each feature directory has one document per stable use-case ID from the original 30-case inventory. Each defines dependencies, contract, flow, exceptions, code responsibilities and acceptance tests. M0 and M8 are technical milestones, not user cases.
4. The [replacement visual design](../ux/index.html), [UX handoff](../ux/README.md) and [state matrix](../ux/STATE-MATRIX.md) govern visual reference. The shared domain, transaction, and HTTP contracts govern behavior.
5. `REVIEW-AND-EXECUTION.md` contains the Codex prompts and the review/fix/QA gates.

## Traceability

| Milestone | Feature/use cases first delivered | Cross-cutting scope |
|---|---|---|
| M0 | None | Environment, category seed, private CSV import, isolated QA |
| M1 | F04-UC01–03 | Singleton template |
| M2 | F01-UC01–02, F02-UC01–04, F03-UC01–03 | Date identity, editability guard and complete ranking for stored plans |
| M3 | F01-UC03 | Multi-week behavior, immutable past, recency |
| M4 | F02-UC05–07 | Atomic move/swap/undo |
| M5 | F05-UC01–06 | Catalogue management |
| M6 | F06-UC01–04 | Recipes, snapshot propagation |
| M7 | F07-UC01–04 | Shopping projection, overlays, history |
| M8 | None | Release tests, deployment, backup/restore |

## Source handling

The baseline incorporates the independent review of the live repository and its partial M0 importer. Preserve local changes and existing migrations. Keep private input, real recipes, private mockups, host identifiers, and configuration out of published artifacts. Use only the synthetic replacement UX board.

## Scope boundaries

One household, one LAN application, one reusable template, weekly menus, catalogue, recipes and shopping. No accounts/login, no images, no outside integrations, no baby menu, no breakfast/snacks, no native apps, no background service, no remote public access. Use plain Python domain/application and Django adapters, SQLite, server-rendered HTML, lightweight CSS/JS. No generic architecture framework.

## Use case index

### F01-weekly-menu

- [F01-UC01 — Create a weekly menu on its first edit](F01-weekly-menu/F01-UC01-create-weekly-menu.md)
- [F01-UC02 — View a persisted weekly menu](F01-weekly-menu/F01-UC02-view-weekly-menu.md)
- [F01-UC03 — Navigate between weekly menus](F01-weekly-menu/F01-UC03-navigate-weeks.md)

### F02-meal-planning

- [F02-UC01 — Assign a dish to an empty slot](F02-meal-planning/F02-UC01-assign-dish.md)
- [F02-UC02 — Replace the dish in an occupied slot](F02-meal-planning/F02-UC02-replace-dish.md)
- [F02-UC03 — Remove a dish from a slot](F02-meal-planning/F02-UC03-remove-dish.md)
- [F02-UC04 — Skip or reactivate a slot](F02-meal-planning/F02-UC04-skip-reactivate-slot.md)
- [F02-UC05 — Move a dish to another slot](F02-meal-planning/F02-UC05-move-dish.md)
- [F02-UC06 — Exchange dishes between occupied slots](F02-meal-planning/F02-UC06-exchange-dishes.md)
- [F02-UC07 — Undo the latest eligible movement](F02-meal-planning/F02-UC07-undo-planning-change.md)

### F03-dish-recommendations

- [F03-UC01 — Find dishes by category and rank](F03-dish-recommendations/F03-UC01-filter-recommendations.md)
- [F03-UC02 — Search dishes for a slot](F03-dish-recommendations/F03-UC02-search-slot-dishes.md)
- [F03-UC03 — Browse all dishes for a slot](F03-dish-recommendations/F03-UC03-browse-unfiltered-dishes.md)

### F04-weekly-template

- [F04-UC01 — View the weekly template](F04-weekly-template/F04-UC01-view-template.md)
- [F04-UC02 — Set or change a template category](F04-weekly-template/F04-UC02-set-template-category.md)
- [F04-UC03 — Leave a template slot free](F04-weekly-template/F04-UC03-clear-template-category.md)

### F05-dish-catalogue

- [F05-UC01 — Browse the dish catalogue](F05-dish-catalogue/F05-UC01-browse-catalogue.md)
- [F05-UC02 — Search the catalogue](F05-dish-catalogue/F05-UC02-search-catalogue.md)
- [F05-UC03 — Create a dish](F05-dish-catalogue/F05-UC03-create-dish.md)
- [F05-UC04 — Edit a dish](F05-dish-catalogue/F05-UC04-edit-dish.md)
- [F05-UC05 — Archive a dish](F05-dish-catalogue/F05-UC05-archive-dish.md)
- [F05-UC06 — Restore an archived dish](F05-dish-catalogue/F05-UC06-restore-dish.md)

### F06-recipe-management

- [F06-UC01 — View a recipe](F06-recipe-management/F06-UC01-view-recipe.md)
- [F06-UC02 — Create or edit recipe information](F06-recipe-management/F06-UC02-edit-recipe.md)
- [F06-UC03 — Save a recipe draft](F06-recipe-management/F06-UC03-save-recipe-draft.md)
- [F06-UC04 — Publish a complete recipe](F06-recipe-management/F06-UC04-publish-recipe.md)

### F07 — Weekly ingredient reminder

- [Current F07 contract from V2.5](V2.5-SHOPPING-REMINDER.md)

The following V1 cases are retained as historical reference.

- [F07-UC01 — Generate and view the weekly shopping list](F07-shopping-list/F07-UC01-generate-shopping-list.md)
- [F07-UC02 — Add, edit and remove manual products](F07-shopping-list/F07-UC02-manage-manual-products.md)
- [F07-UC03 — Adjust and reset generated quantities](F07-shopping-list/F07-UC03-adjust-generated-quantity.md)
- [F07-UC04 — Check or uncheck a shopping item](F07-shopping-list/F07-UC04-check-shopping-item.md)
