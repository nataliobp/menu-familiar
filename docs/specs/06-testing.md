# Verification and QA contract

Tests are part of the implementation, not a later feature. Use `unittest` / Django test runner (already installed via requirements) and stdlib synthetic fixtures. Domain/application tests import no framework; runnable with `python -m unittest discover -s menus/tests/domain` and application equivalent or a documented precise command. Integration/web suite `python manage.py test` runs in separate test DB; confirm actual test runner discovers all suites, including test packages. No tests refer to private catalogue names or copy its rows. Browser QA can use local Chromium/Playwright if already present and permitted, or add a documented dev-only browser dependency only when justified; no new production framework. Real viewport manual checks remain pending until owner performs them. Never claim browser E2E from Django Client alone.

## Test levels

- Domain: exact invariants, transitions, pure ranking/aggregation, recipe validation, normalization, date boundary, no framework imports. Table-driven subtests for every state. Use only synthetic dishes `Plat A`, `Plat B`, `Plat C` and chosen demo ingredients; no real menu or account data.
- Application: simple purpose-specific in-memory fakes; verify ports and transaction coordination, authorization by time, invalid/stale inputs, isolation; don't assume fake rollback proves real atomicity. Inject fake clock and forced failure.
- Integration: actual migrated SQLite file in temp dir, schema constraints, JSON codecs roundtrip, compare-and-swap, rollback **after first write**, query memberships distinct, history and fan-out. For concurrency use `TransactionTestCase` and independent connections to file-backed DB; document deterministic orchestration (no reliance on sleeps). Verify no lost update under collision, one succeeds or lock/409 handled; DB never corrupted. Test migration from empty and upgrade fixture from earlier milestone without loss.
- Web: Django Client with CSRF enforced for representative mutations, wrong method denied, confirmation GET leaves records and versions unchanged, POST without CSRF rejected, Catalan messages, form values preserved, valid redirects, validation/error status, historical write attempts denied at server, no hidden admin/login links, autoescape malicious text, forbidden Host rejected, no image fields/URLs. Tests for duplicate click/stale version, unknown identifiers, no GET side effects.
- Browser: critical journeys at 360×780, 390×790 (also 430 wide), 800×480, 1024×600; measure actual DOM and screenshots locally with synthetic data; no page horizontal overflow; tablet shows 14 slots, long labels accessible; touch/keyboard focus and error paths, mobile list; no remote dependencies. Do not put real-data screenshots in Git.

## Cross-feature acceptance matrix

| ID | Given / When / Then | Primary coverage |
|---|---|---|
| QA-01 | Empty DB, seed category migration and corrected local CSV: import success, compare every required field; repeated identical import no changes. Synthetic malformed and conflict cases rollback; private check separate. | M0 |
| QA-02 | Set Monday lunch category, leave another free; reload from new browser; assign to create the week; change the template; empty editable slots follow, while chosen dishes and historical snapshots stay intact. | F04/F01 |
| QA-03 | Start empty week; choose unrestricted dish, replace with another, remove; unrelated slots unchanged; repeat selection in another slot allowed. | F01/F02 |
| QA-04 | Candidates with multiple categories, preferred/unpreferred, special/normal, planned/never, tied IDs. Filter union no duplicates; exact rank ordinary preferred never, ordinary preferred older before newer, ordinary opposite, then analogous special tiers; `both` equals preferred. Search and all retains eligibility/ranks; archived not shown. | F03 |
| QA-05 | Frozen local Sunday then Monday boundary; create current/future, navigate absent past, existing past read-only. Attempt POST on every historical mutation, verify DB unchanged; earlier current-week slots still editable. | F01/F02/F07 |
| QA-06 | Move selected to pending, swap two, confirm skipped destination, undo each; original snapshots/states/suggestions restored; recency changes; inject failure between row writes and verify rollback. Later planning edit invalidates undo. | F02 |
| QA-07 | Two concurrent requests with same version; first saves; second stale/busy must not overwrite. Recipe update affecting more than one week rolls back all on failure. | Shared |
| QA-08 | Create/edit/archive/restore synthetic dish. Archiving removes from picker, existing selections and past labels remain; editing updates editable week snapshots only. | F05 |
| QA-09 | Missing recipe, partial draft, malformed quantities, complete publish then edit draft; effective publication unchanged until republish; preserve entries on validation failure; current/future propagate, past snapshot unchanged. | F06 |
| QA-10 | A synthetic recipe uses 160 g ingredient X and 1 unit Y; another uses 0.18 kg X and 200 g Y; X totals 340 g, Y separate count/weight rows; adding repeated first occurrence raises X to 500 g; `al gust` separate/no quantity. | F07 |
| QA-11 | Pending, skipped, missing/draft recipe, all skipped, empty generated list with manually added product; coverage truthfully reported without fabricated amounts. | F07 |
| QA-12 | Add extra, adjust generated amount, check row, replace dish; matching key preserves state; vanished adjustment becomes visible orphan; reappearance restores override, not check; reset orphan removes it; manual rows unchanged. | F07 |
| QA-13 | Menu/shopping/recipe rendered at target widths with several very long synthetic names; all 14 slots tablet, no horizontal overflow, detail exposes full name; cancel and stale form preserves data; two-tap move without drag. | UX |
| QA-14 | Fresh clone without private source: migrations/check/tests pass, local source check NOT RUN; no secrets in Git; debug off production, wrong host rejected, CSRF, LAN access only. | M8 |
| QA-15 | Back up isolated DB, restore into separate directory, apply migrations and compare row counts, key sample synthetic values, then serve it; no changes to real family data. | M8 |

