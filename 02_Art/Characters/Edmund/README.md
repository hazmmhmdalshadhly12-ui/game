# 02_Art/Characters/Edmund — مجلد الشخصية (M3.4)

هذا المجلد هو **مركز فهرسة أصول شخصية إدموند ڤيل**. الملفات الثنائية الكاملة تسكن في مسارات عقد `docs/ASSET_REGISTRY.csv` (التي يتحقق منها `tools/validate_project.py`):

| الأصل | المسار الفعلي |
|---|---|
| TLS-CHR-001 — ملف Blender الكامل | `../../blender/source/chr/tls_chr_001_edmund_vale.blend` |
| TLS-CHR-001 — FBX هيكلي | `../../exports/fbx/tls_chr_001_edmund_vale_v001.fbx` |
| TLS-CHR-030 — FBX الزي | `../../exports/fbx/tls_chr_030_edmund_outfit_v001.fbx` |
| TLS-SKL-001 — الهيكل المستقل | `../../blender/source/rig/tls_skl_001_rig_human.blend` + `../../exports/fbx/tls_skl_001_rig_human_v001.fbx` |
| الرندرات والتقارير | `../../reports/character-review/Edmund/` |

## محتويات هذا المجلد

- `textures/` — 4 ملفات texture فعلية (512px، مولّدة numpy بلا حقوق خارجية): `cloth_weave` / `leather_grain` / `skin_micro` / `iris_gray`. نفسها معبأة داخل ملف `.blend` أيضًا.
- `build_scripts/` — خط إنتاج قابل لإعادة التشغيل بالكامل على Blender 5.0.1 headless:
  ```bash
  blender -b --python build_scripts/edmund_build.py -- --out out.blend --texdir tex --stats s.json
  blender -b out.blend --python build_scripts/edmund_rig.py -- --stats r.json
  blender -b out.blend --python build_scripts/edmund_export.py -- --mode export --dir fbx/
  blender -b out.blend --python build_scripts/edmund_render.py -- --mode neutral --shots front,side --out renders/
  ```
- الشخصية منشأة إجرائيًا 100% (لا أصول خارجية، لا نسخ شخصيات محمية) — انظر `reports/character-review/Edmund/QUALITY_REPORT.md` للأرقام والحدود الصادقة.
