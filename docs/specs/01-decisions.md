# Decisions for independent review

> V1 reference. For current F07 behavior, storage access and acceptance, see [V2.5](V2.5-SHOPPING-REMINDER.md).

This record consolidates the approved V1 product rules and the technical defaults resolving the independent review. The linked shared contracts define the acceptance details.

| ID | Decision / rationale | Status |
|---|---|---|
| D01 | Weeks start Monday in Europe/Madrid. Monday date is the identity. Current and future weeks are editable; past weeks are read-only and cannot be backfilled. The final transaction clock check governs rollover. | V1 baseline |
| D02 | Render 14 usable positions for a missing editable week. Create it by Monday date on the first valid mutation, atomically with that change. GET never creates it. | V2.2 |
| D03 | The singleton template owns exactly 14 optional suggestions. Lliure means no suggestion. Editable pending slots read live suggestions. Legacy copies remain stored and do not represent explicit overrides. | V2.2 |
| D04 | Removal makes a selected slot pending. Skipping a selected slot requires confirmation. Direct selection into an omitted slot requires explicit reactivation first. | V1 baseline |
| D05 | Move or exchange within a week. Confirm a move into a skipped slot. Keep suggestions at their positions. Single-level undo survives reload and unrelated refreshes, but expires on a subsequent successful planning edit or changed snapshot of either position. | V1 baseline |
| D06 | Rank ordinary before special, preferred or both before opposite, never planned before oldest to newest, then by ID. Include all persisted meal dates, including future. Filter any category membership. Case- and accent-insensitive search does not change ranking or eligibility. | V1 baseline |
| D07 | Archive removes a dish from new selection. Existing occurrences remain legible, movable and counted. Restore re-enables selection. No hard delete. | V1 baseline |
| D08 | One effective publication and one working draft per dish. Edit from catalogue or editable weekly dish detail. Named draft ingredients may have an unknown quantity. Before publication, valid known quantities contribute provisionally and trigger an incomplete-list warning. Later drafts leave the effective publication unchanged. Publish requires preparation, at least one line, and every line quantified or explicitly al gust. | V1 baseline |
| D09 | Refresh editable slot snapshots atomically with effective catalogue or recipe changes. Historical slots and overlays remain frozen. Each week has a stable shopping derivation version, including weeks from before M7. | V1 baseline |
| D10 | Use the fixed 13-category vocabulary in the domain model. Preserve the existing CSV format with an explicit positional path and comma-separated secondary categories. Validate without silent correction. The reviewed private copy already uses the canonical labels. | V1 baseline |
| D11 | Ingredient identity uses whitespace normalization, NFC and casefold with accents preserved. Use a deterministic label without a global registry. Store exact decimal text and aggregate in canonical units. Unknown draft amounts contribute nothing and al gust is a separate line. | V1 baseline |
| D12 | Keep generated shopping derived and persist only manual items, checks, and adjustments. Matching checks survive recalculation with the updated quantity visible. Preserve adjusted orphans and drop checks when a key disappears. | V1 baseline |
| D13 | Use SQLite transactions, aggregate compare-and-swap, one composite shopping token, conflict reconciliation, and idempotent receipts for dish and manual creation. See the persistence and web contracts. | V1 baseline |
| D14 | No application login. Only the trusted household LAN may access the app, verified before release. Use explicit hosts, CSRF, production secret and safe build inputs. Existing services stay untouched. | V1 baseline |
| D15 | Specify V1 upfront and continue through automated gates per slice. Record owner QA separately and consolidate it before release. Keep implementation, QA acceptance, and release statuses distinct. | V1 baseline |
| D16 | No images, weekend restrictions, recipe generation or extra modules. Only synthetic fixtures and generic documentation belong in publishable artifacts. | V1 baseline |
