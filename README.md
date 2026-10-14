# Agent Video Kit

面向 Agent 的本地视频广告编辑内核。项目使用原生 Windows、Python 和本地 FFmpeg，通过 CLI、结构化 Agent Project JSON、Skills 和可审计的素材权利台账完成广告剪辑流水线；当前工作区位于 `E:\dev\sandbox\AI广告剪辑`。

项目明确不依赖剪映/Jianying 私有运行时、登录态、闭源线上服务、Docker、WSL 或其他虚拟化环境。网络默认关闭，模型、媒体和字体必须从显式本地路径提供。

## 当前状态

- P0 CLI 闭环已实现：项目初始化、媒体摄取与探测、时间线变更、关键帧与运镜、字幕、音频、遮罩、转场、渲染、项目内持久化渲染队列、质量检查、权利门禁、快照/迁移/跨文件事务恢复、确定性素材索引/搜索/重复组、增量刷新、FFmpeg 感知候选和受限互操作（OTIO canonical Stack/Gap 与 MLT 帧时间映射）；项目写入由原生 Windows 文件锁串行化，元数据事务由 `operations/project-transaction.json` 保护，队列取消在渲染持锁时仍可递交并异步确认。
- 当前 E 盘回归：`112/112` 通过；完整证据见 [`docs/validation/回归验证记录_2026-10-13.md`](docs/validation/回归验证记录_2026-10-13.md)。
- 当前实现仍会明确报告近似和未支持能力，不能把 P0 底座描述成已经完全等同于剪映。对象跟踪鲁棒性、复杂路径逐点动画、GPU 效果、多语言离线 TTS、完整外部工程映射和黄金素材集仍按路线图推进。
- 生产 Skill 统一使用 `video-cut-` 前缀，并只保留本地 FFmpeg、本地模型和离线编排入口；可用 `$video-cut-技能名` 调用，清单见 [`video-cut-install-manifest.json`](video-cut-install-manifest.json)。

## 快速开始

在 PowerShell 中从仓库根目录执行：

```powershell
.\ai-ad-editor.ps1 doctor
.\ai-ad-editor.ps1 version
```

直接调用 Python CLI 时：

