#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE LAST SIN: The Sin-Eater — Project Integrity Validator (v2)
=========================================================
فاحص آلي لسلامة مستودع المشروع (يعمل بلا اعتماديات خارجية):
  1) وجود الوثائق المرجعية ومقاسها الأدنى
  2) سلامة docs/ASSET_REGISTRY.csv (ترويسة/معرفات فريدة/قيم شرعية/اعتماديات)
     + مطابقة الأعداد المذكورة في الوثائق للعدد الفعلي (لا أرقام ثابتة قابلة للتقادم)
  3) الاتساق العابر للوثائق (الأسماء المعتمدة والإشارات المتبادلة)
  4) الاتساق الزمني والأعمار (جوسيا/إدموند/سنوات القصة/ترقيم الأيام والفصول)
  5) صدق حالة الأصول: المخطط PLANNED لا ملف له على القرص، وما بعده له ملف فعلي
     — ووجود FBX لا يُعد دليلاً على استيراده داخل Unreal Engine
  6) سلامة أصول المعايرة المصدرة فعليًا (.blend/.fbx/manifest) وتطابقها مع السجل
  7) نظافة المستودع (لا ملفات .blend1)

الاستخدام:  python3 tools/validate_project.py   → exit 0 عند نجاح كل الفحوص
كل رسالة فشل تذكر الملف المتأثر.
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # جذر THE_LAST_SIN/

FAILURES = []
CHECKS_RUN = 0

# ------------------------------------------------------------------ أساسيات
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
    "reports/PHASE_1_AUDIT.md": 3,
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
COUNT_FLOOR = 60  # حد أدنى لصحة السجل (ليس عددًا متوقعًا — العدد الفعلي يُقارن بالوثائق أدناه)

