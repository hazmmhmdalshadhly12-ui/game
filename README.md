# THE LAST SIN: The Sin-Eater — مستودع المشروع
**لعبة مغامرات وتحقيق وغموض تاريخي قوطي | UE5 + Blender | Blackthorne، ويلز 1847**

> الحالة: **المرحلة الأولى (التأسيس والتوثيق) مكتملة** — بتاريخ 22 أكتوبر 2026.
> ⚠️ لم يُبنَ أي إصدار قابل للعب بعد. أول مرحلة قابلة للاختبار هي **M0** (انظر `docs/MILESTONE_PLAN.md`).

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
├── reports/                      ← [موجود] تقارير المراحل (PHASE_1_REPORT.md)
├── tools/                        ← [موجود] أدوات التحقق:
│   ├── validate_project.py       فاحص سلامة المشروع (وثائق+سجل+اتساق)
│   └── make_calibration_assets.py مولد أصول المعايرة (Blender headless)
├── 02_Art/                       ← [موجود جزئيًا — أول أصول فعلية]
│   ├── blender/source/env/       tls_env_001_calibration_gnomon.blend ✅
│   │                             tls_env_002_reference_figure.blend ✅
│   ├── exports/fbx/              ملفا FBX 7.4 سليمان ✅
│   └── exports/manifest_calibration.json  (بيان التحقق الهندسي) ✅
├── 03_Unreal/                    ← [مخطط M0] مشروع UE5 (TLS.uproject)
├── 04_Audio/                     ← [مخطط] الصوتيات
├── 05_Narrative/                 ← [مخطط M2] جداول الحوار والمحاكاة
└── 06_Build/                     ← [مخطط M4] إعدادات بناء المنصات
```

## كيفية التحقق من سلامة المشروع
```bash
python3 tools/validate_project.py
# يجب أن تنتهي بـ: ALL CHECKS PASSED (exit code 0)
```
الفحص يشمل: وجود الوثائق ومقاسها، سلامة سجل الأصول CSV (معرفات فريدة/قيم شرعية)، الاتساق العابر للوثائق (الأسماء المعتمدة)، وسلامة أصول المعايرة المصدرة فعليًا.

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
