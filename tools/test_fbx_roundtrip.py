#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THE LAST SIN: The Sin-Eater — M0 FBX round-trip verification.

Re-imports the two calibration FBX files into a clean Blender (bpy) scene and
measures them, proving that the exported FBX files carry the full CAL-01
contract (scale, pivot, forward axis) before they reach Unreal.

This is a REAL executed test wherever a bpy environment exists
(uv venv .venv-bpy + bpy==5.0.1, see scripts/ in the workspace root).
It is NOT a substitute for the in-engine CAL-01 check.

Checks per asset:
  - binary FBX header + version 7400
  - overall bounding box sizes (converted to Unreal's expected axes)
  - pivot at the origin (min Z == 0)
  - gnomon forward axis (+X in Unreal = -Y in Blender authoring space)
  - material slot count (5 gnomon / 1 figure)

Usage (needs bpy):
    python3 tools/test_fbx_roundtrip.py            (from the repo root)
Exit code: 0 = all checks passed, 2 = bpy missing, 1 = check failures.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FBX_DIR = ROOT / "02_Art" / "exports" / "fbx"
MANIFEST = ROOT / "02_Art" / "exports" / "manifest_calibration.json"

GNOMON_FBX = FBX_DIR / "tls_env_001_calibration_gnomon_v001.fbx"
FIGURE_FBX = FBX_DIR / "tls_env_002_reference_figure_v001.fbx"

TOLERANCE = 0.005  # 0.5% (CAL-01 acceptance), applied on metres here

CHECKS = [0, 0]


def ok(msg):
    CHECKS[0] += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    CHECKS[1] += 1
    print(f"  [FAIL] {msg}")


def fbx_header(path):
    with open(path, "rb") as fh:
        head = fh.read(27)
    if not head.startswith(b"Kaydara FBX Binary  \x00"):
        return None
    return int.from_bytes(head[23:27], "little")


def near(a, b, tol=TOLERANCE):
    return abs(a - b) <= abs(b) * tol


def main():
    print("=" * 56)
    print("THE LAST SIN — M0 FBX round-trip verification (Blender side)")
    print("=" * 56)

    try:
        import bpy  # noqa: F401
        import mathutils
    except ImportError:
        print("bpy / mathutils not available. Install into an isolated env:")
        print("  uv venv .venv-bpy --python 3.11 && uv pip install bpy==5.0.1")
        return 2

    for path in (GNOMON_FBX, FIGURE_FBX):
        if not path.is_file():
            fail(f"missing FBX: {path}")
            return 1

    # ------------------------------------------------------------- headers
    print("\n== FBX headers ==")
    for path in (GNOMON_FBX, FIGURE_FBX):
        version = fbx_header(path)
        if version == 7400:
            ok(f"{path.name}: binary FBX v7400 (UE-supported)")
        else:
            fail(f"{path.name}: unexpected FBX version {version}")

    # ------------------------------------------------------------- import
    print("\n== Round-trip measurement (clean scene import) ==")
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Standard FBX import operator (same API family as the tested generator).
    # Axis handling is auto-detected from the file header (-Y forward / Z up).
    for fbx in (GNOMON_FBX, FIGURE_FBX):
        bpy.ops.import_scene.fbx(filepath=str(fbx))

    meshes = {obj.name: obj for obj in bpy.context.scene.objects if obj.type == "MESH"}
    if len(meshes) != 2:
        fail(f"expected 2 imported mesh objects, found {len(meshes)}: {list(meshes)}")
        return 1

    gnomon = next((o for n, o in meshes.items() if "gnomon" in n), None)
    figure = next((o for n, o in meshes.items() if "figure" in n), None)

    # ------------------------------------------------------------- gnomon
    print("\n== TLS-ENV-001 (gnomon) ==")
    if gnomon is None:
        fail("gnomon object not found after import")
    else:
        # Apply all transforms first so measurements are in world space.
        bpy.ops.object.select_all(action="DESELECT")
        gnomon.select_set(True)
        bpy.context.view_layer.objects.active = gnomon
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        bb = [gnomon.matrix_world @ mathutils.Vector(c) for c in gnomon.bound_box]
        xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
        gmin = (min(xs), min(ys), min(zs)); gmax = (max(xs), max(ys), max(zs))
        size = tuple(gmax[i] - gmin[i] for i in range(3))

        print(f"  measured bounds (m): min={tuple(round(v, 4) for v in gmin)} max={tuple(round(v, 4) for v in gmax)}")
        print(f"  measured size   (m): {tuple(round(v, 4) for v in size)}")

        ok(f"overall X size = {size[0]:.4f} m (contract 1.35 m = plate 1.00 + arrow 0.35)") if near(size[0], 1.35) else fail(f"X size {size[0]:.4f} != 1.35")
        ok(f"overall Y size = {size[1]:.4f} m (contract 1.00 m base)") if near(size[1], 1.00) else fail(f"Y size {size[1]:.4f} != 1.00")
        ok(f"overall Z size = {size[2]:.4f} m (contract 0.77 m)") if near(size[2], 0.77) else fail(f"Z size {size[2]:.4f} != 0.77")
        ok("pivot at origin (min Z == 0)") if near(gmin[2], 0.0, 0.001) else fail(f"min Z = {gmin[2]:.4f} (pivot lifted)")
        ok("base centred on Y (min/max ~ -0.5/+0.5)") if near(gmin[1], -0.5) and near(gmax[1], 0.5) else fail(f"Y range {gmin[1]:.4f}..{gmax[1]:.4f}")
        # Forward: arrow points +X in Blender authoring space -> +X in Unreal.
        if gmax[0] > 0.6 and gmin[0] < -0.4:
            ok(f"forward axis: arrow extends +X (range {gmin[0]:.3f}..{gmax[0]:.3f} -> lands +X in UE)")
        else:
            fail(f"forward axis wrong: X range {gmin[0]:.3f}..{gmax[0]:.3f}")
        slots = len(gnomon.data.materials)
        ok(f"material slots = {slots} (contract 5)") if slots == 5 else fail(f"material slots {slots} != 5")

    # ------------------------------------------------------------- figure
    print("\n== TLS-ENV-002 (reference figure) ==")
    if figure is None:
        fail("figure object not found after import")
    else:
        bpy.ops.object.select_all(action="DESELECT")
        figure.select_set(True)
        bpy.context.view_layer.objects.active = figure
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        bb = [figure.matrix_world @ mathutils.Vector(c) for c in figure.bound_box]
        xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
        fmin = (min(xs), min(ys), min(zs)); fmax = (max(xs), max(ys), max(zs))
        size = tuple(fmax[i] - fmin[i] for i in range(3))

        print(f"  measured bounds (m): min={tuple(round(v, 4) for v in fmin)} max={tuple(round(v, 4) for v in fmax)}")
        print(f"  measured size   (m): {tuple(round(v, 4) for v in size)}")

        ok(f"height Z = {size[2]:.4f} m (canonical 1.75 m)") if near(size[2], 1.75) else fail(f"height {size[2]:.4f} != 1.75")
        ok(f"arm span X = {size[0]:.4f} m (expected ~0.57)") if near(size[0], 0.57) else fail(f"arm span {size[0]:.4f} != 0.57")
        ok(f"depth Y = {size[1]:.4f} m (expected ~0.25)") if near(size[1], 0.25) else fail(f"depth {size[1]:.4f} != 0.245")
        ok("pivot at feet (min Z == 0)") if near(fmin[2], 0.0, 0.001) else fail(f"min Z = {fmin[2]:.4f}")
        slots = len(figure.data.materials)
        ok(f"material slots = {slots} (contract 1)") if slots == 1 else fail(f"material slots {slots} != 1")

    # ------------------------------------------------------------- manifest
    print("\n== manifest cross-check ==")
    if MANIFEST.is_file():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assets = {a["asset_id"]: a for a in data.get("assets", [])}
        g = assets.get("TLS-ENV-001", {}).get("geometry", {})
        if g.get("material_slots") and len(g["material_slots"]) == 5:
            ok("manifest records 5 gnomon material slots")
        else:
            fail("manifest gnomon material slots unexpected")
        f = assets.get("TLS-ENV-002", {})
        if f:
            ok("manifest records TLS-ENV-002 geometry")
        else:
            fail("manifest missing TLS-ENV-002")
    else:
        fail("manifest_calibration.json missing")

    print("\n" + "=" * 56)
    total = CHECKS[0] + CHECKS[1]
    if CHECKS[1] == 0:
        print(f"ALL CHECKS PASSED ({CHECKS[0]}/{total}) — FBX files carry the CAL-01 contract.")
        print("In-engine verification still required on Windows (IMP-01 / CAL-01).")
        return 0
    print(f"FAILED: {CHECKS[1]} of {total} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
