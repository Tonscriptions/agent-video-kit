# Concat 无 GUI Agent 化与剪映差异补全：可行性评估


| 文档编号 | RESEARCH-2026-10-007 |
|---|---|
| 状态 | 有效 |
| 本次审计复核 | 2026-10-13 |
| 证据性质 | 架构可行性；待 P0 样例验证 |
更新时间：2026-10-12  
目标假设：fork Concat，去掉桌面/移动 GUI，只保留本地 CLI、服务接口和视频引擎，再补齐剪映/CapCut 产品线的功能差异。  
约束：不使用剪映；不启动 Docker、WSL 或其他虚拟化环境；优先原生 Windows/Linux/macOS 和本地开源组件。

## 1. 直接结论

| 问题 | 结论 | 说明 |
|---|---|---|
| 能否 fork Concat | **可以** | 仓库为 AGPL-3.0-or-later；贡献指南明确写着代码可以 fork，但 Concat 名称和 Logo 属于商标范围，需要换产品名。 |
| 能否删除 GUI、只保留 CLI | **技术上可以，且有较好基础** | 当前工作区已经有 concat-cli、concat-api、concat-server 和独立引擎 crates；GUI 主要集中在 concat 这个 Slint 前端与 concat-android 适配层。 |
| 删除 GUI 后是否自动得到完整 Agent 内核 | **不可以** | concat-cli 目前已有 probe、render、api、serve、preview、check，但 API 未覆盖窗口所有操作；源码架构文档还记录 README 所称 MCP transport 尚未出现在源码树中。 |
| 能否补齐剪映的全部核心剪辑能力 | **可以作为长期工程目标** | 时间线、渲染、关键帧、字幕、音频、遮罩、跟踪等属于可拆分的工程模块。 |
| 能否补齐剪映全部产品能力 | **不能把它当成单纯 fork 项目** | 生成式视频、数字人、模板/素材/版权库、云协作、移动生态和模型运营需要独立平台、数据和持续运营。 |
| 是否值得做 | **值得做，但目标应改为 Agent-first 视频生产平台** | Concat 适合做可编排本地 NLE 内核，不适合被当成已经完成的剪映替代品。 |

推荐定位：

**Concat engine fork + headless runtime + Agent orchestrator + open-source AI workers + quality gate**

## 2. 现有 Concat 架构对这个计划意味着什么

