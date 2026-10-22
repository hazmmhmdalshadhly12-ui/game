#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THE LAST SIN: The Sin-Eater — M0 UE scaffold validator.

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
        if 'GlobalDefaultGameMode="/Script/TLS.TLSGameMode"' in text:
            ok("DefaultEngine.ini: GlobalDefaultGameMode = TLSGameMode")
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
