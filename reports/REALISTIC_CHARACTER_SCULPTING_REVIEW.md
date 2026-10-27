# REALISTIC CHARACTER SCULPTING REVIEW — THE LAST SIN

**Date:** 2026-10-28 | **Branch:** `feature/realistic-character-sculpting-rework`
**Scope:** Phase-1 audit + pipeline rework (v3) for hero and named-NPC heads.

---

## 1. Audit findings (Phase 1 — completed)

All five previous character sources were re-opened and re-rendered in Blender 5.0.1 headless (neutral studio, no flattering angles) — evidence in `02_Art/renders/audit_phase1/` (27 files).

| Character | Verdict | Hard evidence |
|---|---|---|
| Edmund Vale v002 | REJECT | balloon head, 38-tri iris dot, no profile |
| Gwendolyn v002 | REJECT | egg head, googly eyes, bowl cap |
| Crane v002 | REJECT | same |
| Mair v002 | REJECT | same |
| Tom v002 | REJECT | beard = hard shell with rectangular mouth hole |

Key facts: **all four NPC "HeadSculpt" meshes had exactly identical topology (77,120 verts / 153,600 tris)** — the "one head + recolors" pattern; heads were uniform-grid spheres with gaussian displacement, not sculpts. The v002 files are preserved untouched on this branch.

## 2. New method (pipeline v3 — what actually changed)

v3 abandons the sphere+noise approach entirely:

