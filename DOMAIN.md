# Domain reference

This is the domain reference for the [consolidated V1 baseline](docs/specs/README.md). The product rules are in SPEC.md and architecture boundaries in ARCHITECTURE.md.

## Ubiquitous language and relationships

- **Weekly menu:** A plan for seven days, with a lunch and dinner **slot** for each day. A slot may contain one planned dish.
- **Weekly template:** Reusable category suggestions for the 14 slots. A new week receives copies; a suggestion may be absent and never restricts selection.
- **Dish:** A catalogue entry with identity, categories, meal preference, and an occasion flag. A dish can be planned multiple times and can belong to multiple categories.
- **Recipe:** A dish-owned lifecycle with a working draft and effective publication for two adults. Before publication, known draft quantities contribute provisionally. Drafts can contain named ingredients with unknown quantities.
- **Shopping list:** A week's generated ingredients and user-maintained products, adjustments, and checks. An **orphaned adjustment** is an adjustment whose generated item has disappeared.
- **Recency:** Latest planned meal date across all saved weeks, including future and current dates. Never-planned dishes rank first within their tier.

These concepts form one family meal-planning domain. No separate bounded contexts or context relationships have been established; introduce them only if future use cases demonstrate a useful boundary.

## Entities, aggregates, and values

The weekly menu owns its slots and undo. The template owns suggestions independently. Dish owns recipe state and version. A week has separate shopping overlay state, with related menu and overlay writes coordinated in one transaction.

Use value objects where they enforce position, quantity, and ingredient identity rules. Use immutable values for historical snapshots.

## Established invariants and transitions

- Pending and skipped slots contain no dish. Selected slots contain exactly one. Removal makes the slot pending. Direct assignment requires a pending slot, so an omitted slot must first be reactivated.
- A move makes the source pending and selects the destination. Moving into a skipped slot requires confirmation. Atomic undo restores both prior positions and is invalidated by a later planning edit or a changed snapshot in that pair.
- Meal preferences and occasion flags affect ordering, not eligibility. The ordering precedence and tie rules are specified in `SPEC.md`.
- Shopping aggregation counts each planned occurrence and combines matching ingredients only when units are compatible. Missing recipe information remains visible; quantities are not invented. Refresh preserves manual products and matching adjustments and checks, and exposes orphaned adjustments.

## Domain services

Selection ordering and ingredient aggregation are candidate domain services when their rules do not naturally belong to one entity. They express domain rules without requiring a particular class or infrastructure design. Application orchestration and persistence are outside their responsibility.

## Time and history

Weeks start on Monday in Europe/Madrid. Past menus, shopping state, and displayed values are read-only. Editable snapshots follow catalogue and effective recipe changes. Historical rendering keeps its original projection version across upgrades.

## Detailed domain contract

See the [V1 decision record](docs/specs/01-decisions.md) and [domain model](docs/specs/02-domain-model.md) for transitions, recipe completeness, ingredient identity, undo, and historical derivation.
