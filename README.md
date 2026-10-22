# THE LAST SIN: The Sin-Eater — مستودع المشروع
**لعبة مغامرات وتحقيق وغموض تاريخي قوطي | UE5 + Blender | Blackthorne، ويلز 1847**

> الحالة: **M0 منفذ + M1 "شريحة اليوم الأول في بلاكثورن" مبنية ومنطقها مُختبر فعليًا، وطبقة UE خضعت لمراجعة ثابتة أُغلقت فيها عيوب الترجمة المكتشفة** — 23 أكتوبر 2026.
> **منطق اللعبة كامل يعمل واختُبر فعليًا في بيئة التطوير**: نواة C++ خالصة (`03_Unreal/Source/TLS/Core/`) تُترجم وتُختبر بـ g++ — **418/418 فحصًا** تشمل محاكاة لعب كاملة ليومَي الشريحة (C1 + افتتاحية C2) واختبار حفظ/تحميل مستقر بايت-بايت — نفس الكود يُترجم داخل وحدة UE.
> بيانات اللعب (16 دليلًا، مهام، 5 حوارات، 12 خلفية بجداول، تخطيط القرية) في `05_Narrative/` بصيغة JSON موثقة ومفحوصة (29/29).
> ⚠️ **تجميع UE وتشغيله المرئي يتطلبان محطة Windows** (خطوات مؤتمتة جاهزة 01→04 — مُصلحة ومعززة بفحوص انحدار) — لا ادعاء تشغيل مرئي قبل تنفيذها (انظر `reports/M1_SLICE_REPORT.md`).

## بنية المستودع — ما هو موجود فعلًا الآن مقابل ما هو مخطط
```
THE_LAST_SIN/
├── README.md                     ← [موجود] هذا الملف
├── docs/                         ← [موجود] الوثائق المرجعية التسع:
│   ├── GAME_BIBLE.md             وثيقة اللعبة الأم (القصة/العالم/الأسلوب/النطاق)
│   ├── CHARACTER_REGISTRY.md     سجل الشخصيات (T1–T4) والعلاقات والمعرفة
│   ├── WORLD_REGISTRY.md         سجل المناطق والمباني والمعالم
│   ├── ASSET_REGISTRY.csv        السجل المركزي للأصول (80 أصلًا مسجلًا)
│   ├── TECHNICAL_PIPELINE.md     خط الإنتاج Blender←UE5 (معايير وإعدادات معتمدة)
│   ├── QUEST_ARCHITECTURE.md     بنية المهام والأدلة والحوار والنهايات
│   ├── NPC_SIMULATION.md         محاكاة حياة القرية (جداول/إشاعات/ثقة)
│   ├── PLATFORM_STRATEGY.md      خطة Windows/macOS/PlayStation
│   └── MILESTONE_PLAN.md         خطة M0..M5 والاعتماديات والمخاطر
├── reports/                      ← [موجود] تقارير المراحل (PHASE_1_REPORT.md + PHASE_1_AUDIT.md + M0_IMPLEMENTATION_REPORT.md)
├── .github/workflows/            ← [موجود] CI: فاحصا المشروع يُشغلان على كل push (GitHub Actions)
├── tools/                        ← [موجود] أدوات التحقق:
│   ├── validate_project.py       فاحص سلامة المشروع (68 فحصًا — وثائق+سجل+اتساق)
│   ├── make_calibration_assets.py مولد أصول المعايرة (Blender headless)
│   ├── test_fbx_roundtrip.py     اختبار FBX ذهابًا وإيابًا (bpy)
│   └── validate_unreal_scaffold.py فاحص هيكل مشروع UE (39 فحصًا)
├── 02_Art/                       ← [موجود جزئيًا — أول أصول فعلية]
│   ├── blender/source/env/       tls_env_001_calibration_gnomon.blend ✅
│   │                             tls_env_002_reference_figure.blend ✅
│   ├── exports/fbx/              ملفا FBX 7.4 سليمان ✅
│   └── exports/manifest_calibration.json  (بيان التحقق الهندسي) ✅
├── 03_Unreal/                    ← [موجود — M0+M1] مشروع UE5: Core/ (نواة C++ خالصة مزدوجة الترجمة) +
│   │                             وضع القرية TLSVillageGameMode + NPC/تفاعلات/واجهات UMG بالكود +
│   │                             SaveGame + صوت إجرائي + أتمتة Windows (01..04 .bat)
├── 04_Audio/                     ← [موجود] أصوات placeholder مولّدة إجرائيًا (موثقة كذلك) + بيان
├── 05_Narrative/                 ← [موجود — M1] بيانات اللعب JSON: أدلة/استنتاجات/مهام/
│                                 حوارات/محاكاة/تخطيط العالم — مصدر الحقيقة للطرفين (g++ وUE)
└── 06_Build/                     ← [مخطط M4] إعدادات بناء المنصات
```

