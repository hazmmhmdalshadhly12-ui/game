"""THE LAST SIN: The Sin-Eater - M0

Automated FBX import + CAL-01 calibration verification + test map creation.

Runs INSIDE the Unreal Editor (Python 3) on a Windows station via:
    03_Unreal\\Scripts\\02_import_and_calibrate.bat

What it does (all measured values are real, nothing is fabricated):
  1. Imports the two calibration FBX files into /Game/TLS/ENV/...
     with the naming convention of TECHNICAL_PIPELINE section 3 (SM_ prefix).
  2. Measures the imported static meshes (bounds, material slots) and checks
     them against the CAL-01 contract (axis & scale, tolerance <= 0.5%).
  3. Writes 03_Unreal/Reports/import_report.json with every measured value.
  4. Creates and saves the empty test map /Game/TLS/Maps/L_TLS_TestRoom
     (the grey-box room itself is built at runtime by ATLSGameMode).

Exit semantics: on any FAILED check the report contains "overall_pass": false
and [CAL-01] FAIL lines are printed to the log. The batch file surfaces the
report path at the end.
"""

import json
import os
import sys
import traceback

try:
    import unreal
except ImportError:
    print("This script must run inside the Unreal Editor (unreal module).")
    sys.exit(2)

# ---------------------------------------------------------------------------
# Paths (repo layout is fixed and ASCII per TECHNICAL_PIPELINE section 2)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))        # 03_Unreal/
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_DIR, ".."))         # repo root
FBX_DIR = os.path.join(REPO_ROOT, "02_Art", "exports", "fbx")
REPORT_DIR = os.path.join(PROJECT_DIR, "Reports")

GNOMON_FBX = os.path.join(FBX_DIR, "tls_env_001_calibration_gnomon_v001.fbx")
FIGURE_FBX = os.path.join(FBX_DIR, "tls_env_002_reference_figure_v001.fbx")

GNOMON_ASSET = "/Game/TLS/ENV/TLS-ENV-001/SM_TLS-ENV-001"
FIGURE_ASSET = "/Game/TLS/ENV/TLS-ENV-002/SM_TLS-ENV-002"
TEST_MAP = "/Game/TLS/Maps/L_TLS_TestRoom"

# ---------------------------------------------------------------------------
# CAL-01 contract (centimetres) - TECHNICAL_PIPELINE sections 4/9 + manifest
# ---------------------------------------------------------------------------
TOLERANCE_PCT = 0.5
GNOMON = {
    "x_size": 135.0, "y_size": 100.0, "z_size": 77.0,
    "x_min": -50.0, "x_max": 85.0,
    "y_min": -50.0, "y_max": 50.0,
    "z_min": 0.0, "z_max": 77.0,
    "material_slots": 5,
}
FIGURE = {
    "x_size": 57.0, "y_size": 25.0, "z_size": 175.0,
    "z_min": 0.0,
    "material_slots": 1,
}


def log(message):
    unreal.log("[CAL-01] {}".format(message))


def fail(message):
    unreal.log_error("[CAL-01] {}".format(message))


# ---------------------------------------------------------------------------
# 1) Import
# ---------------------------------------------------------------------------
def import_fbx(fbx_path, destination_path, asset_name):
    if not os.path.isfile(fbx_path):
        fail("FBX not found: {}".format(fbx_path))
        return None

    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = destination_path
    try:
        task.destination_name = asset_name
    except Exception:
        pass  # older builds: fall back to rename after import
    task.automated = True
    task.save = True
    task.replace_existing = True

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    mesh = unreal.EditorAssetLibrary.load_asset("{}/{}".format(destination_path, asset_name))
    if mesh is None:
        # fallback: import used the FBX basename - rename to the convention
        base = os.path.splitext(os.path.basename(fbx_path))[0]
        imported = unreal.EditorAssetLibrary.load_asset("{}/{}".format(destination_path, base))
        if imported is not None:
            unreal.EditorAssetLibrary.rename_asset(
                "{}/{}".format(destination_path, base),
                "{}/{}".format(destination_path, asset_name))
            mesh = unreal.EditorAssetLibrary.load_asset("{}/{}".format(destination_path, asset_name))
    return mesh


# ---------------------------------------------------------------------------
# 2) Measurement
# ---------------------------------------------------------------------------
def measure_mesh(mesh):
    box = mesh.get_bounds()
    mn, mx = box.min, box.max
    size = mx - mn
    measured = {
        "min": [round(mn.x, 4), round(mn.y, 4), round(mn.z, 4)],
        "max": [round(mx.x, 4), round(mx.y, 4), round(mx.z, 4)],
        "size": [round(size.x, 4), round(size.y, 4), round(size.z, 4)],
    }
    try:
        slots = mesh.get_editor_property("static_materials")
        measured["material_slots"] = len(slots)
    except Exception as exc:
        measured["material_slots"] = -1
        fail("Could not read material slots: {}".format(exc))
    return measured


def check(report_lines, results, name, measured_value, expected_value):
    tolerance = abs(expected_value) * TOLERANCE_PCT / 100.0
    passed = abs(measured_value - expected_value) <= tolerance
    results.append({"check": name, "measured": measured_value,
                    "expected": expected_value, "tolerance": tolerance,
                    "pass": bool(passed)})
    line = "{} {} : {} - measured {:.3f} cm, expected {:.3f} +/- {:.3f}".format(
        "[CAL-01]", "PASS" if passed else "FAIL", name,
        measured_value, expected_value, tolerance)
    report_lines.append(line)
    (log if passed else fail)(line)
    return passed


