# M3 — RUNTIME TEST REPORT
## THE LAST SIN: The Sin-Eater — real-environment execution attempt

**Report date:** 2026-10-23 (UTC)
**Branch:** `feature/m3-runtime-validation` (based on `main` @ `0d14fe1`)
**Rule honored throughout:** no PASS without an actually executed test; no invented engine results; CI success is NOT treated as proof the game runs in UE.

---

## 1. Machine and environment (measured, not assumed)

| Item | Measured value | UE 5.4 editor requirement | Verdict |
|---|---|---|---|
| OS | Debian GNU/Linux 13 (trixie), kernel 5.10.134, x86_64, **headless container** | Windows 10/11 64-bit (or macOS; Linux source builds possible) | — |
| CPU | Intel Xeon, **2 cores** | 8+ cores recommended | INSUFFICIENT |
| RAM | **3.9 GiB, 0 swap** | 32 GB recommended for source builds | INSUFFICIENT |
| Storage | **9.2 GB free** | ~100+ GB for UE 5.4 source + build | INSUFFICIENT |
| GPU | **NONE** — `lspci` shows no VGA/3D/display device; `/dev/dri` absent; no Vulkan | Vulkan-capable GPU mandatory for editor/game rendering | INSUFFICIENT |
| Display | None (`DISPLAY` empty) | Required to open any editor/game window | BLOCKED |
| Drivers | No GPU drivers exist on host (`nvidia-smi` absent) | — | — |

Evidence: `reports/M3_EVIDENCE/01_environment_probe.txt` (unedited command output).

## 2. Tools present / missing (probed for real)

| Tool | Status |
|---|---|
| git 2.47.3, g++ 14.2.0 (C++17), GNU Make 4.4.1, Python 3.12.15 | **INSTALLED** |
| Unreal Engine 5.4 | **NOT INSTALLED** (searched common install paths) |
| Epic Games Launcher | **NOT INSTALLED** — no Linux build of the launcher exists (Windows/macOS only) |
| Visual Studio / MSVC (`cl`, `msbuild`) | **NOT INSTALLED** — Windows-only products |
| clang, cmake, dotnet, mono, wine | **NOT INSTALLED** |

## 3. Project files inspected (M3 Phase 1 item 3–4)

- `03_Unreal/TLS.uproject` — `EngineAssociation: "5.4"`, runtime module `TLS`, plugins `PythonScriptPlugin` + `EditorScriptingUtilities`. Consistent, no engine-version conflict.
- `Source/TLS/TLS.Build.cs` — modules Core/CoreUObject/Engine/InputCore/EnhancedInput/UMG/Slate/SlateCore. The `Core/` folder stays UE-include-free by design (same code compiles under g++ here).
- `Config/DefaultEngine.ini` — `GlobalDefaultGameMode=/Script/TLS.TLSVillageGameMode`; startup maps point to `/Game/TLS/Maps/L_TLS_Blackthorne`.
- **No `Content/` folder and no `.umap` exists in the repo — by design:** `Scripts/import_and_calibrate.py` (run inside the editor) creates `L_TLS_TestRoom` and `L_TLS_Blackthorne`; the village itself is built at runtime by `ATLSVillageGameMode` from `05_Narrative/world` data. So "map missing from git" is NOT a defect — but it means first-run requires the CAL-01 automation step inside the editor.
- `main` reviewed before any edit: local `main` == `origin/main` == `0d14fe1`; CI run #9 on that commit: **success** (evidence `05_ci_status.txt`). M2 report present at `reports/M2_IMPLEMENTATION_REPORT.md`.

## 4. Installation attempt (M3 Phase 2) — real attempts, real outputs

| Attempt | Command | Result |
|---|---|---|
| A | `git ls-remote https://github.com/EpicGames/UnrealEngine.git` | FAIL — private source; needs Epic EULA acceptance + Epic-linked GitHub account. The token supplied for this repo is scoped to the user's repository only. |
| B | GitHub API query for tag `5.4.4-release` | HTTP 404 (hidden without Epic-linked auth) |
| C | Epic Games Launcher for Linux | No Linux build exists (Windows/macOS only) |
| D | Source-build feasibility on this host | IMPOSSIBLE — measured: 9.2 GB free (need ~100+ GB), 2 cores, 3.9 GiB RAM, 0 GPU, 0 display |

Full log: `reports/M3_EVIDENCE/02_engine_install_attempts.txt`.
**Stopping point (per the M3 brief itself):** five independent hard blockers; each alone is decisive. Continuing install attempts on this host would waste time on infeasible paths, which the brief explicitly forbids.

## 5. Build / open / run status (M3 Phases 3–4)

