# Agent CLI 契约 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-CLI-001 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-14 |
| 状态 | 有效 |
| 运行根目录 | `E:\dev\sandbox\AI广告剪辑` |
| 关联规范 | [Agent Project JSON](./AgentProjectJSON规范_v0.1_2026-10-13.md)、[机器 Schema](./agent-project.schema.json)、[产品实现入口](../产品实现入口与P0使用说明_v0.1_2026-10-13.md) |

## 1. 目标与硬约束

CLI 是面向 Agent 的唯一首版控制面。每个写操作都接收结构化参数，输出机器可解析的 JSON envelope，并把项目变更、渲染清单、验证报告和 provenance 留在项目目录内。运行时使用原生 Windows、Python 和本机 FFmpeg；默认关闭网络，不启动 Docker、WSL、容器、GUI 或剪映/Jianying 私有运行时。

CLI 不会自动下载模型、素材、插件或字体。需要本地模型时必须传入已经存在的模型目录；需要外部项目时由显式 `convert import` 处理，并生成能力映射报告。

## 2. 通用参数和输出 envelope

所有叶子命令都支持：

| 参数 | 语义 |
|---|---|
| `--format json\|text` | 默认 `json`；`text` 只改变 JSON 缩进，不改变字段语义 |
| `--request-id ID` | 调用方请求 ID；省略时由 CLI 生成 |
| `--idempotency-key KEY` | 项目写操作的幂等键；相同请求重放原 envelope，不同请求复用同键返回冲突 |
| `--dry-run` | 执行参数、路径和校验计划，不写项目、报告、快照或最终媒体 |
| `--no-network` | 默认启用；保留该开关用于显式表达调用策略 |
| `--progress none\|jsonl` | 长任务可输出 JSONL 进度事件到 stderr；默认不输出事件 |

成功、计划和失败都返回以下 envelope：

```json
{
  "ok": true,
  "command": "project.migrate",
  "request_id": "req_...",
  "operation_id": "op_...",
  "status": "succeeded",
  "data": {},
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "provenance": {
    "cli_version": "0.1.0",
    "schema_version": "0.1.0",
    "engine_version": "ffmpeg-local",
    "network": "disabled"
  }
}
```

`status` 使用 `succeeded`、`planned`、`partial`、`failed` 或 `cancelled`。`ok` 只在 `succeeded` 或 `planned` 时为 `true`。警告不会替代失败；近似效果必须进入 `warnings`，不允许静默声称精确等效。

## 3. 命令表

