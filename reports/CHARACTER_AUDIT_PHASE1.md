# CHARACTER AUDIT — PHASE 1 (Rework)

**Date:** 2026-10-28 | **Branch:** `feature/realistic-character-sculpting-rework`
**Auditor:** independent re-render of the actual `.blend` source files with Blender 5.0.1 headless (Cycles CPU, neutral two-point studio light, 900 px, no post-processing, no flattering angles).

**Method:** every character source file was opened and re-rendered by the auditor (fresh camera rig, neutral gray studio) — the images in `02_Art/renders/audit_phase1/` were produced during this audit, not copied from previous marketing renders. Geometry stats were extracted from the same files (`*_stats.json`).

---

## 1. Verdict per character

| Character | File audited | Verdict |
|---|---|---|
| Edmund Vale v002 | `tls_chr_001_edmund_vale_v002.blend` | **REJECT — procedural balloon head, not a sculpt** |
| Gwendolyn | `tls_chr_003_gwendolyn.blend` | **REJECT — egg head, googly eyes, bowl-cut cap** |
| Rev. Crane | `tls_chr_004_crane.blend` | **REJECT** |
| Mair | `tls_chr_006_mair.blend` | **REJECT** |
| Tom Bevan | `tls_chr_007_tom.blend` | **REJECT** |

## 2. Hard geometric evidence

1. **All four NPC "HeadSculpt" meshes are the identical mesh** — exactly `77,120 verts / 153,600 tris` each (from `audit_*_stats.json`). Only displacement parameters differ. This is the "one head with recolors" pattern the production brief explicitly forbids. Edmund's head (110,976 / 221,184) is a different variant of the same procedural grid family.
2. **Eyes are primitive dots**: iris `38 tris`, pupil `30 tris` — flat discs pasted on sphere eyeballs. Real eyes need cornea bulge, limbus ring, eyelid wrap.
3. **Topology is a uniform grid** with a vertical spike artifact at the crown (visible in `audit_edmund_v002_wire.png`); no face-density topology, no loop structure around eyes/mouth suitable for deformation.
4. The ears and eyeballs are separate UV-less objects ( UVs missing on eyes/ears/beard per stats JSON).

## 3. Visual findings (from audit renders)

- **Head shape**: light-bulb/egg balloon — no cranium planes, no brow ridge, no zygomatic arches, no jaw angle, no chin. Profile view (`audit_edmund_v002_left.png`) shows **no facial profile at all** — flat side with faint bumps.
- **Eyes**: floating googly spheres with painted pupils; no eyelids, no sockets, no lashline.
- **Nose/lips/ears**: microscopic bumps; Tom's mouth is a warped sticker; the "beard" is a hard shell with a rectangular mouth hole (`audit_tom_face.png`).
- **Hair**: fractured stepped shards hovering around the skull plus a plastic cap — reads as broken pottery, not hair. No direction, no silhouette, no cards.
- **Skin**: random speckle noise (no anatomical pore/wrinkle logic); pink tint with pasted blotches.
- **Body**: smooth sock mannequin — no clavicles, deltoids, scapulae, muscle groups; neck is a cylinder with a visible seam gap to the head.
- **Clothing**: single woven-shell with texture, no tailoring seams, no folds, no thickness logic; bag strap is a bent cylinder.

## 4. Why the previous claims were inflated

The previous report honestly disclosed "procedural pipeline" but labeled the result "stylized-realistic mid-high". The audit shows the result is below even that: **procedural primitive assembly with displacement noise**. Poly counts (221k head tris) are uniform-grid subdivision, not sculpted detail — triangle count carried no anatomical information. File-format checks (28/28 PASS) verified container validity only, which was correctly disclosed but easily over-read as quality.

## 5. Disposition

- **Preserved**: all v002 files remain untouched on this branch. Nothing deleted.
- **Replacement track**: `feature/realistic-character-sculpting-rework` will rebuild Edmund first, then NPCs, under a new anatomical pipeline (v3) with per-character landmark morphs from a licensed anatomical base, multires sculpt passes, real eye/hair/clothing construction, and a quality gate requiring front/profile/3q/wire/material views per character.
- **Engine status**: unchanged — no Unreal import has ever been tested (disclosed).

## 6. Audit evidence index

`02_Art/renders/audit_phase1/` — 27 files: per character `front / left / threeq / face / wire` PNG + `stats` JSON (Edmund v002, Gwendolyn, Crane, Mair, Tom).
