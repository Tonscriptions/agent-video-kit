# Concat 与 pyJianYingDraft 检查及配套 Skills Star 排行


| 文档编号 | RESEARCH-2026-10-009 |
|---|---|
| 状态 | 有效 |
| 本次审计复核 | 2026-10-13 |
| 证据性质 | 配套 Skill 研究；未完成运行验证 |
核查日期：2026-10-11。用户所指“1、2”按上一份核心列表解释为 **jub0t/concat** 与 **GuanYixuan/pyJianYingDraft**。重点为用户确认的“关键帧与运镜预设”。所有本地产物在 `E:/dev/sandbox/AI广告剪辑/` 下。

**结论：两个程序都有真实编辑接口；Concat 有一个官方开发/运行验证 Skill，pyJianYingDraft 则有多套真正用于视频草稿制作的社区 Skill。** 若希望现在批量套用缩放、平移和缓动，已安装的 `$video-cut-jianying-editor` 是最值得先验证的入口。

检索和源码检查包含隐藏目录 `.claude/skills/`、`.agents/skills/`，不能只搜索普通 `skills/`。初查遗漏了 Concat 的隐藏 Skill，现已更正。

## 1. Concat 检查

- 仓库：4,777 Star；AGPL-3.0-or-later。最新发布 **v0.2.6**，2026-10-06 发布，提供原生 Windows x86_64 / ARM64 的 EXE 和 MSI 安装包。
- 实际编辑内核：`concat-cli api/serve`、JSON-RPC、可选 gRPC；支持 `edit.apply`、模板、效果目录、预览、最终导出。`SetClipKey`、`SetClipCutout` 在源码中有实现。
- 关键帧：支持位置、缩放、旋转、透明度等；时间 `at` 按片段长度的比例表达，不能直接套用剪映 SDK 的微秒时间。命名运镜配方需要结合这些操作与模板构建。
- 官方 Skill：**run-concat**，路径 `.claude/skills/run-concat/SKILL.md`。文件有规范 frontmatter，但用途是编译、启动和验证桌面程序；它没有提供“制作一条广告 → 套推拉平移 → 导出”的创作流程或完整命名运镜库。
- MCP：官方开发文档与本次源码表明完整 MCP 服务仍未合入；CLI/JSON-RPC 是现阶段可用接口。不能将 JSON-RPC stdio 直接当作 MCP stdio。
- Windows 运行准备：本机当前 PATH 没有 Cargo。本次只核验发布包与源码，未安装/编译/启动 Concat。官方 `run-concat` 依赖 Rust 工具链，与下载 Windows 安装包使用 GUI 是两条路线。

