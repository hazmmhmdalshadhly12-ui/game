# REMAINING WORK LEDGER

> THE LAST SIN: The Sin-Eater · living document · updated 2026-10-24 (UTC) after the M3.8 session.
> States: **implemented** (in `main` via merged PRs) · **review** (open PR) · **partial** (started, testable core exists) · **blocked** (external dependency named) · **planned** (spec only).
> The engine-boundary rule: C++ core tests + validators prove the logic layer only. UE compile/PIE/render/input claims require the Windows station and none are made here.

## A. Milestone map (as actually implemented, not as planned on paper)

| Milestone | State | Evidence |
|---|---|---|
| M0 foundation + calibration | implemented | CAL assets + validators; UE-side IMP-01..04 remain blocked |
| M1 slice core + UE shell | implemented (logic + shell code) | 4859→5270-test suite; UE runtime blocked |
| M2 systems (quests, rumors, save v2, settings, D5–D11 blockout) | implemented | suite + validators |
| M3.1/M3.2 investigation loop + strict load | implemented | suite (save byte-stability, order independence) |
| M3.3 asset review | implemented (PR #5 merged) | `reports/asset-review/` |
| M3.4/M3.5/M3.6 Edmund build/repair/quality | implemented (PRs #6–#8 merged) | `02_Art/Characters/Edmund/` + reports |
| M3.7 four pillars as engine systems | implemented (PR #9 merged) | case facts / dossiers / hypotheses / accusations + save v3 |
| **M3.8 gameplay integration + investigation UI** | **review — PR #10 open** | dialogue→testimony bridge, case file (N), board (B), accusation flow, +411 checks |
| M3.9+ (proposed, see §C) | planned | — |
| M4 beta / M5 release | planned | per `docs/MILESTONE_PLAN.md` |

## B. Per-feature ledger

| ID | Feature | State | Depends on | Next concrete action | Validation required | Blocked by |
|---|---|---|---|---|---|---|
| F-01 | UE module compile of M3.8 shell changes | blocked | PR #10 merge | Run `03_Unreal/Scripts/01_*.bat` on Windows; fix any compile findings forward | UE 5.4 build log | **REQUIRES UE 5.4 TEST ENVIRONMENT** |
| F-02 | PIE walk of the vertical slice | blocked | F-01 | Play day1→day2→accusation per `reports/M3_8_REPORT.md` §7 | runtime log + session notes | same as F-01 |
| F-03 | Rumor tick driven from the shell day script | partial | — | Call `Game::TickVillageGossip(Day,Hour)` in `AdvanceDay` (core already tested) | new shell-facing checks + suite | — |
| F-04 | Chapters C2–C7 quest content | planned | M2 systems (ready) | Author quests_slice entries per QUEST_ARCHITECTURE; every quest gets preconditions/branches/save tests | narrative validator + quest tests | — |
| F-05 | T1–T4 full character set | partial | Edmund pipeline proven | Edmund (T1) assets exist; Gwendolyn/Crane/Mair/Ifor blockouts dialogue-ready; build remaining characters through the same Blender scripts | asset registry + FBX round-trip | Blender available; UE import blocked (F-01) |
| F-06 | D0–D11 real environments | partial | — | D0–D4 blockout data + D5–D11 blockout exist; prioritize one cohesive playable route over scattered placeholders | scaffold + world validation | UE-side lightmap/nav blocked (F-01) |
| F-07 | Endings E1–E4 | planned | C6/C7 flags, save system | Implement ending eligibility as deterministic functions of real state (mirror the accusation-tier pattern) | ending eligibility tests incl. wrong-theory cases | — |
| F-08 | Side quests (12 planned) | planned | F-04 | After main chapters; same contract per quest | same as F-04 | — |
| F-09 | Save/load full-content regression | partial | F-04/F-07 | Extend the v3 seam tests per new state types as content lands | suite | — |
| F-10 | Edmund in-engine (skeletal mesh import, anims 001..008) | blocked | F-01 | Import FBX, verify scale/orientation via CAL-01 procedure | in-engine screenshots (no claims before evidence) | **REQUIRES UE 5.4 TEST ENVIRONMENT** |
| F-11 | Art pass on UI (TLS-UI-001..004 engraved look) | planned | F-02 | Replace text-column boards with the M1 art target once PIE confirms layout | visual review | F-02 |
| F-12 | VO / Welsh audio | planned | text final (M3) | Per milestone plan M3/M4 wave | — | external VO budget |

## C. Session handoff (exact continuation state)

- **Integrated `main`:** `cfcd264a` — PRs #5–#9 merged in dependency order this session (GitHub-confirmed merge commits `3ee1b22`, `dfcbc55`, `78146a3`, `d9800eb`, `cfcd264`); CI success on the merge commit.
- **Open PR:** **#10** `feature/m3-8-gameplay-integration` → `main` @ `4ca0f59` — CI `validate` + `core-logic` **success** (GitHub-confirmed). Left open for review per the repo's safety rules; it is mergeable once reviewed.
- **Suite state on the PR head:** core tests **5270/5270**, project **79/79**, narrative **52/52**, scaffold **80/80**.
- **Next concrete task (highest value, no blockers):** F-03 — drive `TickVillageGossip` from the shell's `AdvanceDay`, then F-04 quest authoring for C2 on the same branch or a fresh `feature/m3-9-*` cut from this PR's head after merge.
- **Next task requiring the station:** F-01/F-02/F-10 — the documented Windows path is `03_Unreal/Scripts/01..04`; do not report engine results without the machine.
