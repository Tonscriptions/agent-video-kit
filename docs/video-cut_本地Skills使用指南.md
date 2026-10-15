# video-cut 本地技能使用指南

| 文档编号 | OPS-2026-10-001 |
|---|---|
| 状态 | 有效 |
| 本次审计复核 | 2026-10-14 |
| 证据性质 | 本地 Skill 注册、目录校验与运行策略；不等于完整剪映功能验收 |

> **运行策略（2026-10-14）：** 生产 Skill 只允许调用本地项目、系统 FFmpeg、本地模型和本地文件。禁止剪映、闭源 SaaS、远程 API、在线素材下载、远程渲染和需要联网才能完成的工作流。`sources/` 仍保留公开仓库快照用于许可证、来源和差异审计，但不作为生产 Skill 的可调用依赖。

当前登记 **14 个生产 Skill**。目录名、`SKILL.md` 中的 name、调用名均以 `video-cut-` 开头，且所有生产 Skill 已通过 `quick_validate.py`。发现目录通过 Windows 目录联接指向本项目的 `skills/`，因此 Skill 内容与产品代码随 Git 一起审计。

`$` 是调用标记，不属于目录名。例如 `$video-cut-video-edit` 对应 `skills/video-cut-video-edit/`。

## 常用入口

| 需求 | 调用 |
|---|---|
| 本地 Agent 编辑器编排 | `$video-cut-agent-editor` |
| 时间线、关键帧、遮罩、嵌套序列 | `$video-cut-timeline` |
| 素材裁切、拼接、转码和导出 | `$video-cut-video-edit` |
| FFmpeg 滤镜、音视频质量和编码参数 | `$video-cut-ffmpeg` |
| 素材理解、抽帧、字幕和高光候选 | `$video-cut-video-understand` |
| 本地模型、离线 ASR/TTS 和模型门禁 | `$video-cut-local-models` |
| 远程引用审计与本地路径策略 | `$video-cut-local-policy` |
| 模板、变体、参数和批量生产 | `$video-cut-template-library` |
| 权利、许可证、证据和发布门禁 | `$video-cut-rights-ledger` |
| Scope、音视频质量和验收报告 | `$video-cut-quality` |
| 项目初始化、状态、队列和清理 | `$video-cut-project-ops` |
| 广告创意、Hook、文案变体 | `$video-cut-ad-creative` |
| 视频脚本与内容规划 | `$video-cut-video-content-strategist` |
| 活动归因、漏斗和 ROI 分析 | `$video-cut-campaign-analytics` |

可复制的调用示例：

```text
$video-cut-project-ops 初始化一个本地广告剪辑项目，并输出项目状态。
$video-cut-local-policy 对 project.json 执行 policy audit，拒绝所有远程或闭源服务引用。
$video-cut-video-understand 分析本地素材，生成字幕、镜头摘要和高光候选。
$video-cut-agent-editor 对口播素材执行 media reframe，先检查目标画幅、主体越界和置信度，再应用 crop.* 动态关键帧。
$video-cut-timeline 将高光候选编排为 30 秒竖屏广告，加入关键帧运镜和本地转场。
$video-cut-quality 生成 waveform、vectorscope、histogram、固定 golden 清单和哈希证据报告。
$video-cut-rights-ledger 检查所有素材、模板依赖和父资产的本地许可证证据和发布门禁，并在撤下/争议后创建可审计修订、历史影响报告和发布清单。
```

## 生产 Skill 清单

| # | 调用名 | 生产职责 | 依赖边界 |
|---:|---|---|---|
| 1 | `$video-cut-ad-creative` | 广告 Hook、标题、文案和创意变体 | 本地规则与项目数据 |
| 2 | `$video-cut-agent-editor` | Agent Project、时间线、模板、权利和转换 CLI 编排 | 本项目 `product` CLI |
| 3 | `$video-cut-campaign-analytics` | 归因、漏斗、ROI 和投放效果分析 | 本地 CSV/JSON 数据 |
| 4 | `$video-cut-ffmpeg` | FFmpeg 转码、滤镜、裁切、混音和编码质量 | 系统 FFmpeg 与本地文件 |
| 5 | `$video-cut-local-models` | 本地模型登记、能力探测、离线 ASR/TTS 门禁 | 本地模型目录 |
| 6 | `$video-cut-local-policy` | 本地引用校验、远程引用审计和 provider marker 检查 | `policy audit` CLI |
| 7 | `$video-cut-project-ops` | 项目初始化、状态查询、队列、清理和可复现运行 | `project` CLI |
| 8 | `$video-cut-quality` | Scope、编码元数据、哈希、回归和发布前质量门禁 | 本地 FFmpeg 输出 |
| 9 | `$video-cut-rights-ledger` | 素材许可证、来源证据、用途和发布审批记录 | 项目内 Rights Ledger |
| 10 | `$video-cut-template-library` | 模板 schema、参数、变体、版本和批量渲染 | 本地模板目录 |
| 11 | `$video-cut-timeline` | 时间线、关键帧、曲线、遮罩、转场和嵌套序列 | Agent Project schema |
| 12 | `$video-cut-video-content-strategist` | 视频脚本、短视频结构和内容规划 | 本地 brief/项目数据 |
| 13 | `$video-cut-video-edit` | 已有素材裁切、拼接、叠加、变速和成片加工 | 本地 FFmpeg |
| 14 | `$video-cut-video-understand` | 抽帧、转写、内容摘要、镜头和高光分析 | 本地 FFmpeg 与已登记模型 |

