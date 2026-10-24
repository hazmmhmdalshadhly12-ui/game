# M3.3 — جرد الأصول الفعلي (ASSET_INVENTORY)

> طريقة الجرد: `git ls-files` (‏116 ملفًا متتبعًا) + فحص فيزيائي للمجلدات + قياس أحجام من القرص + فحص كل امتداد 3D معروف (blend/blend1/fbx/obj/glb/gltf/uasset/umap/usd/abc/…).
> التاريخ: 2026-10-23 · أساس الفحص: main @ `7c3d39b` — شجرة عمل نظيفة.

## 1) الأصول ثلاثية الأبعاد الحقيقية — الموجودة فعلًا

هذه القائمة **شاملة** لكل ملف 3D في المستودع (لا يوجد غيرها):

| المسار | الصيغة | الحجم | الأصل/الدور | الحالة عند الفحص الفعلي |
|---|---|---|---|---|
| `02_Art/blender/source/env/tls_env_001_calibration_gnomon.blend` | Blender 5.0 | 91,701 B | TLS-ENV-001 — جسم معايرة المحاور والمقياس | فُتح في Blender 5.0.1 ✅ · mesh واحد 65 vertex / 57 polygon (=110 مثلث) · 5 خامات ألوان · أبعاد 1.35×1.00×0.77 م · سلامة كاملة |
| `02_Art/blender/source/env/tls_env_002_reference_figure.blend` | Blender 5.0 | 109,148 B | TLS-ENV-002 — شخصية مرجعية 1.75 م لمعايرة المقياس | فُتح في Blender 5.0.1 ✅ · mesh واحد 802 vertex / 682 polygon (=1,580 مثلث) · خامة واحدة · أبعاد 0.57×0.25×1.75 م · سلامة كاملة |
| `02_Art/exports/fbx/tls_env_001_calibration_gnomon_v001.fbx` | FBX 7.4 binary | 21,244 B | تصدير TLS-ENV-001 (للاستيراد في UE) | استُورد فعليًا في Blender ✅ · نفس الهندسة والأبعاد بالضبط (65/57، 1.35×1.0×0.77) · الخامات الخمس وصلت |
| `02_Art/exports/fbx/tls_env_002_reference_figure_v001.fbx` | FBX 7.4 binary | 41,804 B | تصدير TLS-ENV-002 | استُورد فعليًا في Blender ✅ · نفس الهندسة والأبعاد بالضبط (802/682، 0.57×0.25×1.75) |

**ملف بيانات مرافق (ليس أصلًا ثلاثيًا):**

| المسار | الحجم | الدور |
|---|---|---|
| `02_Art/exports/manifest_calibration.json` | 2,277 B | Manifest هندسي من مولّد الأصول (Blender 5.0.1، إعدادات تصدير FBX، إحصاءات) |

## 2) الأصول الصوتية (placeholder — مولدة إجرائيًا، ليست تسجيلات حقيقية)

| المسار | الحجم | الحالة |
|---|---|---|
| `04_Audio/ambience/tls_snd_002_wind.wav` | 529,244 B | مولّد بـ `tools/generate_placeholder_audio.py` — EXPORTED (placeholder) |
| `04_Audio/ambience/tls_snd_002_rain.wav` | 529,244 B | placeholder مطابق | 
| `04_Audio/foley/tls_snd_010_footsteps.wav` | 30,912 B | placeholder خطى حجر — EXPORTED (placeholder) |
| `04_Audio/foley/tls_snd_012_page_turn.wav` | 70,604 B | placeholder قلب صفحة — EXPORTED (placeholder) |
| `04_Audio/ui/tls_snd_002_bell_cynog.wav` | 211,724 B | placeholder جرس |
| `04_Audio/manifest_audio.json` | 1,461 B | manifest صوتي |

## 3) ما تم فحصه و**لم يُعثر عليه إطلاقًا** (عدد = 0)

