# 首版范围与发布记录 / First-release scope and notes

Release: **`v0.1.0-alpha.1`** · Stage: **prerelease / alpha** · Acceptance date: **2026-10-24 (Asia/Taipei)**.
CLI/package/schema report 0.1.0. The prerelease tag describes the acceptance stage.

## 发布判定 / Decision

可以收口并发布第一份本地 Agent CLI 预览版；不能关闭“全面达到剪映功能与自然观感”的长期需求。
The local Agent CLI milestone can close and ship as a preview. Full CapCut feature/perceptual equivalence remains open.
The baseline product commit is `ff23569e24ff0c36c620be1176f6db9dc23045fb`; release documentation, Skills and registration improvements are layered over its unchanged 331 frozen inputs.

| # | Scope | Decision / 判定 |
|---|---|---|
| S01 | Native offline install and structured CLI | Included / 纳入：Windows x64 / CPython 3.13, eight pinned wheels |
| S02 | Editable timeline → render → checks → package | Included / 纳入：new source-generated cases and full real responses |
| S03 | Advertised editing/effect/model interfaces | Included within declared contracts; models remain optional external local dependencies |
| S04 | Bilingual onboarding, 17 Skills and case evidence | Included / 纳入：Chinese/English READMEs and bilingual release guides |
| S05 | Complete CapCut feature/preset/library equivalence | Open / 未收口 |
| S06 | Broad natural-media visual/audio acceptance | Open / 未收口：no universal playback/listening/perceptual claim |
| S07 | Continuous 4K/long-form performance and peak RSS | Open / 未收口 |
| S08 | Other platforms/ABIs, universal draft round trip | Open / 未收口 |
| S09 | R113 transitions, R114 runtime closure, later adjustments | Excluded candidates / 未合入本版 |

This is a development preview, not the production `release` stage defined by the older operations plan. Outstanding natural-quality and distribution gates are not silently waived or relabeled as passed. Optional experimental integrations must be enabled deliberately and retain their own rights/runtime requirements.

## 验证口径 / Verification accounting

- Baseline: 2,930 methods passed, 0 skipped, 6991.508 s, source and external fixtures unchanged. [Raw record](../../validation/evidence/float-shaper-20261023-lab/full-r1.json).
- Historical fresh V112 installation: 118 targeted methods and 197 product resources. It overlaps the full suite; do not add counts.
- This release: new eight-wheel build/install, byte comparison with the frozen product, real isolated CLI cases, complete output decoding/probes, Skills and release-document links, desktop/mobile documentation capture and interaction checks. [Current gate](../../validation/evidence/release-v0.1.0-alpha.1-r2/release-verification.json).
- Preserve actual failed first case attempt and any corrective rerun; distinguish documentation/fixture errors from product defects.

## 资产与运行边界 / Distribution boundary

| Asset | Contents | Not included |
|---|---|---|
| `agent-video-kit-v0.1.0-alpha.1-cp313-win_amd64.zip` | Offline bundle, fixed wheels, installer, version/provenance, notices, install instructions | Python, FFmpeg, models, GPU drivers, Node/Chromium |
| `agent-video-kit-v0.1.0-alpha.1-examples.zip` | Generated original inputs, outputs/GIFs, actual logs, project package and reproducer | Unreviewed third-party media or model weights |
| `agent-video-kit-v0.1.0-alpha.1-skills.zip` | 17 prefixed Skills, their resources/licenses and relevant manuals | Agent host, online services or automatically enabled models |
| `SHA256SUMS.txt`, `version.json` | Artifact digests and release metadata | Author signature; no signature is claimed |

## 已知风险与下一阶段 / Risks and next milestones

| # | Open requirement | Next acceptance evidence |
|---|---|---|
| N01 | Renderer coverage differences | Explicit compatibility matrix and real unsupported/supported composition checks |
| N02 | Natural visuals, transitions, masks and color | Authorized varied source set, continuous playback, independent oracles and documented reviewer decisions |
| N03 | Audio quality and sync | Natural speech/music, listening review, phase/pitch and codec-origin coverage |
| N04 | Long-form/4K resource reliability | Measured decode/render latency, peak RSS/VRAM/disk, cancellation and recovery at meaningful durations |
| N05 | Distribution and reproducibility | Additional clean-host evidence, toolchain provenance and versioned upgrade tests |
| N06 | Template/model ecosystem | Redistributable assets with license evidence, reproducible local adapters and quality baselines |
| N07 | Interchange | Real authorized draft corpus with per-feature exact/approximate/unsupported/failure reports |

优先解决质量与运行可靠性，再扩大效果数量；历史通过数不替代新的验收。尚未合入的候选继续保留，不用候选计划测试数冒充已发布结果。
Prioritize quality and runtime reliability before growing the effect catalog. Preserve unmerged candidates, and never present their planned test counts as shipped results.

## 维护与回滚 / Maintenance and rollback

`main` receives validated updates through normal pushes. Tags and existing assets are not overwritten. Maintain Chinese/English READMEs and numbered evidence for every functional update. [Install and rollback instructions](USAGE.md).
Keep the release archive and project snapshot; upgrades install side by side. If a release issue appears, preserve reproduction evidence and publish a subsequent prerelease rather than replacing an existing asset silently.
