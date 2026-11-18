# Roadmap

This roadmap groups the full V1 baseline. The [implementation plan](docs/specs/07-implementation-plan.md) defines slice order, automated gates, and cross-feature regression timing.

Continue through vertical slices after automated gates pass. Consolidate manual owner QA before release. Catalan UI, responsive behavior, privacy, and architectural boundaries apply throughout.

## M0 — Project Foundation

Upgrade the existing catalogue importer and schema with a forward migration. Preserve import compatibility and verify synthetic upgrades and isolated private source fidelity.

## M1 — Weekly Template

- **F04-UC01–UC03:** View the template, set or change a suggested category, and leave a slot without a suggestion.

## M2 — Single Weekly Menu

- **F01-UC01–UC02:** Create and view a persisted weekly menu.
- **F02-UC01–UC04:** Assign, replace, and remove dishes; manage slot states.
- **F03-UC01–UC03:** Find dishes by category, search, and select without a category filter.

Apply the specified selection ordering to the available plan and catalogue, and copy template suggestions when creating the week.

## M3 — Multi-week Planning

- **F01-UC03:** Navigate between weekly menus.
- Extend **F01-UC01–UC02** and the applicable planning and selection use cases to independent weeks. Enforce current and future editability, past-week read-only behavior, historical preservation, and recency across weeks.

## M4 — Advanced Meal Planning

- **F02-UC05–UC07:** Move and exchange dishes and undo the latest eligible operation.

Apply atomicity, undo invalidation, ordering, and historical rules to these changes.

## M5 — Dish Catalogue Management

- **F05-UC01–UC06:** Browse, search, create, edit, archive, and restore dishes.

## M6 — Recipe Management

- **F06-UC01–UC04:** View, create or edit, save drafts, and publish recipes.

Preserve historical recipe details. The effects of recipe changes on shopping lists are delivered in M7.

## M7 — Shopping List

- **F07-UC01–UC04:** Generate and view lists; manage manual products, adjustments, orphaned adjustments, and checks.

Apply refresh and preservation rules, including updates from recipe changes to affected current and future lists while preserving past data.

## M8 — Production Readiness

Verify the completed use cases together against `SPEC.md`, including responsive flows, data protection, historical isolation, and specified test coverage. Complete remaining readiness work required by existing requirements; this milestone adds no product functionality.
