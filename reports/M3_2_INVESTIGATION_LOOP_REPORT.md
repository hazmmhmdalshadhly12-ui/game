# M3.2 — INVESTIGATION LOOP REPORT (EXTENDED)

## THE LAST SIN: The Sin-Eater — the extended investigation loop, load-contract hardening, and the witness-branch fix

**Date:** 2026-10-23 (UTC) · **Base:** `main` @ `0151add` (M3.1 merged) · **Delivered on:** `feature/m3-2-investigation-loop` → Pull Request → merged to `main` after CI.
**Integrity rule honored:** every number below is from a command run in this session. C++ test success is NOT claimed as evidence the game runs inside Unreal Engine — see §7.

---

## 1. Project inspection (before any change — per the brief)

- `main` @ `0151add`, worktree clean (112 mode-bit-only deltas neutralized with `core.fileMode=false` + `git restore`; zero content diff verified twice).
- PR ledger audited via API: #1 (M2), #2 (M3), #3 (M3.1) — all `merged=true`. `feature/m3-investigation-loop` no longer exists; `main` carries M3.1.
- Read: `reports/M3_1_INVESTIGATION_LOOP_REPORT.md` (incl. its "what M3.2 should take" section), M3 evidence files, `docs/QUEST_ARCHITECTURE.md`, `docs/NPC_SIMULATION.md` semantics already encoded in the headers; every API used below was verified against its definition before use (headers + call sites).
- **Baseline recorded BEFORE any change** (fresh runs, this session):

| Command | Baseline result |
|---|---|
| `tools/core_tests/run_core_tests.sh` | **2399 passed, 0 failed** |
| `python3 tools/validate_project.py` | **73/73** |
| `python3 tools/validate_narrative.py` | **43/43** |
| `python3 tools/validate_unreal_scaffold.py` | **70/70** |

- **Gap map built from the data, not from assumptions** — what M3.1/M1/M2 had NOT exercised: 11 of 14 link rules (both SUPPORTING rules, all three CONTRADICTION rules, and the alternative insight routes), the full Crane/Mair dialogue trees, Coles' B3/B4/BH2 and hunger claim, Ifor's day-1-only Trefan topic, the trust gate on Gwendolyn's H2 from both sides, `FindConflicts` in-loop, multi-day decay/forget inside a loop, the `any_of` alibi's **witness branch** (`npc_rumor` targets `T3-07=RUM-SHONI-HILL` / `T3-01=RUM-SHONI-HILL`), and the load contract's treatment of unknown ids and empty-vs-absent sections.

## 2. Real defects found and fixed (the tests earned their keep again)

**Bug 1 (engine) — witnessed words never updated quests (fix: `TLSGameState.cpp`).**
`Game::NotifyWitnessEvent` registered the rumor knowledge but never called `RefreshAfterChange()`. Quest tasks of type `npc_rumor` ("a villager carries the word") therefore could never complete through a witness event — and `Q-S-C3-SHONI`'s `any_of` alibi branch, whose own data reads "let a witness's word travel", was only reachable via the anonymous-leak path (which happens to refresh). The M3.1 loop never hit this because it closed the alibi through the leak branch. **Fix:** refresh on successful registration, exactly like `NotifyPlayerLeakRumor`. Regression: the M3.2 loop closes the alibi through the witness branch and asserts completion + `FLG_SHONI_DOUBTED=1` while the player has NEVER heard `RUM-SHONI-HILL`.

**Bug 2 (contract) — evidence/quest deserializers accepted ghost ids (fix: `TLSEvidence.cpp`, `TLSQuests.cpp`).**
The load contract was inconsistent: village and rumors validate strictly (unknown npc/rumor refused, ranges checked), but `EvidenceSystem::DeserializeState` created runtime entries for ANY id (`Runtime[Id] = R`) and `QuestSystem::DeserializeState` accepted unknown quest ids AND silently mapped garbage status strings to `not_started`. A hand-edited or foreign payload could make `IsCollected("EVD-GHOST")` lie, skew `CollectedIds()` counts, or fabricate `Status("Q-GHOST") == Completed`. **Fix:** unknown/empty evidence ids, unknown insight ids, unknown named link rules (empty rule id = the legitimate NoRule verdict, kept), non-string custody chain entries, unknown/empty quest ids and unknown status strings are all refused. Atomicity is guaranteed by the existing M3.1 snapshot-rollback wrapper. Regressions: six ghost/bad-type payloads each refused with the running session byte-identical afterwards, plus a control load.

