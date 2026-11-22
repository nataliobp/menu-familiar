# Full implementation plan — autonomous execution

This plan records the original V1 delivery slices. The [V2.2 product corrections](V2.1-V2.2.md) supersede its interaction contracts. Continue after automated checks and record owner QA separately for release. Start from the existing partial M0 implementation and preserve the working tree and migrations.

| Slice | IDs and dependencies | Implementation / checkpoint |
|---|---|---|
| M0-A | Environment, reviewed docs | Isolated Python venv, existing Django 5.2 dependency, checks; settings Catalan, timezone Madrid (approved D01), remove admin route, explicit config/env DB path, secure production defaults; English README. Tests with isolated settings, no host changes. |
| M0-B | M0-A | Forward catalogue/schema upgrade from 0001, seeded keys, compatible parser/CLI, fresh and populated migration tests, isolated private fidelity. |
| M1-A | M0 | F04-UC01: seed single template 14 slots; read port, view, responsive shell, tests and dev LAN smoke where possible. |
| M1-B | M1-A | F04-UC02 then 03: set/change/clear, version guard, forms, validation. |
| M2-A | M1 | F01-UC01/02: date identity, past-week guard for every write, immutable copied suggestions, shopping projection version 1. Current week is the staged UI. Check the template-copy acceptance from M1 here. |
| M2-B | M2-A + catalogue | F03-UC03 basic unfiltered picker, F02-UC01 assignment (stable ID order initially), F02-UC02 replacement, F02-UC03 removal; each separately tested; no artificial filter restrictions. |
| M2-C | M2-B | F03-UC01 category filter (soft), F03-UC02 search; ranking in increments ordinary/special precedence then meal preference then current recency and ID ties, verify exact full precedence before finishing M2. |
| M2-D | M2-B | F02-UC04 skip/reactivate, confirmations and state tests. |
| M3-A | M2 | F01-UC03 navigation and future creation. Verify previously implemented guards, rollover and cross-week ranking. |
| M4-A | M3 | F02-UC05 move, then F02-UC06 exchange, then F02-UC07 undo and invalidation; optimistic guards, atomic failure tests, two-tap UI. |
| M5-A | M0/M3 | F05-UC01 browse then UC02 search; F05-UC03 create and UC04 edit, canonical membership, snapshot propagation/version (editable only). |
| M5-B | M5-A | F05-UC05 archive and UC06 restore; verify picker and existing menu behavior. |
| M6-A | M5 | F06-UC01 detail including exact historical snapshot/missing; F06-UC02 editor input and validation; F06-UC03 save partial draft. |
| M6-B | M6-A | F06-UC04 publish, effective revision, template not affected; editable snapshot fan-out, no past data mutation. |
| M7-A | M6 + M4 | F07-UC01 pure aggregation/coverage, read-only list, shopping state overlay model; preserve historical derived values, no GET writes. Integrate all dependent writers in same transaction. |
| M7-B | M7-A | F07-UC02 manual add/edit/remove; F07-UC03 absolute override/reset/orphan; F07-UC04 checked state; re-run all menu/recipe update tests for refresh and preservation. |
| M8 | All | Full regression, browser and no-JS QA, privacy and build audit, production configuration and serving, isolated backup/restore rehearsal. Owner manual QA, network isolation and deployment authorization gate release. |

Start M2 with an unfiltered picker and finish complete ranking before the M2 gate. Build cross-week identity, date guards and version discipline with the first planning write. M3 exposes navigation and future creation, M4 tests move/undo ranking, M6 adds recipe propagation, and M7 reruns relevant planning and recipe cases with shopping. The acceptance matrix names the first runnable gate for cross-feature cases.

## Checkpoint protocol

Maintain `docs/specs/PROGRESS.md` for generic status, or the ignored root `local-progress.md` for a local journal. Initial: status per M0–M8 and 30 IDs, tests, unresolved issues, manual QA status. Update after each slice with: IDs, changed code/migrations, tests and outcomes, known debt, next dependency, local commit hash if permitted. No secrets, real names or full logs. Use atomic local commits with descriptive English messages `M2 F02-UC01: assign a dish to an empty slot`. Do not include unrelated modifications or stage indiscriminately (`git add .` discouraged); check `git diff --cached` and privacy. Spec review commit handled separately. No `git reset --hard`, force-push or destructive cleanup. If interrupted, read progress+git status, rerun checks, continue incomplete slice without replaying already committed work. Independent reviewer examines full diff vs approved baseline and tests. Human manual QA remains an explicit pending release gate.

## Stop conditions

Do not stop after each milestone; proceed to next after automated checks. Stop and report only if required information unavailable, conflicting approved requirements cannot be resolved safely, service/real data risk, credentials/privileged install needed, quota or environment blocks execution, or failing tests cannot be corrected in reasonable attempts. Use best-effort safe work on unblocked slices, clearly identify blockers. No claims about future execution while Codex process is not running. No real external network or billing integrations beyond dependency fetch if authorized. Avoid context bloat: read shared design once, current UC + direct dependencies per slice, progress on resume. Record quota checkpoints outside source if desired; not acceptance criteria.