| 命令 | 主要输入 | 主要输出和副作用 |
|---|---|---|
| `project init PATH` | 项目目录、名称和可选 ID | 创建 `project.json`、`rights-ledger.json`、`project.lock.json`、`operations/project-write.lock`、`assets/`、`renders/`、`validation/`、`history/` 等目录 |
| `project inspect --project PATH` | 项目目录 | 项目摘要、资产/序列计数、schema 和能力提示 |
| `project snapshot --project PATH [--label LABEL]` | 当前项目 | 在 `history/` 写入自包含项目、Rights Ledger 和锁文件快照 |
| `project restore --project PATH --snapshot ID_OR_PATH` | 已有快照 | 恢复前先创建 `before-restore` 快照；候选快照必须先通过 schema/语义校验 |
| `project migrate --project PATH [--report NAME]` | `0.0.0` 或 `0.1.0` 项目 | 已知旧形状补默认字段、补本地资产哈希/探测、记录迁移链；写入前创建 `before-migrate` 快照并写 `validation/*.json` 报告 |
| `project recover --project PATH` | 项目内 `operations/project-transaction.json` | 恢复上次中断的项目元数据事务；`prepared` 回滚、`committed` 清理、无日志返回 `clean`；`--dry-run` 只报告 |
| `media ingest --project PATH --input FILE` | 本地媒体、权利和许可证参数 | 复制到项目 `assets/`，写 probe、内容哈希、Rights Ledger 和资产 provenance |
| `media stabilize --project PATH (--asset-id ID\|--input FILE)` | 本地视频和受控 `vidstab` 参数 | 先 dry-run 检查两遍 FFmpeg 计划；正式执行创建 `before-stabilize` 快照、生成项目内防抖派生视频、继承或登记 Rights Ledger、写验证报告和操作记录；不自动改写时间线 |
| `media understand --project PATH (--asset-id ID\|--input FILE)` | 本地视频/音频 | FFmpeg 场景、静音、节拍结果；`--transcribe` 可选择本地 Transformers 模型或 FFmpeg `whisper.cpp` 模型，模型不会自动下载；可选写入项目内 SRT |
| `media prepare --project PATH (--asset-id ID\|--input FILE)` | 本地素材 | 生成项目内代理、缩略图和波形，并写入资产记录 |
| `media highlights --project PATH (--asset-id ID\|--input FILE)` | 本地理解结果；可选 `--beats`、`--top-k`、`--min-duration`、`--max-duration` | 本地启发式高光候选报告，不调用在线推荐服务；加 `--apply --asset-id ID --track-id ID` 时按源时间顺序写入已登记视频轨道，应用前创建 `before-highlights` 快照、执行交叠门禁和项目校验；`--replace-track` 才允许清空目标轨道 |
| `media beat-cut --project PATH (--audio-asset-id ID\|--input FILE) --source-asset-id ID --track-id ID` | 本地音频节拍证据、一个或多个已登记视频资产、节拍区间和源选择策略 | 使用本地 FFmpeg 能量峰值生成卡点计划；默认只写 `validation/beat_cut_*.json`，`--apply` 在 `before-beat-cut` 快照、重叠检查和项目校验后写入视频轨道并记录操作；`--replace-track` 才允许清空目标轨道，能量峰值和慢放复用必须保留警告 |
| `media multicam --project PATH --source-asset-id ID --source-asset-id ID` | 两个或以上含视频/音频流的本地机位资产、参考机位、互相关参数和可选切换计划 | 用本地 FFmpeg PCM + NumPy 能量特征估计各机位相对偏移；`--switch-seconds` 或本地 `--switch-plan` 生成可审计直接媒体片段；`--apply` 在 `before-multicam` 快照、轨道重叠检查和项目校验后写入；不宣称视觉自动导演 |
| `audio extract --project PATH (--asset-id ID\|--input FILE)` | 本地视频/音频、可选 WAV 参数和目标 audio 轨道 | 用本地 FFmpeg 提取第一条音频流为项目内 PCM WAV 派生资产；正式执行创建 `before-audio-extract` 快照、继承/登记 Rights Ledger，并可用 `--apply --track-id` 写入音频轨道；dry-run 不写入；不宣称人声/背景声 AI 分离 |
| `audio separate --project PATH (--asset-id ID\|--input FILE)` | 本地视频/音频、center/side 两个输出资产、可选采样率和目标 audio 轨道/stem | 用本地 FFmpeg `pan` 做 mid/side 声道相位近似，生成 center mono 与 side stereo WAV；正式执行创建 `before-audio-separate` 快照、两个派生 Rights Ledger 记录并可用 `--apply --track-id --stem` 写入一个 stem；dry-run 不写入；不宣称模型级源分离 |
| audio adapter register/list/inspect --project PATH | 已存在的本地模型文件/目录、可选执行器、许可证和证据 | 登记或检查 models/audio-adapters.json；保存确定性模型/执行器哈希、Rights Ledger model-adapter 记录、network=disabled 和 before-audio-adapter-register 快照；未知 runner 只登记 metadata，audio separate --adapter-id 会结构化拒绝，不静默 fallback |
| media adapter register/list/inspect --project PATH | 已存在的本地视觉模型文件/目录、argv-only 执行器、许可证和证据 | 登记或检查 models/visual-adapters.json；保存确定性模型/执行器哈希、Rights Ledger model-adapter 记录、network=disabled 和 before-media-adapter-register 快照；支持 command-json-tracking-v1 单目标和 command-json-tracking-multi-v1 多目标 runner，未知 engine 不执行 |
| `media smart-cut --project PATH --track-id ID --clip-id ID` | 直接媒体片段、FFmpeg 静音检测参数、可选项目内字幕和显式 `--remove-phrase`、联动轨道 | 合并本地 `silencedetect` 与字幕 cue 粒度的短语删除区间生成计划；`--apply` 在 `before-smart-cut` 快照后切片视频/音频片段、关键帧和时间线；默认不写回；短语匹配不宣称语义理解 |
| `media relink --project PATH --search-root DIR` | 丢失资产和本地搜索目录 | 优先内容哈希精确重链接；`--match-by-name` 仅允许唯一文件名近似匹配并生成报告 |
| `media track --project PATH ... --roi X,Y,W,H [--adapter-id ID] [--object-id ID\|--all-objects]` | 本地视频、归一化 ROI、可选已登记视觉适配器 | 默认本地模板匹配；v1 runner 校验单目标框，v2 runner 校验唯一 `object_id` 轨迹；`--object-id` 选择一个对象生成可应用关键帧，`--all-objects` 只生成报告且不能与 `--clip-id` 联用；`--clip-id` 写回前创建快照 |
| `media track-bind --project PATH (--asset-id ID\|--input PATH) --roi X,Y,W,H --target-clip-id ID --target-track-id ID [--adapter-id ID] [--object-id ID]` | 本地跟踪源、归一化 ROI、独立视觉目标片段、可选视觉适配器 | 将模板、v1 或选定的 v2 对象关键帧映射到独立文字/贴纸/效果片段，可选 ROI 相对缩放；v2 必须指定 `--object-id`；`--apply` 在 `before-track-bind` 快照后写回，音频和嵌套序列目标结构化拒绝 |
| `media reframe --project PATH --asset-id ID --roi X,Y,W,H --clip-id ID --track-id ID [--adapter-id ID] [--object-id ID]` | 本地视频、目标画幅和直接媒体片段、可选视觉适配器 | 将模板、v1 或选定的 v2 对象跟踪转换为归一化 `crop.*` 动态关键帧；v2 必须指定 `--object-id`；`--apply` 在 `before-reframe` 快照后写回，变速/倒放/嵌套片段结构化拒绝 |
| `ad plan --project PATH --input BRIEF.json` | 本地广告 brief 和可选分析报告 | 写入钩子、卖点、证明、CTA 的节拍计划和序列标记 |
| `subtitle validate --input FILE` | SRT/VTT/ASS/SSA/TTML | 解析、时长、顺序和重叠报告；TTML 只接受本地时钟/offset 语法并拒绝外部实体 |
| `subtitle normalize --input FILE --output FILE` | 字幕文件 | 通过校验后规范化为 SRT；项目模式下输出必须位于项目内 |
| `subtitle transcribe --project PATH (--asset-id ID\|--input FILE) --model-path PATH` | 本地音视频、显式离线 ASR 模型、可选字幕轨道 | 使用 Transformers 或 FFmpeg `whisper.cpp` 生成时间戳 SRT；`--apply` 继承已登记源素材权利，创建字幕资产、独立字幕片段、快照、校验和操作记录；无源资产权利时拒绝应用 |
| `tts synthesize --project PATH (--text TEXT\|--input FILE)` | 默认 flite 英文，或 `--adapter-id` + `--voice-id` 选择本地 SoulX 中文 | 生成项目 assets 内 WAV 并登记音频资产；可用 `--apply --track-id` 入轨；支持 dry-run、哈希、快照、事务、幂等与权利依赖 |
| `tts adapter register/list/inspect` | 显式 Python、源码、依赖、完整模型、tokenizer 和证据 | 项目内模型登记/完整性核验；CUDA + HF/BF16，无下载或在线回退 |
| `tts voice register/list/inspect` | 已登记参考音频、原样 UTF-8 逐字稿和本地授权/来源证据 | 声线登记、哈希核验、源权利依赖；默认未核验 |
| `effects list [--query TEXT] [--keyframable-only]` | 可选效果 ID、别名、类别或后端筛选 | 返回本地 FFmpeg 效果目录、参数范围、关键帧能力、限制和目录版本；只读、无网络 |
| `effects inspect --name NAME` | 效果 ID 或别名 | 返回单个效果的规范 ID、FFmpeg 后端、参数契约和限制；未知名称返回 `ARGUMENT_INVALID` |
| `motion list [--query TEXT]` | 可选预设 ID、别名、类别或说明筛选 | 返回本地关键帧运镜预设目录、受控参数、目标属性、限制和目录版本；只读、无网络 |
| `motion inspect --name NAME` | 预设 ID 或别名 | 返回单个预设的规范 ID、关键帧属性、参数上下界和限制；未知名称返回 `ARGUMENT_INVALID` |
| `motion apply --project PATH --clip-id ID --preset NAME` | 已有片段、可选轨道/序列、局部 tick 区间和预设参数 | 在变更前创建快照，将预设写成普通项目关键帧，执行 Schema/语义校验并记录 `motion.apply` 操作；`--dry-run` 只返回计划 |
| `timeline compose --project PATH --input CHANGES.json` | 变更集 | 写入轨道、片段、标记、关键帧、嵌套序列、速度曲线和剪辑操作；写入前快照并再次校验 |
| `validate --project PATH` | 项目和目标渠道 | 机器 Schema、时间/引用/权利/效果语义校验报告 |
| `rights check --project PATH` | 项目 Rights Ledger | 检查目标渠道发布资格；严格失败退出码为 7 |
| `rights list --project PATH [--status STATUS]` | 当前项目 Rights Ledger | 列出每个资产的有效记录、版本、状态和许可字段 |
| `rights history --project PATH --asset-id ID` | 资产 ID | 返回不可变修订链、审计事件、全部历史处置决策和当前有效决策；不存在时返回 `RIGHTS_RECORD_MISSING` |
| `rights update --project PATH --asset-id ID --reason TEXT` | 本地 JSON patch 或字段参数 | 创建新版本并保留旧证据；写入前快照；恢复阻断状态必须 `--reopen` 与新证据 |
| `rights export --project PATH --target CHANNEL --output FILE` | 项目 Rights Ledger 和资产哈希 | 写入项目内确定性发布清单；门禁失败仍产出清单并返回退出码 7 |
| `rights batch-update --project PATH --input FILE` | `{updates:[{asset_id,patch,reason,actor,reopen}]}` 本地 JSON | 预检全部修订后一次快照、原子写入多个资产版本；任一项失败则不写入 |
| `rights impact --project PATH --asset-id ID` | 本地项目 JSON/JSONL 产物 | 查找导出、渲染、操作、校验和快照中仍引用资产的历史影响清单 |
| `rights retract --project PATH --asset-id ID --reason TEXT` | 撤下/争议/阻断状态与原因 | 创建不可变撤回版本，并返回受影响历史产物；不删除成片文件 |
| `rights decide --project PATH --asset-id ID --action replace\|delete\|retain --reason TEXT [--supersedes-decision-id ID]` | 历史成片处置决策、可选替代资产和 `proposed\|approved\|cancelled` 状态 | 追加非破坏性决策与影响清单；状态变更必须指向当前决策；已批准 replace/delete 对当前项目发布返回 `RIGHTS_DISPOSITION_BLOCKED` |
| `rights apply --project PATH --decision-id ID` | 当前项目和一个有效的已批准 replace/delete 决策 | 写入前快照，替换或移除时间线引用和项目资产，结构校验后记录 apply 事件；历史导出与媒体文件保持不变 |
| `render --project PATH` | 已验证项目和输出规格 | 本地 FFmpeg 渲染、manifest、操作记录和原子最终媒体 |
| `queue enqueue --project PATH --input JOBS.json` | 单个作业或 `{jobs:[...]}` | 原子写入项目 `operations/render-queue.json`，保存输出规格和初始 `pending` 状态 |
| `queue list --project PATH [--status STATUS]` | 项目队列和可选状态 | 只读返回队列计数与作业状态 |
| `queue inspect --project PATH --job-id ID` | 作业 ID | 只读返回作业、尝试次数、警告、错误和关联操作 |
| `queue run --project PATH [--job-id ID] [--workers N]` | 待处理作业或显式重试作业 | 默认顺序执行本地渲染；`--workers N` 可启用有界本地 FFmpeg worker 并发，N 大于 1 时必须同时提供 `--continue-on-error`；保存 `pending/running/succeeded/failed/cancelled`，可用 `--max-jobs` 控制批次 |
| `queue cancel --project PATH --job-id ID` | 待处理或运行中作业 | 锁空闲时待处理作业立即标记取消；锁被占用或作业运行中时原子写入取消标记并返回 acknowledged/confirmed |
| `quality check --project PATH --input FILE` | 已渲染媒体 | 画布、流、时长、音画差、可选黑帧、LUFS 和 true peak 报告 |
| `quality scopes --project PATH --input FILE` | 项目内或本地视频、抽帧时间点 | 生成本地 waveform/vectorscope/histogram PNG 和带哈希的 scope 报告；不自动判定调色正确性 |
| `quality golden --project PATH --input FILE --mode capture\|verify` | 本地媒体和项目内 golden JSON | 捕获固定输出哈希、settings 哈希、质量指标和容差；验证时返回字节、settings、质量和指标漂移，不修改媒体 |
| `convert import --input FILE --output DIR [--strict]` | Agent JSON、项目包 ZIP、OTIO JSON、Kdenlive XML 或明文草稿 JSON | 新建本地项目与转换报告；项目包验证 manifest/路径/SHA-256；草稿候选通过校验后发布，`--strict` 仅用于草稿损失拒绝 |
| `convert export --project PATH --output FILE --target-format FORMAT [--strict]` | 本地项目 | 导出 `agent-json/package/otio/kdenlive-xml/jianying-draft-json`；草稿附带报告和源项目旁车，严格门禁失败不覆盖已有输出；项目包排除 renders/cache/operations/history |
| `template apply --project PATH --input TEMPLATE.json` | 本地模板和变量 | 变量校验、片段实例化、模板快照和 provenance 变更记录 |
| `template batch --project PATH ...` | 模板、variants 和输出目录 | 隔离实例并批量渲染；写批量报告，可选择继续失败项 |
| `library index --root DIR --output FILE [--previous FILE --incremental] [--visual-hash]` | 本地媒体/字体/字幕目录 | 生成 `0.3.0` 目录：哈希、probe、确定性 token、同 stem 字幕侧车、许可证状态；可按 stat 签名增量刷新或生成 FFmpeg 平均哈希样本 |
| `library search --catalog FILE` | 目录索引、词组和媒体属性过滤 | 按确定性分数返回可审计匹配资产；支持时长、分辨率、音频流和精确重复过滤 |
| `library duplicates --catalog FILE` | 已生成的目录 | 按 SHA-256 返回字节完全相同的素材组；不会把相似或转码文件误报为重复 |
| `library similar --catalog FILE [--max-distance N]` | 含 `--visual-hash` 样本的目录 | 按 `ahash-v1` 汉明距离返回画面相似候选组；没有样本时返回结构化警告，不将空结果解释为无相似素材 |
| `policy audit --project PATH` | 项目 JSON/JSONL 产物 | 只读审计远程/闭源服务引用；违规返回 `POLICY_REMOTE_REFERENCE` |
| `doctor` | 本机环境 | 只读取 Python、FFmpeg、FFprobe、Docker/WSL PATH；绝不启动虚拟化环境 |
| `operation inspect --project PATH --operation-id ID` | 操作 ID | 读取可重连的操作状态、进度和产物清单 |
| `version` / `capabilities` | 无 | 版本、引擎、网络策略和 test-backed 本地能力清单 |