| النوع | النتيجة | الدليل |
|---|---|---|
| خامات وtextures (png/jpg/tga/exr/dds…) | **0 ملف** | `git ls-files` بكل الامتدادات + فحص كل مواد `.blend` (لا توجد عقد TEX_IMAGE) |
| صور مرجعية/concept art | **0 ملف** | لا مجلد مرجعيات ولا صور من أي نوع |
| ملفات `.blend1` (نسخ احتياطي) | **0 ملف** | فحص فيزيائي لمجلد المصادر |
| شخصيات اللعب (Edmund/Gwendolyn/Crane/Mair/Coles/Shoni/Ifor…) | **0 ملف** | السجل يعجّها PLANNED v000 — لا مسارات `chr/` موجودة |
| بيئات القرية (كنيسة/نزل/طاحونة/كوخ آكل الخطايا…) | **0 ملف** | السجل PLANNED — لا `Content/` ولا نماذج |
| props (فانوس/دفتر السجل/صحن الخبز والملح/مفتاح البوابة…) | **0 ملف** | السجل PLANNED |
| هيكل TLS_Rig_Human وأنيميشن (Idle/Walk/Run…) | **0 ملف** | السجل PLANNED |
| ملفات Unreal (`uasset`/`umap`/`upk`/`Content/`) | **0 ملف** | `03_Unreal/` تحوي Config وScripts وSource فقط — الخرائط تُولد داخل المحرر بـ `import_and_calibrate.py` والقرية تُبنى runtime بواسطة `ATLSVillageGameMode` (بيانات blockout في كود C++، وليست نماذج 3D) |

## 4) تصنيف بقية المستودع (ليس أصولًا فنية)

| الفئة | الملفات | الحجم الكلي | ملاحظات |
|---|---|---|---|
| كود C++/Python (نواة اللعبة + أدوات) | 60 | 717,826 B | محرك بلا UE includes في `03_Unreal/Source/TLS/Core/` + اختبارات + مدققات |
| بيانات سردية JSON/CSV | 13 | 121,903 B | حوارات/أدلة/مهام/شائعات/عالم |
| توثيق Markdown | 18 | 283,201 B | GAME_BIBLE، CHARACTER_REGISTRY، تقارير M0–M3.2 |
| إعدادات/CI | 3 | 1,646 B | `.gitignore` ×2 + workflow |
| مشروع UE | 1 + scripts | 530 B + 18 KB | `TLS.uproject` (EngineAssociation 5.4) + سكربتات .bat/.py |

## 5) مطابقة سجل الأصول مع الواقع (ASSET_REGISTRY.csv)

إجمالي صفوف السجل: **80** — حسب الحالة: **5 EXPORTED / 75 PLANNED**، وحسب الفئة:

| الفئة | عدد الصفوف | موجود فعلًا كملف | مفقود (PLANNED) |
|---|---|---|---|
| ENV بيئات | 20 | 2 (أصول معايرة) | 18 |
| CHR شخصيات | 25 | 0 | 25 |
| MAT مواد | 9 | 0 | 9 |
| ANM أنيميشن | 8 | 0 | 8 |
| PRP props | 8 | 0 | 8 |
| SND صوت | 5 | 3 placeholder (5 ملفات wav على القرص) | 2 |
| UI واجهات | 3 | 0 | 3 |
| TEX خامات | 1 | 0 | 1 |
| SKL هيكل | 1 | 0 | 1 |

> ملاحظة صدق: نسبة "المنجز فنيًا" من السجل = 2 من 80 صف (2.5%) — وكلاهما أصل معايرة داخلية وليس محتوى لعبة مرئيًا للاعب. صحة هذه المطابقة تحققت بفحص كل مسار في السجل مقابل القرص.

## 6) ملاحظة عن "قرية Blackthorne" المطلوبة في الفحص

القرية **موجودة كبيانات ولعب runtime داخل UE فقط**: مناطق D0–D12 ومبانٍ ومسارات معرّفة في بيانات عالم C++ (‏`TLSWorldData` وما شابه) وتُشيّد في زمن التشغيل بواسطة `ATLSVillageGameMode` كـ blockout برمجي. هذا **ليس أصولًا 3D قابلة للرندر من الملفات**، لذلك لا توجد رندرات لها هنا — ولم تُصنع صور بديلة لها إطلاقًا احترامًا لقاعدة "لا نماذج وهمية".
