#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN: The Sin-Eater — Calibration Asset Generator (portable)
====================================================================
يجري تشغيله عبر Blender headless (bpy) لإنتاج أول أصلين من أصول المعايرة
الخاصة بالمرحلة M0 واختبار خط الإنتاج Blender -> FBX فعليًا:

  TLS-ENV-001  gnomon المعايرة (اختبار المحاور/المقياس/المحور الارتكاز)
  TLS-ENV-002  شخصية مرجعية بارتفاع 1.75 م (مرجع مقياس الإنسان)

المخرجات لكل أصل (نسبية إلى جذر المشروع، لا مسارات مطلقة):
  - ملف مصدر .blend   (02_Art/blender/source/env/)
  - ملف تصدير .fbx    (02_Art/exports/fbx/) بإعدادات التصدير المعيارية
  - إحصاءات هندسية داخل 02_Art/exports/manifest_calibration.json

جذر المشروع يُكتشف تلقائيًا نسبةً إلى موقع هذا السكريبت (tools/)،
ويمكن تجاوزه بالخيار --root.

التشغيل (Linux/macOS — الطريقة المُختبرة فعليًا في بيئة المرحلة الأولى):
  # عبر Blender مثبت:
  blender --background --python tools/make_calibration_assets.py
  # عبر حزمة bpy كوحدة بايثون (Python 3.11):
  python tools/make_calibration_assets.py

الخيارات (تمرَّر بعد "--" عند استخدام executable بلندر):
  blender --background --python tools/make_calibration_assets.py -- --root /path/to/THE_LAST_SIN --force
  python tools/make_calibration_assets.py --root /path/to/THE_LAST_SIN --force

  --root PATH   جذر مشروع بديل (افتراضيًا: الأب لمجلد tools/ حيث يقيم السكريبت)
  --force       السماح باستبدال مخرجات موجودة (المستودع يحمي ملفاتك افتراضيًا)

