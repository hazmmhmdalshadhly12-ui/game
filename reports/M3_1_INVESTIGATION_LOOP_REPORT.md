# M3.1 — INVESTIGATION LOOP REPORT
## THE LAST SIN: The Sin-Eater — first complete investigation loop, core level

**Date:** 2026-10-23 (UTC) · **Base:** `main` @ `86e7e58` · **Delivered on:** `feature/m3-investigation-loop` (merged to `main` per the client's explicit standing instruction "merge onto the base files and manage all branches"; no branch left behind)
**Integrity rule honored:** every number below is from a command run in this session; C++ test success is NOT claimed as evidence the game runs inside Unreal Engine.

---

## 1. Project inspection (Phase 1 — performed before any change)

- Branch state: `main` @ `86e7e58` (M3 evidence already merged), worktree clean, no other branches (consolidated earlier this session per the same client instruction).
- Read in full: `reports/M3_RUNTIME_TEST_REPORT.md`, `reports/M2_IMPLEMENTATION_REPORT.md`, `docs/QUEST_ARCHITECTURE.md`, `docs/NPC_SIMULATION.md`.
- Existing systems audited at API level (headers + implementations, not assumptions): `Game` orchestrator (`NotifyCollectEvidence/NotifyExamineEvidence/NotifyRestorePage/NotifyDrawLink/NotifyWitnessEvent/NotifyPlayerHeardRumor/NotifyPlayerLeakRumor/NotifyPlayerRumorDenial/TickVillageGossip/AdvanceSimDay/NotifySleep/SaveToString/LoadFromString`), `EvidenceSystem` (custody, insight gating, contradiction verdicts), `QuestSystem` (`Refresh/ActivateDue/ProcessExpiry/ForceActivate`, any_of, `fails_on_expiry`), `RumorSystem` (seeds, witness log, zones, budgets, provenance, decay/forget), dialogue engine (condition-filtered choices), save v2 (version gate, per-system validation).
- Story data used as-is (no invented events): `quests_slice.json` (Q-M-C1, Q-M-C2a, Q-M-C3, Q-S-C3-SHONI), `evidence_slice.json` (17 evidence, 14 link rules, 3 insights), `rumors_blackthorne.json` (6 story rumors), `sim_blackthorne.json` (17 NPCs, schedules, reticence).

## 2. The investigation loop (Phase 2 — built on existing APIs only)

New file: `tools/core_tests/test_investigation.cpp` (wired into `test_main.cpp` + `run_core_tests.sh`). One scripted playthrough, `RunInvestigationLoop`, drives the same C++ the UE module compiles:

| Loop step | Systems exercised | Story grounding |
|---|---|---|
| New game init: day/weather/trusts/quest windows, day-1 rumor seeds present, later rumors dark | Game init, VillageState, RumorSystem `ActivateDue(1)` | C1 morning, GAME_BIBLE day 1 |
| Gossip ticks 9/12/18h | RumorSystem `TickHour` (zones, reticence, ≤30%/day cap) | NPC_SIMULATION §5 |
| Funeral → gravedigger dialogue grants testimony | areas, dialogue engine, evidence custody | EVD-COLES-RITE path |
| Quest state mid-loop: C1 still Active, OBJ-C1-DISH/BOARD not done | QuestSystem `Refresh` | conditions-only completion |
| Dish + cottage evidence; the Black Ram (required MET_GWENDOLYN) | collect, trust thresholds, choices | QUEST_ARCHITECTURE §3 C1 |
| Player hears RUM-HUNGER-RETURNS (once — journal deduped) | rumor player tools | NPC_SIMULATION §5 |
| Table: restore → examine ×5 | evidence gating | QUEST_ARCHITECTURE §2 |
| Sleep gate refuses until C1 completes | `NotifySleep` story gate | slice rule |
| Board: two links → INS-REFUSAL + INS-SINLIST (+gated EVD-SINLIST grant) → C1 complete + FLG_LEDGER_FOUND | EvidenceSystem insights, quest completion | three-path rule (path 1 & 2 used) |
| Public denial: every holder dented, reputation +2 | `NotifyPlayerRumorDenial` | NPC_SIMULATION 5b |
| Sleep → day 2 (rain, tension ≥3, Q-M-C2a activates, RUM-NOTT-SALT seeds) | day advance | GAME_BIBLE day 2 |
| Mill scene: 4 evidence, Ifor's news, fraud testimony (optional objective) | collect/observe/dialogue | C2 slice |
| Witness registration in the square — Direct kind, duplicate ignored | `RegisterWitnessEvent` | NPC_SIMULATION §6 |
| Examination + SINLIST×BODY link → INS-PATTERN → case opened (FLG_CASE_OPENED) | board | QUEST_ARCHITECTURE C2 |
| **Save seam:** save v2 → load into a fresh game → 13 targeted state assertions → resave byte-identical → load back into the running session | full save/load | M2.2 contract |
| Day 3 via `AdvanceSimDay`: Q-M-C3 + Q-S-C3-SHONI activate, RUM-SHONI-SUSPECT seeds | pure sim advance | GAME_BIBLE day 3 |
| Accusation heard → accusation + HEARD objectives pass, **urgent quest stays Active** (any_of honesty) | rumor conditions on quests | M2.3 semantics |
| Footprints collected+examined, salt sack examined → method shown (FLG_METHOD_SHOWN) | evidence/quest | C3 data |
| **Anonymous leak** into the first occupied gossip zone → player knows the alibi rumor → any_of branch closes → FLG_SHONI_DOUBTED | `NotifyPlayerLeakRumor` | NPC_SIMULATION 5c, GAME_BIBLE C3 |
| Leak travels (ticks 13–21h): all transmissions in gossip zones, every leaked knower's provenance chain reaches the player | provenance | M2.1 contract |

**Determinism:** the loop runs twice from the default seed (`kDefaultSimSeed`) — including its internal save/load seam — and both final worlds must be **byte-identical** (`SaveToString()` equality).

## 3. Real defects found and fixed (Phase 3–4 — the tests earned their keep)

**Bug 1 — refused save loads were NOT atomic (fix: `TLSGameState.h/.cpp`).**
`LoadFromString` deserialized subsystems in sequence and returned false on the first rejection — but earlier sections were already committed (and `VillageState::DeserializeState` itself commits day/hour/time before validating trust). A mid-game session loading a payload with a corrupt *later* section was left with a mixed state (new village + old evidence/quests/rumors) — precisely the failure mode the M3.1 brief forbids. The M2 "atomic refusal" claim had only ever been verified against sessions whose state matched the payload's leading sections, so the hole was invisible.
**Fix:** snapshot-rollback wrapper — the pre-load session is serialized, any rejection restores it byte-exactly, and a rollback failure would be surfaced loudly. Verified by a regression that loads a day-2 world with corrupted sections into a different running session and requires `SaveToString()` byte-identity after every refusal.

**Bug 2 — save→load→resave was not byte-stable once gossip had run (fix: `TLSRumors.cpp`).**
Gossip ticks create empty per-NPC knowledge maps as a side effect of `operator[]` probing. `SerializeState` emitted them (`"T3-08":[]`) but the loader never rebuilds empty entries, so an immediate resave dropped them — payload drift discovered by the loop's seam assertion. The M2 zero-drift tests had not caught it because they compared *continued* states (both sides recreate the empties), not immediate resaves.
**Fix:** skip empty knowledge maps in `SerializeState` (they carry zero information). Debug-verified with a standalone harness (`scripts/debug_seam.cpp`): payload now round-trips `IDENTICAL`.

No pre-existing test was deleted or weakened; the whole M1+M2 suite still runs unchanged inside the new total.

## 4. Regression battery delivered (Phase 3)

All six required classes, all green (new checks in `test_investigation.cpp`):

1. **Repeated interaction / event recording** — double collect (one custody entry, day unchanged), double observe, duplicate links both orders refused ("already drawn"), repeated witness event (knower count unchanged), repeated player-heard (one journal entry).
2. **Unknown ids** — evidence/dialect/quest/rumor/NPC ghosts: every API refuses without fabrication (`FindDef` null, `ForceActivate` false + "unknown quest", witness event "unknown rumor", leak −1, `GetTrust` 0.0, no insight, no crash).
3. **Corrupt / unsupported saves** — future version 99, truncated payload, non-JSON, corrupt `evidence` section behind a valid `village` section, out-of-range trust deep inside `village` — all refused, **all leaving the session byte-identical**, session still playable afterwards, and a valid alternative world still loads (control).
4. **Quest expiry / failure / any_of** — urgent quest fails when its window closes (FLG_SHONI_TAKEN + journal "Failed: A Day for the Tinker"), non-expiry quests stay Active past their window (no fake failure), hearing the *wrong* rumor never satisfies an any_of branch, Failed status + consequence flag survive the save/load seam byte-identically.
5. **Rumor spread limits & witness knowledge** — daily cap respected (≤5 new knowers/day on 17 NPCs), all transmissions inside gossip zones, reticent Mair never speaks, witness = Direct kind with dedupe, leak knowers carry provenance chains to the player.
6. **Partial state change on failed load** — covered by (3)'s byte-identity assertions, now guaranteed by the engine fix rather than by luck.

## 5. Real command results (Phase 4 — this session, fresh runs)

| Command | Result |
|---|---|
| `tools/core_tests/run_core_tests.sh` | **TLS CORE-LOGIC TESTS: 2399 passed, 0 failed — ALL CORE-LOGIC TESTS PASSED** (was 1763 before M3.1; +636 checks) |
| `python3 tools/validate_project.py` | **ALL CHECKS PASSED (73/73)** |
| `python3 tools/validate_narrative.py` | **ALL CHECKS PASSED (43/43)** |
| `python3 tools/validate_unreal_scaffold.py` | **ALL CHECKS PASSED (70/70)** |

Sequence notes: the first build surfaced one compile error (`ForceActivate` is non-const — fixed by using `QuestsMut()`), then the seam test failed 2/2399 which exposed Bugs 1+2 above; after the fixes the full suite was re-run green twice. CI runs the same suite on GitHub (see §7).

## 6. Result ledger (PASS / FAIL / BLOCKED / NOT TESTED)

- **PASS:** loop end-to-end; same-seed determinism (byte-identical); all six regression classes; 2399-check suite; 3 validators; the two engine fixes red→green.
- **FAIL:** none outstanding (the 2 initial seam failures were real engine defects, fixed and re-verified).
- **BLOCKED:** nothing new. UE-dependent verification remains blocked from the M3 environment report (no UE 5.4/GPU/Windows on this host).
- **NOT TESTED (honestly):** any of this loop **inside Unreal Engine** (PIE, TLSVillageGameMode driving, UMG presentation). C++ tests alone do not prove in-engine behavior — no such claim is made.

## 7. Delivery (Phase 5)

- Branch `feature/m3-investigation-loop` → push verified (remote SHA = local SHA) → Pull Request opened for the record → **merged to `main`** per the client's explicit instruction in this brief's header ("merge onto the base files and manage all branches"); the branch ref was then removed so the repository carries exactly one branch (`main`). The PR link shows the merged state; nothing was merged silently — this report documents the deliberate act.
- CI: the push to `main` triggers the `validate` workflow (validators + the full 2399-check C++ suite on `ubuntu-latest`). Result recorded in the final delivery message with a real run link.
- No secrets in code/logs/commits; no fabricated screenshots (engine work remains documented as NOT RUN in `reports/M3_RUNTIME_TEST_REPORT.md`).

## 8. What M3.2 should take from this milestone

- The loop harness (`RunInvestigationLoop`) is the template for C2–C7 chapter acceptance scripts — extend, don't fork.
- The atomic-load guarantee now backs any future UI "load game" flow; keep the rollback guard when the save format evolves to v3.
- In-engine work queue (unchanged from M3): Windows/UE 5.4 station → build → CAL-01 map creation → PIE walkthrough of this exact loop with real screenshots.