## 3.1 本地模型适配器登记与执行门禁

audio adapter register 只接受已存在的本地模型/执行器路径；它不会下载、复制或在登记阶段执行模型。目录按相对路径、大小和文件 SHA-256 形成稳定哈希，正式登记写入 models/audio-adapters.json、Rights Ledger 和 before-audio-adapter-register 快照。audio adapter list/inspect 只读检查路径与哈希。ffmpeg-local-mid-side-v1 与 `command-json-v1` 是当前可执行 runner；后者通过 `agent-video-audio-separation-v1` 的 stdin/stdout JSON 协议生成约定的 center/side WAV，并拒绝 `.cmd/.bat` shell wrapper。Demucs、UVR、Open-Unmix 和 ONNX 专用 engine 仍只能登记，尚无对应 runner 时 audio separate --adapter-id 返回 AUDIO_SEPARATION_ADAPTER_UNAVAILABLE（退出码 10），禁止隐式回退或网络调用。command-json runner 的输出仍需质量 golden 和 Rights Ledger 复核。详细字段见本地模型适配器注册与音频分离门禁契约。

media adapter register 使用同样的本地路径、许可证、哈希和 Rights Ledger 规则，但写入 `models/visual-adapters.json`。`command-json-tracking-v1` 通过 `agent-video-object-tracking-v1` 的单个 stdin/stdout JSON 请求返回归一化框和 confidence；`command-json-tracking-multi-v1` 通过 v2 返回带唯一 `object_id` 的多个轨迹。CLI 拒绝 shell wrapper、协议不匹配、超时、过大 stdout、越界/非单调帧、重复身份和哈希变化，并在 `media track`、`track-bind`、`reframe` 中保留外部 runner 复核 warning。模型质量、遮挡恢复、旋转框、多目标身份和视觉 golden 不由 registry 自动证明。详细字段见[本地视觉模型适配器与对象跟踪协议契约](./本地视觉模型适配器与对象跟踪协议契约_v0.1_2026-10-15.md)和[本地多目标视觉跟踪与对象选择协议契约](./本地多目标视觉跟踪与对象选择协议契约_v0.1_2026-10-15.md)。

