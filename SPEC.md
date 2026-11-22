# Family menu specification

## Scope and language

Build a modular Django application for family meal planning and shopping. Use standard Catalan for all visible content and English for technical documentation, code, identifiers, and comments. The [consolidated V1 specifications](docs/specs/README.md) and [replacement UX prototype](docs/ux/index.html) supersede legacy material. Images and application-level authentication are out of scope. Release requires verified isolation to the trusted household LAN.

## Dish catalogue

- Use `PLATOS_57.csv` as the initial catalogue: all 57 records, retaining their IDs, Catalan names, primary category, any secondary categories, meal preference, and special-occasion flag. A dish may belong to multiple categories; category-based selection must find it under each of them without duplicating the dish within a single result set.
- The CSV contains lunch, dinner, and both meal preferences. These express ordering priorities, never eligibility restrictions: every dish can be selected for either meal.
- Five dishes are marked for special occasions (IDs 25, 31, 43, 52, and 55). The flag affects ordering, not eligibility.
- Recipe information is pending for every CSV record. The CSV has no ingredient quantities or recipes; do not infer them from dish names. Its image status is irrelevant because images are out of scope.
- Allow users to browse and search the catalogue, and archive and restore dishes. Define the effects of archiving and restoration in the corresponding use case specifications while preserving historical menus.
- Allow users to view, draft, and publish recipes. Open the editor from the catalogue or editable weekly dish detail. Drafts can save named ingredients with unknown quantity. Before first publication, known draft amounts contribute provisionally and the list explicitly warns that it is incomplete. Later draft edits take effect only on publication.
- Allow users to create and edit dishes, including their Catalan names, category memberships, meal preferences, and special-occasion flags. Allow users to create and edit recipes and their ingredients, quantities, and units for two adults. Preserve incomplete recipes as incomplete rather than inventing data. Changes must not silently alter historical menus.

## Selection ordering

For a given meal slot and any category filter, order eligible dishes as follows:

1. Ordinary dishes before special-occasion dishes, irrespective of meal preference or planning history. Special-occasion dishes always appear at the end.
2. Within each of those groups, dishes preferred for the slot and dishes marked `both` first; dishes preferred for the other meal follow. All remain selectable.
3. Within each resulting group, order by least recent planning first. Treat a dish never planned as older than one with a planning date. Resolve ties consistently by catalogue ID.

Use the latest planned meal date across all persisted weeks, including future dates and the current plan. Changes to occurrences update ranking, and a dish may appear more than once. Search in the picker and catalogue is case-insensitive and accent-insensitive.

## Weekly planning

- Weeks start Monday in Europe/Madrid local time. Past weeks are read-only, including shopping, undo, and all displayed snapshot values. Current and future weeks are editable. A missing editable week renders all 14 pending slots. The first valid change creates the week and saves the change in one transaction. Past weeks cannot be backfilled.

