# Web and UX implementation contract

Use the replacement V1 [visual design board](../ux/index.html) and [state matrix](../ux/STATE-MATRIX.md) as the visual reference for layout and journeys. They supersede both historical boards; do not consult or implement their obsolete states. All visible content, including Django validation messages, dates, labels, units and empty/error states, uses standard Catalan. No image slots, decorative food imagery, login UI or other modules.

## Navigation and responsive rules

Tablet landscape: left navigation compact, four destinations `Menú setmanal`, `Plats`, `Plantilla`, `Llista de la compra`; one visible primary action per context. Default current week. At 800×480 and 1024×600 display all seven days × two meals at once; seven day columns, two meal cards each, compact header and nav. Truncate visual name only if necessary (2–3 lines), entire text accessible on detail/focus. At 360–430 CSS px mobile portrait use vertical day list (two meal rows each), compact navigation bottom or header, no page-level horizontal scrolling. For tablet short height, adjust spacing/grid, no hidden controls; menus/actions scroll internally when needed. Large touch targets ~44 CSS px where practical; keyboard labels/focus, sufficient contrast, reduced motion. No icon-only ambiguity. No duplicate action clusters per cell; selected opens detail/action sheet; pending opens picker; skipped opens intentional reactivation. No drag required. Forms retain user inputs on validation error; browser back and cancel do not save. Use semantic HTML, escaping, CSRF, accessible error summary and field errors. Local CSS only; no third-party trackers or fonts.

## Text wireframes (synthetic data)

```
TABLET 800x480
┌───────────┬──────────────────────────────────────────────────────┐
│ Menú      │  ‹  16–22 de novembre  ›       Avui                │
│ Plats     │  Dl      Dt      Dc      Dj      Dv      Ds      Dg │
│ Plantilla │  Dinar   Dinar   Dinar   Dinar   Dinar   Dinar   Dinar
│ Compra    │  Plat A  Pendent Plat B  ...     ...     Omès   ... │
│           │  Sopar   Sopar   Sopar   Sopar   Sopar   Sopar   Sopar
│           │  Pendent Plat C  ...     ...     ...     ...     ...│
└───────────┴──────────────────────────────────────────────────────┘
PHONE
‹  16–22 de novembre  ›  Avui
Dilluns 16
  Dinar   Plat A          [open]
  Sopar   + Tria un plat
Dimarts 17 ...
Menú     Plats     Plantilla     Compra
```

`Tria un plat` picker: selected day+meal, `Suggeriments: Verdures` (only when suggested), search `Cerca un plat`, category selector with `Totes les categories`, `Mostra tots els plats`, candidate list with text+category, special label `Ocasió especial` in subdued style, cancel. No confirmation of meal mismatch/occasion needed. The selected slot's suggested label stays fixed when moving; labels don't restrict eligibility. Empty filter -> `No s’han trobat plats` + clear search/filter; absent suggestion defaults to all. For replacement use same picker title `Canvia el plat` and retain original until save.

Template: same 7×2 grid but each card is suggested category or `Lliure`; tap opens category options including `Lliure`, save/cancel, one slot mutation per save; explicit success `Plantilla actualitzada`. No template history or global generic Save button necessary. Week missing: preview 14 empty cards, `Crea el menú` (current/future), past `No hi ha cap menú per a aquesta setmana`, no create. Existing historical: `Setmana passada · només consulta`, no write controls.

Selected slot detail: title, meal position, recipe content or `Recepta pendent`, quantities `Per a 2 adults`, preparation, action sheet `Canvia el plat`, `Retira el plat`, `Omet aquest àpat`, `Mou o intercanvia`. Move mode banner `Tria la destinació` and `Cancel·la`; target selected = exchange, pending = move, skipped = confirmation `Aquest àpat està omès. Vols substituir l’omissió?`; clear selection after server reply, show `Canvi desat` + `Desfés` while eligible. No silent changes on cancel.

Catalogue: list active dishes, filter category, search, `Nou plat`; archived tab/toggle `Arxivats`; name and categories visible, optional preference/special and recipe status; tap detail. Create/edit form name, primary and secondary categories, meal preference `Dinar / Sopar / Tots dos`, special checkbox. Archive confirmation explains existing plans kept; restore from archived detail. No permanent delete. Both catalogue detail and an editable selected slot link to the shared recipe editor. A past slot only shows its saved recipe. Contextual edits return to the same slot and clearly state that edits affect the shared recipe. Recipe editor includes prep textarea, ingredient rows name/quantity/unit/note/`Al gust`, add/remove row, `Desa l’esborrany` and `Publica la recepta`; show effective publication and unpublished draft status. A draft row can show `Quantitat pendent` and retain an optional known unit. Require all ingredients quantified or explicitly `Al gust` to publish. Invalid input preserves entries. Cancel warns before discarding edits. No fabricated recipes.