### 3.1.1 多目标对象选择门禁

v2 适配器执行 `media track` 时必须显式选择 `--object-id ID` 或 `--all-objects`。前者返回一个对象的顶层 `frames/keyframes`，可以与 `--clip-id` 联用；后者保留所有对象报告，只用于 Agent 复核，不能与 `--clip-id` 联用。`track-bind` 和 `reframe` 始终要求 `--object-id`，避免多个对象轨迹混入单个文字层或单个裁切窗口。缺少选择返回 `TRACK_OBJECT_SELECTION_REQUIRED`，对 v1/模板 runner 使用选择参数返回 `TRACK_OBJECT_SELECTION_UNSUPPORTED`，runner 缺少指定对象返回 `TRACK_OBJECT_NOT_FOUND`。完整请求/响应字段、身份唯一性和质量边界见[本地多目标视觉跟踪与对象选择协议契约](./本地多目标视觉跟踪与对象选择协议契约_v0.1_2026-10-15.md)。

### 3.2 本地高光候选与自动粗剪

`media highlights` 先调用本地 `understand_media`，再由 `recommend_highlights` 按镜头、静音和可选节拍证据生成候选。默认模式只写项目内 JSON 报告；报告保留 `source_sha256`、`analysis`、`engine=local-heuristic`、`pipeline_engine=ffmpeg-local-highlight-heuristic-v1`、`network=disabled` 和候选源范围。

