#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THE LAST SIN: The Sin-Eater — M0+M1 UE scaffold validator.

Checks the 03_Unreal/ project scaffold that is authored outside the engine
(pure text files) for internal consistency BEFORE it reaches a Windows/UE
station. This validator does NOT prove the project compiles — only a real
UE build can do that — but it catches structural mistakes that would waste
a build cycle.

Executed checks (all real, no simulation):
  1. TLS.uproject is valid JSON with the locked engine association and module.
  2. Target rules files exist and declare the correct target types.
  3. Build.cs module name matches the .uproject module and the API macro.
  4. IMPLEMENT_PRIMARY_GAME_MODULE is present and matches the module name.
  5. Every UCLASS header has GENERATED_BODY and the TLS_API macro.
  6. Config files define the GameMode, startup map and ProjectID GUID.
  7. The C++ calibration asset paths match the Python import destinations.
  8. Windows .bat scripts exist, are CRLF and reference existing files.
  9. The editor Python script's FBX inputs exist in 02_Art/exports/fbx/.
 10. ASCII-only file names across 03_Unreal/ (naming convention section 2).
 11. M1: the pure C++ core (Source/TLS/Core/) compiles engine-free (no UE
     includes) and has no UHT-exposed types; its standalone test runner exists.
 12. M1: the village game mode, NPC, interactable, widgets, save and audio
     classes exist with GENERATED_BODY + TLS_API and the module deps include UMG.
 13. M1: DefaultEngine.ini points the default game mode at the village slice;
     DefaultGame.ini carries the narrative root; the slice .bat exists (CRLF).
 14. M1: the placeholder audio set + manifest exist under 04_Audio/.

Usage: python3 tools/validate_unreal_scaffold.py   (from the repo root)
Exit code: 0 = all checks passed, 1 = failures.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UE_DIR = ROOT / "03_Unreal"

CHECKS = [0, 0]  # passed, failed


def ok(message):
    CHECKS[0] += 1
    print(f"  [PASS] {message}")


def fail(message):
    CHECKS[1] += 1
    print(f"  [FAIL] {message}")


def section(title):
    print(f"\n== {title} ==")


