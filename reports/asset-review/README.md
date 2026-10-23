# M3.3 — فحص الأصول والشخصيات الفعلية ورندرها — THE LAST SIN: The Sin-Eater

> التاريخ: 2026-10-23 · الفرع: `feature/m3-3-asset-review` · الأساس: main @ `7c3d39b`
> التنفيذ الفعلي: Blender **5.0.1** headless (نفس الإصدار الذي أنتج الأصول) على Linux بدون GPU — رندر CPU عبر Cycles.

## ما فعلته هذه المراجعة

فحصت المستودع بالكامل (116 ملفًا متتبعًا) بحثًا عن أصول ثلاثية الأبعاد وخامات وصور، ثم فتحت كل أصل ثلاثي الأبعاد موجود فعليًا في Blender، وقيسحت محتواه الحقيقي (هندسة/خامات/كاميرات/إضاءة/سلامة الشبكة)، ثم أنتجت **12 رندر حقيقي** من هذه الملفات نفسها دون أي تعديل على الأصول (تحقق checksums قبل/بعد).

## الأرقام الحقيقية

| البند | العدد |
|---|---|
| أصول 3D موجودة فعلًا كملفات (`.blend` + `.fbx`) | **4 ملفات = أصلا معايرة اثنان** (TLS-ENV-001، TLS-ENV-002) |
| أمكن فتحه ورندره بنجاح | **2/2** (12 صورة: 11 من الأصول + 1 تكوين مشهد) |
| خامات/textures/صور في المستودع | **0** |
| شخصيات لعب حقيقية (Edmund، Gwendolyn، Crane…) | **0** (كلها PLANNED في السجل بلا ملفات) |
| بيئات قرية Blackthorne كنماذج 3D | **0** (القرية تُبنى runtime داخل UE من بيانات — لا ملفات نماذج) |
| ملفات `.uasset`/`.umap`/`Content/` | **0** |
| أصول صوتية (placeholder مولدة إجرائيًا) | 5 ملفات WAV |
| صفوف سجل الأصول `ASSET_REGISTRY.csv` | 80: ‏5 EXPORTED / 75 PLANNED بلا ملفات |

## الصور (اضغطي لعرضها داخل GitHub)

### الشخصية المرجعية TLS-ENV-002 (1.75 م — معايرة مقياس، ليست شخصية لعب)
![figure front](renders/characters/character_tls_env_002_reference_figure_front.png)
![figure side](renders/characters/character_tls_env_002_reference_figure_side.png)
![figure back](renders/characters/character_tls_env_002_reference_figure_back.png)
![figure face](renders/characters/character_tls_env_002_reference_figure_face.png)
![figure three_quarter](renders/characters/character_tls_env_002_reference_figure_three_quarter.png)
![figure fbx import](renders/characters/character_tls_env_002_reference_figure_fbx_import_front.png)

### جسم المعايرة TLS-ENV-001 (Gnomon — اختبار المحاور والمقياس)
![gnomon front](renders/props/prop_tls_env_001_calibration_gnomon_front.png)
![gnomon side](renders/props/prop_tls_env_001_calibration_gnomon_side.png)
![gnomon top](renders/props/prop_tls_env_001_calibration_gnomon_top.png)
![gnomon three_quarter](renders/props/prop_tls_env_001_calibration_gnomon_three_quarter.png)
![gnomon fbx import](renders/props/prop_tls_env_001_calibration_gnomon_fbx_import_front.png)

### تكوين مشهد المعايرة (عرض مؤقت من الأصلين الحقيقيين بمقياس 1:1 — ليس مشهد لعبة)
![calibration scene](renders/scenes/scene_calibration_setup_16x9.png)

## الخلاصة الفنية باختصار

- الأصلان الموجودان **سليمان هندسيًا** (0 رؤوس شاردة، 0 حواف غير متجانسة، pivot عند الأصل، أبعاد مطابقة للعقد CAL-01) و**FBX يفتح ويحمل الهندسة والخامات كاملة** — مناسبان لغرضهما كأصول معايرة.
- هما **ليسا** شخصيات أو بيئات لعب: الشخصية المرجعية كرة رأس بلا ملامح وأطراف أسطوانية، والخامات ألوان مسطحة بلا أي textures (نسيج UV موجود لكن غير مستخدم).
- كل ما هو فني في اللعبة الفعلية (25 شخصية، 20 بيئة، 8 props، 9 مواد، 8 أنيميشن…) **غير موجود بعد** — سجل الأصول يصفه بحالة PLANNED v000.
- التوصية العملية الأولى: بناء TLS-SKL-001 (الهيكل) + TLS-TEX-001 (UV checker) ثم TLS-CHR-001/TLS-ENV-101 كأول شخصية/بيئة حقيقية — التفاصيل في [RENDER_REPORT.md](RENDER_REPORT.md).

## الوثائق

- [ASSET_INVENTORY.md](ASSET_INVENTORY.md) — الجرد الكامل: الموجود/المفقود/البرمجي/المرجعي.
- [RENDER_REPORT.md](RENDER_REPORT.md) — إعدادات الرندر، النتائج المقاسة، المشكلات، الحدود الصادقة.