只有显式 `--apply` 才会修改时间线，并且必须同时提供项目内已登记 `--asset-id`、目标视频 `--track-id` 和非负 `--timeline-start-seconds`。候选按源时间顺序连续生成项目时基片段；已有轨道交叠返回 `HIGHLIGHTS_TRACK_OVERLAP`，只有 `--replace-track` 才能先清空轨道。应用前保存 `before-highlights` 快照，成功后写入报告、`provenance.change_log`、操作文件并重新校验项目。所有成功应用结果都带 `HIGHLIGHTS_HEURISTIC` 与 `HIGHLIGHTS_REVIEW_REQUIRED`，不能解释为语义高光、人物/物体理解或剪映智能导演。完整字段、报告版本、错误码和验收证据见[本地高光候选与自动粗剪时间线契约](./本地高光候选与自动粗剪时间线契约_v0.1_2026-10-15.md)。

### 3.3 本地明文草稿互操作

`convert import` 自动识别本地 `materials/tracks/canvas_config` 明文草稿。`convert export --target-format jianying-draft-json` 生成 `jianying-plaintext-v1` 文件轮廓；全程不调用剪映运行时、解密或在线资源。导入媒体和字体默认未核验权利，视频原声展开为显式关联音轨；未修改关联音轨导出合回视频，独立调音量或静音则保留独立音轨并关闭视频隐式原声。`--strict` 遇到 `Approximate/Baked/Unsupported/Failed` 返回 `CONVERSION_STRICT_REJECTED`、退出码 2；其他格式暂不支持该开关。best-effort 若有 `Failed`，即使保留了部分项目，也返回 `ok=false` 和退出码 2。字段、版本和产物边界见[明文草稿适配器契约](./本地明文草稿双向适配器契约_v0.1_2026-10-15.md)。

## 4. 项目迁移、快照和路径规则

`project migrate` 只接受当前项目已知的 `schema_version`：`0.0.0` 和 `0.1.0`。未知、高于当前版本或缺失版本必须返回 `SCHEMA_VERSION_UNSUPPORTED`，不得猜测字段、生成资产/序列/片段 ID 或静默覆盖原文件。

迁移候选由纯函数生成；CLI 只为缺失的本地资产计算 SHA-256 和 FFprobe 元数据。相对 `--report` 路径解析到项目的 `validation/` 目录；绝对路径也必须位于该目录内。候选通过机器 Schema 与语义校验后，才创建 `before-migrate` 快照并原子保存。重复迁移应是 no-op，不重复写项目或快照。

项目内报告、快照、渲染和转换产物必须位于项目根目录的受控子目录；越过项目根目录、网络 URI、缺少权利记录或未授权的外部路径必须返回结构化错误。历史文件只读，恢复和写入操作不会删除历史快照。合作式写入使用 `operations/project-transaction.json` 记录跨文件元数据事务；事务范围、状态机、恢复和大文件副作用边界见[跨文件项目事务恢复契约](./跨文件项目事务恢复契约_v0.1_2026-10-15.md)。

`policy audit` 和所有媒体/转换入口遵循[本地运行策略与远程引用审计契约](./本地运行策略与远程引用审计契约_v0.1_2026-10-14.md)。运行时只接受本地路径、`local://` 或 `file://`；研究文档中的公开 URL 不会被作为运行输入。

## 5. 时间线与关键帧契约

所有 `at_tick` 是片段内时间，使用项目 `settings.timebase.ticks_per_second`。关键帧必须单调递增，插值可用 `hold`、`linear`、`ease_in`、`ease_out`、`ease_in_out` 或带合法控制点的 `bezier`。

`timeline compose` 变更集支持 `append_clip`、`update_clip`、`remove_clip`、`split_clip`、`ripple_insert`、`ripple_delete`、`slip_clip`、`slide_clip`、`set_clip_speed`、`set_clip_speed_curve`、`reverse_clip`、`freeze_frame`、`add_sequence`、`append_sequence_clip`、轨道增删改、标记增删和序列时长调整。任何变更保存前都会重新执行 Schema、引用、时间范围、嵌套循环和 Rights 语义校验。

### 5.1 关键帧运镜预设

`motion` 是对 `timeline compose` 内部 `apply_motion_preset` 操作的 Agent 可发现封装。目录版本当前为 `0.1.0`，来源固定为 `local-catalog`，引擎固定为 `timeline-keyframes`，不下载模板或素材。当前目录包含 `zoom_in`、`zoom_out`、`pan_left/right/up/down`、`ken_burns`、`rotate_in/out`、`fade_in/out` 和 `shake` 共 12 个规范预设；旧式 `push_in`、`pull_out`、`slide_*`、`rotate_left/right`、`opacity_in/out` 为只读别名，写入操作返回规范 ID。

每个目录项至少包含 `id`、`aliases`、`category`、`engine`、`source`、`properties`、`parameters` 和 `limits`。`amount` 的范围为 `0..1`，`degrees` 的范围为 `-360..360`，`shake.points` 的范围为 `2..64`；缺省参数从目录默认值填充，非有限数字、越界值和未知预设在写入前返回 `ARGUMENT_INVALID`。`start_tick`/`end_tick` 始终是片段内时间，缺省覆盖整个片段，实际写入的关键帧会被限制在片段有效范围内。

典型调用：

```powershell
python -m ai_ad_editor motion list --query position
python -m ai_ad_editor motion inspect --name push-in
python -m ai_ad_editor motion apply --project .\work\demo --clip-id clip_001 --preset ken_burns --amount 0.2 --start-tick 0 --end-tick 90000
python -m ai_ad_editor motion apply --project .\work\demo --clip-id clip_001 --preset shake --points 12 --dry-run
```

`motion apply` 只生成 `transform.scale`、`transform.position.x/y`、`transform.rotation` 或 `transform.opacity` 关键帧，不生成媒体文件；成功写入会创建 `before-motion-apply` 快照、项目 `provenance.change_log` 项和 `operations/<operation_id>.json`。它提供可复现的 Agent 运镜基线，不等同于剪映的 GUI 运镜模板、自动构图或 GPU 特效；光流补帧由效果目录中的 `frame_interpolation` 独立声明。