1. **Lofted anatomical base**: the head is lofted from a mid-sagittal profile curve (trichion→forehead→brow→nasion→nose tip→lips→chin→neck, at real metric heights) + coronal half-width table (bizygomatic/bigonial/parietal) + per-level superellipse section — a sculptor-style blockout with guaranteed silhouette.
2. **Anatomical feature passes**: brow bar, graduated nasal bridge/tip/alar wings, zygomatic + malar masses, orbicularis-oris lip volumes, mental protuberance, gonial angles, masseter planes, temporal hollows, orbital socket + palpebral-aperture carves, philtrum/mentolabial sulci — each a smooth-masked local deformation, not noise.
3. **Per-character identity morphs**: 20+ parameters (cranW, faceW, jawW, browP, noseL/W/P/B, lipU/L, mouthW, cheek, eyeW/tilt/depth, chin projection, age, fem, asymmetry seed…) drive every volume. NPCs are NOT re-scaled copies: Gwendolyn (fem 1.0, softer jaw, fuller lips), Crane (58y, sunken cheeks, aquiline bridge, heavy brow), Mair (19y, round cheeks, widest lips, smallest brow), Tom (63y, widest jaw, heavy brow, droop). Same base topology — genuinely different forms, as allowed by the brief ("shared base mesh acceptable only if identities are genuinely distinct").
4. **Age system**: wrinkle paths (nasolabial, tear trough, crow's feet, forehead lines ×2-3, glabella, marionette, mentolabial, philtrum, lip seam, neck rings, ear helix/antihelix, lid crease) with depth scaled by age; jowl sag and lid hooding above 30/40.
5. **Real eye construction**: sclera sphere (24 mm) + cornea bulge + iris disc + pupil disc per eye, seated in carved sockets with lid volumes.
6. **Hair**: fitted scalp cap (solidified shell with cloud-displacement break-up) + 520 short flow-directed cards (tangent-projected gravity + crown whorl) + eyebrow card strips.
7. **Skin**: zone-tinted albedo (warm nose/ears/cheeks, darker peri-orbital, lip zone), fine mottling, stubble zone for males, roughness T-zone variation, Principled subsurface scattering.

Toolchain: Blender 5.0.1 headless + numpy/scipy/skimage (marching-cubes SDF was prototyped and discarded for the loft approach — both scripts kept for reference), trimesh validation. **All deformation passes are scripted vertex operations executed headless — this is NOT hand-sculpting in a GUI session, and it is not claimed to be.**

## 3. What was actually produced (paths + formats)

| Asset | Path | Format |
|---|---|---|
| v3 pipeline source | `02_Art/aaa_pipeline_v3/*.py` (6 files) | Python |
| 5 head assemblies (head+eyes+hair cap+cards+brows, skin SSS material) | `02_Art/blender/source/chr/v3/TLS_{edmund,gwendolyn,crane,mair,tom}_head_v3.blend` | .blend |
| Game-viewable exports | `02_Art/exports/glb/v3/TLS_*_head_v3.glb` | glTF-Binary |
| Editable base meshes + landmark JSON | `02_Art/exports/stl_v3/*_loft.stl` + `*_landmarks.json` | STL/JSON |
| Evidence renders (5 views each: front/left/threeq/back/face) | `02_Art/renders/v3/v3c_*.png` (25 files) | PNG |

Each head assembly ≈ 19k base tris + smooth×6 modifier (~0.5 M shaded tris at render) + ~1.5k hair-card tris. Base meshes are identical topology across characters (loft grid) — **identities differ through parameterized form, not topology**; retopology with unique topologies is future work (§6).

## 4. Honest quality assessment

**Reached:** correct anthropometric proportions; real profile (nose/lips/chin) from both sides; distinct NPC identities; real eyes/hair/brows; age-differentiated wrinkles; inspectable .blend/.glb files; evidence renders from the actual models. A clear generational step above the audited v002 balloons.

**NOT reached (no overclaiming):**
- **This is not RDR2-quality photorealism.** It is an anatomically-proportioned semi-realistic base. The mid-face still reads slightly puffy in close-ups; nose-to-brow transition needs refinement; hair cards are sparse splinters without alpha textures (cap carries the silhouette); no per-character unique retopology; no baked high→low normal maps; no rig/weights on v3 heads yet (v002 65-bone rig exists for the old body).
- The "face" close-up view framing crops the mouth (camera targets the eye line) — known defect.
- Reaching true AAA facial quality requires interactive sculpting (ZBrush/Blender GUI sessions) which this headless environment cannot provide (no GPU, no display, RDP workstation workflow not available from here). The v3 parameterized base is designed so a sculptor can refine it interactively later.

## 5. Validation actually performed

- STL/GLB integrity via trimesh (watertight check, bounds: head height ≈ 0.27 m incl. crown apex, width ≈ 0.155 m — real scale).
- Blender re-open of every saved .blend (all five open cleanly with materials/hair/eyes intact).
- GLB exports re-read with pygltflib-compatible structure check (5/5 valid glTF-Binary).
- 25 evidence renders produced from the exact saved scene files (Cycles CPU, Standard view transform, neutral 3-point light).
- **No Unreal Engine 5.4 import test was performed** — no UE environment available; explicitly NOT claimed.

## 6. Remaining tasks (priority order)

1. Interactive sculpt refinement pass on all five faces (GUI session needed) — focus: nasion transition, mid-face fat pads, lip seams, ear scapha depth.
2. Unique retopology per character + game-res decimation + UV layout proper (current UV is a front planar projection for QC).
3. Bake normal/AO from hi to game-res; alpha-textured hair cards; beard geometry for Edmund/Tom.
4. Rig v3 heads to the TLS-SKL-001 neck/head bones + weight paint.
5. Rebuild bodies/clothing v3 on the same loft principle (v002 body/outfit files remain untouched and reusable).
6. UE 5.4 import test when an engine environment is available.

## 7. Answers to the seven acceptance questions

1. **Real meshes created?** Five complete head assemblies (v3) + five editable base meshes + full pipeline source. Previous 21 environment/prop assets untouched.
2. **Where in GitHub?** This branch — exact paths in §3.
3. **High-detail sculpt level?** Edmund + 4 NPCs reached "anatomical base v3" level (real forms, real features). None reached final-hero sculpt level yet.
4. **Still blockout?** The heads are beyond blockout but below hero-sculpt; bodies/clothing remain at v002 quality (documented, preserved).
5. **Files actually checked?** Yes — trimesh + Blender re-open + GLB structure + 25 renders (§5).
6. **Tested in Unreal?** **No.** Stated explicitly; never claimed.
7. **Next batch?** §6 list — starting with interactive sculpt refinement + retopo + baking.