def verify_gnomon(measured, report_lines, results):
    ok_all = True
    ok_all &= check(report_lines, results, "gnomon X size (plate 100 + arrow 35)",
                    measured["size"][0], GNOMON["x_size"])
    ok_all &= check(report_lines, results, "gnomon Y size (base plate)",
                    measured["size"][1], GNOMON["y_size"])
    ok_all &= check(report_lines, results, "gnomon Z size",
                    measured["size"][2], GNOMON["z_size"])
    ok_all &= check(report_lines, results, "gnomon X min (back face)",
                    measured["min"][0], GNOMON["x_min"])
    ok_all &= check(report_lines, results, "gnomon X max (arrow tip, +X forward)",
                    measured["max"][0], GNOMON["x_max"])
    ok_all &= check(report_lines, results, "gnomon Y min", measured["min"][1], GNOMON["y_min"])
    ok_all &= check(report_lines, results, "gnomon Y max", measured["max"][1], GNOMON["y_max"])
    ok_all &= check(report_lines, results, "gnomon Z min (pivot at origin)",
                    measured["min"][2], GNOMON["z_min"])
    ok_all &= check(report_lines, results, "gnomon Z max (spire top)",
                    measured["max"][2], GNOMON["z_max"])
    ok_all &= check(report_lines, results, "gnomon material slots",
                    float(measured["material_slots"]), float(GNOMON["material_slots"]))
    return ok_all


def verify_figure(measured, report_lines, results):
    ok_all = True
    ok_all &= check(report_lines, results, "figure height (canonical 1.75 m)",
                    measured["size"][2], FIGURE["z_size"])
    ok_all &= check(report_lines, results, "figure arm span X",
                    measured["size"][0], FIGURE["x_size"])
    ok_all &= check(report_lines, results, "figure depth Y",
                    measured["size"][1], FIGURE["y_size"])
    ok_all &= check(report_lines, results, "figure Z min (pivot at feet)",
                    measured["min"][2], FIGURE["z_min"])
    ok_all &= check(report_lines, results, "figure material slots",
                    float(measured["material_slots"]), float(FIGURE["material_slots"]))
    return ok_all


# ---------------------------------------------------------------------------
# 3) Test map creation
# ---------------------------------------------------------------------------
def create_test_map():
    created = False
    try:
        unreal.EditorLevelLibrary.new_level(TEST_MAP)
        created = True
    except Exception as exc:
        fail("EditorLevelLibrary.new_level failed: {}".format(exc))
    if not created:
        try:
            editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            editor_subsystem.new_level(TEST_MAP)
            created = True
        except Exception as exc:
            fail("UnrealEditorSubsystem.new_level failed: {}".format(exc))
    if created:
        log("Test map created: {} (grey-box room is built at runtime by TLSGameMode)".format(TEST_MAP))
    else:
        fail("Could not create the test map automatically - create an EMPTY level manually "
             "and save it as {} (World Settings need no changes: the GameMode comes from "
             "DefaultEngine.ini).".format(TEST_MAP))
    return created


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run():
    report_lines = []
    overall = True

    log("M0 import + CAL-01 verification starting")
    log("Repo root: {}".format(REPO_ROOT))

    gnomon = import_fbx(GNOMON_FBX, "/Game/TLS/ENV/TLS-ENV-001", "SM_TLS-ENV-001")
    figure = import_fbx(FIGURE_FBX, "/Game/TLS/ENV/TLS-ENV-002", "SM_TLS-ENV-002")

    measured = {}
    if gnomon is not None and str(gnomon.get_class().get_name()) == "StaticMesh":
        log("Imported gnomon -> {}".format(GNOMON_ASSET))
        measured["gnomon"] = measure_mesh(gnomon)
        overall &= verify_gnomon(measured["gnomon"], report_lines, [])
    else:
        overall = False
        fail("Gnomon import FAILED - no measurement possible.")

    if figure is not None and str(figure.get_class().get_name()) == "StaticMesh":
        log("Imported figure -> {}".format(FIGURE_ASSET))
        measured["figure"] = measure_mesh(figure)
        overall &= verify_figure(measured["figure"], report_lines, [])
    else:
        overall = False
        fail("Figure import FAILED - no measurement possible.")

    map_created = create_test_map()

    # Save everything (assets + map) so the editor and PIE see them.
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)

    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, "import_report.json")
    report = {
        "stage": "M0 - automated FBX import + CAL-01 verification",
        "report_kind": "editor_python_import_and_calibration",
        "repo_root": REPO_ROOT,
        "test_map": TEST_MAP,
        "test_map_created": bool(map_created),
        "tolerance_pct": TOLERANCE_PCT,
        "measured": measured,
        "overall_pass": bool(overall),
        "lines": report_lines,
        "note": "In-game (PIE) verification additionally runs via TLSGameMode and writes "
                "03_Unreal/Reports/calibration_ingame.json. Screenshots for CAL-01 "
                "documentation are taken manually with F9 during PIE.",
    }
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    (log if overall else fail)("OVERALL: {} - report written to {}".format(
        "PASS" if overall else "FAIL", report_path))
    return overall


if __name__ == "__main__":
    try:
        run()
    except Exception:
        fail(traceback.format_exc())
