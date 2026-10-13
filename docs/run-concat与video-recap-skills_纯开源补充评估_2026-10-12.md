# run-concat 与 video-recap-skills：纯开源补充评估


| 文档编号 | RESEARCH-2026-10-010 |
|---|---|
| 状态 | 有效 |
| 本次审计复核 | 2026-10-13 |
| 证据性质 | 源码与 Skill 研究；未完成运行验证 |
核查日期：2026-10-12，Asia/Taipei。沿用“不得使用剪映、视频制作采用开源方案、原生 Windows、禁止 Docker/WSL”的项目约束。本轮审查源码和依赖，没有安装、启动编辑器或执行视频制作。

**video-recap-skills 应纳入工作流候选：它确有独立 FFmpeg 成片路径，剪映草稿导出只是可选项。run-concat 则应作为 Concat 的构建与运行验证 Skill 评估，不能把它计为已经具备的广告剪辑工作流。**

## 按仓库 Star 比较

| 候选 | 本次 Star | 开源状态 | 实际职责 | 对本项目的判断 |
|---|---:|---|---|---|
| [Concat + run-concat](https://github.com/jub0t/concat/blob/fa51932e73d30bc01a9acd3e2910d7602bba9ca0/.claude/skills/run-concat/SKILL.md) | 4,791 | Concat 主仓库 AGPL-3.0 系列 | 编译 Rust/Slint 程序、启动桌面应用、验证开发修改 | 可保留为独立内核研发路线；Skill 不负责选段、字幕、广告编排或运镜预设 |
| [zenstory-ai/video-recap-skills](https://github.com/zenstory-ai/video-recap-skills) | 563 | 工作流代码 MIT；默认 AI 使用云端服务 | 理解、导演/写稿、切片拼剪、配音、混音字幕、编排与 QC | **有实际复用价值**；核心剪辑/合成独立，严格全开源完整流程还需调整 AI 依赖 |

Star 是所属仓库的数值，不是单个 Skill 独立获得的 Star。此前 Concat 4,783 是同日较早快照，本轮刷新为 4,791。[本轮 API 元数据](E:/dev/sandbox/AI广告剪辑/research/editor-parity/run-concat-recap/github-metadata.json)

## run-concat

最新主分支中的 Skill 明确定位为“Build, launch, and verify” Concat。它解释 Cargo 工作区在 `src/`，列出 `cargo run`、`cargo check`、测试与 lint，并指导开发者检查真实 GUI 行为。这是有用的开发入口；不是只凭加载该 Skill 就能完成广告剪辑的配方。

Concat 程序本身是独立开源编辑器，不能因 Skill 用途有限而否定它已有的时间线、效果和自动化内核。本轮只刷新 `run-concat` 源码；程序能力沿用前次固定源码审查，不将最新主分支全部能力视为已重新验证。

截至本轮 API 检查，最新正式发行仍为 `v0.2.6`，Windows x86_64 二进制问题 #303 仍开放。主分支可能有后续修补，是否解决本机启动/导出需要验证对应构建；不能只依据问题开放就断言所有版本不可用。

[最新发行](https://github.com/jub0t/concat/releases/tag/v0.2.6)、[Windows 问题 #303](https://github.com/jub0t/concat/issues/303)、[状态快照](E:/dev/sandbox/AI广告剪辑/research/editor-parity/run-concat-recap/concat-release-status.json)

**结论：保留 Concat 研发候选。后续仍需建设 Concat 创作 Skill、命名运镜与广告预设，并验证原生 Windows 导出；run-concat 本身不能填补这些部分。** 建议本地名 `$video-cut-run-concat`，当前未安装。

## video-recap-skills

固定提交 `539168622918e058bd250c793b82f043eced31e0` 与本轮最新主分支一致，实际有 **7 个标准 Skills：6 个生产环节 + 1 个按需参考环节**。因此不能仅按“剪映草稿导出工具”描述它。

| 上游 Skill | 实际能力 | 建议本地调用名（尚未安装） |
|---|---|---|
| video-understanding | 场景、语音、画面理解与时间轴证据 | `$video-cut-recap-understanding` |
| video-script | 故事/视听决定、选段计划、解说写作与检查 | `$video-cut-recap-script` |
| video-cut | 单源/多源按计划选段拼剪、句界与帧网格校验 | `$video-cut-recap-cut` |
| video-voiceover | 配音、分段音频与位置记录 | `$video-cut-recap-voiceover` |
| video-assemble | 压低原声、BGM、字幕、图文叠层与响度处理 | `$video-cut-recap-assemble` |
| video-recap | 环境诊断、整条流程与续跑/QC | `$video-cut-recap` |
| video-reference | 按需提取参考视频的创作依据 | `$video-cut-recap-reference` |

[上游 Skill 目录](https://github.com/zenstory-ai/video-recap-skills/tree/539168622918e058bd250c793b82f043eced31e0/skills)

`video-cut` 会输出 `edited_source.mp4`；`video-assemble` 实际构建 FFmpeg 音视频滤镜并输出最终 MP4、字幕与 `timeline.json`。源码的 `EXPORT_JIANYING` 默认是 False，剪映 exporter 在启用该选项时才进入输出流程。**可以保留独立剪合路径，遵守本项目不使用剪映的要求。**

[FFmpeg 合成实现](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-assemble/scripts/assemble.py)、[默认关闭草稿导出](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-assemble/scripts/lib.py)、[中性时间线说明](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/docs/timeline-and-jianying.md)

它的强项是解说和混剪：选段、避免切断台词、按剪后画面写解说、混音/字幕、实际成片 QC。这些方法可复用于素材讲解、产品解说或叙事广告；从剧情解说转成广告，还需要加入品牌、卖点、证据、Hook 和 CTA 的创作约束。

它当前时间线中的关键帧主要是**音量自动化**。画面包装实现包含静态图片、标题/标注和字幕；所核实的这些模块没有通用画面推拉平移、曲线变速或一键 AI 特效库。其对白/剪辑边界锚点也不是用户所指的运镜关键帧预设。该判断针对已审查模块，不能解释为 FFmpeg 无法另外实现这些效果。

[音量与素材时间线](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-assemble/scripts/timeline.py)、[包装图层实现](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-assemble/scripts/packaging.py)、[切片 Skill](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-cut/SKILL.md)

### 严格全开源完整流程的调整

默认 ASR、VLM、TTS 指向小米 MiMo，Fish Audio 是可选配音服务。MIT 工作流代码不能证明这些托管服务也构成本项目要求的开源实现。因此应分别将 ASR、画面理解和配音接到许可证合适的开源模型，保留该项目需要的时间轴/音频契约并验证效果；已有本地音频/字幕时可先复用机械剪合部分。

最新代码已包含 `index-tts` 自托管 TTS 传输入口，不能说配音只能走 MiMo/Fish。该入口接收明确配置的 JSON→WAV 服务，但不会自动安装模型，也不支持全部情绪、语速等控制；端点存在不证明其服务与权重许可证符合约束。ASR/VLM 默认路径仍需单独处理，不能将换一个 TTS provider 当成整条流程完成开源化。

[ASR 实现](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-understanding/scripts/asr.py)、[自托管 TTS 契约](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/skills/video-voiceover/references/index-tts.md)

仓库示例包含可选 Remotion 包装路线。由于本项目采用严格开源筛选，应使用 FFmpeg 等合格组件实现包装，不把该示例的全部制作依赖直接照搬。[示例中的包装路径](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/examples/guohuo-60s/README.md)

上游 CI 有 Windows/macOS/Linux 的 Python lint 与测试配置；该 workflow 没有安装 FFmpeg。不能据此宣布三个平台的实际视频制作链都通过了渲染验收。[CI 配置](https://github.com/zenstory-ai/video-recap-skills/blob/539168622918e058bd250c793b82f043eced31e0/.github/workflows/skill-validate.yml)

## 两者能否组合达到剪映水准

可以作为“创作流程层 + 独立编辑内核”的研发组合，但目前没有核实到现成的官方对接。video-recap 的中性 `timeline.json` 不意味着它能直接进入 Concat；素材引用、时间/帧、音轨、字幕和动画参数需要转换及验证。

`run-concat` 不提供该转换层。video-recap 也不能自动补齐 Concat 的画面运镜或完整 AI 特效。组合后能否达到目标，要用真实广告样片、可修改工程和重复导出验证，不能用两个仓库的 Star 相加作结论。

**当前建议：复用 video-recap 的选段、解说、混音、字幕与 QC 方法；优先将运镜和可修改工程交给已选的 Shotcut + shotcut-mcp 路线。Concat 保留作独立内核替代候选。** 这是待集成的架构建议，不是已经运行成功的整包。上一轮的主选型不变，但补上了有价值的现成创作流程候选。

[主选型报告](E:/dev/sandbox/AI广告剪辑/docs/纯开源_程序与Skill_剪映水准评估_2026-10-12.md)、[video-recap 源码审查快照](E:/dev/sandbox/AI广告剪辑/research/concat-pyjianyingdraft-skills/sources/zenstory-ai__video-recap-skills/source-snapshot.json)