```powershell
$env:PYTHONPATH = "$(Get-Location)\product\src"
python -X utf8 -m ai_ad_editor project init .\workspace\demo
python -X utf8 -m ai_ad_editor media ingest --project .\workspace\demo --input C:\media\source.mp4
python -X utf8 -m ai_ad_editor media reframe --project .\workspace\demo --asset-id <asset_id> --roi 0.20,0.20,0.20,0.35 --clip-id talking_head --track-id track_video_1 --dry-run
python -X utf8 -m ai_ad_editor media track-bind --project .\workspace\demo --asset-id <asset_id> --roi 0.20,0.20,0.20,0.35 --target-clip-id product_label --target-track-id track_text_1 --scale-mode roi --dry-run
python -X utf8 -m ai_ad_editor media smart-cut --project .\workspace\demo --track-id track_video_1 --clip-id speech_clip --linked-track-id track_audio_1 --linked-clip-id speech_audio --dry-run
python -X utf8 -m ai_ad_editor media smart-cut --project .\workspace\demo --track-id track_video_1 --clip-id speech_clip --transcript .\workspace\demo\validation\captions.srt --remove-phrase "嗯" --dry-run
python -X utf8 -m ai_ad_editor media multicam --project .\workspace\demo --source-asset-id camera_wide --source-asset-id camera_close --reference-asset-id camera_wide --switch-seconds 4 --track-id track_video_1 --dry-run
python -X utf8 -m ai_ad_editor media beat-cut --project .\workspace\demo --input .\media\music.wav --source-asset-id <asset_id> --track-id track_video_1 --dry-run
python -X utf8 -m ai_ad_editor subtitle transcribe --project .\workspace\demo --asset-id <asset_id> --model-path E:\models\ggml-small.bin --transcribe-engine ffmpeg-whisper --dry-run
python -X utf8 -m ai_ad_editor media stabilize --project .\workspace\demo --asset-id <asset_id> --derived-asset-id stabilized-source --smoothing 15 --dry-run
python -X utf8 -m ai_ad_editor validate --project .\workspace\demo
python -X utf8 -m ai_ad_editor project recover --project .\workspace\demo
python -X utf8 -m ai_ad_editor render --project .\workspace\demo --output .\workspace\demo\renders\ad.mp4
python -X utf8 -m ai_ad_editor tts synthesize --project .\workspace\demo --text 'Hello local advertising voice' --output .\workspace\demo\assets\voice.wav
python -X utf8 -m ai_ad_editor ad plan --project .\workspace\demo --input .\workspace\brief.json --output .\workspace\demo\validation\ad-plan.json
python -X utf8 -m ai_ad_editor ad apply --project .\workspace\demo --input .\workspace\demo\validation\ad-plan.json
python -X utf8 -m ai_ad_editor effects list --query color
python -X utf8 -m ai_ad_editor effects inspect --name curves
python -X utf8 -m ai_ad_editor motion list --query position
python -X utf8 -m ai_ad_editor motion inspect --name push-in
python -X utf8 -m ai_ad_editor motion apply --project .\workspace\demo --clip-id <clip_id> --preset ken_burns --amount 0.2 --dry-run
python -X utf8 -m ai_ad_editor queue enqueue --project .\workspace\demo --input .\workspace\queue.json
python -X utf8 -m ai_ad_editor queue run --project .\workspace\demo --continue-on-error --progress jsonl
python -X utf8 -m ai_ad_editor queue list --project .\workspace\demo --status failed
python -X utf8 -m ai_ad_editor policy audit --project .\workspace\demo
python -X utf8 -m ai_ad_editor rights list --project .\workspace\demo
python -X utf8 -m ai_ad_editor rights export --project .\workspace\demo --target commercial_ad --output .\workspace\demo\exports\release.json
python -X utf8 -m ai_ad_editor rights impact --project .\workspace\demo --asset-id <asset_id>
python -X utf8 -m ai_ad_editor rights decide --project .\workspace\demo --asset-id <asset_id> --action replace --replacement-asset-id <replacement_asset_id> --status approved --reason "replace historical usage"
python -X utf8 -m ai_ad_editor rights apply --project .\workspace\demo --decision-id <decision_id>
python -X utf8 -m ai_ad_editor quality golden --project .\workspace\demo --input .\workspace\demo\renders\ad.mp4 --mode capture --require-audio --expensive
python -X utf8 -m ai_ad_editor quality golden --project .\workspace\demo --input .\workspace\demo\renders\ad.mp4 --mode verify --require-audio --expensive
```

渲染前要为可发布素材补齐 Rights Ledger；没有许可证、来源和允许用途的素材会被发布门禁阻断。当前 Rights Ledger 0.2.0 支持不可变修订、模板/父资产依赖闭包、哈希校验、批量修订、撤下/争议/过期状态、渠道校验、历史影响报告、非破坏性的历史成片 replace/delete 决策、决策审批/撤销链、替代资产依赖门禁、已批准处置发布阻断、本地 `rights apply` 当前项目变更、审计历史和确定性发布清单。素材库 `0.3.0` 的增量刷新、感知候选和复核边界见 [`docs/specs/本地素材库增量刷新与感知候选契约_v0.1_2026-10-14.md`](docs/specs/本地素材库增量刷新与感知候选契约_v0.1_2026-10-14.md)。模板变量支持类型、枚举、数值/字符串范围、默认值和字符串内嵌替换，模板操作支持追加、更新/替换/删除片段、轨道和标记，并把解析后的变量写入 `template_snapshot`；具体边界见 [`docs/specs/广告模板变量契约_v0.1_2026-10-14.md`](docs/specs/广告模板变量契约_v0.1_2026-10-14.md)。队列状态文件位于项目 `operations/render-queue.json`；项目写命令使用 `operations/project-write.lock`，冲突返回 `PROJECT_WRITE_LOCKED`，元数据事务日志位于 `operations/project-transaction.json`，可通过 `project recover` 恢复中断写入；`queue cancel` 在锁被占用时写入原子取消标记并返回已递交/待确认状态。失败或取消作业需要显式 `queue run --job-id ID` 重试。完整命令契约见 [`docs/specs/AgentCLI契约_v0.1_2026-10-13.md`](docs/specs/AgentCLI契约_v0.1_2026-10-13.md)，事务状态机见 [`docs/specs/跨文件项目事务恢复契约_v0.1_2026-10-15.md`](docs/specs/跨文件项目事务恢复契约_v0.1_2026-10-15.md)，队列状态机见 [`docs/specs/本地渲染队列与任务状态契约_v0.1_2026-10-14.md`](docs/specs/本地渲染队列与任务状态契约_v0.1_2026-10-14.md)，并发与取消语义见 [`docs/specs/本地项目写锁与取消通道契约_v0.1_2026-10-14.md`](docs/specs/本地项目写锁与取消通道契约_v0.1_2026-10-14.md)，实现入口见 [`docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md`](docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md)。

