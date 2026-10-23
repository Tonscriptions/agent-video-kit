# Skills / 技能目录

[中文 README](../../../README.md) · [English README](../../../README.en.md) · [使用逻辑 / Usage](USAGE.md)

17 个入口全部以 `$video-cut-` 开头。Skill 是给 Agent 的任务说明；实际媒体处理由 CLI、FFmpeg 或明确登记的本地模型完成。
All 17 entries use `$video-cut-`. Skills instruct an Agent; media processing runs in the CLI, FFmpeg, or explicitly registered local models.

| # | Skill | 用途 / Purpose | 输入 → 输出 / Input → output | 相关入口 / Related commands |
|---|---|---|---|---|
| 1 | [`$video-cut-agent-editor`](../../../skills/video-cut-agent-editor/SKILL.md) | 总入口：计划、项目创建与交付<br>Route editing work, initialize projects and deliver outputs | `brief + local media → project / manifest` | `project init; timeline compose; render` |
| 2 | [`$video-cut-timeline`](../../../skills/video-cut-timeline/SKILL.md) | 时间线、关键帧、运镜、转场、嵌套<br>Author timelines, keyframes, camera moves, transitions and nesting | `edit JSON → editable sequence` | `timeline compose; timeline edit; preview frame` |
| 3 | [`$video-cut-quality`](../../../skills/video-cut-quality/SKILL.md) | 像素、蒙版、Scope、渲染证据核验<br>Review pixels, masks, scopes and render evidence | `render + manifest → review report` | `quality check; quality scopes; quality golden` |
| 4 | [`$video-cut-project-ops`](../../../skills/video-cut-project-ops/SKILL.md) | 快照、恢复、重链和队列<br>Manage snapshots, recovery, relinking and render queues | `project / jobs → recoverable operations` | `project snapshot; project recover; queue run` |
| 5 | [`$video-cut-local-policy`](../../../skills/video-cut-local-policy/SKILL.md) | 本地运行规则与远程引用审计<br>Audit local-only execution and remote references | `project → audit / refusal` | `policy audit` |
| 6 | [`$video-cut-rights-ledger`](../../../skills/video-cut-rights-ledger/SKILL.md) | 素材、字体、模型和模板权利台账<br>Record and check media, font, model and template rights | `local evidence → rights ledger` | `rights check; rights update` |
| 7 | [`$video-cut-local-models`](../../../skills/video-cut-local-models/SKILL.md) | 显式登记已有离线模型<br>Register and run existing offline model adapters | `existing weights + licenses → local inference artifacts` | `media adapter register; subtitle transcribe; audio separate` |
| 8 | [`$video-cut-video-understand`](../../../skills/video-cut-video-understand/SKILL.md) | 镜头、静音、帧证据与转写<br>Analyze scenes, silence, frame evidence and transcripts | `local video / audio → analysis JSON` | `media understand; media contact-sheet` |
| 9 | [`$video-cut-template-library`](../../../skills/video-cut-template-library/SKILL.md) | 模板变量、素材索引、片段组复用<br>Apply templates, index assets and reuse edited clip groups | `template + variables → editable variant` | `template apply; library index; fragment apply` |
| 10 | [`$video-cut-long-to-short`](../../../skills/video-cut-long-to-short/SKILL.md) | 口播/课程长视频转短片<br>Turn talks or lessons into reviewed short clips | `recording + reviewed transcript → short-clip projects` | `media highlights; timeline compose` |
| 11 | [`$video-cut-screen-demo`](../../../skills/video-cut-screen-demo/SKILL.md) | 录屏锚点、缩放与产品演示<br>Edit screen demos with action anchors and zooms | `screen recording + action anchors → demo project` | `timeline compose; preview range` |
| 12 | [`$video-cut-reference-remake`](../../../skills/video-cut-reference-remake/SKILL.md) | 参考片结构复刻并替换原创素材<br>Rebuild reference pacing and layout using replacement assets | `reference + original replacements → editable remake` | `media understand; timeline compose` |
| 13 | [`$video-cut-ffmpeg`](../../../skills/video-cut-ffmpeg/SKILL.md) | 通用本地音视频处理<br>Perform general local FFmpeg media operations | `local files → converted / extracted media` | `native ffmpeg / ffprobe` |
| 14 | [`$video-cut-video-edit`](../../../skills/video-cut-video-edit/SKILL.md) | 修剪、拼接、压缩等工具流程<br>Trim, concatenate, resize and compress local media | `local files + edit instructions → output` | `native ffmpeg; inspect bundled scripts` |
| 15 | [`$video-cut-ad-creative`](../../../skills/video-cut-ad-creative/SKILL.md) | 广告创意、文案和变体规划<br>Plan ad copy, hooks and creative variants | `offer + audience → creative brief` | `advisory skill; no render kernel` |
| 16 | [`$video-cut-video-content-strategist`](../../../skills/video-cut-video-content-strategist/SKILL.md) | 内容定位与脚本策略<br>Plan content direction, scripts and channel strategy | `goals + supplied references → content plan` | `advisory skill; no render kernel` |
| 17 | [`$video-cut-campaign-analytics`](../../../skills/video-cut-campaign-analytics/SKILL.md) | 基于提供数据的投放分析<br>Analyze supplied campaign data | `local campaign data → analysis / next variant` | `advisory skill; no platform connector` |

