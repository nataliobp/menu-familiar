# Application design and contracts

## Package layout (target; add only needed files per slice)

```text
config/                       # Django settings, root URLs, WSGI/ASGI
menus/
  domain/                     # common.py, catalogue.py, template.py, planning.py, recipe.py, shopping.py
  application/
    ports.py                  # purpose-specific protocols, transaction and clock
    errors.py                 # application errors, stable error codes
    dto.py                    # input/output DTOs; split by feature if warranted
    catalogue.py              # import and catalogue use cases
    template.py               # template use cases
    planning.py               # calendar, slot editing, recommendations
    recipe.py                 # recipe draft/publication
    shopping.py               # generated list and overlays
  infrastructure/
    persistence/              # orm_models.py, mappers.py, repositories.py (split when useful)
    csv_catalogue.py          # private CSV parser
    clock.py                  # system local clock
    transactions.py           # Django atomic, optimistic guards
  web/
    urls.py, forms.py, views.py, wiring.py
  models.py                   # Django model discovery: imports adapter ORM models only
  migrations/
  management/commands/import_catalogue.py
  templates/menus/            # base, menu, picker, template, catalogue, recipe, shopping, errors
  static/menus/               # CSS, optional small JS; no remote assets or images
  tests/domain/, tests/application/, tests/integration/, tests/web/
manage.py
```

Django `views.py` at root may re-export adapter entry points during migration of skeleton; no domain logic there. `wiring.py` constructs dependencies per request/command. Use Django templates and forms, POST/redirect/GET (PRG) default, small local JS for confirmation/unsaved warning and optional async fragments. No REST framework, event bus, broker, async tasks, SPA or framework-specific dependency in inner layers. Module names are targets, not a demand for empty files. Each named use case is an application function or small class with `execute`; do not create redundant handler/service/facade layers.

## Ports (Python Protocols; no generic CRUD)

Signatures use domain values and application DTOs; `None` denotes missing, errors are application error types. Implement only operations used by milestone. Repository saves perform compare-and-swap (`expected_version`); return new version. All writes use the single transaction context-manager port with a Django adapter using `transaction.atomic()`. One command owns the transaction. ID generation for new dishes/manual items belongs to adapter; use `create(...) -> id` return value rather than fake counters in production.

| Port | Operations |
|---|---|
| `Clock` | `today() -> date` (timezone-aware system adapter); test fake supplies boundary dates. |
| `CategoryRepository` | `list_all() -> tuple[Category,...]`, `get(key)`; seed in migration; immutable vocabulary. |
| `DishRepository` | `get(id) -> Dish | None`, `get_many(ids)`, `create(dish_data) -> Dish`, `insert_with_id(dish)`, `save(dish, expected_version) -> int`, `list_candidates(category=None, query=None, include_archived=False)`; select efficient catalogue summary projection for list. |
| `WeeklyTemplateRepository` | `get() -> WeeklyTemplate`, `save(template, expected_version)`; initial row seeded; no create/delete UI. |
| `WeeklyMenuRepository` | `get(week_start)`, `create_from_template(menu)`, `save(menu, expected_version)`, `find_editable_with_dish(dish_id, from_week)`, `latest_planned_dates(dish_ids) -> mapping[int,date]`; find/edit current/future only; query projections must preserve semantics. |
| `ShoppingStateRepository` | `get(week_start) -> ShoppingListState | None`, `create_if_absent` on mutation only, `save(state, expected_version)`, `create_manual` returning stable ID. |
| `CreationReceiptStore` | Find or insert a scoped result for dish or manual-product creation in the same transaction. Reuse an existing adapter when practical. |
| `AtomicRunner` | `atomic() -> context manager`; explicit mapping of persistence failure, unique conflict, busy/locked; tests verify rollback. |