## 目录

| 路径 | 用途 |
|---|---|
| [`product/`](product/) | Agent CLI、项目领域模型、FFmpeg 渲染器和测试 |
| [`skills/`](skills/) | 可编辑的本地 `video-cut-*` Skills |
| [`sources/`](sources/) | 上游仓库快照、ZIP、提交和许可证证据 |
| [`research/`](research/) | 开源社区调研、Skill 审计和上游证据脚本 |
| [`docs/`](docs/) | 产品需求、架构、规范、路线图和验收记录 |
| [`ai-ad-editor.ps1`](ai-ad-editor.ps1) | 原生 Windows CLI 包装入口 |
| [`register-video-cut-skills.ps1`](register-video-cut-skills.ps1) | 建立本地 Skill 发现目录联接 |
| [`enable-auto-push.ps1`](enable-auto-push.ps1) | 安装 Git 提交后自动推送钩子 |

项目文档统一放在 `docs/`；新增需求、架构、研究结论和验收记录应先更新对应文档，再修改代码或 Skill。

## 主要能力

自动字幕流水线还提供 `subtitle transcribe`：可选择显式本地 Transformers 模型目录或 FFmpeg `whisper.cpp` 模型文件，生成项目内 SRT；使用 `--apply` 时会在源素材已有 Rights Ledger 记录的前提下登记派生字幕资产、创建独立字幕轨道片段、快照、校验和操作记录。模型不会自动下载，FFmpeg Whisper 只有在本机构建暴露 `whisper` 滤镜时才运行，具体边界见 [`docs/specs/本地AI适配器与字幕流水线规范_v0.1_2026-10-13.md`](docs/specs/本地AI适配器与字幕流水线规范_v0.1_2026-10-13.md)。

当前渲染器覆盖多轨时间线、裁切/滑移/涟漪编辑、静态和 cubic Bezier 关键帧、12 项本地关键帧运镜预设（`motion list/inspect/apply`，含别名和参数边界）、本地对象跟踪到目标画幅的 `media reframe` 动态裁切、将跟踪结果绑定到独立文字/贴纸/效果片段的 `media track-bind`、`media smart-cut` 静音与字幕短语裁切计划、`media beat-cut` 本地能量节拍卡点混剪计划、`media multicam` 本地多机位音频偏移估计与固定/显式机位切换计划、`media stabilize` 基于本地 `vidstabdetect`/`vidstabtransform` 的两遍防抖派生资产、倒放与反向速度曲线段反射、任意位置视频定格、默认同点音频静音插入、常用 FFmpeg xfade 转场（含连续片段的显式 `auto_handle`）、独立文字轨道与视频轨道按 `track.order` 统一层级排序、图层锚点定位、文字片段的缩放/旋转/透明度关键帧、遮罩、混合、fade/dissolve 透明层转场和 slide/wipe 空间转场、纯文字画布与本地透明层旋转、字幕动画与高级 drawtext 样式、字体 advance width 换行和源文本逐字时间匹配、固定点数路径/多边形遮罩、line/cubic 曲线控制点关键帧、动态 feather、blend、动态 crop、序列级全局和局部区间调节层、项目内 LUT3D（`.cube/.3dl/.csp/.dat`）及可审计的 `lut register/list/inspect` 资产库、`.cube` 静态 `intensity` identity 混合缓存、效果参数逐帧关键帧、通过 `effects list/inspect` 可发现的 45 项本地 FFmpeg 效果目录（含 HSL、RGB 曲线、三向色轮、曝光、色阶、曲线、降噪、时域混合、镜头校正、框线、去闪烁和本地 `minterpolate` 光流补帧）、音频轨道的 mute/solo/volume/pan/role 控制、片段音量/声像自动化、降噪/压缩/均衡/响度/旁白闪避、多画布输出、10-bit 像素格式、WebM `yuva420p` 透明画布、显式本地 HDR tone map、FFmpeg 内置 flite ASCII/英文离线 TTS、色彩元数据、确定性本地素材 token/字幕侧车搜索、SHA-256 精确重复组、stat 签名增量刷新、可选 FFmpeg `ahash-v1` 感知候选、项目内 JSON 渲染队列、无 GUI 的 waveform/vectorscope/histogram 色彩审查图、固定质量 golden 清单和 JSONL 进度/取消/安全恢复。