## Cross-feature regression gates

| Gate | Required coverage |
|---|---|
| M0 | Fresh migration and populated upgrade from 0001, invalid legacy data rollback, and subsequent automatic IDs. Synthetic unordered header, quoted multi-category field and conflict rollback. Record private fidelity separately. |
| M2 | Virtual weeks, live template suggestions, stale writes, read-only guard, all ranking tiers and picker normalization vectors. |
| M3 | Madrid Sunday/Monday rollover before the final clock check, DST calendar and year navigation, future recency, past direct-write refusal. |
| M4 | Move, exchange, undo and rollback. M5/M6 verify that related snapshot refresh invalidates undo and unrelated refresh rebases it. |
| M5 | Dish lost response and concurrent same token, payload mismatch conflict, rollback then retry, assignment racing archival, and catalogue search on composed and decomposed accents. |
| M6 | Editor from catalogue and editable slot, changed slot and rollover rejection, known and unknown draft rows, publish rejection for unknown values, and rollback across all affected weeks. |
| M7 | Exact boundary amounts and overprecision, overflow and corrupt-text rollback, exact reload of the former precision-loss example, and full-range override through orphan/reappearance. Verify composite token races for initial overlay creation, recipe publication versus shopping adjustment, and multi-query read consistency. Check retained checks with updated amounts, manual create receipt replay after deletion, and deterministic frozen historical DTO before and after a projection/codec upgrade. |
| M8 | Exercise critical flows without JavaScript, compare stale and current form values before explicit submission, and simulate a lost acknowledgment. At 360×780, 390×790, 430-wide, 800×480 and 1024×600 verify controls, focus return and error announcements, including long labels, notices and software keyboard. Verify LAN access and denial and inspect Docker context/image and published package with synthetic exclusion markers. |

For numeric limits, verify the 100-row cap and the exact maximum of `1399999999998600.000` in canonical units. Test a quantified draft at the limit and reject the first value outside each bound. The aggregate overflow branch is a defensive test using invalid persisted input.

## Manual QA script (consolidated owner gate)

Use a disposable DB and synthetic seed first. Set real local `DJANGO_DB_PATH` to the isolated absolute path; verify before migrate/QA. Never run conflict tests against the family DB. A live browser can be opened on host LAN only via configured dev port; check no other services changed. On real catalogue only perform non-destructive fidelity and safe planning intentionally chosen by owner.

1. M0: check 13 category labels, upgrade a populated synthetic database, and import synthetic and private data independently to disposable databases; run identical rerun; exercise partial match, conflict and malformed file; inspect counts, no other changes; run checks and test suite. Owner may inspect real values locally. Do not require a temporary catalogue GUI to prove import.
2. M1: open template on mobile and tablet, set/modify/clear category, refresh; verify all 14 positions and no menu creation side effects.
3. M2: create current menu, select any dish without filter, replace/remove, apply category filter/search, skip/reactivate, use unrelated category and opposite preference; see exact priority order with synthetic fixtures. Refresh from second device.
4. M3: navigate last/next/current; create future plan; edit past day of current week; past menu read-only including direct POST in automated test; verify live hints in empty editable slots and ranked suggestions across weeks.
5. M4: move, swap, confirm/cancel skipped destination, undo; another edit invalidates; try stale tabs. Same shopping totals for unchanged occurrences when M7 present.
6. M5/M6: create synthetic dish, edit metadata, archive/restore; view pending recipe, save draft, fix invalid numeric field, publish, edit draft and republish; verify current/future vs past.
7. M7: generated sums, repeated occurrences, incompatible units, taste rows, warning, extras, overrides, check, orphan/reset/reappear. Edit menu/recipe and revisit from second screen. Future editable, historical immutable.
8. M8: viewport matrix, accessibility basics, LAN access from two devices, restart persistence, backup/restore rehearsal, no public data/ports. Review actual mockups against implementation. Owner reports pass/fail per case/slice.

Record automated command, exit status, count, skip reason, and browser evidence location or `NOT RUN` in local implementation progress. Record human QA as pending until performed. No claim of release complete if blocking failures or unresolved cases remain. A failed test requires root cause and repeat of relevant suite; no deleting tests to pass. Final regression full suite plus independent review.
