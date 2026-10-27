# AAA Sculpting Pipeline v2 — THE LAST SIN

خط إنتاج نحت رقمي إجرائي يعمل **headless** على Blender 5.0.1. كل الهندسة حقيقية وقابلة للفحص (grid displacement + gauss fields + crease paths + noise)، وليست placeholders.

## الملفات

| الملف | الوظيفة |
|---|---|
| `sculpt_lib.py` | محرك النحت: شبكات، حقول gauss تشريحية، تجاعيد على مسارات، noise دقيق، محرك الرأس والأذن |
| `body_lib.py` | بناء الجسم **من مواضع عظام الـ rig الموجود** (توافق مضمون مع TLS-SKL-001) + يد بأصابع من سلاسل عظام الأصابع |
| `outfit_lib.py` | ملابس 1847 (أصداف قماشية بإزاحة + ثنيات جاذبية + solidify)، شعر (قبعة صلبة + بطاقات)، لحية |
| `env_lib.py` | وحدات بيئة: حجارة مداميك heightfield، أردواز، ألواح خشب، صخور، أشجار، قبور |
| `textures_v2.py` | مولد خامات PBR PNG (جلد/صوف/كتان/جلد/حديد/نحاس/حجر/أردواز/خشب/طين) |
| `build_edmund_v2.py` | الدفعة 1: إدموند كامل + سكينning حتمي + اختبارات تشوه + تصدير |
| `build_npcs.py` | الدفعة 2: 4 شخصيات ببارامترات هوية |
| `build_env_v2.py` | الدفعة 3: طقم + كوخ + كنيسة + مقبرة + طبيعة |
| `build_props_v2.py` | الدفعة 4: 11 أداة تحقيق |
| `verify_all_v2.py` | فحص مستقل (إعادة استيراد + إحصاءات) |
| `render_docs.py` | صور توثيق Cycles CPU من المجسمات الحقيقية |

## التشغيل

```bash
blender --background --factory-startup --python build_edmund_v2.py
blender --background --factory-startup --python build_npcs.py
blender --background --factory-startup --python build_env_v2.py
blender --background --factory-startup --python build_props_v2.py
blender --background --factory-startup --python verify_all_v2.py
```

## بيانات التصدير

- hi-poly: `.blend` + `.glb` (Nanite/فحص)
- game-res: `.fbx` (rig + أوزان) + `_game.blend`
- الأصول الثابتة الكبيرة تتضمن `UCX_*` لتصادم UE
- المتطلبات: 4GB RAM (اختُبر على 2 vCPU بدون GPU)

## القيد المعروف

النحت إجرائي مُبرمَج — المستوى "stylized-realistic". لرفع الوجوه لمستوى photoreal: افتح `.blend` في Blender GUI واستخدم Sculpt Mode على Multires (البنية الجاهزة تدعم ذلك مباشرة).
