# Architecture

## Purpose and principles

The application plans family meals and shopping lists as specified in `SPEC.md`, which remains the authority for functional behavior. Implementations must follow Domain-Driven Design (DDD), hexagonal architecture (ports and adapters), dependency inversion, and use case driven development. Apply these principles to protect important behavior and family data, not to add layers for their own sake. Introduce an abstraction only when it expresses a real boundary or rule; do not add dependencies, generic frameworks, or functionality in anticipation of future needs. Defer implementation details until the corresponding use cases are specified. The application has no application-level authentication or access management.

## Packages and responsibilities

The following is the intended structure as functionality is added, not a requirement to create empty packages or refactor existing code immediately:

```text
menus/
    domain/          # Model, invariants, domain rules and domain errors
    application/     # Use cases, input/output data and ports
    infrastructure/  # Django persistence and other concrete adapters
    web/             # Django views, forms, URLs and presentation
    migrations/      # Django schema migrations
    tests/           # Tests organized by boundary and behavior
config/              # Django project configuration and entry points
```

Split modules by cohesive concepts or use cases as they grow. Django may require conventional discovery modules such as `menus/models.py`; these are infrastructure entry points, not a place to put domain rules. Keep templates and static files in conventional Django locations. This structure is a guide, not a mandate for a class or file per concept.

## Dependencies and boundaries

Dependencies point inward: web and infrastructure adapters depend on application and domain; application depends on domain and on ports it defines; domain depends on neither application nor adapters. The composition root in Django configuration or adapter wiring supplies concrete implementations to use cases. Application code invokes ports without importing Django models or knowing which database is used. Domain and application layers must run without Django settings, ORM, HTTP, forms, templates, or other framework APIs. Adapters translate framework data and errors at their boundaries. Do not pass ORM instances, requests, or responses into the domain or application layers.

Ports describe capabilities required by use cases, expressed in domain or application terms. Prefer small, purpose-specific interfaces or protocols when a boundary is needed; do not wrap every function or create a generic repository hierarchy. Read-only queries may use a purpose-specific query port and an efficient adapter projection rather than loading an entire aggregate, provided they preserve the same business rules and isolation.

## Domain model

Model concepts and invariants from the specification in plain Python. Entities have identity and a lifecycle; value objects represent values and validate their own meaning where useful. Aggregates are consistency boundaries: changes that must be valid together are enforced through their root and persisted atomically. Choose boundaries around actual invariants, not database tables.

- A weekly menu is a natural aggregate for its 14 slots, their pending, selected, or skipped states, copied category suggestions, and planning edits. A slot has at most one selected dish. Moves and exchanges affect both slots together. The latest move or exchange can be undone only until another planning edit invalidates it.
- A reusable weekly template owns its suggestions independently. Creating a week copies them; later template edits do not change that week.
- Dishes and recipes have their own identities and editing lifecycles. Category membership, meal preference, and special-occasion status guide selection without restricting eligibility. Recipe information may be incomplete; quantities must never be invented.
- Past weekly menus are read-only, with copied dish and recipe values and versioned historical shopping derivation. Monday in Europe/Madrid determines classification. Editable snapshots and shopping state propagate atomically under the [time and persistence contracts](docs/specs/04-persistence.md#concurrency-and-atomicity).
- Shopping-list state belongs to a week and includes manual products, generated-item adjustments, checked state, and visible orphaned adjustments. Refresh preserves matching state and does not silently discard orphaned adjustments.

Use value objects where they clarify rules, for example a meal slot, quantity and unit, or ingredient identity. Define matching and unit compatibility explicitly; do not guess conversions. Use a domain service for a rule that spans concepts and does not naturally belong to one entity, such as selection ordering or ingredient aggregation, when a simple function is sufficient. Ordering follows the complete precedence and tie rules in `SPEC.md`, including current planning and the latest planned date. Domain services do not access Django or persistence directly.

## Use cases and orchestration

Each user intention should have an explicit application entry point, such as creating a week from a template, selecting or replacing a dish, moving or exchanging slots, undoing a move, editing a recipe, or refreshing a shopping list. A use case validates its inputs, loads the necessary state through ports, calls domain behavior, coordinates persistence within a transaction where required, and returns framework-independent results or errors. It does not implement presentation or SQL. Keep related simple operations together when separate classes would add ceremony without clarity.

Use cases must enforce past-week read-only behavior at the application boundary as well as in the interface, preserve historical data, and update affected current and future shopping lists when recipes change or an editable week is changed. Count every planned occurrence, report missing recipe information, combine only compatible ingredients, and retain manual and adjusted list state as specified. Use cases are the preferred entry points for web actions and imports so that alternate adapters cannot bypass invariants.

## Ports and adapters

Repository ports express the load and save operations needed for weekly menus, templates, catalogue and recipe data, and shopping state as implementation needs emerge. They need not correspond one-to-one with tables or expose CRUD methods that no use case needs. A transaction boundary can be expressed as a small application port or supplied around a use case by composition; its implementation belongs to infrastructure.

Django is an adapter: views and forms translate HTTP input into use case inputs and results into Catalan user-facing responses; ORM models, migrations, and repository implementations map persisted records to and from the domain. Django constraints can reinforce invariants but do not replace domain validation. CSV import is an adapter that preserves the supplied catalogue data and calls appropriate application behavior. Keep framework-specific validation and persistence details at the edge. No application code should rely on Django signals for essential use case behavior.

## Transactions and consistency

A use case defines its atomic operation. Its infrastructure transaction includes all reads, invariant checks, and writes that must succeed together. A move or exchange and its undo must update both slots and undo state together; any subsequent planning edit invalidates undo in the same transaction as that edit. Related historical preservation and shopping-list updates that must agree are committed together. A failure rolls back the whole operation and must not discard unrelated slots or list state.

Protect against concurrent requests overwriting newer work using appropriate database transactions and locking or version checks in the adapter. Undo must verify that it is still valid before restoring state. Keep transactions as short as practical, and do not assume an in-memory object alone provides concurrency safety. The concrete mechanism must match the configured database's capabilities and be tested against it.

## Delivery process

The complete V1 specification precedes implementation. Deliver vertical slices with automated verification and checkpoint progress. Consolidate manual owner QA before release.

## Testing strategy

Work incrementally and test behavior at the appropriate boundary:

- **Domain:** fast framework-independent tests for invariants and rules, including slot transitions, moves and undo, ordering precedence and ties, aggregation, missing data, and historical isolation.
- **Application:** framework-independent use case tests with simple in-memory fakes or stubs for ports. Verify orchestration, historical preservation, week editability, undo invalidation, list refresh and preservation, and error paths without reproducing implementation details.
- **Integration:** exercise Django adapters and the configured database, including mappings, catalogue import, constraints, transactions, rollback, and concurrency protection where supported. Verify that state survives reload and that changes to unrelated weeks or services are not made.
- **End to end:** cover representative user journeys through Django, including planning, recipes, undo, and shopping, with Catalan visible text. Verify mobile and the specified 800×480 and 1024×600 landscape viewports for usable controls and no page-level horizontal scrolling.

Automated gates apply to each slice. Consolidated manual owner QA is required for release. Cover the cross-feature [acceptance matrix](docs/specs/06-testing.md#cross-feature-acceptance-matrix) and use focused tests at the boundary that owns each behavior.