`media stabilize` 会把稳定化视频登记为项目派生资产并继承父素材权利；它不自动修改时间线，执行前应先 dry-run，执行后检查防抖报告和质量门禁。参数、快照、两遍 FFmpeg 流程和质量边界见 [`docs/specs/本地视频防抖与稳定化派生素材契约_v0.1_2026-10-15.md`](docs/specs/本地视频防抖与稳定化派生素材契约_v0.1_2026-10-15.md)。

`media beat-cut` 会用本地 FFmpeg 音频能量峰值生成卡点混剪计划，并可将已登记的本地视频素材按节拍写入视频轨道；默认只生成报告，`--apply` 才创建 `before-beat-cut` 快照并应用。它不声称音乐语义理解，节拍不足、源素材复用或慢放都会进入报告和 JSON warning。参数、源范围、重叠门禁和验收边界见 [`docs/specs/本地节拍卡点与混剪时间线契约_v0.1_2026-10-15.md`](docs/specs/本地节拍卡点与混剪时间线契约_v0.1_2026-10-15.md)。

广告工作流还提供本地 `ad plan` / `ad apply`：先从 brief 生成阶段和标记，再在快照、项目校验和重复标记门禁下写入序列，便于 Agent 继续用模板和素材库完成换料；契约见 [`docs/specs/广告计划与时间线应用契约_v0.1_2026-10-15.md`](docs/specs/广告计划与时间线应用契约_v0.1_2026-10-15.md)。

关键帧运镜目录和独立应用入口见 [`docs/specs/关键帧运镜预设契约_v0.1_2026-10-15.md`](docs/specs/关键帧运镜预设契约_v0.1_2026-10-15.md)：Agent 可先用 `motion list/inspect` 获取本地预设，再用 `motion apply` 以快照、校验和操作记录的方式写入片段关键帧。

智能剪口播入口见 [`docs/specs/本地智能剪口播与静音裁切契约_v0.1_2026-10-15.md`](docs/specs/本地智能剪口播与静音裁切契约_v0.1_2026-10-15.md)：Agent 可先执行 `media smart-cut --dry-run` 生成可审计计划，再用 `--apply` 在 `before-smart-cut` 快照后同步切片直接媒体视频片段和显式指定的音频片段；除本地 `silencedetect` 外，可通过项目内 SRT/VTT/ASS/SSA/TTML 与重复的 `--remove-phrase` 指定明确短语，按整条字幕 cue 生成可审计删除区间。该规则是词法匹配，不猜测逐词时间，也不宣称语义理解；嵌套序列、speed curve 与 freeze 片段仍会结构化拒绝。

多机位入口见 [`docs/specs/本地多机位同步与切换契约_v0.1_2026-10-15.md`](docs/specs/本地多机位同步与切换契约_v0.1_2026-10-15.md)：`media multicam` 先用本地 FFmpeg/NumPy 音频特征估计相对偏移，再用 `--switch-seconds` 或显式本地 JSON 生成切换计划；`--apply` 创建 `before-multicam` 快照并写入直接媒体片段。它不把低置信度音频互相关描述成视觉自动导演，必须复核 `score`、偏移和报告 warning。

自动重构图入口见 [`docs/specs/本地自动重构图与对象跟踪应用契约_v0.1_2026-10-15.md`](docs/specs/本地自动重构图与对象跟踪应用契约_v0.1_2026-10-15.md)：Agent 可把本地模板跟踪转换为目标画幅的 `crop.x/y/width/height` 关键帧，应用前检查置信度、主体越界警告和 `before-reframe` 快照；嵌套、变速和倒放片段会结构化拒绝。