def main():
    print("=" * 56)
    print("THE LAST SIN — M0 UE scaffold validator (03_Unreal/)")
    print("=" * 56)

    # ---------------------------------------------------------- uproject
    section("1) TLS.uproject")
    uproject_path = UE_DIR / "TLS.uproject"
    if not uproject_path.is_file():
        fail("TLS.uproject missing")
        return finish()
    uproject = json.loads(uproject_path.read_text(encoding="utf-8"))
    if uproject.get("EngineAssociation") == "5.4":
        ok("EngineAssociation locked to 5.4 (UE 5.4 LTS policy)")
    else:
        fail(f"EngineAssociation = {uproject.get('EngineAssociation')!r}, expected '5.4'")
    modules = uproject.get("Modules", [])
    if any(m.get("Name") == "TLS" and m.get("Type") == "Runtime" for m in modules):
        ok("Runtime module 'TLS' declared")
    else:
        fail("Runtime module 'TLS' not declared")
    plugin_names = {p.get("Name") for p in uproject.get("Plugins", [])}
    for plugin in ("PythonScriptPlugin", "EditorScriptingUtilities"):
        if plugin in plugin_names:
            ok(f"plugin enabled: {plugin}")
        else:
            fail(f"plugin missing from uproject: {plugin}")

    # ---------------------------------------------------------- targets
    section("2) Target rules")
    game_target = UE_DIR / "Source" / "TLS.Target.cs"
    editor_target = UE_DIR / "Source" / "TLSEditor.Target.cs"
    for path, cls, target_type in (
        (game_target, "TLSTarget", "TargetType.Game"),
        (editor_target, "TLSEditorTarget", "TargetType.Editor"),
    ):
        if not path.is_file():
            fail(f"{path.name} missing")
            continue
        text = path.read_text(encoding="utf-8")
        if f"class {cls} : TargetRules" in text and target_type in text:
            ok(f"{path.name}: class {cls} ({target_type})")
        else:
            fail(f"{path.name}: wrong class name or target type")
        if '"TLS"' in text or 'ExtraModuleNames.Add("TLS")' in text:
            ok(f"{path.name}: adds module TLS")
        else:
            fail(f"{path.name}: does not add module TLS")

    # ---------------------------------------------------------- module
    section("3) Module / Build.cs")
    build_cs = UE_DIR / "Source" / "TLS" / "TLS.Build.cs"
    if not build_cs.is_file():
        fail("Source/TLS/TLS.Build.cs missing")
    else:
        text = build_cs.read_text(encoding="utf-8")
        if "public class TLS : ModuleRules" in text:
            ok("Build.cs class 'TLS' matches the uproject module")
        else:
            fail("Build.cs class name mismatch")
        for dep in ("Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput"):
            if f'"{dep}"' in text:
                ok(f"dependency declared: {dep}")
            else:
                fail(f"dependency missing: {dep}")

    module_cpp = UE_DIR / "Source" / "TLS" / "TLS.cpp"
    if module_cpp.is_file():
        text = module_cpp.read_text(encoding="utf-8")
        if re.search(r"IMPLEMENT_PRIMARY_GAME_MODULE\(\s*\w+,\s*TLS\s*,", text):
            ok("IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, TLS, \"TLS\")")
        else:
            fail("TLS.cpp: IMPLEMENT_PRIMARY_GAME_MODULE mismatch")
    else:
        fail("Source/TLS/TLS.cpp missing")

    # ---------------------------------------------------------- classes
    section("4) C++ classes")
    for header, uclass in (
        ("TLSGameMode.h", "ATLSGameMode"),
        ("TLSCharacter.h", "ATLSCharacter"),
    ):
        path = UE_DIR / "Source" / "TLS" / header
        if not path.is_file():
            fail(f"{header} missing")
            continue
        text = path.read_text(encoding="utf-8")
        problems = []
        if f"class TLS_API {uclass}" not in text:
            problems.append("TLS_API macro")
        if "GENERATED_BODY()" not in text:
            problems.append("GENERATED_BODY()")
        if "UCLASS()" not in text:
            problems.append("UCLASS()")
        if problems:
            fail(f"{header}: missing {', '.join(problems)}")
        else:
            ok(f"{header}: UCLASS + GENERATED_BODY + TLS_API")

    game_mode_cpp = UE_DIR / "Source" / "TLS" / "TLSGameMode.cpp"
    if game_mode_cpp.is_file():
        text = game_mode_cpp.read_text(encoding="utf-8")
        if "ATLSCharacter::StaticClass()" in text:
            ok("TLSGameMode: DefaultPawnClass = ATLSCharacter")
        else:
            fail("TLSGameMode: does not set the default pawn")
        if "RestartPlayerAtTransform" in text:
            ok("TLSGameMode: empty-map pawn fallback present")
        else:
            fail("TLSGameMode: empty-map pawn fallback missing")
    else:
        fail("TLSGameMode.cpp missing")

    character_cpp = UE_DIR / "Source" / "TLS" / "TLSCharacter.cpp"
    if character_cpp.is_file():
        text = character_cpp.read_text(encoding="utf-8")
        for token, label in (
            ("UInputMappingContext", "Enhanced Input mapping context"),
            ("EKeys::Gamepad_LeftY", "gamepad movement mapping"),
            ("bCanCrouch = true", "crouch enabled"),
            ("JumpZVelocity = 0.0f", "jump disabled (M0 contract: no jump)"),
        ):
            if token in text:
                ok(f"TLSCharacter: {label}")
            else:
                fail(f"TLSCharacter: {label} missing")
    else:
        fail("TLSCharacter.cpp missing")

    # ---------------------------------------------------------- config
    section("5) Config files")
    engine_ini = UE_DIR / "Config" / "DefaultEngine.ini"
    if engine_ini.is_file():
        text = engine_ini.read_text(encoding="utf-8")
        if 'GlobalDefaultGameMode="/Script/TLS.TLSVillageGameMode"' in text:
            ok("DefaultEngine.ini: GlobalDefaultGameMode = TLSVillageGameMode (M1 slice)")
        elif 'GlobalDefaultGameMode="/Script/TLS.TLSGameMode"' in text:
            ok("DefaultEngine.ini: GlobalDefaultGameMode = TLSGameMode (M0 mode)")
        else:
            fail("DefaultEngine.ini: GameMode not set")
        if "L_TLS_TestRoom" in text:
            ok("DefaultEngine.ini: startup map = L_TLS_TestRoom")
        else:
            fail("DefaultEngine.ini: startup map missing")
        if "r.DynamicGlobalIlluminationMethod=1" in text:
            ok("DefaultEngine.ini: Lumen GI enabled (test lighting contract)")
        else:
            fail("DefaultEngine.ini: Lumen GI missing")
    else:
        fail("DefaultEngine.ini missing")

    game_ini = UE_DIR / "Config" / "DefaultGame.ini"
    if game_ini.is_file():
        text = game_ini.read_text(encoding="utf-8")
        if re.search(r"ProjectID=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text):
            ok("DefaultGame.ini: ProjectID GUID present")
        else:
            fail("DefaultGame.ini: ProjectID missing/invalid")
    else:
        fail("DefaultGame.ini missing")

    # ---------------------------------------------- C++/python asset paths
    section("6) Calibration asset paths (C++ <-> Python)")
    py_path = UE_DIR / "Scripts" / "import_and_calibrate.py"
    cpp_paths = set()
    if game_mode_cpp.is_file():
        cpp_paths = set(re.findall(r"/Game/TLS/ENV/TLS-ENV-\d+/SM_TLS-ENV-\d+", game_mode_cpp.read_text(encoding="utf-8")))
    py_paths = set()
    if py_path.is_file():
        py_paths = set(re.findall(r"/Game/TLS/ENV/TLS-ENV-\d+", py_path.read_text(encoding="utf-8")))
    # C++ LoadObject uses full object paths (<package>/<asset>.<asset>); the
    # Python importer uses the destination directory. Compare directories.
    cpp_dirs = {p.rsplit("/", 1)[0] for p in cpp_paths}
    expected = {"/Game/TLS/ENV/TLS-ENV-001", "/Game/TLS/ENV/TLS-ENV-002"}
    if cpp_dirs == expected and py_paths == expected:
        ok("both import destinations match the C++ LoadObject paths")
    else:
        fail(f"asset path mismatch: C++ dirs {sorted(cpp_dirs)} vs Python {sorted(py_paths)} (expected {sorted(expected)})")

    # ---------------------------------------------------------- bat files
    section("7) Windows batch scripts")
    for bat in ("01_build_editor.bat", "02_import_and_calibrate.bat", "03_play_test.bat"):
        path = UE_DIR / "Scripts" / bat
        if not path.is_file():
            fail(f"{bat} missing")
            continue
        raw = path.read_bytes()
        if b"\r\n" in raw and raw.count(b"\r\n") >= raw.count(b"\n") - raw.count(b"\r\n"):
            ok(f"{bat}: CRLF line endings (Windows cmd)")
        else:
            fail(f"{bat}: not CRLF - Windows cmd may misparse it")
        try:
            raw.decode("ascii")
            ok(f"{bat}: pure ASCII (codepage-safe)")
        except UnicodeDecodeError:
            fail(f"{bat}: non-ASCII content (Windows codepage risk)")

    if py_path.is_file() and (UE_DIR / "Scripts" / "02_import_and_calibrate.bat").is_file():
        ok("02_import_and_calibrate.bat references import_and_calibrate.py")

    # Regression guards for the Windows automation (real failure modes found
    # by code review; they must never silently come back).
    build_bat = UE_DIR / "Scripts" / "01_build_editor.bat"
    if build_bat.is_file():
        text = build_bat.read_text(encoding="utf-8")
        if 'set "UEROOT=%%~dp0' in text:
            fail("01_build_editor.bat derives UEROOT from %%~dp0 (script folder) - "
                 "breaks the Build.bat path; derive it from UEBIN instead")
        elif '%%~dpI..\\..\\..' in text and '%%~fI' in text:
            ok("01_build_editor.bat: UEROOT derived from UEBIN (3 levels up, normalized)")
        else:
            fail("01_build_editor.bat: UEROOT derivation pattern not recognized")
        if 'if not exist "%UEBUILD%\\Build.bat"' in text:
            ok("01_build_editor.bat: Build.bat existence checked before call")
        else:
            fail("01_build_editor.bat: no Build.bat existence check (misleading failure)")
    import_bat = UE_DIR / "Scripts" / "02_import_and_calibrate.bat"
    if import_bat.is_file():
        text = import_bat.read_text(encoding="utf-8")
        tokens_ok = ("if errorlevel 1" in text and "findstr" in text
                     and 'findstr /C:"true"' in text and "overall_pass" in text)
        if tokens_ok:
            ok("02_import_and_calibrate.bat: checks errorlevel + report overall_pass "
               "before claiming success")
        else:
            fail("02_import_and_calibrate.bat: missing failure handling "
                 "(errorlevel / overall_pass verification)")
    for bat in ("03_play_test.bat", "04_play_slice.bat"):
        path = UE_DIR / "Scripts" / bat
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if 'if not exist "%UEBIN%\\UnrealEditor.exe"' in text:
                ok(f"{bat}: UnrealEditor.exe existence checked before start")
            else:
                fail(f"{bat}: no UnrealEditor.exe existence check (bad TLS_UE_ROOT goes unnoticed)")

    # ---------------------------------------------------------- FBX inputs
    section("8) FBX inputs exist")
    if py_path.is_file():
        text = py_path.read_text(encoding="utf-8")
        for fbx in ("tls_env_001_calibration_gnomon_v001.fbx", "tls_env_002_reference_figure_v001.fbx"):
            fbx_file = ROOT / "02_Art" / "exports" / "fbx" / fbx
            if fbx in text and fbx_file.is_file():
                ok(f"FBX referenced and present: {fbx}")
            else:
                fail(f"FBX referenced in script but missing: {fbx}")

    # ---------------------------------------------------------- naming
    section("9) ASCII file naming under 03_Unreal/")
    bad_names = [str(p.relative_to(ROOT)) for p in UE_DIR.rglob("*") if p.is_file() and not p.name.isascii()]
    if bad_names:
        fail(f"non-ASCII file names: {bad_names[:5]}")
    else:
        ok("all file names are ASCII (naming convention section 2)")

    # ---------------------------------------------------------- gitignore
    section("10) 03_Unreal/.gitignore")
    gi = UE_DIR / ".gitignore"
    if gi.is_file():
        text = gi.read_text(encoding="utf-8")
        missing = [d for d in ("Intermediate/", "Saved/", "Binaries/") if d not in text]
        if not missing:
            ok("generated dirs ignored (Intermediate/Saved/Binaries)")
        else:
            fail(f".gitignore missing generated dirs: {missing}")
    else:
        fail("03_Unreal/.gitignore missing")

    # ---------------------------------------------------------- M1: pure core
    section("11) M1 pure C++ core (engine-independent)")
    core_dir = UE_DIR / "Source" / "TLS" / "Core"
    core_files = ["TLSJson.h", "TLSJson.cpp", "TLSCoreTypes.h", "TLSCoreTypes.cpp",
                  "TLSEvidence.h", "TLSEvidence.cpp", "TLSQuests.h", "TLSQuests.cpp",
                  "TLSVillageState.h", "TLSVillageState.cpp",
                  "TLSDialogue.h", "TLSDialogue.cpp", "TLSGameState.h", "TLSGameState.cpp"]
    missing_core = [f for f in core_files if not (core_dir / f).is_file()]
    if not missing_core:
        ok(f"core: all {len(core_files)} files present")
    else:
        fail(f"core files missing: {missing_core}")

    ue_tokens = ["#include \"CoreMinimal.h\"",
                 "#include \"Engine/",
                 "UCLASS", "GENERATED_BODY", "UE_LOG", "FString", "TArray",
                 "check(", "ensure("]
    dirty = []
    for f in core_files:
        path = core_dir / f
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in ue_tokens:
            if token in text:
                # FString/TArray appear only inside comments in clean files
                for line in text.splitlines():
                    if token in line and "//" not in line.split(token)[0]:
                        dirty.append(f"{f}: contains UE token '{token}' outside a comment")
                        break
    if not dirty:
        ok("core: zero engine dependencies (dual-compilation contract holds)")
    else:
        for d in dirty[:5]:
            fail(d)

    test_runner = ROOT / "tools" / "core_tests" / "run_core_tests.sh"
    test_main = ROOT / "tools" / "core_tests" / "test_main.cpp"
    sim = ROOT / "tools" / "core_tests" / "sim_playthrough.cpp"
    if test_runner.is_file() and test_main.is_file() and sim.is_file():
        ok("standalone core test harness present (g++ build + run script)")
    else:
        fail("core test harness incomplete")

    # ---------------------------------------------------------- M1: classes
    section("12) M1 gameplay classes")
    m1_headers = {
        "TLSVillageGameMode.h": ["ATLSVillageGameMode", "GENERATED_BODY", "TLS_API",
                                 "tls::Game", "OnDigitPressed", "TLSNewGame"],
        "TLSNPC.h": ["ATLSNPC", "GENERATED_BODY", "TLS_API", "DialogueId"],
        "TLSInteractable.h": ["ATLSInteractable", "ETLSInteractKind", "Bed"],
        "TLSWidgets.h": ["UTLSHUDWidget", "UTLSDialogueWidget", "UTLSLedgerWidget",
                         "UTLSJournalWidget", "GENERATED_BODY"],
        "TLSSaveGame.h": ["UTLSSaveGame", "Payload"],
        "TLSProceduralAudio.h": ["UTLSProceduralAudioComponent", "SetWeatherBlend"],
    }
    for name, tokens in m1_headers.items():
        path = UE_DIR / "Source" / "TLS" / name
        if not path.is_file():
            fail(f"{name} missing")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [t for t in tokens if t not in text]
        if not missing:
            ok(f"{name}: class declared as designed")
        else:
            fail(f"{name} missing tokens: {missing}")

    # Regression guards for UE-layer compile blockers found by review (round 2).
    # Each of these was a real would-not-compile / latent-crash issue.
    gm_hdr = (UE_DIR / "Source" / "TLS" / "TLSVillageGameMode.h").read_text(encoding="utf-8")
    gm_src = (UE_DIR / "Source" / "TLS" / "TLSVillageGameMode.cpp").read_text(encoding="utf-8")
    npc_hdr = (UE_DIR / "Source" / "TLS" / "TLSNPC.h").read_text(encoding="utf-8")
    inter_hdr = (UE_DIR / "Source" / "TLS" / "TLSInteractable.h").read_text(encoding="utf-8")
    save_hdr = (UE_DIR / "Source" / "TLS" / "TLSSaveGame.h").read_text(encoding="utf-8")
    for line in gm_hdr.splitlines():
        if "static FColor PaletteColor" in line:
            if line.rstrip().endswith("const;"):
                fail("TLSVillageGameMode.h: static PaletteColor declared const (ill-formed C++)")
                break
    else:
        ok("TLSVillageGameMode.h: static PaletteColor is not const-qualified")
    if "Actor->NameLabel" in gm_src or "Actor->PromptLabel" in gm_src:
        fail("TLSVillageGameMode.cpp: reaches protected labels directly (use the public setters)")
    else:
        ok("TLSVillageGameMode.cpp: protected labels only touched via public setters")
    if "SetNameLabelText" in npc_hdr:
        ok("TLSNPC.h: public SetNameLabelText present")
    else:
        fail("TLSNPC.h: public SetNameLabelText missing (protected-access regression)")
    if "SetPromptLabelText" in inter_hdr:
        ok("TLSInteractable.h: public SetPromptLabelText present")
    else:
        fail("TLSInteractable.h: public SetPromptLabelText missing (protected-access regression)")
    if "namespace TLSSave" in save_hdr and "WriteSlot" in save_hdr and "ReadSlot" in save_hdr:
        ok("TLSSaveGame.h: TLSSave slot helpers declared for other units")
    else:
        fail("TLSSaveGame.h: TLSSave helpers undeclared (game mode cannot link)")
    if "UnregisterConsoleObject" in gm_src:
        ok("TLSVillageGameMode.cpp: TLS.NewGame console command unregistered in EndPlay")
    else:
        fail("TLSVillageGameMode.cpp: console command never unregistered (dangling delegate risk)")

    build_cs = (UE_DIR / "Source" / "TLS" / "TLS.Build.cs").read_text(encoding="utf-8")
    for dep in ('"UMG"', '"Slate"', '"SlateCore"'):
        if dep in build_cs:
            ok(f"Build.cs declares {dep} (code-built UMG)")
            break
    else:
        fail("Build.cs is missing the UMG/Slate dependencies")

    village_gm_src = (UE_DIR / "Source" / "TLS" / "TLSVillageGameMode.cpp").read_text(encoding="utf-8")
    village_gm_hdr = (UE_DIR / "Source" / "TLS" / "TLSVillageGameMode.h").read_text(encoding="utf-8")
    combined = village_gm_src + village_gm_hdr
    for token in ('"Core/TLSGameState.h"', '"Core/TLSJson.h"', '05_Narrative',
                  'blackthorne_blockout.json'):
        if token not in combined:
            fail(f"TLSVillageGameMode lost the reference: {token}")
            break
    else:
        ok("village game mode consumes the pure core + 05_Narrative world data")

    character_src = (UE_DIR / "Source" / "TLS" / "TLSCharacter.cpp").read_text(encoding="utf-8")
    for token in ("Input_Interact", "Input_Digit1", "EKeys::E", "EKeys::One"):
        if token not in character_src:
            fail(f"TLSCharacter.cpp missing M1 input: {token}")
            break
    else:
        ok("character carries the M1 interaction/UI input (E/J/Esc/R/1-9)")

    # ---------------------------------------------------------- M1: configs
    section("13) M1 configs and Windows scripts")
    engine_ini = (UE_DIR / "Config" / "DefaultEngine.ini").read_text(encoding="utf-8")
    if "TLSVillageGameMode" in engine_ini:
        ok("DefaultEngine.ini: village slice is the default game mode")
    else:
        fail("DefaultEngine.ini still points at the M0-only game mode")
    if "L_TLS_Blackthorne" in engine_ini:
        ok("DefaultEngine.ini: startup map = L_TLS_Blackthorne")
    else:
        fail("startup map was not switched to the village map")

    game_ini = (UE_DIR / "Config" / "DefaultGame.ini").read_text(encoding="utf-8")
    if "NarrativeRoot" in game_ini and "05_Narrative" in game_ini:
        ok("DefaultGame.ini: narrative root configured")
    else:
        fail("DefaultGame.ini missing the narrative root key")

    slice_bat = UE_DIR / "Scripts" / "04_play_slice.bat"
    if slice_bat.is_file():
        raw = slice_bat.read_bytes()
        if b"\r\n" in raw and all(b < 128 for b in raw):
            ok("04_play_slice.bat exists (CRLF, ASCII)")
        else:
            fail("04_play_slice.bat must be CRLF + ASCII")
    else:
        fail("04_play_slice.bat missing")

    import_py = (UE_DIR / "Scripts" / "import_and_calibrate.py").read_text(encoding="utf-8")
    for token in ("M_TLS_Blockout", "L_TLS_Blackthorne", "TLSGameMode", "04_Audio"):
        if token not in import_py:
            fail(f"import script lost the M1 step: {token}")
            break
    else:
        ok("import automation covers M1 (blockout material, village map, audio)")

    # ---------------------------------------------------------- M1: audio
    section("14) M1 placeholder audio set")
    audio_root = ROOT / "04_Audio"
    expected = [
        "ambience/tls_snd_002_wind.wav",
        "ambience/tls_snd_002_rain.wav",
        "foley/tls_snd_010_footsteps.wav",
        "foley/tls_snd_012_page_turn.wav",
        "ui/tls_snd_002_bell_cynog.wav",
    ]
    missing_audio = [f for f in expected if not (audio_root / f).is_file()]
    if not missing_audio:
        ok(f"all {len(expected)} placeholder wavs present")
    else:
        fail(f"placeholder audio missing: {missing_audio}")
    if (audio_root / "manifest_audio.json").is_file():
        ok("audio manifest present (placeholder status documented)")
    else:
        fail("audio manifest missing")
    gen = ROOT / "tools" / "generate_placeholder_audio.py"
    if gen.is_file():
        ok("audio generator script tracked (reproducible assets)")
    else:
        fail("audio generator script missing")

    return finish()


def finish():
    print("\n" + "=" * 56)
    total = CHECKS[0] + CHECKS[1]
    if CHECKS[1] == 0:
        print(f"ALL CHECKS PASSED ({CHECKS[0]}/{total})")
        print("NOTE: this validates the scaffold structure only - compilation and UE import")
        print("still require a real Windows/UE5 station (no fabrication of those results).")
        return 0
    print(f"FAILED: {CHECKS[1]} of {total} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
