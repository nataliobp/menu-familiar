# Family menu specification

## Scope and language

Build a simple, modular Django application for planning family meals and deriving a shopping list. All interface text and other user-visible content must be in standard Catalan. Code, identifiers, comments, and technical documentation are in English. Preserve the behavior and layouts of any applicable existing Spanish UX/UI specifications while localizing their visible text. No images of any kind are included in the application.

## Dish catalogue

- Use `PLATOS_57.csv` as the initial catalogue: all 57 records, retaining their IDs, Catalan names, primary category, any secondary categories, meal preference, and special-occasion flag. A dish may belong to multiple categories; category-based selection must find it under each of them without duplicating the dish within a single result set.
- The CSV contains lunch, dinner, and both meal preferences. These express ordering priorities, never eligibility restrictions: every dish can be selected for either meal.
- Five dishes are marked for special occasions (IDs 25, 31, 43, 52, and 55). The flag affects ordering, not eligibility.
- Recipe information is pending for every CSV record. The CSV has no ingredient quantities or recipes; do not infer them from dish names. Its image status is irrelevant because images are out of scope.
- Allow users to create and edit dishes, including their Catalan names, category memberships, meal preferences, and special-occasion flags. Allow users to create and edit recipes and their ingredients, quantities, and units for two adults. Preserve incomplete recipes as incomplete rather than inventing data. Changes must not silently alter historical menus.

## Selection ordering

For a given meal slot and any category filter, order eligible dishes as follows:

1. Ordinary dishes before special-occasion dishes, irrespective of meal preference or planning history. Special-occasion dishes always appear at the end.
2. Within each of those groups, dishes preferred for the slot and dishes marked `both` first; dishes preferred for the other meal follow. All remain selectable.
3. Within each resulting group, order by least recent planning first. Treat a dish never planned as older than one with a planning date. Resolve ties consistently by catalogue ID.

Use the latest date on which a dish is planned as its recency. The current plan counts; moving, replacing, or removing a planned dish must update the ordering to reflect the resulting plan. A dish may be planned more than once.

## Weekly planning

- Present a week as seven days with a lunch and a dinner slot for each day: 14 slots in total. Each slot holds at most one dish and may remain empty.
- Provide a reusable weekly template with suggested categories for each of its 14 slots. Users can edit these suggestions and reuse the template for new weeks. A suggested category guides selection but does not restrict it: users can choose a dish from any category. Creating a week copies its suggestions; changing the template does not change existing weeks.
- Each slot has one of three states: `pending` means no dish has been chosen and the slot still needs a decision; `selected` means exactly one dish is assigned; `skipped` means the user intentionally omitted the slot and no dish is assigned. New slots start as `pending`. Users can mark a slot as `skipped`, return it to `pending`, or select a dish; selecting a dish sets `selected`. Replacing a selected dish keeps it `selected`. Show the states distinctly in Catalan.
- Allow a user to select a dish for an empty slot and replace a dish in an occupied slot. Preferences and special-occasion flags must not block either action.
- Allow moving a dish to an empty slot and exchanging dishes between occupied slots. Preserve the selected dishes and update their positions and recency accordingly. A move sets its source to `pending` and its destination to `selected`, including when the destination was `skipped`.
- Moves and exchanges are atomic: both affected slots change together or neither does. Offer undo for the latest move or exchange, restoring both slots and their prior states as one atomic operation. A subsequent planning edit invalidates that undo so it cannot overwrite newer work; after undo it is no longer available.
- Persist the plan so it remains available after leaving and returning. Planning changes must not silently discard unrelated slots.
- Keep each weekly menu independent. Editing a different week, the reusable template, dishes, or recipes must not retroactively change a historical week's slots, displayed dish or recipe details, or shopping list. Preserve the values needed for that week; an explicit edit to that week changes only that week. Recency ordering may still consult planned dates across weeks.

## Shopping list

- Generate a shopping list from the dishes currently in the selected week, using recipe ingredient quantities for two adults. Count each planned occurrence; combine matching ingredients when their units are compatible, and keep incompatible units separate without guessing conversions.
- Refresh the list when the selected week's plan or its recipe data changes. Pending and skipped slots contribute nothing. Historical weeks retain their own recipe data and list unless explicitly edited.
- Because the supplied CSV contains no recipes or quantities, identify dishes with missing ingredient information and make clear that the list is incomplete. Never present invented quantities as facts. Recipe data must be supplied before a complete list can be generated.
- Allow manual products to be added, edited, and removed for a week, including their quantities and units. Allow users to adjust generated quantities for that week's shopping list without changing the underlying recipes. Clearly distinguish manual products and adjusted quantities from generated values; allow an adjustment to be reset to the generated value.
- Provide a checkbox for each shopping-list item and persist its checked state and manual edits for the week. Refreshing the generated list must preserve manual products, adjustments, and checks for items that still match; it must not silently discard an adjustment when its generated item disappears. Make such orphaned adjustments visible for user review.

## Responsive design

- Provide a responsive, touch-usable interface for mobile phones and for landscape tablets at 800×480 and 1024×600. Planning, catalogue management, recipes, undo, and shopping must remain readable and operable at these sizes without obscured controls or page-level horizontal scrolling. Adapt the weekly layout to available space while keeping all 14 slots accessible.

## Verification and constraints

- Test catalogue import, multiple-category membership, the complete ordering precedence and ties, preference flexibility, and all 14 slots and editing operations.
- Test shopping-list aggregation, repeated dishes, incompatible units, missing recipe data, and updates after plan changes.
- Test template reuse and independence, slot state transitions, atomic moves and exchanges and their undo, historical isolation, and dish and recipe editing. Test manual products, quantity adjustments, checkboxes, and preservation across list refreshes.
- Verify the responsive flows on mobile and landscape viewports of 800×480 and 1024×600.
- Protect family data. Do not alter existing Home Server services. Work incrementally, avoid unnecessary dependencies and functionality, and do not introduce images.