Shopping: header week and coverage notice, generated rows with name/quantity/check, manual products separately, `Afegeix un producte`, field/secondary action for override `Ajusta la quantitat`, `Restableix`, remove manual, orphans section `Ajustos pendents de revisar`. Show base and overridden amount, explicit provisional/draft warning, pending planning coverage and missing recipe names/positions; incompatible units separate. `Al gust` quantity text no numeric adjust. Checked states persist across devices and survive changes to matching amounts. Display the new calculated amount, even when an override remains. Avoid totals that imply full coverage. Empty list with create/plan action or add extras when week exists. Past lists read-only. Tablet two columns if space; mobile vertical.

## HTTP routes and adapter behavior

Use Catalan navigation labels and the routes below (internal action paths and technical function names may be English). Routing canonical `/menu/` current, `/menu/<YYYY-MM-DD>/` specific Monday; invalid date or malformed slot -> 404 or form validation 400. `pos` encodes `<day_index>/<meal>` in URLs; stable technical values allowed. GET reads and renders forms or confirmations without writing. Require CSRF on every POST, including non-persisting form previews, and version fields where specified. Use forms with PRG and flash status, return rendered error form with proper status when invalid. Redirect to specific current target with filter/context where safe, not arbitrary user-controlled URL. Mount `menus.web.urls` at the root. `/healthz` exposes status only.

| Routes | Method/use cases |
|---|---|
| `/` -> `/menu/`, `/menu/`, `/menu/<week>/` | GET F01-UC02/03; current/prev/next date links |
| `/menu/<week>/create/` | POST F01-UC01 |
| `/menu/<week>/slots/<day>/<meal>/` | GET selected detail/action sheet (F01/F06) |
| `/menu/<week>/slots/<day>/<meal>/triar/?mode=suggested&category=&q=&action=assign` | GET F03-UC01–03; `action=replace` for selected; `mode=all` removes category |
| `/menu/<week>/slots/<day>/<meal>/{assign,replace,reactivate}/` | POST F02-UC01/02/04 with version |
| `/menu/<week>/slots/<day>/<meal>/{remove,skip}/` | GET read-only confirmation; POST F02-UC03/04 with version and confirmation where required |
| `/menu/<week>/slots/<day>/<meal>/move/` | GET destination chooser, move/exchange review, or skipped-target confirmation |
| `/menu/<week>/{move,exchange,undo}/` | POST F02-UC05–07 with version; move and exchange also carry both positions |
| `/plantilla/` | GET template F04-UC01 |
| `/plantilla/<day>/<meal>/` | GET editor; POST set or clear suggestion F04-UC02/03 |
| `/plats/?q=&category=&archived=0`, `/plats/<id>/` | GET F05 browse/search/detail |
| `/plats/new/`, `/plats/<id>/edit/` | GET form; POST F05-UC03/04 |
| `/plats/<id>/{archive,restore}/` | GET read-only confirmation; POST F05-UC05/06 with version and confirmation |
| `/plats/<id>/recepta/` | GET F06-UC01; historical recipe uses only the saved slot detail |
| `/plats/<id>/recepta/edit/`, `/menu/<week>/slots/<day>/<meal>/recepta/edit/` | GET editor F06-UC02; POST non-persisting form preview |
| `/plats/<id>/recepta/{draft,publish}/`, `/menu/<week>/slots/<day>/<meal>/recepta/{draft,publish}/` | POST F06-UC03/04 |
| `/compra/` redirects to current, `/compra/<week>/` | GET F07-UC01 |
| `/compra/<week>/manual/add/`, `/compra/<week>/manual/<id>/edit/` | GET form; POST F07-UC02 with composite version |
| `/compra/<week>/manual/<id>/remove/` | GET read-only confirmation; POST F07-UC02 with composite version and confirmation |
| `/compra/<week>/adjust/` | GET form; POST F07-UC03 with generated key and composite version |
| `/compra/<week>/reset/`, `/compra/<week>/checked/` | POST F07-UC03/04 with item reference and composite version; checked also carries desired boolean |