### 旧 Skill 的处理

曾经加载的生成服务、网页捕获、在线视频下载、Remotion/HyperFrames、剪映适配、远程素材库和云端营销 Skill 已从生产 `skills/` 目录删除，并从 Codex 发现目录解除联接。删除只影响生产入口；原始公开仓库快照仍可在 `sources/` 中追溯，不能直接被本地 Agent 调用。安装清单中的 `source_repositories` 只承担来源审计职责。

## 本地运行流程

1. 使用 `$video-cut-project-ops` 初始化或检查项目目录。
2. 使用 `$video-cut-local-policy` 执行 `policy audit --project <project>`；发现 URL、云存储、流媒体、服务商标记时立即停止。
3. 使用 `$video-cut-video-understand` 读取已落盘素材；素材必须先进入项目资产库并写入 Rights Ledger。
4. 使用 `$video-cut-timeline`、`$video-cut-video-edit` 和 `$video-cut-ffmpeg` 生成时间线及本地渲染计划；需要横竖屏重构时，由 `$video-cut-agent-editor` 先执行 `media reframe --dry-run`，检查主体边界后再应用。
5. 使用 `$video-cut-local-models` 选择已登记的离线模型；没有本地模型时输出能力缺口，不自动改走远程服务。
6. 使用 `$video-cut-quality` 先跑 `quality check` 和 Scope，再用 `quality golden --mode capture` 固定通过的本地媒体/设置哈希，交付前用 `--mode verify` 检查漂移。
7. 使用 `$video-cut-rights-ledger` 执行 `rights list/history/check`；发生多资产证据变更时用 `rights batch-update`，发生撤下时用 `rights retract` 和 `rights impact` 保留影响链；需要历史成片替换/删除时用 `rights decide` 生成 proposed/approved 决策和影响清单，批准后用 `rights apply` 更新当前项目时间线并保留历史文件，最后用 `rights export` 生成发布清单，再由 `$video-cut-agent-editor` 执行导出。

核心命令示例：

```powershell
$env:PYTHONPATH = (Resolve-Path .\product\src).Path
python -X utf8 -m ai_ad_editor capabilities
python -X utf8 -m ai_ad_editor policy audit --project .\project
python -X utf8 -m ai_ad_editor doctor --project .\project
```

`policy audit` 是生产前硬门禁。它只读取项目内 JSON/JSONL 和本地文件元数据，不发起网络请求；发现远程协议、URL 或已知服务商标记时返回失败信封 `POLICY_REMOTE_REFERENCE`。媒体导入和格式转换也会在写入前拒绝远程引用。

## 来源、版本与目录

| 项目 | 位置 |
|---|---|
| 项目根目录 | `E:\dev\sandbox\AI广告剪辑` |
| 可编辑生产 Skill | `E:\dev\sandbox\AI广告剪辑\skills` |
| Codex 发现目录 | `C:\Users\carzy\.codex\skills`（Windows 目录联接） |
| 原始仓库与 ZIP 快照 | [`sources/`](../sources/) |
| 来源、版本、目录映射与哈希 | [`video-cut-install-manifest.json`](../video-cut-install-manifest.json) |
| 本地校验结果 | [`research/video-cut-validation.json`](../research/video-cut-validation.json) |
| 注册脚本 | [`register-video-cut-skills.ps1`](../register-video-cut-skills.ps1) |
| 本地运行策略契约 | [`本地运行策略与远程引用审计契约_v0.1_2026-10-14.md`](./specs/本地运行策略与远程引用审计契约_v0.1_2026-10-14.md) |
| Agent CLI 契约 | [`AgentCLI契约_v0.1_2026-10-13.md`](./specs/AgentCLI契约_v0.1_2026-10-13.md) |

移动项目目录或变更 Skill 后，重新运行注册脚本并刷新安装清单哈希。所有新需求、规范、ADR、计划和验证记录继续写入 `docs/`。

## 校验边界

本指南证明生产 Skill 的目录、前缀、本地依赖和注册关系可重复检查；它不宣称已经关闭全部剪映差异。当前仍需独立证据推进的能力包括复杂本地模型跟踪、多语言高质量离线 TTS/ASR、GPU 级特效、跨字体精确排版、复杂音频空间处理、更多转场语义、跨格式工程互操作、版权登记的正式黄金媒体集和跨设备视觉阈值。每项能力只有在产品实现、回归测试和固定证据同时具备后，才可从差异清单中关闭。

后续制作遵循 [`AGENTS.md`](../AGENTS.md)：只使用原生 Windows 工具，禁止 Docker/WSL 等虚拟化环境；若使用浏览器，完成后关闭不再使用的 tab。

## 中文离线配音调用增量

`$video-cut-local-models` 与 `$video-cut-agent-editor` 已同步 SoulX 模型和参考声登记、原样逐字稿、完整性、生成 WAV 资产和 `--apply` 音轨调用。默认 flite 仍只接受 ASCII；中文需显式本地适配器、CUDA 和完整权重。见[配音契约](./specs/本地SoulX中文配音与声线登记契约_v0.1_2026-10-15.md)与[实测记录](./validation/SoulX中文离线配音实测_2026-10-15.md)。发布资格继续由模型、声源、文本及输出权利门禁决定。
