# M2 IMPLEMENTATION REPORT — THE LAST SIN: The Sin-Eater

**Branch:** `feature/m2-systems` (local; not pushed — see §9)
**Base:** `main` @ `954f73a` ("docs: record the 23-Oct round", 2026-10-22)
**Head:** `8c0a707` (+ report commit)
**Date:** 2026-10-23 (Cairo time)
**Report language rule:** every status below is a verified fact from a command run inside this environment, or an explicit NOT RUN.

---

## 1. Repository state before M2 (verified, not assumed)

- `main` latest commit: `954f73a`, CI run on it: `validate` workflow = success (6 total runs, last success).
- Baseline verification run in this session **before** any M2 change:
  - core tests: **418/418 PASS** (`tools/core_tests/run_core_tests.sh`, g++ C++17)
  - `tools/validate_project.py`: **73/73**
  - `tools/validate_narrative.py`: **29/29**
  - `tools/validate_unreal_scaffold.py`: **70/70**
- Existing systems audited and reused (not replaced): `TLSGameState` orchestrator, Evidence/Quest/Village/Dialogue systems, save v1, 17 NPCs (5 named + 12 T3) with 24h schedules, M1 evidence set, `Q-M-C1` + `Q-M-C2a` quests.
- UE version verified from `TLS.uproject`: `EngineAssociation: 5.4` — matches the project-locked engine; no version conflict found.
- Historical suspected defect `03_Unreal/Scripts/01_build_editor.bat` (UEROOT derived from the script's own path): **already fixed** before M2 by commit `68fd509` ("derive UEROOT from UEBIN"); re-verified in the file: `UEROOT` is now derived from the located `UEBIN`.

## 2. Files created / modified (branch diff `954f73a..HEAD`)

**Created (engine core, all pure C++17, no engine includes):**
- `03_Unreal/Source/TLS/Core/TLSRumors.h/.cpp` — rumor & witness engine
- `03_Unreal/Source/TLS/Core/TLSRng.h` — deterministic splitmix64, serializable state
- `03_Unreal/Source/TLS/Core/TLSSettings.h/.cpp` — settings & accessibility model

**Modified (engine core):**
- `TLSCoreTypes.h/.cpp` — `Reticence` on NPCDef, rumor-aware + tension `IGameContext` hooks, `ETaskType` ×3 new (`NpcRumor`, `PlayerRumor`, `TensionBelow`), `EQuestStatus::Failed`, `ObjectiveDef.bAnyOf`, `QuestDef.bFailsOnExpiry/FlagsOnFail`
- `TLSGameState.h/.cpp` — rumor driving (tick/witness/heard/leak/denial), `AdvanceSimDay`, save v2 + version gate + hardening, `SettingsModel` member + journal policy, `QuestsMut()`
- `TLSQuests.h/.cpp` — new task types, any-of branches, `ProcessExpiry`, failed-status serialization, load validation
- `TLSVillageState.cpp` — `reticence` loading, save validation (day/hour/trust ranges, unknown-NPC rejection)

**Created (data, story-grounded):**
- `05_Narrative/rumors/rumors_blackthorne.json` — 6 rumors (C1–C2 days), 4 gossip zones, relationship seed matrix, rules (≤30%/day cap)
- expanded `05_Narrative/world/blackthorne_blockout.json` — districts D5–D11 (9 areas), 10 buildings, 7 paths, ground 240×250, `region_status` honesty map

**Modified (data):** `05_Narrative/sim/sim_blackthorne.json` (reticence: Mair 0.9, John Brook 0.6, Betti 0.5), `05_Narrative/quests/quests_slice.json` (+ `Q-M-C3`, `Q-S-C3-SHONI`)

**Created/modified (tools & tests):**
- `tools/core_tests/test_rumors.cpp` (9 sections), `test_quests.cpp`, `test_settings.cpp`, `test_fixtures.h`
- `tools/core_tests/test_main.cpp` (+ game integration, 7-day sim, save-version gate, five-point save/load, corrupt payloads, expanded-world zones), `run_core_tests.sh` (new sources)
- `tools/validate_narrative.py` (+ rumors section, quest rumor-target checks, world-expansion checks)
- `tools/bench_sim.cpp` + `tools/bench_sim.sh` (reproducible benchmark)

No pre-existing test was deleted or weakened; all 418 M1 checks still run inside the suite.

## 3. M2.1 — Rumor & witness system — **Completed and tested**

Implemented (per `NPC_SIMULATION.md` §4–6 and the M2 brief):
- Every rumor: unique id, origin (`npc` or `world:event`), day/hour/place, origin confidence, per-day decay, transmission **provenance chains** (each step a real append-only log entry), wording **variants with mutation** per hop (clamped to the last variant).
- Four testimony kinds: **Direct / Hearsay / Inference / Unverified**; effective-kind degradation (hearsay < 0.40 confidence or ≥2 mutations reports Unverified); direct never degrades.
- Spread bound to **schedules + co-location in gossip zones + relationships (< 0 blocks) + reticence (+ village tension)** — never an instant broadcast; trust rule slows maligning-Edmund rumors through trusted mouths.
- Termination rules: **daily spread cap ≤ 30% of population (persistent per-day counter)**, speaker hourly + daily budgets, saturation (everyone knows → zero transmissions), daily decay with a forget threshold (knowledge erased → rumor inactive), max 6 active rumors enforced at load.
- Duplicate guards: same (rumor, from, to, day, hour) never recorded twice; witness events and player-heard are idempotent.
- Player tools (`NPC_SIMULATION` §5): leak (anonymous, zone-occupant only, deterministic), public denial (−0.30 confidence to all holders + that day's gossip halved + reputation +2), silence.
- NPCs act only on what they know: `NpcKnowsRumor`/`PlayerHeardRumor` condition hooks consumed by the quest system.
- Data: 6 story-true rumors — Hunger-returns (d1), Quiet-Guinea (d1), Nott salt-death (d2, direct seed = the finder), Edmund-blame (d2, inference), Shoni-suspect (d3, +1.0 tension), Shoni-alibi (leak-only counter-rumor).

## 4. M2.2 — Save & deterministic continuation — **Completed and tested**

- Save format **v2**: world state (day/hour/weather/tension/reputation/trust per NPC), evidence custody, quest runtime incl. failed state, flags, areas, dialogue history, journal, **rumor layer (knowledge + full transmission history + witness log + daily counters + denial day)** and the **64-bit sim RNG state (hex — avoids double precision loss above 2³)**.
- Version gate: `save_version > 2` refused with a clear message; **v1 legacy saves load with a clean rumor layer**; v2 missing `sim_rng` refused.
- Load-time integrity: JSON-level + per-system validation (unknown rumor refs, out-of-range confidence/variant/day/hour, trust value range + unknown NPC, flags/areas/dialogue/journal type checks) — every rejection is **atomic** (a refused load leaves the running session untouched, verified per case).
- No pointers/references are ever serialized; ids only.
- **Five save points** across the 7-day sim (days 1/2/3/5/7): each loaded into a fresh world, both continued to day 7 — byte-identical world state, identical rumor history, re-converged RNG streams (**zero drift**, the `NPC_SIMULATION` 10.2 round-trip rule).

## 5. M2.3 — Data-driven quest system (C1–C3) — **Completed and tested**

- All quest content is data (`quests_slice.json`); the engine hardcodes nothing but the task-type semantics.
- New condition types bind quests to the M2 world: `npc_rumor` (`NPC=RUMOR` — the NPC must actually know), `player_rumor`, `tension_below` (emergent village tension).
- **Branches / alternative outcomes**: `any_of` objectives (any single task completes the objective) — the Shoni defence passes via the player's own leak OR a witness's word travelling (`T3-07`/`T3-01`).
- **Failure + resumable continuation**: `fails_on_expiry` + `flags_on_fail`; `AdvanceSimDay` fails overdue urgent quests, applies consequence flags (`FLG_SHONI_TAKEN`), journals the failure; the main quest continues — failure is a world consequence, not a dead end.
- Story-true data (GAME_BIBLE day 3): `Q-M-C3` "The Coming Inspector" (accusation → physical method → optional calm) and `Q-S-C3-SHONI` "A Day for the Tinker" — the bible's **urgent optional** day-3 task.
- Duplicate-completion guard: completed quests stay completed; `flags_on_complete` are never re-applied (verified by wiping a flag and re-firing every condition).
- Condition conflicts: a fixture quest with contradictory objectives provably never completes (documented behavior, automatable).
- Reload: partial quest progress byte-identical across the save/load seam; a loaded world resumes exactly where it stood.
- Validator: rumor task targets must resolve against sim NPCs + rumor ids; urgent quests must carry a consequence flag.

## 6. M2.4 — Settings & accessibility — **Completed at core level; UE presentation bindings NOT RUN**

Every setting below drives a **real core behavior** (no decorative values):
- Audio master/music/sfx/dialogue (0–1, clamped). Real policy: **dialogue volume < 0.20 forces subtitles on**; `subtitles_always` overrides. *UE mixer binding: NOT RUN (no engine).*
- Quality tier → **real consumer: gossip-ticks-per-frame budget** (low 1 / medium 2 / high 4), demonstrated by a frame-loop consumption test.
- Large text → `TextScale()` 1.0/1.5 for dialogue readability. *UMG font binding: NOT RUN.*
- Colorblind modes (none / deuteranopia / protanopia / tritanopia) → **four ledger-board token tables** built from the GAME_BIBLE 7.2 palette (amber/blue as-drawn; luminance-separated amber/blue for deuteranopia & protanopia; rose/teal off the confusion axis for tritanopia; paper/ink invariant). Accessibility is documented as the sanctioned exception to the strict palette rule. *Board rendering binding: NOT RUN.*
- Rumor auto-journal toggle → **real consumer**: `Game::NotifyPlayerHeardRumor` journals only when enabled.
- Input: keyboard+mouse **and** gamepad default bindings; `SetBinding` **rejects two actions on one code** (keyboard and gamepad codes equally protected; never silently remaps).
- Persistence: `tls.settings.v1`, validate-then-commit; corrupt payloads refused (wrong types, unknown tiers/modes, duplicate bindings); **settings are per-install — world saves carry no settings payload** (verified).
- Bug found and fixed during testing: `large_text` was never read back from a payload.

## 7. M2.5 — World districts D4–D11 — **Blockout data completed; Blender/UE build NOT RUN**

Honest three-state ledger (`region_status` in the world file — machine-checked):
- **Data-defined (JSON):** all 20 areas, including D5 Capel Seion+School (day 2), D6 Cors Wyllt + Nan's hut (day 4), D7 Blackthorne Level (day 4), D8 Deep Level + Y Porth (day 4), D9 Pen y Bwlch Pass + Moor (day 5), D10 Plas Blackthorne (day 3), D11 Poorhouse + outskirts (day 1). D4 (Mill) already existed from M1.
- **Blockout built (Blender/FBX):** none. The only 3D in the repo remains the M0/M1 calibration assets (`tls_env_001/002`). No district blockout has been modeled — no assets were faked.
- **Tested in UE:** none — NOT RUN (no UE 5.4 in this Linux container).
- Every new area: rect footprint (non-overlap script-verified; designed nesting documented for Nan's-hut-in-swamp and lane-in-moor), `day_unlock` (1–9), district coverage D0–D11, 10 buildings with GAME_BIBLE 7.2 palette tokens, 7 paths connecting all districts into one walkable graph; ground grown 140×160 → 240×250 (the M1 tile framed only the day-1/2 slice); Afon Ddu crosses the full valley.
- Engine integration verified where it exists: expanded zone ids resolve through `VillageState` schedules and correctly remain **non-gossip** zones (gossip stays in the social cores).
- W-05 Capel Seion re-homed into its own district; W-06 engine house corrected from mill to mine level (a data error vs WORLD_REGISTRY D7, now fixed).

## 8. Real test results (all commands run in this session)

| Suite | Before M2 | After M2 |
|---|---|---|
| `tools/core_tests/run_core_tests.sh` | 418/418 | **1763/1763 PASS** |
| `tools/validate_project.py` | 73/73 | **73/73** |
| `tools/validate_narrative.py` | 29/29 | **44/44** |
| `tools/validate_unreal_scaffold.py` | 70/70 | **70/70** |

New coverage highlights (all green): invalid rumor/quest/settings data rejection (14+ corrupt-payload cases), spread cap/budget/saturation/forgetting, provenance integrity after 7 days of churn, determinism + seed divergence, five-point save/load zero-drift, expiry failure + save/load survival, duplicate-completion guard, condition-conflict impossibility, colorblind token sanity, input conflict rejection, expanded-world zone consumption.

**Failures found and fixed during M2 (the tests earned their keep):**
1. Daily spread cap was per-tick, not per-day → persistent per-day counter (the ≤30% rule was silently violated before).
2. Public denial did not actually dull spread → denial day halves telling chance.
3. Transmission log stored the **pre-mutation** variant → log now records the wording actually told.
4. `AdvanceSimDay` (the M2 day-advance path) never activated due quests and never processed expiry → both added (NotifySleep keeps its own story gate).
5. Leak/heard player actions did not refresh quest conditions → refresh added; leak now implies the player knows the rumor.
6. `large_text` setting was never read back from persistence.
7. Missing `<set>` include broke the standalone build; weak type-checks on `rules`/`npc_relationships`/flags/journal allowed corrupt payloads silently → all tightened.
8. Save v2 RNG serialized through double would lose bits above 2⁵³ → hex string.

## 9. UE build/run & platform compatibility — **NOT RUN (blocked by environment)**

| Item | State |
|---|---|
| UE 5.4 C++ compile of `03_Unreal/Source/TLS/Core` inside the module | **NOT RUN** — Linux container, no UE 5.4, no GPU. Core files are engine-free C++17 and compile standalone with `g++ -Wall -Wextra` (CI-identical); UE compile remains a Windows/station task. |
| Map open/play in engine | **NOT RUN** |
| Blender blockouts for D4–D11 | **NOT RUN** (none exist; none claimed) |
| Windows / macOS / Apple Silicon verification | **NOT RUN** — no OS access beyond this container. `EngineAssociation 5.4` verified in the project file; `01_build_editor.bat` UEROOT defect verified already fixed. |
| CI on the branch | **BLOCKED — not pushed.** The provided GitHub token returns **401 Bad credentials** (expired/revoked) on both `api.github.com` and git push. **No push was faked.** |

**Deliverable instead of push:** 6 reviewable patch files (one per commit) at `download/m2-patches/0001…0006`, applicable with `git am` onto `main` @ `954f73a`. A renewed token + `git push -u origin feature/m2-systems` (or `git am *.patch` on any machine) reproduces the branch exactly.

## 10. Performance measurements (real, reproducible — `tools/bench_sim.sh`)

**Environment:** Debian container, g++ 14.2 (`-O1`, CI-identical flags), x86_64 VM (Xeon-class host, 2 vCPU, 4 GB RAM). Single run shown; the tool re-measures on every invocation.

| Metric (17 NPCs, 6 rumors) | Measured |
|---|---|
| Mean gossip tick (1 simulated hour, 14/day) | **3.46 µs** |
| Full simulated day (14 ticks + decay + activation) | **48.4 µs** |
| High-tier frame spend (4 ticks/frame, core algorithm only) | **13.8 µs** |

**Honest framing:** these are the standalone **core algorithm** costs. The `NPC_SIMULATION` §10 budget (**≤ 1.5 ms/frame on the minimum Windows spec, measured inside UE**) is **not claimed** — a live UE 5.4 measurement remains station work. What the measurement does establish: the core gossip simulation consumes ~0.2% of the frame budget at the high-tier tick rate, leaving ample headroom for the engine-side integration costs.

## 11. Five-state summary per milestone item

| Item | State |
|---|---|
| M2.1 rumor & witness engine (rules, provenance, caps, tools, data) | **Completed and tested** (engine + data + game levels, 7-day sim) |
| M2.2 save/load (v2, version gate, integrity, 5-point zero drift) | **Completed and tested** |
| M2.3 quest system (data-driven, rumor conditions, branches, failure, C1–C3 data) | **Completed and tested** (C1–C2 pre-existing data unchanged; C3 authored story-true) |
| M2.4 settings & accessibility (core model + real consumers) | **Completed and tested at core level**; UE presentation bindings **NOT RUN** |
| M2.5 world D4–D11 (data + engine integration) | **Blockout data completed and tested at data/engine level**; Blender blockouts **NOT RUN**; UE maps **NOT RUN** |
| 7-day headless sim (NPC_SIMULATION §10 rules) | **Completed and tested** (cap, zones, reticence, provenance, determinism) |
| Performance ≤1.5 ms/frame | **Blocked (environment)** — core measured at 3.46 µs/tick; UE-side measurement NOT RUN, not claimed |
| UE 5.4 compile / map open / play | **Blocked (environment)** — NOT RUN |
| macOS / Apple Silicon save verification | **Blocked (environment)** — NOT RUN |
| Branch push + CI | **Blocked (permissions)** — token 401; 6 reviewable patches delivered instead |

## 12. Commits on `feature/m2-systems`

| Commit | Content |
|---|---|
| `03ea01e` | M2.1 rumor & witness engine + M2.2 save-v2 contract |
| `b05d5dc` | M2.2 save/load integrity hardening + five-point zero-drift verification |
| `64a6c91` | M2.3 data-driven quest system — rumor conditions, branches, failure |
| `73c2c57` | M2.4 settings & accessibility model with real core behaviors |
| `2e2ff45` | M2.5 world districts D5–D11 — blockout data, honest build states |
| `8c0a707` | M2 reproducible core-sim benchmark with measured numbers |

## 13. What M3 needs from this milestone

- The UE layer compiles `03_Unreal/Source/TLS/Core/*` as-is (no engine includes were introduced); the UE day script consumes `AdvanceSimDay` + `GossipTicksPerFrame()`; the ledger board consumes `BoardColors()`; Enhanced Input consumes `Bindings()`; the mixer consumes the four volume channels and the subtitle policy.
- C4+ chapters plug into the quest schema unchanged; new rumors are data rows within the 6-active cap (raise `max_active` in data when C4+ content lands).
- Every `region_status` entry marked `blockout_data` waits on Blender blockouts → UE import → engine play; the pipeline (import_and_calibrate.py, scripts 01–04) is in place from M0/M1.