[发布包](https://github.com/jub0t/concat/releases/tag/v0.2.6)、[官方 Skill](https://github.com/jub0t/concat/blob/main/.claude/skills/run-concat/SKILL.md)、[MCP 当前状态](https://concatenate.pages.dev/docs/transports/mcp/)

## 2. pyJianYingDraft 检查

- 仓库：4,527 Star；Apache-2.0。GitHub 发布与 PyPI 当前版本均为 **0.3.0**；PyPI 要求 Python >=3.8，并依赖 pymediainfo、imageio，Windows 另依赖 uiautomation。
- 它是剪映草稿 SDK，最终原生效果由剪映客户端渲染。官方 README 自报 10.8 支持素材、关键帧、字幕、特效/滤镜/转场等；蒙版目前标记不支持，模板读取可能需 `fallback_loader`。
- 自动导出是另一模块：旧 UI 控制器验证 5.9/6.8，对剪映 7+ 的表格标记不支持。这不否定新版草稿生成能力。
- 原始主仓库快照未发现标准 `SKILL.md`；配套 Skill 来自社区封装、API 项目和专项工作流。
- 本机当前系统 Python 3.13 没找到 PyPI 的 pyJianYingDraft、pymediainfo 或 uiautomation；但已有 JyWrapper 带内嵌库，因此“系统 Python 无包”不能推断“已装 Skill 缺源码”。实际运行必须按该 Skill 的 bootstrap 和依赖核验。
- 已安装的 `$video-cut-jianying-editor` 为 1.7.0，安装记录 commit **32c56928ded4f9e2c2b80e099dc7abb793d2c30b** 与当前上游相同，无需重复下载同一版本。内嵌 SDK 提供了 Bezier 缓动扩展，不能混用未修改的 PyPI 包假设所有参数相同。

[官方 SDK 与兼容矩阵](https://github.com/GuanYixuan/pyJianYingDraft)、[PyPI](https://pypi.org/project/pyJianYingDraft/)、[已装 Skill 的来源](https://github.com/luoluoluo22/jianying-editor-skill)


## 可核验配套 Skill，按仓库 Star 排序

Star 为 2026-10-11 GitHub API 查询结果，按整个仓库统计；同仓多个 Skill 只列一次。这里包括直接 SDK 配套与间接草稿输出配套，并在关系栏注明。

| 排名 | 仓库 / Skill | Star | 适配关系 | 关键帧、运镜及用途 |
|---|---|---:|---|---|
| 1 | jub0t/concat · [run-concat](https://github.com/jub0t/concat/blob/1ab750a339c5db249d353b21b9f3cc9ddb1a1a22/.claude/skills/run-concat/SKILL.md) | 4,777 | Concat 官方配套 | 编译、启动、验证 Rust/Slint 桌面程序 |
| 2 | luoluoluo22/jianying-editor-skill · [jianying-editor](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/SKILL.md) | 3,897 | 直接适配 pyJianYingDraft | JyWrapper、草稿、特效/字幕、缩放/平移关键帧、Bezier 缓动 |
| 3 | sun-guannan/VectCutAPI · [vectcut-api](https://github.com/sun-guannan/VectCutAPI/blob/cfa4779a52f1dc59a56d90cc5868778eb50c6a97/vectcut-skill/skill/SKILL.md) / [capcut-director](https://github.com/sun-guannan/VectCutAPI/blob/cfa4779a52f1dc59a56d90cc5868778eb50c6a97/.agents/skills/capcut-director/SKILL.md) | 2,292 | 通过 API 适配 pyJianYingDraft | HTTP/MCP 编排草稿、特效、视频关键帧；另有时间线指导 Skill |
| 4 | zenstory-ai/video-recap-skills · [video-assemble](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-assemble/SKILL.md) / [video-recap](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-recap/SKILL.md) / [video-cut](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-cut/SKILL.md) | 563 | 间接配套：草稿格式兼容 | 解说、剪辑、混音、字幕、导出可编辑剪映草稿 |
| 5 | isYangs/jianying-editor-skill · [jianying-editor](https://github.com/isYangs/jianying-editor-skill/blob/a20c5228fcc88e27587c32d6d916f776869473b2/SKILL.md) | 215 | 直接适配 pyJianYingDraft | JyWrapper、素材、特效、Ken Burns/缩放/位置关键帧指导 |
| 6 | wangcanyu/daihuo-fanpai · [daihuo-fanpai](https://github.com/wangcanyu/daihuo-fanpai/blob/b296543ca7097d002a272271886033dcd82c5b59/SKILL.md) | 59 | 直接调用 SDK 的广告流水线 | 带货视频反推、重生成、配音、拼接、剪映草稿交付 |
| 7 | ops120/video-recap-skills-plus · [video-assemble](https://github.com/ops120/video-recap-skills-plus/blob/edd5c1b6d341aa30af9a4cf63a89a396631d6f18/skills/video-assemble/SKILL.md) / [video-recap](https://github.com/ops120/video-recap-skills-plus/blob/edd5c1b6d341aa30af9a4cf63a89a396631d6f18/skills/video-recap/SKILL.md) / [video-cut](https://github.com/ops120/video-recap-skills-plus/blob/edd5c1b6d341aa30af9a4cf63a89a396631d6f18/skills/video-cut/SKILL.md) | 41 | 间接配套：草稿格式兼容 | 解说/合成与剪映草稿输出 |
| 8 | guoluhua38-max/jianying-editor-skill · [jianying-editor](https://github.com/guoluhua38-max/jianying-editor-skill/blob/a081fbd4aaba9f53f356045aeb0ed570b55a4b2f/SKILL.md) | 31 | 直接适配 pyJianYingDraft | JyWrapper/关键帧规则的另一维护副本 |
| 9 | jjjane233/jianying-editor-skill-11.5 · [jianying-editor-11-5](https://github.com/jjjane233/jianying-editor-skill-11.5/blob/133399a1f9a581be394a2c043e8f649a7145650c/skills/jianying-editor-11-5/SKILL.md) | 2 | JyWrapper 的版本专项适配 | Windows 11.5 草稿保存、增量修改、CLI、原生 DraftIO 桥 |
| 10 | DogeCoding/capcut-skill · [capcut-jianying](https://github.com/DogeCoding/capcut-skill/blob/aaa0b8f8a3c660759ef421454d488452f19c1688/SKILL.md) | 0 | 直接适配 pyJianYingDraft | 草稿、SRT、效果枚举、FFmpeg 静音粗剪 |


## 各项边界、许可与本地名称

新候选仅作为研究源码读取，未注册为本地 Skill。建议安装名均使用 `video-cut-` 前缀，调用时在名称前加 `$`。只有已装 `video-cut-jianying-editor` 当前可以按该名称调用。

- **jub0t/concat**（4,777 Star，AGPL-3.0-or-later）：开发与运行验证 Skill；没有视频剪辑配方、命名运镜预设或剪辑任务编排。需要 Rust/Cargo。 建议本地名：`video-cut-run-concat`。
- **luoluoluo22/jianying-editor-skill**（3,897 Star，MIT；内嵌库 Apache-2.0）：已安装；1.7.0；当前上游 commit 与安装记录相同。内嵌 SDK 有修改，不能假设等同于 PyPI 0.3.0。 建议本地名：`video-cut-jianying-editor`。
- **sun-guannan/VectCutAPI**（2,292 Star，Apache-2.0；vectcut-skill 子包 MIT）：公开主流程以草稿生成保存为主；云渲染/完整 Agent 应用未开源。capcut-director 有强制关闭进程/批量删除锁的示例，后续适配需改成保留用户工作与指定项目范围。 建议本地名：`video-cut-vectcut-api / video-cut-capcut-director`。
- **zenstory-ai/video-recap-skills**（563 Star，MIT）：export_jianying.py 用标准库直接写 JSON，参考 pyJianYingDraft 格式但不调用该 SDK。音量 ducking 关键帧与画面运镜预设不是同一种能力。 建议本地名：`video-cut-recap-assemble / video-cut-recap / video-cut-recap-cut`。
- **isYangs/jianying-editor-skill**（215 Star，MIT）：与已装 JyWrapper 属同类 Skill，215 Star；存在旧版导出与运行依赖假设，不是替换现有包的明显升级。 建议本地名：`video-cut-jianying-editor-isyangs`。
- **wangcanyu/daihuo-fanpai**（59 Star，MIT）：deliver.py 实际调用 pyJianYingDraft。重点是广告生产，不提供完整命名运镜库；生成依赖即梦/Seedance 等服务。源码含 WSL 路径兼容分支，原生路径也有处理，本项目只考虑原生运行。 建议本地名：`video-cut-daihuo-fanpai`。
- **ops120/video-recap-skills-plus**（41 Star，MIT）：独立 JSON 草稿导出器，未直接依赖 pyJianYingDraft；与 video-recap-skills 同类，不应当作新的 SDK 内核。 建议本地名：`video-cut-recap-plus-assemble / video-cut-recap-plus / video-cut-recap-plus-cut`。
- **guoluhua38-max/jianying-editor-skill**（31 Star，MIT）：与最高 Star 项目结构与使用方式相近，没有核验到比已装包更强的独有运镜能力。 建议本地名：`video-cut-jianying-editor-guoluhua`。
- **Xanthus-Sanslab/jianying-ai-mcp**（11 Star，未找到项目 LICENSE；依赖库另有许可）：pyproject 固定 pyJianYingDraft 0.3.0；项目自报 Windows 剪映 10.0.5 测试。11 Star，许可未明确，作为公开源码候选单列。 建议本地名：`video-cut-jianying-ai-editor`。
- **jjjane233/jianying-editor-skill-11.5**（2 Star，MIT；继承内嵌库声明）：作者仅验证 11.5.0.14471；使用本机客户端组件 ABI，2 Star。保留上游关键帧接口不等于已验证全部运镜/特效，须按本版记录核验。 建议本地名：`video-cut-jianying-editor-11-5`。
- **DogeCoding/capcut-skill**（0 Star，MIT）：macOS 为主，Windows 路径需适配；没有核验到命名运镜预设库。0 Star，适合作为最小示例参考。 建议本地名：`video-cut-capcut-jianying`。


## 公开源码候选及未纳入排行的项目

Xanthus-Sanslab/jianying-ai-mcp（11 Star）有真实 `jianying-ai-editor` Skill、MCP 服务和固定 pyJianYingDraft 0.3.0 依赖，配套关系明确；目前未找到项目 LICENSE，不能直接当作许可明确的开源包。[Skill 源码](https://github.com/Xanthus-Sanslab/jianying-ai-mcp/blob/main/skills/jianying-ai-editor/SKILL.md)

| 项目 | Star | 核查结论 |
|---|---:|---|
| [mcncarl/yichen-skills](https://github.com/mcncarl/yichen-skills) | 4,372 | 有 yichen-jianying-edit，但 LICENSE 是个人学习/非商业许可，原生剪映流程又偏 Apple Silicon Mac；不列为可用于本广告项目的开源 Skill。 |
| [mcncarl/jianying-headless](https://github.com/mcncarl/jianying-headless) | 3,041 | 同样为个人学习/非商业许可；有配套 Skill，主要原生链路为 macOS，Windows FFmpeg 分支与原生剪映草稿不同。 |
| [OpenDemon/Pilipili-AutoVideo](https://github.com/OpenDemon/Pilipili-AutoVideo) | 206 | skills/SKILL.md 是说明文档，缺少 name/description YAML frontmatter；也未找到项目 LICENSE。保留为流水线参考，未列为可直接注册的开源 Skill。 |
| [DreamLab-AI/agentbox](https://github.com/DreamLab-AI/agentbox) | 23 | 找到 23 Star 的 Concat 实验集成 concatcontainer，交付的是 Docker/Compose 构建选项，没有独立的 Concat 命名 Skill；不符合本项目禁止 Docker/WSL 的运行约束。 |
| [YGtemple/jianying-editor-skill](https://github.com/YGtemple/jianying-editor-skill) | 1 | 有 Skill 入口，但当前仓库缺少对应执行脚本/资源包，未找到项目 LICENSE；是文档/规则参考。 |


## 针对关键帧与运镜预设的优先顺序

1. **制作内容、继续剪映：先验证现有 `$video-cut-jianying-editor`。** 已包含缩放、位置、Ken Burns 类动画与 Bezier 缓动的指导及接口；可以把“推近/拉远/横移”等保存为项目内参数配方，再复用到批量素材。
2. **希望由 MCP/HTTP 批量执行：评估 VectCutAPI 的 vectcut-api Skill。** 服务与 Skill 均存在，参数化关键帧适配关系明确；需要核对草稿结构和目标客户端版本。
3. **建立独立内核：Concat 适合继续评估，但 run-concat 是开发运行 Skill。** 对广告剪辑还需要围绕 JSON-RPC 补充创作 Skill 与命名运镜配方；本次没有发现可核验的独立社区创作 Skill 可直接替代这层。
4. **广告内容流程：daihuo-fanpai 更贴近带货制作；解说流程看 video-recap-skills。** 两类管线的关键帧图片生成、音量 ducking 和相机运镜预设应分别评估，不能因为都有“关键帧”字样就视为同一能力。

### 本次发现的运镜示例问题

已装 Skill 的 `rules/keyframes.md` 示例把“绝对时间线时间”传给 `add_keyframe`；底层 API 与官方文档定义的是**相对片段头部的时间偏移**。例如片段在时间线 1 秒开始、持续 4 秒，关键帧应为片内 `0s → 4s`，而不是绝对 `1s → 5s`。批量运镜应按片内时间建立配方，避免直接照搬该示例。

Concat 的比例时间、剪映 SDK 的片内微秒、API 接口的时间字段也需要分别转换；建议统一项目配方为“片段时长比例 + 起止变换 + 缓动”，由各内核适配器转换。该建议是基于接口检查的实施判断，本次没有渲染样片证明视觉一致性。


## 源码证据

以下链接固定到本次读取的 commit，避免后续主分支更新造成混淆。

- [jub0t/concat · .claude/skills/run-concat/SKILL.md](https://github.com/jub0t/concat/blob/1ab750a339c5db249d353b21b9f3cc9ddb1a1a22/.claude/skills/run-concat/SKILL.md#L2)
- [jub0t/concat · src/crates/concat-cli/src/main.rs](https://github.com/jub0t/concat/blob/1ab750a339c5db249d353b21b9f3cc9ddb1a1a22/src/crates/concat-cli/src/main.rs#L9)
- [jub0t/concat · src/crates/concat-project/src/commands/properties.rs](https://github.com/jub0t/concat/blob/1ab750a339c5db249d353b21b9f3cc9ddb1a1a22/src/crates/concat-project/src/commands/properties.rs#L128)
- [jub0t/concat · src/crates/concat-core/src/animate.rs](https://github.com/jub0t/concat/blob/1ab750a339c5db249d353b21b9f3cc9ddb1a1a22/src/crates/concat-core/src/animate.rs#L8)
- [GuanYixuan/pyJianYingDraft · README.md](https://github.com/GuanYixuan/pyJianYingDraft/blob/6bb2d06a713f7b58e1375269daec835a03882086/README.md#L22)
- [luoluoluo22/jianying-editor-skill · scripts/jy_wrapper.py](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/jy_wrapper.py#L30)
- [luoluoluo22/jianying-editor-skill · rules/keyframes.md](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/rules/keyframes.md#L23)
- [sun-guannan/VectCutAPI · create_draft.py](https://github.com/sun-guannan/VectCutAPI/blob/cfa4779a52f1dc59a56d90cc5868778eb50c6a97/create_draft.py#L2)
- [sun-guannan/VectCutAPI · vectcut-skill/skill/SKILL.md](https://github.com/sun-guannan/VectCutAPI/blob/cfa4779a52f1dc59a56d90cc5868778eb50c6a97/vectcut-skill/skill/SKILL.md#L2)
- [zenstory-ai/video-recap-skills · skills/video-assemble/scripts/export_jianying.py](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-assemble/scripts/export_jianying.py#L1)
- [isYangs/jianying-editor-skill · scripts/jy_wrapper.py](https://github.com/isYangs/jianying-editor-skill/blob/a20c5228fcc88e27587c32d6d916f776869473b2/scripts/jy_wrapper.py#L37)
- [wangcanyu/daihuo-fanpai · deliver.py](https://github.com/wangcanyu/daihuo-fanpai/blob/b296543ca7097d002a272271886033dcd82c5b59/deliver.py#L14)
- [ops120/video-recap-skills-plus · skills/video-assemble/scripts/export_jianying.py](https://github.com/ops120/video-recap-skills-plus/blob/edd5c1b6d341aa30af9a4cf63a89a396631d6f18/skills/video-assemble/scripts/export_jianying.py#L1)
- [Xanthus-Sanslab/jianying-ai-mcp · src/jianying_ai_mcp/draft_ops.py](https://github.com/Xanthus-Sanslab/jianying-ai-mcp/blob/ae14f5356ae1499a247937077af550a34d580beb/src/jianying_ai_mcp/draft_ops.py#L10)
- [Xanthus-Sanslab/jianying-ai-mcp · pyproject.toml](https://github.com/Xanthus-Sanslab/jianying-ai-mcp/blob/ae14f5356ae1499a247937077af550a34d580beb/pyproject.toml#L12)
- [jjjane233/jianying-editor-skill-11.5 · skills/jianying-editor-11-5/SKILL.md](https://github.com/jjjane233/jianying-editor-skill-11.5/blob/133399a1f9a581be394a2c043e8f649a7145650c/skills/jianying-editor-11-5/SKILL.md#L3)
- [DogeCoding/capcut-skill · SKILL.md](https://github.com/DogeCoding/capcut-skill/blob/aaa0b8f8a3c660759ef421454d488452f19c1688/SKILL.md#L2)
- [mcncarl/yichen-skills · LICENSE](https://github.com/mcncarl/yichen-skills/blob/9bd78982aa75aa179258bc9009fe4dcf2f2973b9/LICENSE#L6)
- [mcncarl/jianying-headless · LICENSE](https://github.com/mcncarl/jianying-headless/blob/42b3d75b15bd9f3a9bb4c11b2f5205f7b4312252/LICENSE#L6)
- [DreamLab-AI/agentbox · concatcontainer/README.md](https://github.com/DreamLab-AI/agentbox/blob/da800ade9d09c77a08d8642f76c30b9b94364519/concatcontainer/README.md#L3)


## 本地产物与验证范围

- `research/concat-pyjianyingdraft-skills/repository-metadata.json`：17 个相关仓库的元数据。
- `research/concat-pyjianyingdraft-skills/github-repository-search.json`：GitHub 检索查询与候选结果；结合公开网页搜索补充。
- `research/concat-pyjianyingdraft-skills/release-checks.json`：Concat 0.2.6、pyJianYingDraft 0.3.0 发布与 PyPI 依赖信息。
- `research/concat-pyjianyingdraft-skills/companion-skill-findings.json`：Skill 入口、YAML 核查、适配关系、commit、源码行号和排除理由。
- 同目录 `sources/`：新增候选的文本/代码快照；已有 Concat、pyJianYingDraft、VectCutAPI 快照复用 `research/agent-video-kernels/sources/`。

完成公开源码、标准 Skill 入口、许可文件、SDK 调用关系、版本与本机基础依赖检查。没有安装候选程序或新 Skill，没有启动 Docker/WSL，没有实际打开编辑器或渲染样片。源码文本快照不是完整可运行安装包；编译/运行依赖与素材未包含。网页检索使用检索工具，没有打开浏览器标签页。