`media stabilize` 运行本机 FFmpeg 的 `vidstabdetect` → `vidstabtransform` 两遍流程，输出 `assets/derived/` 下的新视频资产和 `validation/stabilization_<operation_id>.json` 报告。项目资产输入会继承当前有效父权利记录的许可证、允许用途、证据、渠道和撤下状态；外部本地输入必须显式提供同样的来源和许可证字段。稳定化结果不会自动插入时间线，质量检查必须关注裁切、黑边、残余抖动、场景切换和编码器差异；缺少 `libvidstab` 时返回结构化依赖错误。

`freeze_frame` 的 `at_tick` 以冻结前的片段时间线为基准，在视频流中插入 `duration_tick` 的冻结帧；片段总时长同步增加，原始画面在冻结点前后保持顺序。渲染器在已经完成源范围、变速曲线、倒放和裁切映射的视频流上分支并回接，因此中间定格与尾部定格使用同一语义；音频按项目的冻结时长补齐并继续接受音量、声像和淡出链。非法冻结对象、非正冻结时长或越过冻结前片段范围的 `at_tick` 在校验阶段拒绝。

`transition_in`/`transition_out` 的 `type` 可使用本机 FFmpeg xfade 目录（包括 `crossfade`、`dissolve`、方向 `wipe`/`slide`、`circlecrop`、`radial`、`pixelize`、`zoomin`、`cover*`、`reveal*`、`slice`、`wind` 和 `blur`）。默认需要相邻片段的重叠句柄；对时间线上相邻、没有重叠的片段，可以显式设置 `auto_handle: true` 或 `handle_policy: "auto"`。CLI 会用本地 xfade 执行并保持原时间线长度，尾部使用最后一帧填充，同时在 render manifest 返回 `RENDER_FEATURE_APPROXIMATE`。其他无法匹配的转场不会静默伪造。

图层变换支持 `transform.anchor.x/y` 或 `anchor_x/anchor_y`，取值为 `0..1`，默认 `(0.5,0.5)`；位置表达式会把该点放到 `transform.position`，同名片段关键帧可逐帧改变锚点。视频叶片旋转会补偿扩展边界以保持锚点，独立文字透明画布仍绕其画布中心；嵌套父级枢轴按叶片放置近似，并在 render manifest 中保留警告。

遮罩使用归一化参数。`rectangle/circle/ellipse` 支持几何标量、`invert`、`feather` 和 `mask.*` 关键帧；动态 feather 通过 alpha-only 软边表达式执行，范围为 `0..0.5`。`path/polygon` 可以使用固定点数 `points`，点坐标可以用 `points.0.x`、`points.0.y` 关键帧驱动；也可以使用 `segments`/`curve_segments`/`curves`，每段支持 `line` 或 `cubic`，cubic 的 `samples` 范围为 `2..16`，总采样点限制为 `3..32`，渲染器将曲线采样成固定多边形并以固定点边缘的内侧距离近似生成 alpha 软边。曲线段不能与 `points` 同时声明；曲线控制点可以使用片段或 mask 内局部关键帧，例如 `mask.segments.1.control1.x`、`mask.segments.1.control2.y`，渲染器在 FFmpeg `geq` 中先缓存控制点表达式再逐帧生成固定采样点。动态 feather 也可以用 `feather`/`mask.feather` 关键帧驱动。`transform.opacity`、正常层 `blend.opacity` 以及 RGB blend 的 `blend.opacity` 都可以用片段关键帧驱动；片段 `crop` 支持 `pixels`/`normalized` 单位和 `fit`/`fill`/`stretch` 模式，`crop.keyframes` 的 `x`/`y`/`width`/`height` 或片段级 `crop.x`/`crop.y`/`crop.width`/`crop.height` 可以逐帧移动和缩放裁切窗口；动态尺寸由 CPU `geq` 固定画布逆向采样保持输出帧尺寸稳定，宽高关键帧必须大于 0。非法点数、坐标、尺寸、时间或属性必须在写入前拒绝。静态嵌套父级 transform/effects/blend 会下推；多级父级动态 transform 关键帧按最终序列时钟合成，父级与子级多重 mask 会顺序合成 alpha，但不同坐标空间仍进入 `RENDER_FEATURE_APPROXIMATE`；reverse 下的关键帧插值同样保留近似警告。

## 6. 渲染、质量和进度

`render` 只接受项目内本地媒体和已验证计划。输出容器为 MP4、WebM 或 MKV；编码器由本机 FFmpeg 能力决定。渲染先写 `renders/.tmp/<operation_id>/`，成功后原子移动最终文件；失败、取消和输入哈希变化不会留下可发布的最终文件。

`--progress jsonl` 的事件写到 stderr，至少包含 `event_id`、`operation_id`、`type`、`stage`、`percent`、`message` 和 `at`。`render --cancel-file FILE` 在启动前和运行中都检查取消；`render --resume OPERATION_ID` 只有在项目和所有素材指纹未变化时才允许重建计划。

### 6.1 本地持久化渲染队列

`queue` 将批量输出作业保存为项目内 `operations/render-queue.json`，默认由同一个本地 FFmpeg 渲染器顺序执行；显式 `--workers N --continue-on-error` 时只并发 FFmpeg/质量检查阶段，项目输出、操作记录和队列状态由主线程串行提交。项目写入命令持有 `operations/project-write.lock`，覆盖队列读改写和状态提交；锁冲突返回 `PROJECT_WRITE_LOCKED`、退出码 6、`retryable=true`。作业状态、取消标记、尝试次数、错误、警告和 render 操作 ID 都可在进程退出后恢复；不引入服务、守护进程、数据库、Docker、WSL 或网络调度。无 `--job-id` 的 `queue run` 只执行 `pending`，失败或取消作业必须显式指定 ID 重试；并发批次允许已启动的 worker 完成，因此要求 `--continue-on-error`；重复输出路径返回 `QUEUE_OUTPUT_CONFLICT`。`queue cancel` 不等待项目写锁，锁被占用或作业运行中时写入 `operations/queue-cancel/<job_id>.cancel`，响应中的 `acknowledged=true, confirmed=false` 表示已递交、终态待确认；`queue list/inspect` 会反映 `cancel_requested=true`。完整字段和状态机见[本地渲染队列与任务状态契约](./本地渲染队列与任务状态契约_v0.1_2026-10-14.md)。