## 安装与发现 / Install and discovery

```powershell
Set-Location E:\dev\sandbox\AI广告剪辑
.\register-video-cut-skills.ps1
# Optional custom discovery location; existing unrelated directories are preserved:
.\register-video-cut-skills.ps1 -SkillsDirectory E:\agent-skills
```

脚本从当前仓库 `skills/` 推导目标，创建 Windows 目录联接，并更新本机安装映射。仓库迁移后重新运行；已经指向其他目录的同名项会拒绝覆盖。
The script derives targets from this checkout, creates Windows junctions and updates the local mapping. Run it after relocation. A conflicting existing entry is preserved and refused.
The installed CLI bundle does not itself install an Agent host or register Skills. Download the Skills asset or use the source checkout, then register with your Agent's supported discovery mechanism.

## 调用示例 / Example requests

```text
$video-cut-agent-editor 用本地两张产品图和配乐制作 6 秒竖屏广告；保留可编辑项目、权利证据和输出检查。
$video-cut-timeline Add a reviewed zoom preset to the local clip, preserve source timing, and preview its first and last frames.
$video-cut-quality 核验当前输出与 manifest；分别说明自动检查、目检、连续播放和听审结果。
$video-cut-template-library Apply this local template to the supplied product image and render one editable variant.
```

## 组合逻辑与依赖 / Routing and dependencies

创意/策略 → agent-editor → rights-ledger + local-policy → video-understand → timeline/template → quality → project-ops。
Creative/strategy → agent-editor → rights-ledger + local-policy → understanding → timeline/template → quality → project operations.

`local-models` 只有在任务需要时使用；ASR、OCR、RVM、SAM2、LaMa、VACE、HDemucs、SoulX 等需要各自已有的原生环境、权重和许可证明，不包含在基础安装包。
Optional model adapters require their own existing native environment, weights and license evidence. They are not bundled or downloaded automatically.
Advertising strategy and campaign analysis use supplied information; they do not establish model execution, platform access, attribution accuracy or ad performance.

前 3 个核心入口已按首版重整，完整历史移至各自 `references/pre-release-routing.md`。其余入口保留专项说明，以本版能力清单和契约为准。
The three core entrypoints were condensed for this release; dated instructions remain in their references. Specialist entries retain their contracts. Current capabilities and release boundaries take precedence over older paragraphs.

第三方 Skill 的固定来源、哈希和单独许可证见 [安装清单](../../../video-cut-install-manifest.json)。修改过的本地入口不能视作上游原样版本。
Pinned upstream origins, local hashes and separate licenses are recorded in the installation manifest. Locally edited entries are not pristine upstream versions.