`Recipe` is a Dish-owned lifecycle; no independent RecipeRepository required. `CatalogueCsvReader` is an infrastructure function returning validated input records or structured errors to `ImportCatalogue`; no application imports of CSV/Django parser. Stage decoded rows in memory (57 rows) then atomic conflict-check/write. Prefer one transaction per user command, not per slot/ingredient. The application service loads aggregates, invokes domain behavior, saves with version guards, coordinates other affected aggregates and returns results. Do not use Django signals for propagation. Use sorted week keys for multi-week updates to keep consistent access order. No external I/O inside transaction except persistence.

## Result and failure contract

Queries return frozen DTOs, not ORM records; adapters format dates, labels, units and Catalan translations. Commands return `CommandResult` containing target identifiers, changed flag and current version(s) plus optional notification code. Define `NotFound`, `ValidationError` (field error map / codes), `InvalidTransition`, `PastWeekReadOnly`, `Conflict` (stale/version or duplicate/conflicting import), `Unavailable` (busy, retryable). Domain errors map to application errors; DB exceptions never exposed to user. Never assume success until DB commit. HTTP mapping in UX contract. Unhandled error logs opaque request ID only; no request payloads/recipes in logs.

## Use case signatures and dependencies

`week` is validated Monday `date`, `position` a `SlotPosition`, `expected_version` optimistic token. Commands capture local today inside the transaction, reject past-week writes, and apply the final rollover check in [persistence](04-persistence.md#concurrency-and-atomicity). All query DTOs contain editability when applicable, plus versions. `SnapshotFactory` is a plain application mapper from `Dish` to immutable `DishSnapshot`; use `RefreshEditableDishSnapshots` helper for catalogue/recipe mutations (not user-visible UC). `ReconcileShoppingState` helper becomes active M7 within transaction; earlier milestones do not need storage or a no-op abstraction.

| ID | Application entry point and input | Output / dependencies |
|---|---|---|
| M0-T02 | `ImportCatalogue(records: Sequence[ImportRecord])` | counts inserted/unchanged; Dish, Category, Atomic |
| F01-UC01 | `CreateWeeklyMenu(week)` | WeeklyMenuView; Clock, Template, Menu, Atomic |
| F01-UC02 | `GetWeeklyMenu(week=None)` | WeeklyMenuView or missing preview; Clock, Menu |
| F01-UC03 | `NavigateWeeklyMenu(week, direction)` | target date/read model; reuse GetWeeklyMenu, Clock |
| F02-UC01 | `AssignDish(week, position, dish_id, expected_version)` | updated menu; Clock, Dish, Menu, Atomic, SnapshotFactory |
| F02-UC02 | `ReplaceDish(...)` same input | updated menu; same deps |
| F02-UC03 | `RemoveDish(week, position, expected_version)` | updated menu; Clock, Menu, Atomic |
| F02-UC04 | `SetSlotSkipped(week, position, skipped, expected_version, confirm_remove=False)` | updated menu; Clock, Menu, Atomic |
| F02-UC05 | `MoveDish(week, source, destination, expected_version, confirm_skipped=False)` | updated menu, undo availability; Clock, Menu, Atomic |
| F02-UC06 | `ExchangeDishes(week, first, second, expected_version)` | updated menu, undo availability; same deps |
| F02-UC07 | `UndoPlanningChange(week, expected_version)` | updated menu; same deps |
| F03-UC01 | `GetDishRecommendations(week, position, category_key=None, query=None, filter_mode='suggested')` | ranked CandidateView list, effective filter; Menu, Dish, Category, Clock; `latest_planned_dates` |
| F03-UC02 | `SearchSlotDishes(...)` (same query, q supplied) | reuse recommendation query; no extra service layer |
| F03-UC03 | `BrowseAllSlotDishes(...)` (filter_mode='all') | reuse recommendation query; no extra service layer |
| F04-UC01 | `GetWeeklyTemplate()` | TemplateView, version, Category options; Template, Category |
| F04-UC02 | `SetTemplateCategory(position, category_key, expected_version)` | TemplateView; Template, Category, Atomic |
| F04-UC03 | `ClearTemplateCategory(position, expected_version)` | TemplateView; Template, Atomic |
| F05-UC01 | `BrowseCatalogue(category_key=None, archived=False, q=None)` | CatalogueView; Dish, Category |
| F05-UC02 | `SearchCatalogue(q, category_key=None, archived=False)` | same query; no new service necessary |
| F05-UC03 | `CreateDish(dish_data, creation_token)` | DishView with ID; Dish, Category, CreationReceipt, Atomic |
| F05-UC04 | `EditDish(dish_id, dish_data, expected_version)` | DishView; Dish, Category, Clock, Menu, Atomic; refresh editable snapshots |
| F05-UC05 | `ArchiveDish(dish_id, expected_version)` | DishView; Dish, Atomic |
| F05-UC06 | `RestoreDish(dish_id, expected_version)` | DishView; Dish, Atomic |
| F06-UC01 | `GetRecipe(dish_id, week=None, position=None)` | RecipeView (catalogue effective/draft status or exact slot snapshot); Dish/Menu, Clock |
| F06-UC02 | `GetRecipeEditor(dish_id, slot_context=None)` / `ValidateRecipeInput(data)` | EditorView or field errors; Dish, pure validators |
| F06-UC03 | `SaveRecipeDraft(dish_id, recipe_data, expected_version, slot_context=None)` | RecipeView; Dish, Clock, Menu, Atomic, refresh editable snapshots if effective changed |
| F06-UC04 | `PublishRecipe(dish_id, recipe_data, expected_version, slot_context=None)` | published RecipeView; same deps; validate complete |
| F07-UC01 | `GetShoppingList(week)` | ShoppingView incl. coverage/orphans, read-only; Clock, Menu, ShoppingState |
| F07-UC02 | `AddManualItem(week,data,expected_version,creation_token)` / `EditManualItem(week,item_id,data,expected_version)` / `RemoveManualItem(...)` | ShoppingView; Clock, Menu, ShoppingState, Atomic; CreationReceipt for add |
| F07-UC03 | `AdjustGeneratedItem(week,key,amount,expected_version)` / `ResetGeneratedAdjustment(...)` | ShoppingView; same deps; generated keys validated against week |
| F07-UC04 | `SetShoppingItemChecked(week,item_ref,checked,expected_version)` | ShoppingView; same deps; explicit desired boolean |

For M7 shop commands use one composite expected token `(menu_version, overlay_version_or_zero)`. Read projections consistently and reconcile any persisted overlays before commit when the plan or effective snapshot changes. Increment each version only for persisted changes to its aggregate. See the [transaction contract](04-persistence.md#concurrency-and-atomicity) for lazy overlay initialization, creation receipts, and retry. Expose named errors as Catalan HTTP responses, including input-preserving reconciliation for stale versions. Invalid submitted bounds are field errors; corrupt stored data or aggregate overflow rolls back and maps to controlled unavailability.

Slot-origin recipe edits use `slot_context=(week, position)`. On editor GET and inside each write transaction, require an editable week and that its selected slot still references the requested dish. A changed slot returns conflict, a past week returns read-only, and no write may fall back to the catalogue route. Validate the dish version as for catalogue edits. The recipe is shared and affects other editable occurrences. Use a safe return to the slot detail on success or cancel. A historical slot never links to a live editor.

## Read DTOs

`WeeklyMenuView`: date range, existence, editable, version (None if absent), 14 ordered slot DTOs including suggestion label/state/name/recipe status/dish id, undo_available; preview absent uses null selections, no persistence. `PickerView`: week, slot, action(assign/replace), expected version, filter/query, category choices, candidates with name/primary and secondary labels/meal preference/special flag, no images. `TemplateView`: 14 positions, labels, choices, version. `DishView`/`CatalogueView`: stable ID, labels, preference, special, archived, recipe status, version (details only), optional search. `RecipeView`: display title, prep, ingredient DTOs, status, draft presence, source (live or frozen snapshot), editable/version. `ShoppingView`: week label, editability, composite version, generated rows (base/effective, unit, checked, adjusted), manual rows, orphans, coverage, empty indicator. Framework-specific URL/form rendering belongs to web adapter.
