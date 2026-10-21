#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN: The Sin-Eater — Project Integrity Validator
=========================================================
فاحص آلي لسلامة مستودع المشروع (يعمل بلا اعتماديات خارجية):
  1) وجود الوثائق المرجعية ومقاسها الأدنى
  2) سلامة docs/ASSET_REGISTRY.csv (ترويسة/معرفات فريدة/قيم شرعية/اعتماديات)
  3) الاتساق العابر للوثائق (الأسماء المعتمدة والإشارات المتبادلة)
  4) سلامة أصول المعايرة المصدرة فعليًا (.blend/.fbx/manifest) وتطابقها مع السجل
  5) نظافة المستودع (لا ملفات .blend1)

الاستخدام:  python3 tools/validate_project.py   → exit 0 عند نجاح كل الفحوص
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # جذر THE_LAST_SIN/

FAILURES = []
CHECKS_RUN = 0


def ok(msg):
    global CHECKS_RUN
    CHECKS_RUN += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    global CHECKS_RUN
    CHECKS_RUN += 1
    print(f"  [FAIL] {msg}")
    FAILURES.append(msg)


def section(title):
    print(f"\n== {title} ==")


def read(p, encoding="utf-8"):
    return ROOT.joinpath(p).read_text(encoding=encoding, errors="replace")


# ------------------------------------------------------------------ 1) الوثائق
section("1) وجود الوثائق المرجعية ومقاسها")

DOCS_MIN_KB = {
    "docs/GAME_BIBLE.md": 12,
    "docs/CHARACTER_REGISTRY.md": 8,
    "docs/WORLD_REGISTRY.md": 5,
    "docs/TECHNICAL_PIPELINE.md": 7,
    "docs/QUEST_ARCHITECTURE.md": 6,
    "docs/NPC_SIMULATION.md": 5,
    "docs/PLATFORM_STRATEGY.md": 5,
    "docs/MILESTONE_PLAN.md": 5,
    "docs/ASSET_REGISTRY.csv": 8,
    "README.md": 2,
    "reports/PHASE_1_REPORT.md": 4,
}
for rel, minkb in DOCS_MIN_KB.items():
    f = ROOT / rel
    if not f.exists():
        fail(f"ملف ناقص: {rel}")
    elif f.stat().st_size < minkb * 1024:
        fail(f"ملف أصغر من الحد الأدنى ({minkb}KB): {rel} — {f.stat().st_size}B")
    else:
        ok(f"{rel} ({f.stat().st_size // 1024}KB)")

# ------------------------------------------------------------------ 2) سجل الأصول CSV
section("2) سلامة سجل الأصول ASSET_REGISTRY.csv")

EXPECTED_HEADER = [
    "AssetID", "Category", "Name", "Description", "Milestone", "Status",
    "Version", "PolyBudget", "LODs", "Materials", "BlenderPath", "UEPath",
    "Dependencies", "VerifyMethod", "Notes",
]
CATEGORIES = {"ENV", "CHR", "PRP", "ANM", "MAT", "TEX", "SND", "UI", "VFX", "SKL"}
MILESTONES = {"M0", "M1", "M2", "M3", "M4", "M5"}
STATUSES = {"PLANNED", "BLOCKOUT", "MODELED", "TEXTURED", "RIGGED", "ANIMATED",
            "EXPORTED", "IMPORTED", "INTEGRATED", "APPROVED", "RETIRED"}
VERIFY = {"CAL-01", "IMP-01", "IMP-02", "IMP-03", "IMP-04", "QG-AUD", "QG-UI"}
ID_RE = re.compile(r"^TLS-[A-Z]{2,3}-\d{3}$")

