# M3.7 — PILLARS CORE REPORT

## THE LAST SIN: The Sin-Eater — the case-fact ledger, the dossiers, the hypotheses, and the accusations (the four pillars as engine systems)

**Date:** 2026-10-24 (UTC) · **Base:** `main` @ `7c3d39bf` (M3.2) · **Delivered on:** `feature/m3-7-pillars-core` → Pull Request (NOT merged — this session's brief forbids merging to `main` without explicit authorization).
**Integrity rule honored:** every number below is from a command run in this session. C++ test success is NOT claimed as evidence the game runs inside Unreal Engine — see §7.

---

## 1. Project inspection (before any change — per the brief)

- Live repo audited via API first: default branch `main` @ `7c3d39bf`; 4 open PRs forming the stacked Edmund art chain (#5 M3.3 → main, #6 M3.4 → main, #7 M3.5 → base M3.4, #8 M3.6 → base M3.5). **The art chain was left completely untouched** — this milestone is core-track work on a fresh branch off `main`, so the PR dependencies cannot conflict.
- Worktree clean after clone (`core.fileMode=false` for the mode-bit neutralization this repo already uses).
- Baseline recorded BEFORE any change (fresh runs, this session):

| Command | Baseline result |
|---|---|
| `tools/core_tests/run_core_tests.sh` | **3690 passed, 0 failed** |
| `python3 tools/validate_project.py` | **73/73** |
| `python3 tools/validate_unreal_scaffold.py` | **70/70** |
| `python3 tools/validate_narrative.py` | **43/43** |

- Architecture read end to end (headers + call sites): `TLSCoreTypes` (IGameContext), `TLSEvidence` (board/links/insights), `TLSDialogue` (conditions/tones), `TLSQuests` (windows/any_of/failure), `TLSRumors` (provenance/decay/witness events), `TLSVillageState` (trust/tension/schedules), `TLSGameState` (orchestrator, atomic save v2), `TLSJson` (deterministic serializer). Canon read: `CHARACTER_REGISTRY.md` (incl. the Knowledge Ledger prose table), `QUEST_ARCHITECTURE.md` (E1 reliability bar, C1–C7, flag ledger), `GAME_BIBLE.md` (endings E1–E4), `MILESTONE_PLAN.md`.

## 2. The gap map (what the four mandatory pillars were missing)

| Pillar | Already on `main` | Missing (found, not assumed) |
|---|---|---|
| **A — the connected village** | Rumor engine: knowledge boundaries, provenance chains, hop mutation, decay | The **case-fact layer**: the registry's Knowledge Ledger (who closed Y Porth, the 17-name list, the last tray, the mill shadow…) was prose. No engine object held per-NPC *testimony variants* of canonical facts with reveal gates, so testimony could not systematically agree/conflict/omit, and discoveries could not propagate to knowledge elsewhere by data. |
| **B — deduction-first** | Board: link rules, contradictions, insights (OR-of-AND paths) | **Hypotheses** (player constructions graded against real state) and the **open-questions shelf** did not exist. The board could verify links but could not hold an argument the player is trying to prove or refute. |
| **C — believable motives** | Trust/tone/bias/reticence/schedules; dialogue conditions on real state | Motives/fears/secrets were prose only. No machine-readable **dossiers** the validator and engine check against (concealment must be gated testimony, not decoration). |
| **D — real consequences** | Flags, quest failure windows, trust/tension, persistent save | No **formal accusation**: no confidence tiers, no deterministic evidence-grounded verdicts, no wrong-accusation consequences. The emotional core of a mystery game was absent. |

## 3. What M3.7 added (all on the existing architecture — nothing replaced)

New core modules (pure C++17, dual-compiled, no engine includes):

| Module | Delivered |
|---|---|
| `TLSCaseFacts.h/.cpp` | `CaseFactDef` (id, topic, **truth_summary** validator-facing, **canon_ref** mandatory, truth-anchor flag), `TestimonyDef` per NPC (stance affirms/denies/claims/omits, origin witnessed/told/inferred/documented, reliability, deliberate-lie + mandatory lie_reason, `grants` semantics, `RevealConditions` = trust/evidence/insights/flags/day evaluated against **IGameContext live state**), `DossierDef` (public/deep motive, fear, secret facts that MUST have gated testimonies — concealment is playable or refused), learned-fact tracking (first learning wins, via/from/day/hour), deterministic conflict derivation **among only the accounts the player could hold** (silence never conflicts; deliberate lies explain themselves in data), strict save/load (unknown fact/npc ids refused). |
| `TLSDeduction.h/.cpp` | `HypothesisDef` (requirements: insights/evidence/facts; refuters: flag / fact / board-contradiction rule / player rumor — every refuter carries its reason), verdict ladder Unsupported → Partial → Supported with **permanent Refuted** (no resurrection), `OpenQuestion` derivation (the missing pieces of formed, non-refuted, non-supported hypotheses), `AccusationDef` (grounding insight + evidence bundle with the QUEST_ARCHITECTURE 2.1 **min_reliability bar** + grounding fact; `max_tier` data cap; `repeatable` flag; per-tier consequences: trust/tension/reputation/flags/journal), tier evaluation Baseless/Partial/Grounded as a deterministic function of state, strict save/load. |
| `TLSGameState` integration | `LoadCaseFactsData`/`LoadDeductionData`; `AvailableTestimony`/`HearTestimony`/`LearnFact` (journal note only on FIRST learning — a real bug the tests caught, see §4); `FormHypothesis`/`OpenQuestions`/`MakeAccusation`; `IGameContext` extended additively with `ContradictionRuleDrawn` + `EvidenceReliability` (safe defaults — no existing implementor breaks); `VillageState::ApplyTrustEvent` (event trust delta without tone weight, keeping bias/clamp/spillover); `RefreshAfterChange` now re-grades hypotheses AFTER quest flags land (a completed quest can fire a refuter). |
| Save format v3 | New required-when-v3 sections `case` + `deduction`; **v1/v2 payloads still load** (case layer starts clean — documented contract, regression-tested); ghost fact/hypothesis/accusation ids refused atomically by the M3.1 rollback guard. |

New data files (canon-only — every entry carries `canon_ref`):

- `05_Narrative/case_facts/case_facts_slice.json` — 6 facts / 7 testimonies / 5 dossiers:
  - `FACT-NOTT-SIN` (Coles affirms from carrying the sacks — CHR-15 canon),
  - `FACT-17-LIST` (Gwendolyn, gated at **trust 60** — her registry threshold; Q-S12's alternative path exists precisely for players who never reach it),
  - `FACT-LAST-TRAY` (**truth anchor**: Gwendolyn's innocent account is hearable but grants nothing — the poison truth stays in day-6 canon),
  - `FACT-MILL-SHADOW` (Crane's witnessed shadow, unlocked by footprints + INS-PATTERN, not by trust — CHR-04),
  - `FACT-COLES-RING` (confession under kindness at trust 35 — CHR-13),
  - `FACT-MAIR-RETURNED` (**truth anchor**: Mair's silence is itself an account; her reveal day_min 4 = C5, outside the slice).
- `05_Narrative/deduction/deduction_slice.json` — 3 hypotheses / 4 accusations:
  - `HYP-HUNGER-RETURNED` (the village's theory; refuted by the two board contradictions),
  - `HYP-NOTT-FRAUD-PATTERN` (fully supportable in-slice: INS-PATTERN + weights + fraud testimony + the learned fact),
  - `HYP-SHONI-CUTPURSE` (the county's theory, formalized; refuted by FLG_METHOD_SHOWN **or** the alibi rumor),
  - `ACC-SHONI-TINKER` (declared baseless — the wrong accusation the county pushes),
  - `ACC-NOTT-FRAUD` (grounding = INS-SINLIST + weights/list, avg reliability 0.875 ≥ the 0.7 bar; baseless costs reputation, grounded pays it),
  - `ACC-COLES-RING` (true-but-cruel: grounded only after the earned confession, and the village punishes it anyway — a repeatable accusation whose second telling lands harder),
  - `ACC-CRANE-SERMON` (`max_tier: partial` — intent cannot be proven in the slice; the real confrontation is C6 canon).

## 4. Real defects found and fixed (the tests earned their keep)

**Bug 1 (engine) — repeated hearings duplicated journal entries (`TLSGameState.cpp`).** `HearTestimony` journaled the fact's note on EVERY call whose reveal conditions passed, not only on first learning. The S2 idempotence check caught it red (journal +2). Fix: journal only when the call performed the learning. Same guard added to `LearnFact`.

**Bug 2 (engine) — hypothesis verdicts were graded before quest flags landed (`TLSGameState.cpp`).** `RefreshAfterChange` re-checked hypotheses BEFORE `QuestSys->Refresh` applied completion flags, so a quest completion that fires a refuter (FLG_METHOD_SHOWN kills `HYP-SHONI-CUTPURSE`) was invisible until an unrelated later refresh. Fix: re-grade after the quest pass. The refutation test went red→green on this fix.

**Bug 3 (engine) — `repeatable` was declared in the schema but never parsed (`TLSDeduction.cpp`).** The loader omitted `GetBool("repeatable")`, silently forcing every accusation non-repeatable. Fix + regression (the Coles two-tier flow now exercises the declared behavior).

**Test-side corrections (not engine bugs, kept as lessons in comments):** the board requires BOTH endpoints examined before a link (M3.1's "lamp has read" rule) — two flows were drawing unexamined; Q-M-C3 completes only when the county's rumor is also heard; two hypotheses with a single requirement were instantly "supported" and got a second honest requirement.

## 5. Real command results (this session, fresh runs)

| Command | Result |
|---|---|
| `tools/core_tests/run_core_tests.sh` | **4859 passed, 0 failed — ALL CORE-LOGIC TESTS PASSED** (baseline 3690 → **+1169 checks**; repeat run identical — stability confirmed) |
| `python3 tools/validate_narrative.py` | **ALL CHECKS PASSED (50/50)** (43 → +7 new sections: facts, dossiers, hypotheses, accusations) |
| `python3 tools/validate_project.py` | **ALL CHECKS PASSED (73/73)** — no regression |
| `python3 tools/validate_unreal_scaffold.py` | **ALL CHECKS PASSED (70/70)** — Core/ purity re-verified (no UE includes in the new modules) |

What the new checks prove (and do not): the 8 S-sections of `test_m37_pillars.cpp` drive the REAL core through the knowledge boundary (Gwen at trust 60, Mair's wall, Crane's evidence-gated silence, Coles' confession), truth anchors (the tray account heard but never granting), conflict derivation, the full hypothesis ladder including both refuter kinds and no-resurrection, all four accusation verdict paths with exact consequence arithmetic (trust deltas computed from each NPC's actual bias), the v3 save seam (byte-identical resave, ghost refusal atomicity, v2 legacy load), and the no-soft-lock guarantee (the baseless Shoni accusation never blocks Q-S-C3-SHONI). They prove the LOGIC layer only — not UE compilation, rendering, or PIE.

## 6. Files changed

| File | Change |
|---|---|
| `03_Unreal/Source/TLS/Core/TLSCaseFacts.h/.cpp` | NEW — case-fact ledger: facts, testimony variants, dossiers, reveal gates, learned tracking, conflicts, strict save/load |
| `03_Unreal/Source/TLS/Core/TLSDeduction.h/.cpp` | NEW — hypotheses, refuters, open questions, accusation tiers, per-tier consequences, strict save/load |
| `03_Unreal/Source/TLS/Core/TLSCoreTypes.h` | IGameContext: additive `ContradictionRuleDrawn` + `EvidenceReliability` (safe defaults) |
| `03_Unreal/Source/TLS/Core/TLSGameState.h/.cpp` | Case/deduction loaders + APIs, journal-first-learning fix, refresh ordering fix, save v3 (backward compatible) |
| `03_Unreal/Source/TLS/Core/TLSVillageState.h/.cpp` | `ApplyTrustEvent` (event trust delta without tone weight) |
| `05_Narrative/case_facts/case_facts_slice.json` | NEW — 6 facts, 7 testimonies, 5 dossiers (canon_ref on every entry) |
| `05_Narrative/deduction/deduction_slice.json` | NEW — 3 hypotheses, 4 accusations (canon_ref on every entry) |
| `tools/core_tests/test_m37_pillars.cpp` | NEW — 8 sections, ~1140 checks |
| `tools/core_tests/test_main.cpp` | Wires `tls_test_m37::RunAll()`; version-gate tests updated to the v3 contract (future = 4, v3 loads, v1 legacy unchanged) + explicit "v3 reloads" check |
| `tools/core_tests/test_investigation.cpp`, `test_m32_extended.cpp` | save_version wire-format assertions 2 → 3 (assertion strength unchanged) |
| `tools/core_tests/run_core_tests.sh` | Compiles the two new core TUs + the new test TU |
| `tools/validate_narrative.py` | Sections 7–8: the case-fact and deduction cross-reference checks (+7 checks) |
| `README.md` | Status line, current numbers (4859/4859, 50/50), honest core-vs-engine boundary note unchanged |

No pre-existing test was deleted or weakened; the whole M1+M2+M3.1+M3.2 suite still runs unchanged inside the new total. No secrets or tokens in code/logs/commits. No invented canon: every fact/hypothesis/accusation names its registry chapter.

## 7. Result ledger (PASS / FAIL / BLOCKED / NOT TESTED)

- **PASS:** full suite 4859/4859 (twice); validators 50/50, 73/73, 70/70; the four-pillar integration loop end-to-end on real data; v3 save/load seam incl. atomic ghost refusal and v2 legacy; no-soft-lock guarantee after the wrong accusation.
- **FAIL:** none outstanding (all red→green fixes listed in §4).
- **BLOCKED — REQUIRES UE 5.4 TEST MACHINE:** UE module compilation of the new TUs under MSVC; PIE playthrough of the C1–C3 loop with the case layer; UI presentation of testimonies/hypotheses/accusations (the UE widgets layer does not yet surface M3.7 APIs — that is the next core+UE task, and it is deliberately NOT claimed as done).
- **NOT TESTED:** Windows automation scripts (01–04 .bat) against the new APIs — unchanged by this milestone, still engine-blocked as documented in `reports/M3_RUNTIME_TEST_REPORT.md`.

## 8. Next actions (in priority order)

1. **UE layer surfacing (next session):** extend `TLSVillageGameMode`/`TLSWidgets` to call `Game::AvailableTestimony/HearTestimony/FormHypothesis/MakeAccusation/OpenQuestions` — the case board UI (testimonies, hypotheses, open questions, accusation dial). The core API is stable and tested; the UE layer is where the slice becomes playable.
2. **Dialogue data hooks:** add `dialogue`-presented testimonies (the existing `has_evidence` condition style can gate on `on_learned_flags` M3.7 now sets) so NPCs *in dialogue* react to learned facts; the fact layer already sets the flags.
3. **Chapter C4+ content** per `MILESTONE_PLAN` M3 scope: facts/testimonies for Griffiths/Harries/Bellamy (the Y-Porth line) reusing this exact schema — no new engine work needed.
4. **Endings model (M3.8 candidate):** E1–E4 condition evaluation over the existing flag set (`FLG_FINAL_CHOICE` etc.) + the accusation ledger, deterministic and testable offline.
