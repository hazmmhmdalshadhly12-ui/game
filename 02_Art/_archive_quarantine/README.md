# QUARANTINE — 停用与拒绝的角色资产 / Retired & rejected character assets

日期 / Date: 2026-11-08
决定人 / Decided by: 项目负责人 (user) + art pipeline review
分支 / Branch: `feature/realistic-character-sculpting-rework`

## 为什么被隔离 / Why quarantined

用户在 2026-11-08 的审查结论（原文）:
> "واللي إنت عملته في الشخصية ده مش نحت ... أنا عايز نحت حقيقي"
> （"你给角色做的这个东西不是雕刻……我要真正的雕刻"）

Phase-1 审计（commit 94d5e52，证据见 `02_Art/renders/audit_phase1/`）同样判定:

| 问题 | 证据 |
| --- | --- |
| v002 "221k-tri head" 与全部 NPC 头部均由参数化/程序化网格生成 | `reports/AAA_SCULPTING_PRODUCTION_REPORT.md` 自述 procedural |
| 4 个 NPC 头部几何完全相同（77,120 v / 153,600 tri），仅换发型/肤色/服装 | audit_phase1 stats JSON |
| 眼睛为 38 三角形圆点贴片，无面部侧影轮廓 | audit 渲染 |
| v3 "loft" 头部仍是数学放样曲面（sagittal profile + superellipse sections），不是雕刻 | `aaa_pipeline_v3/v3_loft.py` |

结论: 这些文件**不是数字雕刻**。它们被移动到此目录以免污染生产路径；
**未删除**（git 历史与文件都保留），但不得作为角色生产资产使用。

## 内容 / Contents

- `blend_characters/` — v002 Edmund、v3 loft 头部、v2 头部套件的 .blend 源
- `glb_characters/` — 对应 GLB 导出
- `fbx_characters/` — 对应 FBX 导出（v002/v3 角色）
- `stl_v3/` — v3 STL 校验导出
- `renders_v3_characters/` — v1/v2/v3 角色渲染图（audit_phase1 证据图保留在原处:
  `02_Art/renders/audit_phase1/`）

## 什么没有被隔离 / What was NOT quarantined

- 环境/道具资产（stone kit、church、cemetery、investigation props）— 未被本判定覆盖
- 身体套件与服装（`tls_chr_020_body_kit / tls_chr_025_garments / tls_chr_030_edmund_outfit`）
- 所有审计证据渲染图
- v001 原始提交的历史文件

## 替代路径 / Replacement

真正的雕刻管线与当前状态见 `reports/REALISTIC_CHARACTER_SCULPTING_REVIEW.md`
（v4: Blender Sculpt Mode 真实笔刷管线 `02_Art/aaa_pipeline_v4/`）。