| Step | Result | Reason |
|---|---|---|
| Build C++ modules with UBT/MSVC | **BLOCKED** | No UE 5.4, no MSVC — neither can exist on this host |
| Open `TLS.uproject` in Unreal Editor | **BLOCKED** | No engine, no GPU, no display |
| Map load (`L_TLS_Blackthorne`) | **NOT TESTED** | Map is generated in-editor by CAL-01 automation; cannot run without editor |
| PIE / standalone game run | **NOT TESTED** | Requires the above |
| Rumors / witnesses / quests / save / settings inside UE | **NOT TESTED** | Their UE-layer wiring can only execute inside the engine |

**What WAS executed for real on this machine (engine-independent):**

| Check | Result |
|---|---|
| Full C++17 core-logic suite (the same `Core/` source that compiles into the TLS UE module) | **PASS — 1763/1763** (`03_core_tests_final.txt`) |
| `tools/validate_project.py` | **PASS — 73/73** |
| `tools/validate_narrative.py` | **PASS — 43/43** |
| `tools/validate_unreal_scaffold.py` (project structure, scripts, uproject/config consistency) | **PASS — 70/70** |
| CI on `main` @ `0d14fe1` (validate + core-logic jobs) | **PASS** (`05_ci_status.txt`) — recorded as CI-only evidence, not as game-run proof |

## 6. Screenshots (M3 Phase 5) — explicit disclosure

**No real screenshots exist for this M3 run.** This host has no GPU, no display, and no UE installation — the software the seven screenshots would depict does not exist here, and fabricating images is forbidden by both the brief and this project's standing integrity rules. `reports/M3_EVIDENCE/06_no_screenshots_statement.txt` states this formally. Real screenshots (`01`–`07`) become capturable only on a Windows/GPU machine running UE 5.4; the folder structure and naming convention are ready for that session.

## 7. Result ledger (PASS / FAIL / BLOCKED / NOT TESTED)

- **PASS:** environment probe; toolchain probe; project-file consistency checks; 1763/1763 core tests; 73/73 + 43/43 + 70/70 validators; CI on main.
- **FAIL:** none new (no system regressed; no code changed in M3).
- **BLOCKED (with precise cause):** UE install (private source + resources), UBT/MSVC build (no toolchain), editor open (no engine/GPU/display), in-editor map generation, PIE/standalone run, in-UE feature testing.
- **NOT TESTED:** map load, player movement, interactables, rumor/quest/save/settings systems inside UE, crash behavior. All require the blocked steps above.

## 8. Remaining errors, causes, and next steps

1. **Root blocker:** this container is not a UE-capable host and cannot be made one (no GPU passthrough, capped disk/RAM, private Epic source). It is a permanent NOT-RUN for engine work, not a temporary one.
2. **Required for any M3 runtime progress — a Windows environment with:** GTX 1650-class GPU or better, 32 GB RAM, 150+ GB SSD, Windows 10/11, Visual Studio 2022 with "Game development with C++" workload, UE 5.4 via Epic Games Launcher (GitHub source alternative: Epic-linked account + EULA). Concrete options: the user's own PC is below minimum spec (3rd-gen i3, integrated graphics — documented in M0), so a GPU cloud VM (Azure NV-series, AWS G4dn, Paperspace, Vast.ai) or any qualifying physical Windows PC is required.
3. **On that machine the runbook is already prepared and verified structurally:** `01_build_editor.bat` → `02_import_and_calibrate.bat` (creates both maps via CAL-01) → `03_play_test.bat` / `04_play_slice.bat`; then capture `01_environment.png` … `07_known_errors.png` into `reports/M3_EVIDENCE/`.
4. **After first successful editor run:** test in this order — map load, player movement, interactables, then M2 systems (rumor ticks witnessed in PIE, save slot v2, quest advancement, settings persistence) — and record every result with a real screenshot.

## 9. Deliverables of this M3 run

- `reports/M3_RUNTIME_TEST_REPORT.md` (this file)
- `reports/M3_EVIDENCE/01_environment_probe.txt` — real hardware/OS/toolchain capture
- `reports/M3_EVIDENCE/02_engine_install_attempts.txt` — real install attempts + feasibility math
- `reports/M3_EVIDENCE/03_core_tests_final.txt` — full 1763-check suite output
- `reports/M3_EVIDENCE/04_validators_final.txt` — 73/73, 43/43, 70/70
- `reports/M3_EVIDENCE/05_ci_status.txt` — real CI runs with links
- `reports/M3_EVIDENCE/06_no_screenshots_statement.txt` — formal disclosure about screenshots
- Branch: `feature/m3-runtime-validation` (no direct edits to `main`)