Successful mutation redirects with 303 preferred (302 Django PRG acceptable for browser), 400 invalid input/transition, 404 unknown identifier, 403 historical write/CSRF, 409 stale version/concurrent change with `El contingut ha canviat. Actualitza la pàgina abans de tornar-ho a provar.`, 503 busy/unavailable with retry, 500 generic without stack trace. Preserve original input and explain conflict without auto-replaying stale actions. Cancel/no-op safe. Normal first visit never requires login. Configure allowed hosts; unknown host fails. No offline operation or sync; timeout/network error shows honest retry, no double optimistic success. Browser default POST form retains input where feasible; if small JS used disable duplicate submit while pending, re-enable on failed request; critical interactions work without JavaScript.

## Server-rendered paths and recovery

Every critical flow works with links, native forms, and server-rendered responses. JavaScript may render the same flows as dialogs or bottom sheets. Use a single set of validations and commands.

| Flow | Full-page fallback |
|---|---|
| Move or exchange | GET `/menu/<week>/slots/<day>/<meal>/move/` renders destination choices. A GET with a named destination renders the confirmation for a skipped target or a submit form for move or exchange. POST the explicit action with both positions and the version from the rendered choice. Preserve that version through confirmation. Cancel links to the slot. |
| Destructive or omission confirmations | GET each existing mutation URL with a confirmation view for remove, selected-slot skip, archive, restore, and manual removal. Confirmation never mutates. POST includes the confirmed intent and version; a direct unconfirmed submission with a current token renders the confirmation without writing. A stale token requires choosing the action again. |
| Template, picker and shopping | Use the existing GET forms and POST actions. GET on manual add/edit and adjustment shows the full form. Keep checkboxes operable with an explicit submit control. Validate all date, ID, key and version fields on POST. |
| Contextual recipe editor | GET `/menu/<week>/slots/<day>/<meal>/recepta/edit/`; POST corresponding `/recepta/draft/` or `/recepta/publish/` under the slot with the dish identity and version. Catalogue routes remain available. |
| Recipe row changes and cancel | POST editor form with `add_row`, `remove_row` or `review_discard` renders submitted values without saving. Use separate submit actions for save/publish. A deliberate discard returns to the originating detail. |

On `409`, return typed values and a separate read-only current value or status. Offer a non-mutating review step using the same form endpoint and a distinct action. It reloads current state and shows it alongside the submitted values without applying them. Ask for explicit reconciliation before a new submission with the reviewed token. A stale planning intent must be chosen again, and a deleted or historical target remains disabled. Never silently replace the stale token and submit. For `503` after a confirmed rollback, preserve form input and offer retry. After a lost response, state that the outcome is unknown. For create dish or manual product, retry the identical input with the same creation token to recover its original result. For other writes, inspect current state before retrying. See [atomicity and receipts](04-persistence.md#concurrency-and-atomicity).

Use a logical heading or surviving trigger as the focus destination after close or redraw, trap focus in an enhanced modal and keep background controls out of the tab order. Error summaries announce errors and link to fields. Test full names, validation notices, scrollable short-height dialogs and the on-screen keyboard at the [responsive QA gate](06-testing.md#cross-feature-acceptance-matrix). X02–X05 in the board are simulations; X04 illustrates optional feedback only while a real request is pending.

## V1 visual design and traceability

The replacement package under `docs/ux/` uses a synthetic catalogue independent of the private CSV. The [state matrix](../ux/STATE-MATRIX.md) maps 74 states to all 30 use cases. Use the board's four viewport choices and grouped visual wall for design review; its controls and data are not part of the product. The visual hierarchy uses a muted green/cream palette, compact cards, simple labelled secondary actions, keyboard focus outlines and an adaptable dialog/bottom sheet. The tablet retains the 14 positions in one compact grid and the mobile uses vertical days with bottom navigation. Selected cards show the fixed slot suggestion (when useful) and the detail shows the dish's actual categories separately. Quantity reset is available within the adjustment dialog; it is not a duplicate primary action in every row. Use these presentation rules as the V1 reference.

Examples and injected error states are in-memory design demonstrations, not backend test results. The route, validation, concurrency, transaction, historical and data rules in `docs/specs/` are normative. The UI must not expose review controls, demo data, fake loading buttons, or rely on a mock backend. No images, authentication, weekend restrictions or family records from legacy mockups. Refer to `../ux/VALIDATION.md` for prototype checks and limitations.