ملاحظة صدق: هذا السكريبت اختُبر فعليًا على Linux (bpy 5.0.1 عبر Python 3.11).
صيغة الأوامر على Windows مماثلة (بدّل الشرطة المائلة إن لزم) لكنها لم تُختبر
في بيئة Windows بعد — أول تشغيل لها مخطط داخل بوابة M0.
"""

import argparse
import json
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- bpy guard
try:
    import bpy
except ImportError:
    sys.stderr.write(
        "\n[TLS-ERROR] هذا السكريبت يتطلب Blender أو وحدة bpy، وليسا متوفرين "
        "في بيئة Python الحالية.\n"
        "الحلول:\n"
        "  1) شغّله عبر Blender المثبت:\n"
        "     blender --background --python tools/make_calibration_assets.py\n"
        "  2) أو ثبّت وحدة bpy المناسبة لإصدار بايثون لديك (يفضل 3.11):\n"
        "     pip install bpy\n"
        "لا يمكن إنتاج أصول المعايرة بدونه.\n"
    )
    sys.exit(2)

# ---------------------------------------------------------------- CLI / paths
def discover_root() -> Path:
    """جذر المشروع = أب مجلد tools/ حيث يقيم هذا السكريبت (مع بدائل أمان)."""
    try:
        here = Path(__file__).resolve().parent
    except NameError:
        here = Path(sys.argv[0]).resolve().parent if sys.argv[0].endswith(".py") else Path.cwd()
    return here.parent


def parse_cli() -> argparse.Namespace:
    """وسائط السكريبت: بعد "--" عند التشغيل عبر executable بلندر، أو الطبيعية عبر بايثون."""
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="make_calibration_assets.py",
        description="مولد أصول معايرة M0 لـ THE LAST SIN (Blender headless)",
    )
    parser.add_argument("--root", default=None,
                        help="جذر مشروع بديل (افتراضيًا: الأب لمجلد tools/)")
    parser.add_argument("--force", action="store_true",
                        help="السماح باستبدال مخرجات موجودة (حماية افتراضية بدونها)")
    return parser.parse_args(argv)


args = parse_cli()
ROOT = Path(args.root).resolve() if args.root else discover_root()

if not ((ROOT / "README.md").exists() or (ROOT / "docs").is_dir()):
    sys.stderr.write(
        f"\n[TLS-ERROR] المجلد المحدد لا يبدو جذر مشروع THE LAST SIN:\n"
        f"  {ROOT}\n"
        f"الجذر الصحيح يجب أن يحوي README.md أو docs/ (وفيه tools/ و02_Art/).\n"
        f"صحّح المسار عبر:  --root /path/to/THE_LAST_SIN\n"
    )
    sys.exit(2)

SRC_DIR = ROOT / "02_Art" / "blender" / "source" / "env"
FBX_DIR = ROOT / "02_Art" / "exports" / "fbx"
MANIFEST = ROOT / "02_Art" / "exports" / "manifest_calibration.json"

# --------------------------------------------------------------- helpers
def log(msg):
    print(f"[TLS] {msg}", flush=True)


def new_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf and "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    return mat


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # تعطيل ملفات النسخ الاحتياطي .blend1 داخل مستودع نظيف
    try:
        bpy.context.preferences.filepaths.save_version = 0
    except Exception as e:
        log(f"save_version pref note: {e}")
    log("scene cleared (factory empty)")


def make_box(name, location, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    return obj


def select_all(objects, active):
    for o in bpy.data.objects:
        o.select_set(o in objects)
    bpy.context.view_layer.objects.active = active


def finalize_mesh(name, objects):
    """يجمع الكائنات في mesh واحد، يضبط المحور الارتكاز عند نقطة الأصل، ويطبق التحويلات."""
    select_all(objects, active=objects[0])
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def mesh_stats(obj):
    mesh = obj.data
    verts = [list(v.co) for v in mesh.vertices]
    bbox_min = [min(v[i] for v in verts) for i in range(3)]
    bbox_max = [max(v[i] for v in verts) for i in range(3)]
    dims = [round(bbox_max[i] - bbox_min[i], 4) for i in range(3)]
    return {
        "vertices": len(verts),
        "polygons": len(mesh.polygons),
        "material_slots": [s.name for s in mesh.materials if s],
        "dimensions_m": dims,
        "bbox_min": [round(v, 4) for v in bbox_min],
        "bbox_max": [round(v, 4) for v in bbox_max],
    }


def export_fbx(obj, filepath):
    """التصدير المعياري: Forward=-Y / Up=Z / FBX Units Scale (1 م = 100 uu)."""
    select_all([obj], active=obj)
    bpy.ops.export_scene.fbx(
        filepath=str(filepath),
        use_selection=True,
        object_types={"MESH"},
        axis_forward="-Y",
        axis_up="Z",
        apply_scale_options="FBX_SCALE_UNITS",
        global_scale=1.0,
        mesh_smooth_type="OFF",
        bake_space_transform=False,
    )


def fbx_header_info(filepath):
    """قراءة ترويسة FBX الثنائية للتحقق من الصلاحية ورقم الإصدار."""
    with open(filepath, "rb") as f:
        head = f.read(27)
    magic_ok = head.startswith(b"Kaydara FBX Binary")
    version = struct.unpack("<I", head[23:27])[0] if len(head) >= 27 else 0
    return {"magic_ok": magic_ok, "fbx_version": version}

# --------------------------------------------------------------- asset 001
def build_gnomon():
    clear_scene()
    m_base = new_material("TLS_M_Gnomon_Base", (0.15, 0.16, 0.18))
    m_body = new_material("TLS_M_Gnomon_Body", (0.55, 0.55, 0.55))
    m_axis_x = new_material("TLS_M_Gnomon_AxisX", (0.75, 0.08, 0.08))   # أحمر  = +X (أمام Unreal)
    m_axis_y = new_material("TLS_M_Gnomon_AxisY", (0.10, 0.30, 0.80))  # أزرق  = -Y (أمام التأليف في Blender)
    m_axis_z = new_material("TLS_M_Gnomon_AxisZ", (0.85, 0.68, 0.15))  # ذهبي  = +Z (الأعلى)

    parts = []
    # قاعدة قياس 1×1 م (سماكة 2 سم) — للتحقق من المقياس: 100 uu في Unreal
    parts.append(make_box("plate_1m", (0, 0, 0.01), (1.0, 1.0, 0.02), m_base))
    # مكعب 0.5 م فوق القاعدة
    parts.append(make_box("cube_050", (0, 0, 0.27), (0.5, 0.5, 0.5), m_body))
    # سهم +X (أمام Unreal) — أحمر
    parts.append(make_box("arrow_px", (0.55, 0, 0.27), (0.60, 0.08, 0.08), m_axis_x))
    # لوح -Y (أمام التأليف في Blender) — أزرق
    parts.append(make_box("plate_my", (0, -0.26, 0.27), (0.30, 0.02, 0.30), m_axis_y))
    # هرم +Z (الأعلى) — ذهبي
    bpy.ops.mesh.primitive_cone_add(radius1=0.08, radius2=0.0, depth=0.25, location=(0, 0, 0.645))
    spire = bpy.context.active_object
    spire.name = "spire_pz"
    spire.data.materials.append(m_axis_z)
    parts.append(spire)

    obj = finalize_mesh("tls_env_001_calibration_gnomon", parts)
    return obj

# --------------------------------------------------------------- asset 002
def build_reference_figure():
    clear_scene()
    m_skin = new_material("TLS_M_Reference_Body", (0.50, 0.48, 0.45))

    parts = []
    # ساقان: قطر 15 سم، ارتفاع 90 سم (0 -> 0.90)
    for x in (-0.09, 0.09):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.075, depth=0.90, location=(x, 0, 0.45))
        parts.append(bpy.context.active_object)
    # جذع: أسطوانة مضغوطة على Y، من 0.90 إلى 1.50
    bpy.ops.mesh.primitive_cylinder_add(radius=0.17, depth=0.60, location=(0, 0, 1.20))
    torso = bpy.context.active_object
    torso.scale = (1.0, 0.72, 1.0)
    parts.append(torso)
    # ذراعان جانبيتان: من 0.90 إلى 1.48
    for x in (-0.235, 0.235):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.58, location=(x, 0, 1.19))
        parts.append(bpy.context.active_object)
    # رأس: كرة نصف قطرها 12.5 سم، قمتها عند 1.75 م بالضبط
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.125, location=(0, 0, 1.625))
    parts.append(bpy.context.active_object)

    for p in parts:
        p.data.materials.append(m_skin)

    obj = finalize_mesh("tls_env_002_reference_figure", parts)
    return obj

# --------------------------------------------------------------- main
def main():
    started = time.time()
    log(f"project root: {ROOT}")

    # حماية ملفات المستخدم: رفض استبدال مخرجات موجودة إلا بطلب صريح
    targets = [
        SRC_DIR / "tls_env_001_calibration_gnomon.blend",
        SRC_DIR / "tls_env_002_reference_figure.blend",
        FBX_DIR / "tls_env_001_calibration_gnomon_v001.fbx",
        FBX_DIR / "tls_env_002_reference_figure_v001.fbx",
        MANIFEST,
    ]
    existing = [t for t in targets if t.exists()]
    if existing and not args.force:
        sys.stderr.write(
            "\n[TLS-ERROR] مخرجات معايرة موجودة مسبقًا — لن أستبدلها دون طلب صريح:\n"
        )
        for t in existing:
            sys.stderr.write(f"  {t}\n")
        sys.stderr.write(
            "إن أردت إعادة التوليد فوقها أضف الخيار:  --force\n"
            "(للإصدار الجديد بدل الاستبدال، انقل الملفات القديمة يدويًا أولًا.)\n"
        )
        sys.exit(3)
    if existing:
        log(f"--force given: replacing {len(existing)} existing output file(s)")

    # إنشاء مجلدات الإخراج عند غيابها (نسخة نظيفة من المستودع مثلًا)
    for d in (SRC_DIR, FBX_DIR):
        d.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("TLS-ENV-001", build_gnomon),
        ("TLS-ENV-002", build_reference_figure),
    ]
    results = []
    for asset_id, builder in jobs:
        obj = builder()
        stats = mesh_stats(obj)

        blend_path = SRC_DIR / f"{obj.name}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=blend_path.as_posix())

        fbx_path = FBX_DIR / f"{obj.name}_v001.fbx"
        export_fbx(obj, fbx_path)

        entry = {
            "asset_id": asset_id,
            "object_name": obj.name,
            "blend_path": blend_path.relative_to(ROOT).as_posix(),
            "fbx_path": fbx_path.relative_to(ROOT).as_posix(),
            "fbx_info": fbx_header_info(fbx_path),
            "geometry": stats,
        }
        results.append(entry)
        log(f"{asset_id}: {stats['vertices']} verts / {stats['polygons']} polys / "
            f"dims={stats['dimensions_m']} m / fbx v{entry['fbx_info']['fbx_version']}")

    manifest = {
        "project": "THE LAST SIN: The Sin-Eater",
        "stage": "M0 calibration assets (Blender-side)",
        "blender_version": bpy.app.version_string,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_sec": round(time.time() - started, 1),
        "export_settings": {
            "axis_forward": "-Y", "axis_up": "Z",
            "apply_scale_options": "FBX_UNITS_SCALE", "global_scale": 1.0,
            "note": "1 m في Blender = 100 uu في Unreal Engine؛ استيراد UE معلق حتى M0 (لا يوجد UE في هذه البيئة) — وجود FBX لا يعني نجاح الاستيراد",
        },
        "assets": results,
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(f"manifest written: {MANIFEST.relative_to(ROOT).as_posix()}")

    # بوابات قبول ذاتية: الأبعاد المتوقعة
    g, rf = results[0]["geometry"], results[1]["geometry"]
    checks = [
        ("gnomon overall X = 1.35 m (لوح 1.0 + سهم 0.35)", abs(g["dimensions_m"][0] - 1.35) < 0.001),
        ("gnomon Y = 1.00 m (قاعدة القياس)", abs(g["dimensions_m"][1] - 1.00) < 0.001),
        ("gnomon Z = 0.77 m (ارتفاع كلي)", abs(g["dimensions_m"][2] - 0.77) < 0.001),
        ("figure height = 1.75 m", abs(rf["dimensions_m"][2] - 1.75) < 0.001),
        ("both FBX valid binary", all(r["fbx_info"]["magic_ok"] for r in results)),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        log(f"CHECK {'PASS' if ok else 'FAIL'}: {name}")
    if failed:
        log(f"SELF-CHECK FAILED: {failed}")
        sys.exit(1)
    log("ALL SELF-CHECKS PASSED")


if __name__ == "__main__":
    main()