跟踪绑定入口见 [`docs/specs/本地跟踪绑定与对象锚定契约_v0.1_2026-10-15.md`](docs/specs/本地跟踪绑定与对象锚定契约_v0.1_2026-10-15.md)：Agent 可把本地模板跟踪的归一化位置和可选 ROI 尺寸映射到独立文字、贴纸或效果片段，先 dry-run，再用 `--apply` 创建 `before-track-bind` 快照、报告、provenance、操作记录和项目校验。目标必须是视觉片段；音频片段和嵌套序列会结构化拒绝，源跟踪时钟到目标片段时长的映射和模板漂移会保留 warning。

字幕入口支持 SRT、VTT、ASS/SSA 与本地 TTML/DFXP 时码，`subtitle validate/normalize` 会拒绝外部实体、负时码和缺少结束时间的 cue，并统一输出项目内 SRT。

所有不确定能力通过 `capabilities` 清单和渲染 warning 披露。运行：

```powershell
python -X utf8 -m ai_ad_editor capabilities
python -X utf8 -m ai_ad_editor library index --root .\library --output .\work\library.json
python -X utf8 -m ai_ad_editor library search --catalog .\work\library.json --query "product launch" --kind video --has-audio
python -X utf8 -m ai_ad_editor library duplicates --catalog .\work\library.json
python -X utf8 -m ai_ad_editor library index --root .\library --output .\work\library.json --previous .\work\library.json --incremental --visual-hash
python -X utf8 -m ai_ad_editor library similar --catalog .\work\library.json --max-distance 12
python -X utf8 -m ai_ad_editor lut register --project .\work\demo --input .\looks\warm.cube --lut-id lut_warm --license-spdx CC0-1.0 --verification-status verified
python -X utf8 -m ai_ad_editor lut list --project .\work\demo
python -X utf8 -m ai_ad_editor lut inspect --project .\work\demo --lut-id lut_warm
# 在效果参数中使用：{"type":"lut3d","parameters":{"lut_id":"lut_warm","intensity":0.5}}
python -X utf8 -m ai_ad_editor quality scopes --project .\work\demo --input .\work\demo\renders\ad.mp4 --at-seconds 1.25
python -X utf8 -m ai_ad_editor quality golden --project .\work\demo --input .\work\demo\renders\ad.mp4 --mode verify --require-audio
```

## 验证

```powershell
$env:PYTHONPATH = "$(Get-Location)\product\src"
$env:AI_AD_EDITOR_RUNTIME_DIR = "$(Get-Location)\product\.runtime"
python -X utf8 -m compileall -q product\src product\tests
python -X utf8 -m unittest discover -s product\tests -v
python -X utf8 research\audit_video_cut_skills.py
```

运行时临时文件、模型目录、Python 字节码和库缓存固定在 `product/.runtime/`，不写回 C 盘旧路径。当前 `doctor` 应报告 `network=disabled`、`docker_or_wsl_started=false`、`jianying_runtime_enabled=false`；`policy audit` 应报告项目产物无远程引用。

## Git 发布约定

主分支为 `main`，远端为 `origin`：

```text
git@github.com:Tonscriptions/agent-video-kit.git
```

首轮初始化推送使用：

```powershell
git push -u origin main --force
```

后续提交后执行 `git push origin main`。运行 `.\enable-auto-push.ps1` 会安装原生 Git `post-commit` 钩子，让后续在 `main` 分支上的成功提交自动推送；钩子不会在其他分支或未配置 `origin` 时强行推送。也可以直接执行 [`git-auto-push.ps1`](git-auto-push.ps1)。

自动推送仍受 GitHub SSH 凭据、网络和远端保护规则约束；推送失败会保留本地提交并返回错误，不会删除或重写工作区文件。

## 约束与路线

根目录 [`AGENTS.md`](AGENTS.md) 是本地工作区约束。产品需求、能力差异、Concat/FFmpeg 评估、开源素材版权和剪映项目互操作边界均已归档在 [`docs/README.md`](docs/README.md)。当前工作区迁移记录见 [`docs/工作区迁移记录_2026-10-13.md`](docs/工作区迁移记录_2026-10-13.md)。