## كيفية التحقق من سلامة المشروع
```bash
python3 tools/validate_project.py            # 73/73 — الوثائق + السجل + الاتساق + خط الفن والصوت
python3 tools/validate_unreal_scaffold.py   # 70/70 — هيكل UE (M0+M1) + نقاء النواة من تبعيات UE + فحوص انحدار السكريبتات وطبقة UE
python3 tools/validate_narrative.py         # 29/29 — بيانات 05_Narrative ومرجعيتها المتقاطعة
tools/core_tests/run_core_tests.sh          # 418/418 — ترجمة g++ وتشغيل منطق اللعبة فعليًا
```
الفحص الأخير **يرجم نفس ملفات C++ التي تُترجم داخل وحدة UE** ويشغّلها: محاكاة لعب كاملة (جنازة اليوم 1 → لوحة السجل → نوم → جريمة الطاحونة في اليوم 2)، قاعدة المسارات الثلاثة لكل حقيقة كبرى، واختبار ذهاب-وإياب الحفظ بايت-بايت. الربعة مجتمعة تعمل في CI على كل push (GitHub Actions).

## إعادة توليد أصول المعايرة (يتطلب Blender — وحدة bpy)
جذر المشروع يُكتشف تلقائيًا من موقع السكريبت (`tools/`)؛ للتحديد اليدوي: `--root <مسار>`.
السكريبت **يرفض استبدال مخرجات موجودة** حمايةً لملفاتك — أضف `--force` لإعادة التوليد فوقها.
عند غياب Blender/bpy يخرج برسالة خطأ واضحة (كود 2) تشرح خياري التثبيت.

**Linux/macOS (مُختبر فعليًا في بيئة المرحلة الأولى — bpy 5.0.1 على Python 3.11):**
```bash
# عبر Blender المثبت:
blender --background --python tools/make_calibration_assets.py
# أو عبر حزمة bpy (يفضل Python 3.11):
python3 tools/make_calibration_assets.py
# ينتج: ملفي .blend + ملفي FBX + manifest_calibration.json
```

**Windows (لم يُختبر بعد — أول تشغيل مخطط ضمن بوابة M0):**
```powershell
# المتطلبات: Blender 4.x/5.x مثبت ومضاف إلى PATH (أو وحدة bpy متوافقة مع Python 3.11)
blender --background --python tools/make_calibration_assets.py
# أو بمسار تثبيت صريح وجذر بديل:
& "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --background --python tools/make_calibration_assets.py -- --root D:\Projects\THE_LAST_SIN
```
> ⚠️ صيغة Windows أعلاه مماثلة منطقيًا للنمط المُختبر لكنها **غير مُتحقق منها في بيئة Windows**؛ لا تُعتبر ناجحة إلا بعد أول تشغيل موثق داخل M0.

## مبادئ العمل في هذا المستودع
1. **لا نمذجة بلا سجل:** كل أصل جديد يدخل `docs/ASSET_REGISTRY.csv` قبل فتح ملفه.
2. **قاموس الأسماء** في `docs/GAME_BIBLE.md` §10 هو مصدر الحقيقة للكتابة.
3. **لا إنتاج جماعي للأصول** قبل اعتماد M0 (بوابة CAL-01 داخل UE).
4. كل المخرجات أصلية 100% — سياسة الأصالة في `docs/GAME_BIBLE.md` §11.
5. تُرفض أي إضافة UE/Blender غير مدعومة على المنصات الثلاث (انظر `docs/PLATFORM_STRATEGY.md` §7).