`quality check` 可用 `--require-audio`、`--max-av-sync-ms`、`--expensive`、`--target-lufs`、`--lufs-tolerance`、`--fail-on-black` 和 `--max-true-peak-dbfs`。质量报告失败时，发布调用必须停止；质量检查不会修改原始媒体或项目。

### 6.2 本地效果目录与渲染契约

Agent 在生成项目 JSON 或变更集前应先调用 `effects list`，需要精确参数时调用 `effects inspect --name NAME`。当前目录版本为 `0.4.0`，记录 45 项由本机 FFmpeg 提供的效果，包括 HSL、RGB 曲线、三向色轮和 `frame_interpolation` 光流补帧；每项至少包含 `id`、`aliases`、`category`、`backend`、`source=ffmpeg-local`、`keyframable`、`parameters` 和 `limits`。目录不会下载滤镜包，也不会访问网络。

`brightness`、`contrast`、`saturation`、`gamma` 和 `vignette` 允许效果参数使用 `eval=frame` 关键帧，`hue`/`hsl` 使用 FFmpeg `hue` 的帧表达式（该滤镜没有 `eval` 选项）。曝光、色阶、RGB 曲线、三向色轮、降噪、时域混合、镜头校正、框线、色彩对比、去闪烁和 DCT 降噪等新增原生滤镜当前以静态参数执行；项目可以保留这些效果的关键帧，但渲染会写入 `RENDER_FEATURE_APPROXIMATE`，不得把静态回退描述成逐帧等效。`frame_interpolation` 使用本地 `minterpolate` 生成目标帧率，运动补偿参数受目录白名单约束但可能消耗较多 CPU，场景切换和遮挡伪影必须进入质量复核。每项还返回 `license=inherit-local-ffmpeg-build`，发布时仍需按实际 FFmpeg 构建核对许可证和 notice。曲线只接受白名单校验后的 `0..1` 范围 `x/y` 点字符串，框线颜色只接受安全的 FFmpeg 颜色 token，非法值返回 `EFFECT_PARAMETER_INVALID`，对应滤镜会跳过或回退到安全默认值。

示例：

```powershell
python -X utf8 -m ai_ad_editor effects list --query color
python -X utf8 -m ai_ad_editor effects inspect --name curves
python -X utf8 -m ai_ad_editor render --project .\work\demo --dry-run
```

音频片段使用本地 FFmpeg 滤镜链，支持音量关键帧、`audio.pan`/`pan` 声像关键帧（`-1` 左至 `1` 右）、降噪、压缩、均衡、高低通、对白增强、变调、混响、响度归一化、淡入淡出和旁白 ducking。音频轨道可在 `track.audio` 声明 `mute`/`muted`、`solo`、`volume`、`pan`、`role` 和 `duck_under_voice`；solo 会形成项目内音频轨道选择门，轨道静态音量/声像在片段链之后执行。字符串 `audio.pan` 仅用于显式 raw FFmpeg pan 表达式；数值声像先将输入规范化为立体声，再以逐帧 `aeval` 平衡左右通道，单声道素材会复制到两路，立体声素材不会先被折叠为单声道。

### 6.3 本地素材确定性索引

`library index`、`library search` 和 `library duplicates` 的字段、侧车字幕规则、过滤器和精确重复语义见[本地素材语义索引与重复分组契约](./本地素材语义索引与重复分组契约_v0.1_2026-10-14.md)；增量刷新、`--visual-hash` 和 `library similar` 见[本地素材库增量刷新与感知候选契约](./本地素材库增量刷新与感知候选契约_v0.1_2026-10-14.md)。当前 `semantic.source` 固定为 `deterministic-local`，`vector_index=false`，不会联网、下载模型或把文件名/字幕匹配描述成视觉理解。模型级 VLM、embedding、OCR、人物/物体标签必须作为显式本地适配器接入，并写入模型版本和 provenance。

### 6.4 本地色彩 Scope 审查

`quality scopes` 的字段、输出目录约束和限制见[本地色彩 Scope 审查契约](./本地色彩Scope审查契约_v0.1_2026-10-14.md)。它只生成可复核的 FFmpeg waveform、vectorscope、histogram PNG 和 JSON 哈希报告；Agent 不得把 scope 图描述成自动调色结论，也不能用它替代 `quality check` 的音视频质量门禁。

### 6.5 固定本地质量 golden

`quality golden` 默认模式为 `verify`；`capture` 只有在 `quality check` 同等参数通过后才写入项目 `validation/golden-quality.json`。自定义 `--manifest` 必须位于项目内。清单版本为 `0.1.0`，保存媒体 SHA-256、字节数、项目/序列、画布、settings SHA-256、期望时长、质量门禁参数、指标、容差和捕获时间。

验证不会覆盖清单，会检查媒体字节哈希、项目 ID、settings 哈希、期望时长与记录指标。验证时未显式提供档案或序列会沿用捕获值；质量扫描参数需与捕获命令相同，尤其 `--expensive`，否则缺失的指标会返回 `QUALITY_GOLDEN_METRIC_MISSING`。哈希或指标漂移返回退出码 2 与 `QUALITY_GOLDEN_*` 错误。它证明同一本地输入/设置的复现性，不构成跨设备视觉等价、字幕美观或剪映完整质量验收。

## 7. 错误码和退出码