当前源码树的 Cargo workspace 使用 crates/* 自动纳入成员，主要组成如下：

| 层 | 当前 crate | 对无 GUI 版本的处理 |
|---|---|---|
| 时间和基础模型 | concat-core | 保留 |
| 项目、命令、撤销 | concat-project | 保留并扩展 Agent schema |
| 媒体读写 | concat-media | 保留 |
| 单帧合成 | concat-render | 保留，GPU 做成可选后端 |
| 导出 | concat-export | 保留并补批量队列、断点、质量门禁 |
| 效果包 | concat-effects | 保留，补能力声明、版本和依赖锁 |
| 文本 | concat-text | 保留，补字幕格式和排版契约 |
| 语音 | concat-speech | 保留，拆出转录、TTS、音色模型任务 |
| 视觉 | concat-vision | 保留，补跟踪、分割、补帧和重构图 worker |
| 窗口主机 | concat-host | 不直接删除；拆成 headless runtime、playback、preview、model service |
| API 分发 | concat-api | 保留并扩充为完整 Agent contract |
| 网络服务 | concat-server | 保留 JSON-RPC/gRPC；单独实现 MCP adapter |
| 桌面 GUI | concat | 移出 headless workspace 或放入可选 gui profile |
| Android GUI | concat-android | 从 headless 发行版移除 |
| 性能工具 | concat-perf | 保留为基准和回归工具 |

关键事实：

1. concat crate 的描述就是 Slint editor window；它依赖 Slint、文件对话框、系统托盘、平台窗口和字体 UI。
2. concat-cli 已经是独立 binary，命令包括 probe、render、api、serve、preview、check。因此 CLI 不是从零开始。
3. concat-api 目前仍依赖 concat-host；直接删除 concat GUI crate，不代表所有窗口耦合已经消失。
4. concat-host 的描述是“编辑器窗口需要但不是 edit 本身的内容”，其中包含会话、项目文件夹、预览、播放、模板、模型下载和音频输出。无 GUI 版本需要把这些职责分成可测试的 headless runtime。
5. 当前 API 与窗口能力并不等价。架构文档列出 voiceover、meters、font picker、presets、click-to-preview、copy/paste 等窗口操作没有对应 API verb。
6. 当前源码树中的 socket transport 是 JSON-RPC 和 gRPC；架构文档明确指出 README 提到的 MCP transport 尚未在树中实现。MCP 需要作为真正的第三个 adapter 写入测试。

## 3. 第一步：fork 和许可证边界

### 可以做的事

- fork 仓库；
- 删除或重构 GUI；
- 修改 crate、协议、模型和渲染器；
- 用自己的品牌和仓库名发布；
- 把新增模块按兼容许可证组织。

### 必须保留的义务

- 保留 AGPL-3.0-or-later 版权与许可证文件；
- 为修改后的发布物提供对应源代码；
- 保留第三方许可证、模型、字体、效果包和 FFmpeg 相关声明；
- 如果将修改版作为网络服务向用户提供，需要按 AGPL 第 13 条处理对应源代码提供义务；
- 不使用 Concat 名称和 Logo 暗示官方产品；
- 不把 LICENSE-EXCEPTIONS.md 当成整个 fork 的许可证豁免，它主要处理插件边界；
- 商业闭源集成、模型权重、字体和素材库分别做许可证审计。

这部分是合规边界，不是工程实现建议；商业发布前应让熟悉 AGPL 的律师复核。

## 4. 第二步：删除 GUI 的正确方式

不建议物理删除目录后直接运行 cargo build。建议先建立两个 workspace/profile：

| 目标 | 做法 | 结果 |
|---|---|---|
| headless workspace | 从 members 中排除 concat 和 concat-android；保留核心、host/runtime、api、server、cli | CLI/服务可以独立编译 |
| optional GUI workspace | GUI 放在 apps/gui 或单独 workspace，依赖 headless crates | GUI 变成可选客户端，不污染 Agent 构建 |
| headless feature | 将 GPU、音频播放、模型下载、预览卡片、桌面文件操作设成 feature | 服务器可按环境裁剪 |
| runtime 拆分 | 从 concat-host 中抽取 session、project IO、template、media jobs、model jobs | API 不再依赖窗口概念 |
| 输出协议 | 所有任务通过结构化 request/event/result 传输 | CLI、JSON-RPC、gRPC、MCP 共用一套语义 |
| GUI 兼容期 | 暂时保留 GUI 分支，用来做视觉回归和人工对照 | 避免删除 GUI 后失去验证工具 |

### 删除范围

需要从 headless 发行版中移除或隔离：

- Slint UI、Slint build script 和生成的 UI 模块；
- winit、系统托盘、文件/文件夹对话框、窗口拖拽；
- Android activity、iOS/Android 发布桥；
- GUI 字体选择器、面板状态、鼠标手势和剪贴板；
- GUI 专用预览卡片和屏幕播放；
- GUI-only 的远程设置页和窗口确认弹窗。

### 不应删除的内容

- concat-project 的时间线、命令、撤销和文档迁移；
- concat-render/compositor；
- concat-export；
- concat-effects；
- concat-speech 和 concat-vision；
- 媒体探测、代理、缓存和色彩管理；
- API、服务鉴权、写入根目录限制和作业事件。

## 5. 第三步：CLI/API 需要先补成“真正的 Agent 内核”

当前 CLI 可以作为入口，但还不够作为剪映级 Agent 内核。至少要建立以下稳定协议：

| 协议层 | 必须补的内容 |
|---|---|
| Project schema | 项目、时间线、轨道、素材、片段、关键帧、遮罩、效果、字幕、音频路由、导出规格的版本化 JSON |
| Capability schema | 每个效果可用参数、可否关键帧化、输入/输出色彩、GPU/CPU 后端、平台限制、许可证 |
| Command schema | import、probe、place、split、trim、ripple、set_keyframe、apply_effect、caption、tts、export、validate |
| Job schema | queued、running、cancelled、failed、succeeded、partial；支持重试和幂等 job id |
| Event schema | progress、warning、artifact、metric、log、error；不把普通日志混在 stdout 协议中 |
| File policy | 输入白名单、输出根目录、模型目录、临时目录、路径规范化和协议 URL 白名单 |
| Determinism | 固定随机种子、模型版本、效果版本、FFmpeg build、硬件后端和色彩配置 |
| Preview | 关键帧 PNG、contact sheet、低清代理和时间点帧检查 |
| Validation | 时长、帧率、A/V sync、响度、黑帧、冻结帧、字幕溢出、编码器、色彩元数据 |
| MCP adapter | 将同一套 API 暴露为 MCP tools/resources/prompts，不在 MCP 层重新实现剪辑逻辑 |

特别要注意：如果 API 仍然依赖 concat-host 的窗口状态，CLI 只是“把 GUI 入口换成命令行”，并没有获得真正 Agent-first 架构。

## 6. “补齐剪映差异”应分成三种目标

### 目标 A：核心剪辑内核接近剪映

可实现范围：

- 多轨、多时间线、链接音视频；
- 分割、修剪、插入、覆盖、波纹；
- 变速、速度曲线、冻结、倒放；
- 位置/缩放/旋转/透明度/音量/效果参数关键帧；
- 缓动和运镜预设；
- 转场、滤镜、混合模式、文本、字幕；
- LUT、HSL、曲线、HDR/10-bit；
- 代理、预览、批量导出。

判断：**可行**。主要工作是 API 完整度、效果包数量、像素/时间码一致性和性能。

### 目标 B：Agent 广告剪辑平台达到剪映的主要工作流

需要补：

- 镜头边界和语音活动检测；
- Whisper/ASR、去停顿、去无效词；
- 物体/人物/相机跟踪；
- 自动重构图和主体保持；
- 人声分离、降噪、响度和音乐卡点；
- 广告脚本、卖点、镜头计划和变体生成；
- 9:16、1:1、16:9 多版本自动适配；
- 输出检查、素材哈希、模型和参数 manifest。

判断：**可行，但已经是一个多服务系统**。Concat 负责执行计划；Agent 和视觉/音频 worker 负责生成计划与分析结果。

### 目标 C：剪映/CapCut 全产品能力对标

还包括：

- 文本/图像生成视频；
- 数字人、换脸、口型同步；
- 生成背景、局部重绘、物体移除；
- 商业音乐、音效、贴纸和模板库；
- 品牌包、社区素材、推荐系统；
- 云草稿、多人协作、评论、权限；
- 移动端接续和跨设备同步；
- 模型运营、内容审核、版权与商业授权。

判断：**不能视为 Concat fork 的有限补丁**。这需要视频内核、AI 模型平台、资产与版权平台、协作后端和持续运营团队。

## 7. 工程量分层估算

以下是工程量级估算，不包含自研基础模型训练、商业素材采购和大规模云基础设施。

| 阶段 | 交付目标 | 主要工作 | 适合团队 | 粗略工程量 |
|---|---|---|---|---|
| P0 | 可编译的 headless fork | workspace 拆分、移出 concat/concat-android、保留 concat-cli、整理 feature、改品牌和发行脚本 | 1–2 名 Rust 工程师 | 1–3 人月 |
| P1 | 稳定 CLI/JSON-RPC | headless runtime、项目 schema、完整错误、任务事件、鉴权、路径限制、日志和回归素材集 | 2–3 名 Rust/媒体工程师 | 3–6 人月 |
| P2 | Agent 可用内核 | 补 API 缺口、MCP adapter、dry-run、幂等任务、预览、manifest、质量门禁 | 2–4 名 Rust/平台工程师 | 4–9 人月 |
| P3 | 核心剪辑工作流 | 关键帧/曲线/遮罩/字幕/音频/色彩/转场的端到端回归和性能优化 | 3–5 名媒体工程师 | 9–18 人月 |
| P4 | 广告自动剪辑 | ASR、VAD、镜头检测、主体跟踪、自动重构图、节拍、脚本和多比例变体 | 4–7 名媒体/ML/Agent 工程师 | 12–24 人月 |
| P5 | 生成式和生态能力 | 视频生成、数字人、生成填充、模板/素材库、品牌包、版权、协作和审核 | 8–15 名跨职能成员 | 24–60+ 人月，持续运营 |

解释：

- P0–P2 是“把 Concat 变成可用 Agent 内核”的范围。
- P3 是“剪辑器核心接近剪映”的范围。
- P4 是“广告自动化达到较高实用度”的范围。
- P5 已经是独立产品公司级范围，不能用单个 fork 的工作量理解。

## 8. 主要技术阻塞点

| 阻塞点 | 严重度 | 原因 | 处理方式 |
|---|---:|---|---|
| API 覆盖不完整 | 高 | 窗口中存在没有 API verb 的操作 | 先做 capability/command inventory，再补 API |
| MCP 声明与源码不一致 | 高 | README 声明 MCP，架构文档记录源码树没有 MCP transport | 固定基线，先实现并测试 adapter |
| concat-api 依赖 concat-host | 高 | GUI 外壳虽然可删，但 host 仍承载窗口外的会话/播放/预览/模型职责 | 拆 headless runtime |
| GPU/CPU 结果一致性 | 高 | 预览、GPU、FFmpeg 导出可能产生视觉差异 | 金样帧、像素阈值、色彩和编码回归 |
| 时基与关键帧 | 高 | 速度曲线、冻结、转场句柄、关键帧重锚定会互相影响 | 用有理帧率和固定 edit decision list 测试 |
| AI 模型许可和下载 | 高 | 模型、字体、效果和语音来源各自有许可证 | manifest、SHA-256、来源和许可字段 |
| Windows 发布 | 高 | 当前 v0.2.6 有公开 Windows x86_64 release binary issue | 自建 CI、签名、DLL smoke test、版本 pin |
| 性能和缓存 | 中高 | 速度曲线、预取、混音和代理可能放大内存/解码成本 | 预算、取消、缓存回收、长视频基准 |
| 安全边界 | 高 | Agent 会传入路径、参数、模型和网络请求 | 根目录限制、URL 白名单、资源上限、无 shell 拼接 |
| “剪映水准”的验收 | 高 | 剪映有大量平台、模板和 AI 运营能力，不能用单一导出成功判断 | 建立 100+ 个可复现验收案例 |

## 9. 推荐实施路线

### 阶段一：先做 headless 分支，不补新 AI

1. 复制仓库并使用新品牌，不发布名为 Concat 的产品。
2. 固定一个上游 commit，记录 Rust、FFmpeg、模型和依赖版本。
3. 建立 headless Cargo workspace，排除 concat 和 concat-android。
4. 抽取 headless runtime，确保 concat-cli 不依赖 Slint。
5. 把现有 CLI 的 probe、render、api、serve、preview、check 做成 CI smoke tests。
6. 清理 stdout/stderr，让 JSON-RPC、日志和进度不互相污染。

### 阶段二：把 API 变成稳定产品接口

1. 列出所有 Project/Command/Export/Media/Effect/Caption/Speech/Vision 操作。
2. 为每个操作写 JSON schema、错误码、幂等规则和版本迁移。
3. 先实现 JSON-RPC 和本地 CLI，再实现 gRPC 与 MCP adapter。
4. 增加 dry-run、preview、cancel、resume、validate 和 manifest。
5. 将所有 Agent 任务限制在明确的 roots 和资源预算内。

### 阶段三：补齐广告工作流

1. ASR/VAD/镜头检测；
2. 主体与相机跟踪；
3. 自动重构图和安全区域；
4. 人声分离、降噪、响度、节拍；
5. 脚本到 edit plan；
6. 多比例广告变体；
7. 质量门禁和交付报告。

### 阶段四：再评估生成式功能和生态

只有当 P0–P4 的任务、质量和可复现性稳定后，才决定是否继续投入数字人、生成式视频、模板生态和协作平台。否则这些功能会把核心内核的稳定性拖垮。

## 10. 最终判断

你的三个步骤中：

- **步骤 1：完全可行。** 需要 AGPL 合规和更换品牌。
- **步骤 2：可行，但应理解为“把 GUI 变成可选客户端并拆出 headless runtime”，不是简单删除两个目录。**
- **步骤 3：分层可行。** 补齐核心剪辑和 Agent 广告工作流可做；补齐剪映全部产品生态，不是一个有限范围的 fork 任务。

最合理的产品边界是：

**先做一个无 GUI、可本地运行、可被 MCP/CLI/JSON-RPC 调用、能输出可复现广告视频的 Agent 视频内核。**

达到这个边界后，再按数据和验收结果逐项增加跟踪、自动重构图、智能粗剪、模板和生成式模块。不要一开始把“剪映所有功能”作为单一版本的完成条件。

## 11. 依据

- [Concat GitHub 仓库](https://github.com/jub0t/concat)
- [Concat CONTRIBUTING.md](https://github.com/jub0t/concat/blob/main/CONTRIBUTING.md)
- [Concat ARCHITECTURE.md](https://github.com/jub0t/concat/blob/main/ARCHITECTURE.md)
- [Concat Windows x86_64 v0.2.6 issue #303](https://github.com/jub0t/concat/issues/303)
- [GNU Affero General Public License](https://www.gnu.org/licenses/agpl-3.0.html)
- [剪映官网](https://www.jianying.com/)