**Documented tolerance (tested, not changed):** unknown `reached_areas` strings stay accepted — `Game` keeps no area registry, no task or dialogue condition can reference a non-existent area (proven inert), and the value round-trips byte-stably. Now a documented contract with a regression, not an accident.

## 3. What M3.2 added (all on existing systems and story data — nothing invented)

New file `tools/core_tests/test_m32_extended.cpp` (wired into `test_main.cpp` + `run_core_tests.sh`; M3.1's file untouched):

| Pillar (brief §3) | Delivered |
|---|---|
| **أ — the extended loop** | Day 1→3 through the REAL core: churchyard register observed AND collected; Ifor's Trefan topic asserted available day 1 and gone day 2 (`day_max` gate both directions); Gwendolyn's trust gate asserted CLOSED after only a gentle exchange and OPEN after `G04+H1` (≥ 20 exactly as M3.1's data implied); Mair's pressing tone costs exactly 4.0 trust (`(−3−5)×0.5`) then kind +1.0; Crane's dish DENIAL lands in the dish's custody chain; Coles' hunger babble grants the claim the board later refutes; OBJ-C1-SIDE (optional) verified while the quest is Active; C1 completed via the ALTERNATIVE board routes (`ledger+witness` → INS-REFUSAL, `rite-paper+guinea` → INS-SINLIST); day 2: witness registration (Direct, hop 0), fraud topic, the SACK+BODY supporting link (`Consistent`, no insight), SERMON+WEIGHTS contradiction (`CONTRADICTION`, no insight), a deliberate no-rule pair recorded as board silence, INS-PATTERN via the FRAUD route, the duplicate-route draw re-granting nothing, Crane's `CH3` tower-night topic asserted shut before INS-PATTERN and open after it, Gwendolyn's day-2 mill topic; day 3: footprints method, HUNGER+FOOTPRINTS contradiction, non-gossip leak refused with no journal entry, the alibi closed through the WITNESS branch (player never hears the rumor), `FindConflicts` reports the shoni topic conflict for T3-07, day-3 gossip stays in zones. |
| **ب — save/restore expansion** | 3-cycle save→load→resave byte-identical on a rich mid-loop state; the seam inside the loop (witness kind, contradiction/no-rule/duplicate links, flags, insights all survive; resave byte-identical; load back into the running session); **sim-RNG seam** — two sessions restored from the same payload replay the same gossip hour with identical transmissions and byte-identical resaves (in-loop AND standalone); ghost-id/bad-status refusals (§ Bug 2) each leaving the session untouched; empty-vs-absent equivalence for all four optional sections (`flags`, `reached_areas`, `dialogue_history`, `journal`); the four required v2 sections refused when absent; a load during an open dialogue ends the session and replaces the world cleanly. |
| **ج — regression & determinism** | Order independence: the same day-1 interaction SET in two different orders lands on the same canonical semantic state (sorted quests/flags/evidence/insights/links/trust/rumor counts; journals legitimately differ in order and are excluded with the reason stated); the extended loop run twice from the default seed is byte-identical; a decay watch verifies the witnessed curve EXACTLY (0.9^d for `RUM-NOTT-SALT`, six decays, no drift) and the leaked word dying exactly when the DATA says (0.55 × 0.75^5 < 0.15 on day 8 — the forget day is computed from the def, not hardcoded); daily cap and gossip-zone discipline hold on every watched day; **no-resurrection**: after `Q-S-C3-SHONI` fails on expiry, a later witness delivery cannot revive it, `FLG_SHONI_DOUBTED` stays 0, and the Failed state survives the seam. |

## 4. Real command results (this session, fresh runs)

| Command | Result |
|---|---|
| `tools/core_tests/run_core_tests.sh` | **3690 passed, 0 failed — ALL CORE-LOGIC TESTS PASSED** (baseline 2399 → **+1291 checks**) |
| `python3 tools/validate_project.py` | **ALL CHECKS PASSED (73/73)** — no regression |
| `python3 tools/validate_narrative.py` | **ALL CHECKS PASSED (43/43)** — no regression |
| `python3 tools/validate_unreal_scaffold.py` | **ALL CHECKS PASSED (70/70)** — no regression (Core/ purity re-verified: no UE includes) |

Sequence notes: 8 build+run iterations were needed. The failures encountered were real signal, worked red→green: one compile error (reference-vs-pointer in the order test), two payload-surgery mistakes of the TEST itself (`[2,` is not JSON; `reached_areas` is an array, not an object; serializer re-sorts sets on resave), three LOOP-design catches (B3 is a ROOT choice; `EVD-RITE-PAPER` must be examined before its board link; the day-offset in the decay watch), and the two genuine ENGINE defects (§2 Bugs 1–2) which the new tests exposed and now pin. A full repeat run of the suite reproduced 3690/3690 (stability check). CI runs the same suite on GitHub (§6).

## 5. Files changed

| File | Change |
|---|---|
| `03_Unreal/Source/TLS/Core/TLSGameState.cpp` | Witness events now refresh quest evaluation (Bug 1) |
| `03_Unreal/Source/TLS/Core/TLSEvidence.cpp` | Strict deserialization: unknown evidence/insight/rule ids + non-string custody entries refused (Bug 2) |
| `03_Unreal/Source/TLS/Core/TLSQuests.cpp` | Strict deserialization: unknown quest ids + unknown status strings refused (Bug 2) |
| `tools/core_tests/test_m32_extended.cpp` | NEW — the extended loop, decay watch, order independence, save/restore expansion, no-resurrection (~1200 lines, 12 sections) |
| `tools/core_tests/test_main.cpp` | Wires `tls_test_m32::RunAll()` into the suite |
| `tools/core_tests/run_core_tests.sh` | Compiles the new translation unit |
| `README.md` | Status line, current numbers (3690/3690, 43/43), honest core-vs-engine boundary note |
| `reports/M3_2_INVESTIGATION_LOOP_REPORT.md` | This report |

No pre-existing test was deleted or weakened; the whole M1+M2+M3.1 suite still runs unchanged inside the new total.

## 6. Delivery

- Branch `feature/m3-2-investigation-loop` → push verified (remote SHA = local SHA) → Pull Request opened toward `main` → CI green → **merged to `main`** per this brief's explicit instruction, then verified on `main` (SHA + CI run on the merge commit).
- No secrets, no tokens in code/logs/commits; no fabricated results.

## 7. Result ledger (PASS / FAIL / BLOCKED / NOT TESTED)

- **PASS:** extended loop end-to-end (twice, byte-identical); witness-branch alibi closure (red→green over the engine fix); load-contract hardening (red→green); order independence; decay/forget curve exact to 6 decimals; save/restore expansion incl. RNG seam; 3690-check suite; 3 validators; stability repeat run.
- **FAIL:** none outstanding (all initial failures fixed or proven to be test-side surgery mistakes, then re-verified).
- **BLOCKED:** nothing new. UE-dependent verification remains blocked from the M3 environment report (no UE 5.4/GPU/Windows on this host).
- **NOT TESTED (honestly):** any of this loop **inside Unreal Engine 5.4** — PIE, `TLSVillageGameMode` driving these APIs, UMG presentation, in-engine save/load UI. C++ tests alone do not prove in-engine behavior; no such claim is made. The path to close this is unchanged: a Windows/UE 5.4 station → build → CAL-01 → PIE walkthrough with real screenshots (`reports/M3_RUNTIME_TEST_REPORT.md` §next-steps).

## 8. Acceptance criteria (brief §7) — checked

- [x] Real code AND test changes (3 engine files + 1 new suite file + wiring)
- [x] Relevant tests pass with no unjustified regression (73/73, 43/43, 70/70 held; 2399→3690)
- [x] README.md updated to the current truth
- [x] Clear commit message referencing M3.2
- [x] Pull Request toward `main` exists
- [x] Merged into `main` (permissions allowed; merge verified by SHA + CI)
- [x] Final repository state and CI result verified
