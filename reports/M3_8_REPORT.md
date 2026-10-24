# M3.8 — UNREAL GAMEPLAY INTEGRATION REPORT

## THE LAST SIN: The Sin-Eater — the case layer reaches the player: the dialogue→testimony bridge, the case file, the deduction board, and the accusation flow

**Date:** 2026-10-24 (UTC) · **Base:** integrated `main` @ `cfcd264a` (PRs #5–#9 merged, dependency-ordered) · **Branch:** `feature/m3-8-gameplay-integration`
**Integrity rule honored:** every number below is from a command run in this session. UE compilation, PIE, rendering and input remain **BLOCKED — REQUIRES UNREAL ENGINE 5.4 TEST ENVIRONMENT**; nothing in this report claims engine-side execution.

---

## 0. Session start — live audit (before any change, per the brief)

- `main` @ `7c3d39bf` (M3.2), clean worktree. Baselines re-run fresh:
  - `tools/core_tests/run_core_tests.sh` → **3690/3690**
  - `validate_project.py` → **73/73** · `validate_narrative.py` → **43/43** · `validate_unreal_scaffold.py` → **70/70**
- Five open PRs, all `mergeable: clean`, CI `validate` + `core-logic` success on every head:
  - #5 M3.3 asset review → `main` (independent, `reports/asset-review/` only)
  - #6 M3.4 Edmund character → `main` (independent, `02_Art/` + registry)
  - #7 M3.5 → base **#6** (stacked) · #8 M3.6 → base **#7** (stacked)
  - #9 M3.7 pillars core → `main` (independent, `03_Unreal/Core` + `05_Narrative` + `tools`)
- Dependency map verified from the actual commit graph (all five fork from `7c3d39bf`; the art chain is a strict superset chain; zero file overlap with #9).

## 1. Phase-1 integration (executed, GitHub-confirmed)

Merged via the GitHub API in dependency order — **not** numerical order of the stacked chain's bases:

| Step | PR | Merge commit (GitHub-confirmed) |
|---|---|---|
| 1 | #5 M3.3 asset review | `3ee1b22339` |
| 2 | #6 M3.4 Edmund character | `dfcbc55828` |
| 3 | #7 M3.5 repairs (after its base #6 landed) | `78146a3d71` |
| 4 | #8 M3.6 quality upgrade (after its base #7 landed) | `d9800ebd2d` |
| 5 | #9 M3.7 pillars core | `cfcd264a67` |

No conflicts occurred (zero file overlap between the art chain and the core track; `docs/ASSET_REGISTRY.csv` was touched only by the art chain, `README.md` only by #9). No force-push, no branch deletion, no history rewrite; every branch's work is preserved in `main` via merge commits.

**Integrated baseline re-verified locally on `cfcd264a`:** core tests **4859/4859**, project **79/79**, narrative **43→50/50** (M3.7's own additions), scaffold **70/70**. GitHub CI on the merge commit: `core-logic` + `validate` = **success**.

## 2. The M3.8 gap (what was actually missing)

The M3.7 case layer was complete and tested in the core, but the UE gameplay shell never loaded it (`LoadCoreData` loaded evidence/quests/sim/dialogues only), no UI exposed testimonies/dossiers/hypotheses/accusations, no input could reach them, and no data path let a conversation teach a fact. The pillars existed as engine systems, not as gameplay.

## 3. What M3.8 added

### 3.1 Core (pure C++17, dual-compiled — no engine includes)

| Change | File | Contract |
|---|---|---|
| `DialogueEffects.RevealFacts` | `TLSCoreTypes.h` | New additive field: facts the SPEAKING NPC's testimony makes hearable in this line. |
| Parsing `reveal_facts` | `TLSDialogue.cpp` | Choice `effects` and node `on_enter` both accept the list. |
| The bridge | `TLSGameState.cpp` `ApplyEffects` | Calls `HearTestimony(FactId, NpcId)` per reveal. The **knowledge boundary stays with the testimony's reveal gate**: the line may play, the fact is learned only when the speaker's own conditions pass. Unknown ids are impossible by load-time validation (S6), so a silent failure can only be "conditions unmet" — by design. |
| `DeductionSystem::PreviewTier` + private `EvaluateTier` | `TLSDeduction.h/.cpp` | The tier an accusation WOULD land at, from live state, recording nothing. `MakeAccusation` now uses the **same** `EvaluateTier` — preview and execution cannot drift. |
| `Game::PreviewAccusationTier` | `TLSGameState.h/.cpp` | UE-facing wrapper; false only for unknown ids. |
| `Game::ValidateDialogueCaseLinks` | `TLSGameState.h/.cpp` | Every `reveal_facts` target must exist AND be owned by the dialogue's speaking NPC. Sessions without the case layer pass trivially (legacy shape). |

### 3.2 The UE gameplay shell (code-built UMG, the M0–M1 convention)

- **`LoadCoreData`** now loads `case_facts_slice.json` + `deduction_slice.json` **before** the dialogues, then refuses the session if `ValidateDialogueCaseLinks` fails; `rumors_blackthorne.json` loads too — the village gossip engine the core tests drive is now live in the shell.
- **`UTLSCaseFileWidget`** (key **N**): testimonies Edmund actually holds, in heard order — stance/origin/reliability/claim text, deliberate lies flagged with their data-declared reason; dossiers show public motive + fear always, secrets as "keeps something back…" until earned, deep motive only after **every** secret fact is learned. Truth summaries are never rendered (pillar B).
- **`UTLSBoardWidget`** (key **B**): hypotheses with live verdicts (Refuted shows why and stays refuted), the open-questions shelf, contradictions derived only among accounts the player could hold, and the accusation list. Forming a theory is an explicit digit act; requirements are NEVER listed — the open-questions shelf is the fair signal.
- **The accusation flow**: digits select → the status line shows the honest strength readout from `PreviewTier` ("your case STANDS firmly / is THIN / has NO ground") → **E speaks it** (confirm step) → `MakeAccusation` lands tier-specific consequences → the verdict line + toast. Non-repeatable accusations grey out ("already said").
- **Input**: `N` case file, `B` board (KB+M), gamepad `Y`/`RightShoulder`; the HUD status line always shows `[N] case file [B] board` — deduction-first never means interface-hidden. A toast announces each testimony that lands mid-dialogue ("Casebook: new testimony noted").
- Panels rebuild their lines from authoritative core state on every open/act; widgets hold no state of their own.

### 3.3 Data (canon-only, minimal diffs — 47 lines across 3 files)

| Dialogue | Reveal point | Gate (dialogue ≡ testimony) |
|---|---|---|
| Gwen `NODE_LASTNIGHT` | `FACT-LAST-TRAY` on_enter | H1 grants `EVD-GWEN-LASTNIGHT` before the node; the account is **heard but teaches nothing** (truth anchor) |
| Gwen `NODE_LIST_TOLD` (new) | `FACT-17-LIST` | new hub choice `GU1` at trust 60 (her registry threshold) after the guinea thread opened |
| Coles `NODE_FRAUD` | `FACT-NOTT-SIN` on_enter | `BH3` grants `EVD-COLES-FRAUD` before the node (day 2) |
| Coles `NODE_RING` (new) | `FACT-COLES-RING` | new hub choice `BH5` at trust 35 (kindness confession) |
| Crane `NODE_SHADOW_TOLD` (new) | `FACT-MILL-SHADOW` | new hub choice `CH5`: day 2 + `EVD-FOOTPRINTS` + `INS-PATTERN`; CH3's deflection untouched |

Testimony reveal conditions remain authoritative; the dialogue beats mirror them so a spoken line and a learned fact land together — no silent leaks.

### 3.4 Validators (strengthened, never weakened)

- `validate_narrative.py` **50→52**: the bridge cross-reference (targets exist + speaker owns the testimony) + a coverage check that the bridge is actually wired (5 reveal points / 3 files shipped).
- `validate_unreal_scaffold.py` **70→80**: core purity now covers **24** files (adds TLSRng/TLSSettings/TLSSettings/TLSCaseFacts/TLSDeduction to the dual-compilation contract); new section 13 checks the shell loads the case layer before dialogues, calls the load-time validation, loads rumor defs, declares the M3.8 entry points, maps N/B, carries `RevealFacts`/`PreviewTier`, and ships the data files.

### 3.5 Tests (`test_m38_slice.cpp`, 411 new checks → suite **5270**)

- **S1** the bridge through real dialogue: H1→tray account heard-but-not-learned; `GU1` shut below trust 60, opens at the threshold, teaches `FACT-17-LIST` with provenance (`via=testimony, from=CHR-03`).
- **S2** Coles: `BH3`→`NODE_FRAUD` teaches `FACT-NOTT-SIN` (evidence lands **before** the revealing node — ordering verified); ring confession shut below 35, earned at 35.
- **S3** Crane: CH3 opens on insight alone, CH5 does **not** open without the prints; with them, the shadow is taught and flagged.
- **S4** `PreviewTier` ≡ `MakeAccusation` (Grounded on the canon INS-SINLIST bundle; Crane capped Partial with intent unprovable); preview is a read (no recording); consequences land exactly (`FLG_NOTT_SIN_PUBLIC`, reputation ±4, tension +1); non-repeatable refusal; `ACC-SHONI-TINKER` always baseless.
- **S5** bridge-learned state survives save v3 byte-identically with provenance and the heard list.
- **S6** load-time contract: the shipped data passes; an unknown-fact reveal and a wrong-owner reveal are both refused with naming errors; a session without the case layer passes trivially.

Two pre-existing M3.7 assertions were updated to the new (correct) contract, with comments explaining why: the trust drive now crosses reveal nodes, so a fact may be taught by the dialogue first (the direct hearing becomes the idempotent second telling), and the tray account adds one deduplicated heard entry. Learned counts and byte-stability assertions are unchanged.

## 4. Real defects found and fixed this session

1. **Compile blocker (UE shell):** the board's confirm line contained raw `"` inside a `TEXT()` literal (shell-escaping artifact) — a guaranteed compile failure on Windows; found by static review round, fixed with proper `\"` escapes.
2. **Digit-layout staleness (UE shell):** `RefreshBoardUI` read `AccusableIds` before rebuilding it, so formable-theory digits could start at a stale offset; accusation ids are now computed first.
3. **Null-deref guard (UE shell):** the pending-accusation status line now guards its lookup (ids are rebuilt same-refresh, the guard keeps a stale index honest).
4. **Behavior fix (UE shell):** `OnJournalToggle` opened the journal **over** an already-open table/board panel (the hidden panel stayed visible behind it); every panel toggle now requires `PanelMode == None`, matching the new case-layer toggles.
5. **PreviewTier return type:** an intermediate build error (`bool` vs `EAccusationTier`) caught by the suite before any commit.

## 5. Command results (this session, fresh runs)

| Command | Result |
|---|---|
| `tools/core_tests/run_core_tests.sh` | **5270 passed, 0 failed** (baseline 3690 → +1169 M3.7 → +411 M3.8) |
| `python3 tools/validate_project.py` | **79/79** |
| `python3 tools/validate_narrative.py` | **52/52** (43 + 7 M3.7 + 2 M3.8) |
| `python3 tools/validate_unreal_scaffold.py` | **80/80** (70 + 10 M3.8) |
| GitHub CI on integrated `main` (`cfcd264a`) | `core-logic` + `validate` = **success** |

These prove the logic layer and the data contracts. They do **not** prove UE compilation or runtime behavior — see §6.

## 6. Engine validation status

**BLOCKED — REQUIRES UNREAL ENGINE 5.4 TEST ENVIRONMENT** for: module compile of the touched UE files (`TLSVillageGameMode`, `TLSWidgets`, `TLSCharacter`), PIE launch, widget rendering/layout, Enhanced Input binding behavior, save-slot IO, and the full playable walk of the slice (§7). The static round found and fixed one would-not-compile literal (§4.1); it cannot substitute for the compiler. `03_Unreal/Scripts/01..04` remain the documented Windows path.

## 7. The playable vertical slice (through the real shell)

With this milestone the shell provides the complete deduction loop a player can walk once a Windows/UE5.4 station runs it:

1. Day 1 — Edmund walks Blackthorne (procedural blockout from `blackthorne_blockout.json`), observes/collects evidence, talks: Gwen's tray account lands on the case file (heard, teaches nothing — the mystery stays sealed), Coles hints the Hunger.
2. Day 2 — Coles' sacks account teaches `FACT-NOTT-SIN`; the mill prints + the pattern insight open Crane's shadow admission; board links derive contradictions; the player pins `HYP-NOTT-FRAUD-PATTERN` and watches the open-questions shelf shrink; the sworn list from Gwen (trust 60) and the ring confession (trust 35) are earned alternate paths.
3. The board's accusation flow speaks the fraud case — the tier readout tells the player how strong their own case is, the grounded verdict pays reputation and publishes the sin; the county's tinker story stays speakable and baseless. Journal, quests, trust, tension, hypotheses, heard testimony and accusation log all persist through the save desk (v3, byte-stable).

Resolution requires no arbitrary waypoint: the board tells the player what their own case lacks, and every path to the truth has at least one alternate route (the QUEST_ARCHITECTURE three-routes rule).

## 8. Honest limitations

- The slice's **engine-side** acceptance (compile/PIE/input/render) is blocked, not done — §6.
- Accusation consequences currently surface as trust/tension/reputation/flags + journal; C6+ canon scenes that *react* to `FLG_NOTT_SIN_PUBLIC` are future content (C2–C7 quests), not M3.8 scope.
- The board is text-column based (the M1 engraved-look art pass TLS-UI-001..004 remains the visual target); functional, readable, atmospheric per the brief, not yet art-final.
- Rumor **tick** is loaded and callable but not yet driven from the day script in the shell (core tests drive it); wiring `TickVillageGossip` into the day advance is the natural M3.9 item.