rows = []
try:
    with ROOT.joinpath("docs/ASSET_REGISTRY.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        if header != EXPECTED_HEADER:
            fail(f"ترويسة CSV غير مطابقة للمعيار: {header}")
        else:
            ok("ترويسة السجل مطابقة للمعيار (15 عمودًا)")
        rows = [r for r in reader if (r.get("AssetID") or "").strip()]
except Exception as e:
    fail(f"تعذر قراءة CSV: {e}")

if len(rows) >= 60:
    ok(f"عدد الأصول المسجلة = {len(rows)} (الحد الأدنى 60)")
else:
    fail(f"عدد الأصول المسجلة {len(rows)} أقل من 60")

ids = [r["AssetID"].strip() for r in rows]
dupes = {i for i in ids if ids.count(i) > 1}
if dupes:
    fail(f"معرفات مكررة: {sorted(dupes)}")
else:
    ok("لا معرفات مكررة")

bad_id = [i for i in ids if not ID_RE.match(i)]
if bad_id:
    fail(f"معرفات خارج النمط TLS-XXX-NNN: {bad_id}")
else:
    ok("كل المعرفات تطابق النمط TLS-XXX-NNN")

bad_cat = [(r["AssetID"], r["Category"]) for r in rows if r["Category"] not in CATEGORIES]
bad_ms = [(r["AssetID"], r["Milestone"]) for r in rows if r["Milestone"] not in MILESTONES]
bad_st = [(r["AssetID"], r["Status"]) for r in rows if r["Status"] not in STATUSES]
bad_vf = [(r["AssetID"], r["VerifyMethod"]) for r in rows if r["VerifyMethod"] not in VERIFY]
bad_bp = [(r["AssetID"], r["BlenderPath"]) for r in rows if not (r["BlenderPath"] or "").strip()]
bad_ue = [(r["AssetID"], r["UEPath"]) for r in rows if not (r["UEPath"] or "").startswith("/Game/")]
for label, bad in [("التصنيف", bad_cat), ("الميلستون", bad_ms), ("الحالة", bad_st),
                   ("طريقة التحقق", bad_vf), ("مسار Blender", bad_bp), ("مسار UE", bad_ue)]:
    if bad:
        fail(f"قيم غير شرعية في عمود {label}: {bad[:5]}")
    else:
        ok(f"عمود {label}: كل القيم شرعية")

idset = set(ids)
bad_deps = []
for r in rows:
    for dep in re.split(r"[;+]", (r["Dependencies"] or "").replace(" ", "")):
        if dep and dep != "none" and dep not in idset and dep != "...":
            bad_deps.append((r["AssetID"], dep))
if bad_deps:
    fail(f"اعتماديات غير مسجلة في السجل: {bad_deps[:5]}")
else:
    ok("كل الاعتماديات تشير إلى أصول مسجلة أو none")

# ------------------------------------------------------------------ 3) الاتساق العابر
section("3) الاتساق العابر للوثائق (الأسماء والإشارات)")

texts = {rel: read(rel) for rel in DOCS_MIN_KB if ROOT.joinpath(rel).exists()}

CROSS = {
    "docs/GAME_BIBLE.md": ["Edmund Vale", "إدموند ڤيل", "Blackthorne", "1847",
                            "Unreal Engine 5", "Blender", "قاموس الأسماء", "حدود نطاق"],
    "docs/CHARACTER_REGISTRY.md": ["إدموند ڤيل", "غويندولين ميريديث", "ماير هيوز",
                                     "سايلاس كرين", "أوسيان هاريس", "أنغاراد", "إليس بريتشارد",
                                     "TLS-CHR-001", "TLS-CHR-020"],
    "docs/WORLD_REGISTRY.md": ["St. Cynog", "الكبش الأسود", "Y Porth", "Afon Ddu",
                                 "Plas Blackthorne", "TLS-ENV-010", "TLS-ENV-101"],
    "docs/TECHNICAL_PIPELINE.md": ["axis_forward", "-Y", "FBX_SCALE_UNITS", "Nanite",
                                     "ORM", "Lumen", "CAL-01", "IMP-01", "TLS-ENV-001",
                                     "TLS-SKL-001", "TLS-MAT-001", "TLS-ANM-001"],
    "docs/QUEST_ARCHITECTURE.md": ["Q-S01", "Q-S02", "Q-S03", "Q-S04", "Q-S05", "Q-S06",
                                    "Q-S07", "Q-S08", "Q-S09", "Q-S10", "Q-S11", "Q-S12",
                                    "FLG_LEDGER_FATE", "E1", "E2", "E3", "E4"],
    "docs/NPC_SIMULATION.md": ["الثقة", "الإشاع", "Tension", "headless", "TLS-CHR-020"],
    "docs/PLATFORM_STRATEGY.md": ["PlayStation Partners", "TRC", "Notarization",
                                   "Metal", "Enhanced Input", "Apple Silicon"],
    "docs/MILESTONE_PLAN.md": ["M0", "M1", "M2", "M3", "M4", "M5",
                                "معايير القبول", "المخاطر", "CAL-01"],
    "README.md": ["validate_project.py", "MILESTONE_PLAN", "ASSET_REGISTRY"],
    "reports/PHASE_1_REPORT.md": ["بيئة العمل", "مسارات", "Blender", "Unreal",
                                   "PlayStation", "M0", "الناقص"],
}
for rel, needles in CROSS.items():
    missing = [n for n in needles if n not in texts.get(rel, "")]
    if missing:
        fail(f"{rel}: كلمات مفتاحية غائبة: {missing}")
    else:
        ok(f"{rel}: الكلمات المفتاحية حاضرة ({len(needles)})")

# إشارات المعرفات بين الوثائق والسجل
for rel, pattern in [("docs/CHARACTER_REGISTRY.md", r"TLS-CHR-\d{3}"),
                      ("docs/WORLD_REGISTRY.md", r"TLS-ENV-\d{3}"),
                      ("docs/TECHNICAL_PIPELINE.md", r"TLS-[A-Z]{3}-\d{3}")]:
    found = set(texts.get(rel, "") and re.findall(pattern, texts.get(rel, "")))
    missing_ids = sorted(i for i in found if i not in idset)
    if missing_ids:
        fail(f"{rel}: معرفات مذكورة وغير مسجلة في CSV: {missing_ids}")
    elif found:
        ok(f"{rel}: {len(found)} معرف أصول مذكور — كلها مسجلة في السجل")

# ------------------------------------------------------------------ 4) أصول المعايرة الفعلية
section("4) أصول المعايرة المصدرة فعليًا (Blender→FBX)")

BLEND1 = ROOT / "02_Art/blender/source/env/tls_env_001_calibration_gnomon.blend"
BLEND2 = ROOT / "02_Art/blender/source/env/tls_env_002_reference_figure.blend"
FBX1 = ROOT / "02_Art/exports/fbx/tls_env_001_calibration_gnomon_v001.fbx"
FBX2 = ROOT / "02_Art/exports/fbx/tls_env_002_reference_figure_v001.fbx"
MANIFEST = ROOT / "02_Art/exports/manifest_calibration.json"

for f, minb in [(BLEND1, 50_000), (BLEND2, 50_000), (FBX1, 10_000), (FBX2, 10_000)]:
    if not f.exists():
        fail(f"أصل معايرة ناقص على القرص: {f.name}")
    elif f.stat().st_size < minb:
        fail(f"أصل معايرة أصغر من المتوقع: {f.name} ({f.stat().st_size}B)")
    else:
        ok(f"{f.name} ({f.stat().st_size // 1024}KB)")

for f in [FBX1, FBX2]:
    if f.exists():
        head = f.read_bytes()[:20]
        if head.startswith(b"Kaydara FBX Binary"):
            ok(f"{f.name}: ترويسة FBX ثنائية سليمة")
        else:
            fail(f"{f.name}: ترويسة FBX غير سليمة: {head!r}")

manifest_ok = False
if MANIFEST.exists():
    try:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest_ok = True
        ok(f"manifest_calibration.json قابل للقراءة (Blender {m.get('blender_version')})")
        by_id = {a["asset_id"]: a for a in m.get("assets", [])}
        g = by_id.get("TLS-ENV-001", {}).get("geometry", {})
        r = by_id.get("TLS-ENV-002", {}).get("geometry", {})
        if abs(r.get("dimensions_m", [0, 0, 0])[2] - 1.75) < 0.001:
            ok("الشخصية المرجعية بارتفاع 1.75 م بالضبط (من الملف الفعلي)")
        else:
            fail(f"ارتفاع الشخصية المرجعية خاطئ: {r.get('dimensions_m')}")
        if abs(g.get("dimensions_m", [0, 0, 0])[1] - 1.00) < 0.001:
            ok("قاعدة gnomon بعمق 1.00 م (من الملف الفعلي)")
        else:
            fail(f"قاعدة gnomon خاطئة: {g.get('dimensions_m')}")
        if all(a["fbx_info"]["magic_ok"] for a in m.get("assets", [])):
            ok("كل ملفات FBX سليمة الترويسة (fbx_version=7400)")
        else:
            fail("FBX غير سليم في الملف")
    except Exception as e:
        fail(f"manifest غير قابل للتحليل: {e}")
else:
    fail("manifest_calibration.json ناقص")

# تطابق حالة السجل مع واقع القرص
if rows:
    st = {r["AssetID"]: r["Status"] for r in rows}
    for aid, expected in [("TLS-ENV-001", "EXPORTED"), ("TLS-ENV-002", "EXPORTED")]:
        if st.get(aid) != expected:
            fail(f"حالة {aid} في السجل = {st.get(aid)} بينما الملف موجود فعليًا — يجب EXPORTED")
        else:
            ok(f"حالة {aid} في السجل متطابقة مع واقع القرص (EXPORTED)")
    exported_count = sum(1 for r in rows if r["Status"] == "EXPORTED")
    ok(f"توزيع الحالات: EXPORTED={exported_count} / PLANNED={len(rows) - exported_count} (صدق الحالة)")

# ------------------------------------------------------------------ 5) نظافة المستودع
section("5) نظافة المستودع")

blend1s = list(ROOT.rglob("*.blend1")) + list(ROOT.rglob("*.blend~"))
if blend1s:
    fail(f"ملفات نسخ احتياطية غير مرغوبة: {[str(p.relative_to(ROOT)) for p in blend1s]}")
else:
    ok("لا ملفات .blend1/.blend~ (مستودع نظيف)")

# ------------------------------------------------------------------ الخلاصة
print("\n" + "=" * 56)
if FAILURES:
    print(f"النتيجة النهائية: FAILED — {len(FAILURES)} فحص فاشل من أصل {CHECKS_RUN}")
    for fl in FAILURES:
        print(f"  - {fl}")
    sys.exit(1)
print(f"النتيجة النهائية: ALL CHECKS PASSED ({CHECKS_RUN}/{CHECKS_RUN})")
sys.exit(0)