rows = []
try:
    with ROOT.joinpath("docs/ASSET_REGISTRY.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        if header != EXPECTED_HEADER:
            fail(f"ترويسة CSV غير مطابقة للمعيار في docs/ASSET_REGISTRY.csv: {header}")
        else:
            ok("ترويسة السجل مطابقة للمعيار (15 عمودًا)")
        rows = [r for r in reader if (r.get("AssetID") or "").strip()]
except Exception as e:
    fail(f"تعذر قراءة docs/ASSET_REGISTRY.csv: {e}")

ASSET_COUNT = len(rows)
if ASSET_COUNT >= COUNT_FLOOR:
    ok(f"عدد الأصول المسجلة فعليًا = {ASSET_COUNT} (الحد الأدنى لصحة السجل {COUNT_FLOOR})")
else:
    fail(f"عدد الأصول المسجلة {ASSET_COUNT} أقل من الحد الأدنى {COUNT_FLOOR} (docs/ASSET_REGISTRY.csv)")

ids = [r["AssetID"].strip() for r in rows]
dupes = {i for i in ids if ids.count(i) > 1}
if dupes:
    fail(f"معرفات مكررة في docs/ASSET_REGISTRY.csv: {sorted(dupes)}")
else:
    ok("لا معرفات مكررة")

bad_id = [i for i in ids if not ID_RE.match(i)]
if bad_id:
    fail(f"معرفات خارج النمط TLS-XXX-NNN في docs/ASSET_REGISTRY.csv: {bad_id}")
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
        fail(f"قيم غير شرعية في عمود {label} (docs/ASSET_REGISTRY.csv): {bad[:5]}")
    else:
        ok(f"عمود {label}: كل القيم شرعية")

idset = set(ids)
bad_deps = []
for r in rows:
    for dep in re.split(r"[;+]", (r["Dependencies"] or "").replace(" ", "")):
        if dep and dep != "none" and dep not in idset and dep != "...":
            bad_deps.append((r["AssetID"], dep))
if bad_deps:
    fail(f"اعتماديات غير مسجلة في السجل (docs/ASSET_REGISTRY.csv): {bad_deps[:5]}")
else:
    ok("كل الاعتماديات تشير إلى أصول مسجلة أو none")

# مطابقة الأعداد المذكورة في الوثائق مع العدد الفعلي (لا أرقام ثابتة)
DOC_COUNT_CLAIMS = {
    "README.md": [r"(\d+)\s*أصلًا مسجلًا"],
    "reports/PHASE_1_REPORT.md": [r"(\d+)\s*أصلًا مسجل"],
    "docs/GAME_BIBLE.md": [r"المسجل حاليًا:\s*(\d+)"],
}
for rel, patterns in DOC_COUNT_CLAIMS.items():
    claims = []
    try:
        text = read(rel)
        for pat in patterns:
            claims += [int(m) for m in re.findall(pat, text)]
    except Exception as e:
        fail(f"تعذر قراءة {rel} لمطابقة عدد الأصول: {e}")
        continue
    wrong = [c for c in claims if c != ASSET_COUNT]
    if not claims:
        fail(f"{rel}: لا يوجد ذكر قابل للفحص لعدد الأصول المسجلة (أُضف عبارة صريحة مثل: {ASSET_COUNT} أصلًا مسجلًا)")
    elif wrong:
        fail(f"{rel}: عدد أصول مذكور لا يطابق السجل الفعلي ({ASSET_COUNT}): {wrong}")
    else:
        ok(f"{rel}: كل الأعداد المذكورة للأصول تطابق السجل الفعلي ({ASSET_COUNT})")

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
    "reports/PHASE_1_AUDIT.md": ["تصحيح", "التحقق", "M0"],
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
        fail(f"{rel}: معرفات مذكورة وغير مسجلة في docs/ASSET_REGISTRY.csv: {missing_ids}")
    elif found:
        ok(f"{rel}: {len(found)} معرف أصول مذكور — كلها مسجلة في السجل")

# ------------------------------------------------------------------ 4) الاتساق الزمني والأعمار
section("4) الاتساق الزمني والأعمار (حقائق قانونية من إنجيل اللعبة)")

# سنوات القصة القانونية (ثوابت سردية لا أرقام إحصائية قابلة للتقادم)
# 1830 موثقة في سجل الشخصيات (قائمة الفلاشباكات)؛ الإنجيل يوثقها ضمنيًا بـ"سبعة عشر عامًا"
STORY_PRESENT = 1847
FLASHBACK_1839 = 1839
FLASHBACK_1830 = 1830

bible = texts.get("docs/GAME_BIBLE.md", "")
chrreg = texts.get("docs/CHARACTER_REGISTRY.md", "")

for y, label, where, txt in [
    (STORY_PRESENT, "سنة الحاضر", "docs/GAME_BIBLE.md", bible),
    (FLASHBACK_1839, "سنة الغرق", "docs/GAME_BIBLE.md", bible),
    (FLASHBACK_1839, "سنة الغرق (فلاشباك)", "docs/CHARACTER_REGISTRY.md", chrreg),
    (FLASHBACK_1830, "سنة الفلاشباك الأول", "docs/CHARACTER_REGISTRY.md", chrreg),
    (STORY_PRESENT, "سنة أيام جوسيا الأخيرة", "docs/CHARACTER_REGISTRY.md", chrreg),
]:
    if str(y) in txt:
        ok(f"{where}: {label} {y} حاضرة")
    else:
        fail(f"{where}: {label} {y} غائبة — اختلال قانوني")

# عمر جوسيا: †N في الإنجيل هو المصدر، ويجب أن يتطابق في سجل الشخصيات وCSV والفلاشباكات
josiah_gb = [int(m) for m in re.findall(r"جوسيا ڤيل \(†(\d+)\)", bible)]
josiah_cr = [int(m) for m in re.findall(r"— الأب المتوفى، †(\d+)", chrreg)]
if len(set(josiah_gb)) == 1 and josiah_gb:
    JOSIAH_AGE = josiah_gb[0]
    if josiah_cr == josiah_gb:
        ok(f"عمر وفاة جوسيا متطابق بين GAME_BIBLE وCHARACTER_REGISTRY (†{JOSIAH_AGE})")
    else:
        fail(f"docs/CHARACTER_REGISTRY.md: عمر وفاة جوسيا †{josiah_cr} لا يطابق إنجيل اللعبة †{josiah_gb}")
else:
    JOSIAH_AGE = None
    fail(f"docs/GAME_BIBLE.md: تعذر استخراج عمر وفاة جوسيا †N بشكل قاطع: {josiah_gb}")

row_by_id = {r["AssetID"]: r for r in rows}
if JOSIAH_AGE:
    d2 = row_by_id.get("TLS-CHR-002", {}).get("Description", "")
    if f"{JOSIAH_AGE} عامًا وقت الوفاة" in d2:
        ok(f"docs/ASSET_REGISTRY.csv TLS-CHR-002: عمر الوفاة {JOSIAH_AGE} متطابق مع الإنجيل")
    else:
        fail(f"docs/ASSET_REGISTRY.csv TLS-CHR-002: وصف العمر ({d2}) لا يطابق †{JOSIAH_AGE} من الإنجيل")
    expected_1839 = JOSIAH_AGE - (STORY_PRESENT - FLASHBACK_1839)
    d102 = row_by_id.get("TLS-CHR-102", {}).get("Description", "")
    m102 = re.search(r"\((\d+) عامًا", d102)
    if m102 and int(m102.group(1)) == expected_1839:
        ok(f"docs/ASSET_REGISTRY.csv TLS-CHR-102: عمر فلاشباك 1839 ({expected_1839}) متسق حسابيًا مع †{JOSIAH_AGE}")
    elif m102:
        fail(f"docs/ASSET_REGISTRY.csv TLS-CHR-102: عمر فلاشباك 1839 = {m102.group(1)} "
             f"بينما المتسق مع †{JOSIAH_AGE} هو {expected_1839} (1847−1839={STORY_PRESENT - FLASHBACK_1839})")
    else:
        fail(f"docs/ASSET_REGISTRY.csv TLS-CHR-102: لا عمر قابل للفحص في الوصف: {d102}")

# عمر إدموند 29 (قانون السرد) حاضر ومتطابق في الوثيقتين
ed_gb = "29 عامًا" in bible
ed_cr = "29 عامًا" in chrreg
if ed_gb and ed_cr:
    ok("عمر إدموند (29) حاضر ومتطابق في GAME_BIBLE وCHARACTER_REGISTRY")
else:
    where = [n for n, p in [("docs/GAME_BIBLE.md", ed_gb), ("docs/CHARACTER_REGISTRY.md", ed_cr)] if not p]
    fail(f"عمر إدموند 29 غائب أو متغير في: {where}")

# فجوة السبعة عشر عامًا (1847−1830=17): ذكر نصي + حساب صحيح
if "سبعة عشر عامًا" in bible and (STORY_PRESENT - FLASHBACK_1830) == 17:
    ok("فجوة الانقطاع (سبعة عشر عامًا) متسقة حسابيًا مع 1847−1830")
else:
    fail("docs/GAME_BIBLE.md: فجوة السبعة عشر عامًا غائبة أو غير متسقة مع 1847−1830")

# ترقيم الأيام: 0..9 في الإنجيل، وتطابق جدول الفصول في وثيقة المهام
days_gb = set()
for m in re.finditer(r"اليوم (\d+)(?:–(\d+))?", bible):
    days_gb.add(int(m.group(1)))
    if m.group(2):
        days_gb.add(int(m.group(2)))
if days_gb == set(range(0, 10)):
    ok("docs/GAME_BIBLE.md: ترقيم الأيام كامل ومتسق (اليوم 0..9)")
else:
    fail(f"docs/GAME_BIBLE.md: ترقيم الأيام غير كامل أو شاذ: {sorted(days_gb)} (المتوقع 0..9)")

quest = texts.get("docs/QUEST_ARCHITECTURE.md", "")
chapters = {}
for m in re.finditer(r"\|\s*(C\d|P0)\s*\|\s*(\d+)(?:–(\d+))?\s*\|", quest):
    cid, d1, d2 = m.group(1), int(m.group(2)), m.group(3)
    chapters[cid] = (d1, int(d2) if d2 else d1)
expected_map = {"P0": (0, 0), "C1": (1, 1), "C2": (2, 2), "C3": (3, 3),
                "C4": (4, 4), "C5": (5, 5), "C6": (6, 6), "C7": (7, 8)}
if chapters == expected_map:
    ok("docs/QUEST_ARCHITECTURE.md: جدول الفصول P0,C1..C7 يطابق أيام الإنجيل (0..8)")
else:
    fail(f"docs/QUEST_ARCHITECTURE.md: جدول الفصول/الأيام {chapters} لا يطابق المتوقع {expected_map}")
if re.search(r"\|\s*—\s*\|\s*9\s*\|", quest):
    ok("docs/QUEST_ARCHITECTURE.md: الخاتمة في اليوم 9 مطابقة للإنجيل")
else:
    fail("docs/QUEST_ARCHITECTURE.md: صف الخاتمة (اليوم 9) غير موجود بصيغة متطابقة")

# كل إشارات "اليوم N" في الوثائق داخل المدى 0..9
day_refs_bad = []
for rel in ["docs/CHARACTER_REGISTRY.md", "docs/WORLD_REGISTRY.md",
            "docs/QUEST_ARCHITECTURE.md", "docs/ASSET_REGISTRY.csv"]:
    for m in re.finditer(r"اليوم (\d+)", texts.get(rel, "")):
        if not (0 <= int(m.group(1)) <= 9):
            day_refs_bad.append((rel, m.group(1)))
if day_refs_bad:
    fail(f"إشارات أيام خارج المدى 0..9: {day_refs_bad[:5]}")
else:
    ok("كل إشارات اليوم N في سجلات الشخصيات/العالم/المهام/الأصول داخل نطاق 0..9")

# ------------------------------------------------------------------ 5) صدق حالة الأصول
section("5) صدق الحالة: المخطط مقابل الموجود فعلًا (وجود FBX ≠ استيراد UE)")

UE_PROJECT_DIR = ROOT / "03_Unreal"
EXISTING_STATUSES = {"BLOCKOUT", "MODELED", "TEXTURED", "RIGGED", "ANIMATED", "EXPORTED",
                     "IMPORTED", "INTEGRATED", "APPROVED"}

planned_with_file = []
claimed_missing_file = []
for r in rows:
    bp = (r["BlenderPath"] or "").strip()
    f = ROOT / bp if bp else None
    if r["Status"] == "PLANNED":
        if f and f.exists():
            planned_with_file.append((r["AssetID"], bp))
    elif r["Status"] in EXISTING_STATUSES:
        if not (f and f.exists()):
            claimed_missing_file.append((r["AssetID"], r["Status"], bp))

if planned_with_file:
    fail(f"أصول حالتها PLANNED لكن لها ملفات موجودة فعلًا على القرص (حدّث الحالة): {planned_with_file[:5]}")
else:
    ok(f"كل الأصول PLANNED ({sum(1 for r in rows if r['Status'] == 'PLANNED')}) بلا ملفات وهمية على القرص")

if claimed_missing_file:
    fail(f"أصول حالتها تتجاوز PLANNED دون ملف فعلي على القرص: {claimed_missing_file[:5]}")
else:
    exported = [r for r in rows if r["Status"] == "EXPORTED"]
    ok(f"كل أصل بحالة موجودة (EXPORTED={len(exported)}) له ملف فعلي مطابق لمساره في السجل")

# حالات ما بعد التصدير تتطلب دليل UE فعليًا — وجود FBX وحده لا يكفي
post_ue = [(r["AssetID"], r["Status"]) for r in rows
           if r["Status"] in {"IMPORTED", "INTEGRATED", "APPROVED"}]
if post_ue:
    if UE_PROJECT_DIR.exists() and any(UE_PROJECT_DIR.glob("*.uproject")):
        ok(f"حالات ما بعد الاستيراد {post_ue} مدعومة بوجود مشروع UE فعلي (03_Unreal/*.uproject)")
    else:
        fail(f"أصول حالتها تستلزم استيراد UE لكن لا يوجد مشروع UE (03_Unreal/*.uproject غائب) — "
             f"وجود FBX ليس دليلاً على الاستيراد: {post_ue}")
else:
    ok("لا ادعاءات استيراد/تكامل UE في السجل (صادق: وجود FBX = تصدير Blender ناجح فقط، والاستيراد معلق حتى M0)")

# ------------------------------------------------------------------ 6) أصول المعايرة الفعلية
section("6) أصول المعايرة المصدرة فعليًا (Blender→FBX) — المسارات مشتقة من السجل")

# مشتق من CSV لا من مسارات مكتوبة يدويًا: أصل EXPORTED يجب أن يملك .blend و.fbx سليمي الترويسة
cal_checked = 0
for r in rows:
    if r["Status"] != "EXPORTED":
        continue
    cal_checked += 1
    bp = ROOT / r["BlenderPath"]
    stem = bp.stem
    fbx = ROOT / "02_Art" / "exports" / "fbx" / f"{stem}_v001.fbx"
    if not bp.exists():
        fail(f"{r['AssetID']}: ملف المصدر مفقود رغم حالة EXPORTED — {r['BlenderPath']}")
        continue
    if bp.stat().st_size < 50_000:
        fail(f"{r['AssetID']}: ملف المصدر أصغر من المتوقع — {r['BlenderPath']} ({bp.stat().st_size}B)")
    else:
        ok(f"{r['AssetID']}: {r['BlenderPath']} ({bp.stat().st_size // 1024}KB)")
    if not fbx.exists():
        fail(f"{r['AssetID']}: ملف FBX مفقود رغم حالة EXPORTED — 02_Art/exports/fbx/{stem}_v001.fbx")
        continue
    head = fbx.read_bytes()[:20]
    if head.startswith(b"Kaydara FBX Binary"):
        ok(f"{r['AssetID']}: 02_Art/exports/fbx/{stem}_v001.fbx — ترويسة FBX ثنائية سليمة "
           f"(تصدير Blender ناجح؛ الاستيراد داخل UE لم يُنفذ بعد)")
    else:
        fail(f"{r['AssetID']}: ترويسة FBX غير سليمة في 02_Art/exports/fbx/{stem}_v001.fbx: {head!r}")
if cal_checked == 0:
    fail("لا توجد أصول بحالة EXPORTED للتحقق الفعلي من القرص")

MANIFEST = ROOT / "02_Art" / "exports" / "manifest_calibration.json"
if MANIFEST.exists():
    try:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        ok(f"02_Art/exports/manifest_calibration.json قابل للقراءة (Blender {m.get('blender_version')})")
        by_id = {a["asset_id"]: a for a in m.get("assets", [])}
        g = by_id.get("TLS-ENV-001", {}).get("geometry", {})
        rf = by_id.get("TLS-ENV-002", {}).get("geometry", {})
        if abs(rf.get("dimensions_m", [0, 0, 0])[2] - 1.75) < 0.001:
            ok("الشخصية المرجعية بارتفاع 1.75 م بالضبط (من الملف الفعلي)")
        else:
            fail(f"ارتفاع الشخصية المرجعية خاطئ في manifest_calibration.json: {rf.get('dimensions_m')}")
        if abs(g.get("dimensions_m", [0, 0, 0])[1] - 1.00) < 0.001:
            ok("قاعدة gnomon بعمق 1.00 م (من الملف الفعلي)")
        else:
            fail(f"قاعدة gnomon خاطئة في manifest_calibration.json: {g.get('dimensions_m')}")
        if all(a["fbx_info"]["magic_ok"] for a in m.get("assets", [])):
            ok("كل ملفات FBX سليمة الترويسة وفق البيان (تصدير Blender فقط — لا يثبت استيراد UE)")
        else:
            fail("FBX غير سليم وفق manifest_calibration.json")
        # مطابقة معرفات البيان مع السجل
        man_ids = {a["asset_id"] for a in m.get("assets", [])}
        exp_ids = {r["AssetID"] for r in rows if r["Status"] == "EXPORTED"}
        if man_ids == exp_ids:
            ok("معرفات البيان مطابقة تمامًا للأصول EXPORTED في السجل")
        else:
            fail(f"معرفات البيان {sorted(man_ids)} لا تطابق حالات EXPORTED في السجل {sorted(exp_ids)}")
    except Exception as e:
        fail(f"02_Art/exports/manifest_calibration.json غير قابل للتحليل: {e}")
else:
    fail("02_Art/exports/manifest_calibration.json ناقص")

# توزيع الحالات للصدق الإحصائي
if rows:
    from collections import Counter
    dist = Counter(r["Status"] for r in rows)
    ok("توزيع الحالات: " + ", ".join(f"{k}={v}" for k, v in sorted(dist.items())))

# ------------------------------------------------------------------ 7) نظافة المستودع
section("7) نظافة المستودع")

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