- Present a week as seven days with a lunch and a dinner slot for each day: 14 slots in total. Each slot holds at most one dish and may remain empty.
- Provide a reusable weekly template with suggested categories for each of its 14 slots. Users can edit these suggestions and see them on the next render of every editable week, including weeks with existing menus. A template slot may have no suggested category. A suggested category guides selection but does not restrict it: users can choose a dish from any category. Show the current suggestion with its colour pictogram and `Tria un plat` before opening a pending slot. The picker starts with the current category and allows switching to all categories. Historical views never read the current template.
- Each slot has one of three states: `pending` means no dish has been chosen and the slot still needs a decision; `selected` means exactly one dish is assigned; `skipped` means the user intentionally omitted the slot and no dish is assigned. New slots start as `pending`. Users can mark a slot as `skipped`, return it to `pending`, or select a dish; selecting a dish sets `selected`. Replacing a selected dish keeps it `selected`. Show the states distinctly in Catalan.
- Week navigation, standalone category filters and picker or catalogue searches apply directly. Tap a dish to assign or replace it. Tap a template category to save it. Destructive actions use a confirmation dialog. Keep server-rendered form fallbacks.
- Assign to pending slots, replace a selected dish, or remove it to return the slot to pending. Reactivate a skipped slot explicitly before direct assignment. Meal preference and special-occasion status never block selection.
- Move to a pending slot or, after confirmation, to a skipped slot. Exchange two selected dishes. Positions retain their suggestions, and a move leaves its source pending.
- Moves, exchanges and undo are atomic. Undo restores both previous slot states once. A subsequent successful planning edit or snapshot change affecting either involved position invalidates undo. An unrelated snapshot refresh or a no-op preserves it.
- Persist the plan so it remains available after leaving and returning. Planning changes must not silently discard unrelated slots.
- Keep each weekly menu independent. Editing a different week, the reusable template, dishes, or recipes must not retroactively change a historical week's slots, displayed dish or recipe details, or shopping list. Preserve the values needed for that week; edits to a current or future week change only that week, except for the specified effects of recipe changes. Recency ordering may still consult planned dates across weeks.

## Shopping list

- Generate a shopping list from the dishes currently in the selected week, using recipe ingredient quantities for two adults. Count each planned occurrence; combine matching ingredients when their units are compatible, and keep incompatible units separate without guessing conversions.
- Refresh affected current and future shopping lists when their plans or the recipes of their planned dishes change. Pending and skipped slots contribute nothing. Past weeks retain their historical recipe details and shopping lists unchanged.
- Because the supplied CSV contains no recipes or quantities, identify dishes with missing ingredient information and make clear that the list is incomplete. Never present invented quantities as facts. Recipe data must be supplied before a complete list can be generated.
- Allow manual products to be added, edited, and removed for a week, including their quantities and units. Allow users to adjust generated quantities for that week's shopping list without changing the underlying recipes. Clearly distinguish manual products and adjusted quantities from generated values; allow an adjustment to be reset to the generated value.
- Persist each checkbox and manual edit for its week. Matching generated items retain checks and adjustments when their calculated quantity changes. Show the updated calculated quantity. Keep disappeared adjustments visible for review.

## Responsive design

- Provide a responsive, touch-usable interface for mobile phones and for landscape tablets at 800×480 and 1024×600. Planning, catalogue management, recipes, undo, and shopping must remain readable and operable at these sizes without obscured controls or page-level horizontal scrolling. Adapt the weekly layout to available space while keeping all 14 slots accessible.

## Delivery approach

- Specify all 30 use cases upfront. The [decision record](docs/specs/01-decisions.md) resolves the V1 product rules and the shared contracts define their implementation.
- Use rolling planning to sequence implementation details within M0–M8, with small vertical slices and automated quality gates.
- Deliver in small vertical slices that provide complete use case behavior across the necessary layers. Use Incremental Delivery and avoid building speculative infrastructure or functionality.
- Track automated verification per slice and complete consolidated manual owner QA before release.

## Verification and constraints

- Test catalogue import, browsing, search, archiving and restoration, recipe viewing, drafts and publication, week navigation, unfiltered selection, template slots without suggestions, dish assignment, replacement and removal, multiple-category membership, the complete ordering precedence and ties, preference flexibility, and all 14 slots and editing operations.
- Test shopping-list aggregation, repeated dishes, incompatible units, missing recipe data, and updates after plan changes.
- Test template reuse and independence, slot state transitions, atomic moves and exchanges and their undo, strict past-week read-only behavior, current and future editing, historical isolation, and dish and recipe editing. Test recipe changes across affected current, future, and past weeks. Test manual products, quantity adjustments, checkboxes, and preservation across list refreshes.
- Verify the responsive flows on mobile and landscape viewports of 800×480 and 1024×600.
- Protect family data. Do not alter existing Home Server services. Work incrementally, avoid unnecessary dependencies and functionality, and do not introduce images.