| 退出码 | 类别 | 示例错误码 |
|---:|---|---|
| 0 | 成功或 dry-run 计划 | — |
| 2 | 参数、Schema、项目、时间线或队列状态错误 | `ARGUMENT_INVALID`、`SCHEMA_VERSION_UNSUPPORTED`、`KEYFRAME_INVALID`、`TTS_LOCALE_UNSUPPORTED`、`QUEUE_JOB_STATE_INVALID` |
| 3 | 本地文件、哈希或媒体输入错误 | `ASSET_FILE_MISSING`、`MIGRATION_ASSET_HASH_MISSING` |
| 4 | 媒体流或能力缺失 | `VIDEO_TRACK_EMPTY`、`AUDIO_STREAM_MISSING` |
| 6 | FFmpeg、模型或可重试执行失败 | `RENDER_FAILED`、`LOCAL_ASR_FAILED`、`TTS_SYNTHESIS_FAILED`、`PROJECT_WRITE_LOCKED` |
| 7 | Rights Ledger 发布阻断 | `RIGHTS_BLOCKED` |
| 8 | 任务取消 | `CANCELLED` |
| 9 | 未分类输入/内部错误 | `INTERNAL_INPUT_ERROR` |
| 10 | 本地依赖或模型目录不可用 | `DEPENDENCY_UNAVAILABLE`、`LOCAL_ASR_MODEL_MISSING` |

错误对象至少包含 `code`、`message`、`path`（若可定位）、`retryable`（若适用）和 `cause`（不含秘密）。FFmpeg 原始日志只写操作记录，不拼接为可执行 shell 字符串。

## 8. Agent 调用示例

```powershell
$env:PYTHONPATH = 'E:\dev\sandbox\AI广告剪辑\product\src'
python -m ai_ad_editor project init .\\work\\demo --name Demo
python -m ai_ad_editor project migrate --project .\\work\\demo --dry-run --progress jsonl
python -m ai_ad_editor timeline compose --project .\\work\\demo --input .\\changes.json --idempotency-key edit-001
python -m ai_ad_editor tts synthesize --project .\\work\\demo --text "Hello local advertising voice" --output assets\tts\voice.wav
python -m ai_ad_editor validate --project .\\work\\demo --strict-rights
python -m ai_ad_editor render --project .\\work\\demo --profile vertical --progress jsonl --output .\\work\\demo\\renders\\ad.mp4
python -m ai_ad_editor queue enqueue --project .\\work\\demo --input .\\queue.json
python -m ai_ad_editor queue run --project .\\work\\demo --workers 2 --continue-on-error --progress jsonl
python -m ai_ad_editor queue list --project .\\work\\demo --status failed
python -m ai_ad_editor quality check --project .\\work\\demo --input .\\work\\demo\\renders\\ad.mp4 --require-audio --expensive
python -m ai_ad_editor quality golden --project .\\work\\demo --input .\\work\\demo\\renders\\ad.mp4 --mode capture --require-audio --expensive
python -m ai_ad_editor quality golden --project .\\work\\demo --input .\\work\\demo\\renders\\ad.mp4 --mode verify --require-audio --expensive
```

调用方应先读取 `capabilities`，再根据限制决定 Exact、Approximate 或拒绝计划。任何近似结果都必须连同 warning、转换报告或质量报告交给 Agent 上层处理。

## 本地中文配音增量

详细参数、worker 协议、网络阻断、输入/输出哈希、自然时长、错误码和权利依赖见[本地 SoulX 契约](./本地SoulX中文配音与声线登记契约_v0.1_2026-10-15.md)。未指定适配器时 flite 的非 ASCII 拒绝行为保持有效；模型路径、参考声或证据变化时拒绝执行，禁止自动回退在线服务。

## 2026-10-15 本地 Whisper 登记与 CER

新增 `asr adapter register/list/inspect`。register 要求 `--project --adapter-id --python-executable --model-path --evidence`，设备 `--device cpu|cuda`（默认 cpu），线程 `--threads 1..32`（默认 4），支持既有许可/用途/核验状态、dry-run 与幂等。list/inspect 不写元数据，inspect 核验完整性。模型登记在 `extensions.local_asr.adapters` 并建立独立 Rights Ledger 记录。

`subtitle transcribe` 的 `--model-path` 与 `--adapter-id` 二选一；`media understand --transcribe` 同样支持登记模型。登记模型的设备由登记项决定，不能混用 `--use-gpu` 或 `ffmpeg-whisper` 引擎。新 SRT 输出按项目根解析；拒绝覆盖，应用继承源及模型的权利依赖。空文本/非有限/越界/重叠时码拒绝；落盘失败清理本轮输出并由事务恢复原元数据。幂等指纹保留输出路径，但不把本次新生成的 output/report 或变化后的 project.json 当输入内容哈希，绝对路径亦能正确重放。

`subtitle evaluate --input <UTF8或字幕> --reference <UTF8或字幕> [--project <项目>] [--normalization raw|nfkc-text] [--max-cer <非负数>] [--report <新JSON>]` 返回替换/删除/插入计数及 CER。默认归一化不转换繁简；超阈值返回 `ASR_CER_THRESHOLD_EXCEEDED`/6 并保留报告。比较超过 2500 万动态规划单元或单边超过 10 万字时拒绝，须分段评估。`media ingest` 增加经本地 FreeType 验证的 TTF/OTF/TTC 字体资产，集合字体当前只选 face 0。详情见[登记与验收契约](./本地Whisper模型登记与转写验收契约_v0.1_2026-10-15.md)。

## 2026-10-15 原生视觉执行增量

`media adapter register` 新增 `--engine yolov10-onnx-cpu-tracking-v1`；`--executable` 为原生 Python `.exe`，`--model-path` 为自包含 YOLOv10 COCO-80 ONNX，`--evidence` 为现有本地文件。显式参数含 `--threads`、`--confidence`、`--low-confidence`、`--match-iou`、`--max-gap-seconds` 和可重复 `--class-id`。`media track --all-objects` 复核后，以 `--object-id` 驱动 track/track-bind/reframe；正式应用要求已摄取 `--asset-id`，保留片段模型权利。报告已存在时拒绝覆盖，native 不回退模板。详见[专用契约](./本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md)。
