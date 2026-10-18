# OpenFilm 官方 Skill 到本地能力的映射

这十份 Skill 最适合复用创作步骤和交付标准。它们是任务说明，不是新的视觉理解、对齐或生成算法；本轮没有安装或运行这些 Skill，也没有据此新增成片验收。源码固定 `eefd6a8d`，各文件摘要/行数及当前本地 CLI 分发表静态核对见[机器记录](validation/evidence/openfilm-skill-local-mapping-20261018.json)。命令名存在不代表表中整个创作工作流已实现或效果已达标。

| 编号 | 上游 Skill | 现有本地入口，可作为改写目标 | 应复用的任务步骤 | 仍需实现/独立验收 |
|---|---|---|---|---|
| S01 | [replicate](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/replicate/SKILL.md) | `media understand`、`timeline compose`、`motion apply`、`quality golden`、`rights check` | 参考片与生产素材分开；按同时间点核对剪口、文字、动作和声音，说明实际偏差 | 自动视觉语义拆解、风格复刻和自然质量；参考片音乐/画面不自动取得发布权利 |
| S02 | [screen-demo](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/screen-demo/SKILL.md) | `media smart-cut/track/reframe`、`motion apply`、`timeline compose` | 真实录屏的裁剪、等待段计划、追焦/放大、速度披露与可读性检查 | 界面语义和点击自动定位、逐帧隐私审查、实际录屏入口；跟踪不能冒充理解点击 |
| S03 | [long-to-short](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/long-to-short/SKILL.md) | `subtitle transcribe/segment`、`media highlights/reframe`、`timeline edit` | 保留完整问答与限定条件；选段卡、竖屏构图和字幕流程 | 稳定逐词强制对齐、语义完整性、通用说话人/高光质量；启发式候选分数不是内容质量 |
| S04 | [keynote](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/keynote/SKILL.md) | `ad plan/apply`、`motion html-source/html-render`、`template apply` | 每项主张配真实产品证据，保持品牌、数字和标题可编辑 | 产品素材、事实校核、完整发布片美学和一致性；线上抓取/生成改为明确本地来源 |
| S05 | [motion-graphics](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/motion-graphics/SKILL.md) | `motion html-controls/html-render/html-quality`、`fragment apply` | 主题化图表/标题、参数化改稿、可重建动效和全帧报告 | 复杂字形/变换、Canvas 语义、WebGL/完整媒体和自然美学；门禁通过不等于高级动效 |
| S06 | [presenter-pip](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/presenter-pip/SKILL.md) | `media matting/track-bind`、`timeline compose`、`subtitle transcribe` | 讲解窗口避让重点/字幕/平台按钮，按讲话切换信息 | 词级同步、发丝/手持物边缘、遮挡和自动内容理解，需要自然长片独立核验 |
| S07 | [lyric-video](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/lyric-video/SKILL.md) | `subtitle normalize/segment`、`timeline compose`、`motion apply` | 原歌词/行次、字词视觉设计及独立时间误差报告 | 上游要求唱词落点误差在两帧内；当前没有满足该指标的独立歌曲强制对齐实测，估时不能代替 |
| S08 | [collage](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/collage/SKILL.md) | `media ingest/mask-edit`、`timeline compose`、`fragment save` | 有来源的照片/纸片/文字拼贴，人物不被擅自改变，可复用包装组 | 授权内容库与自然拼贴风格；现有模板/片段组不等于版权素材商城 |
| S09 | [whiteboard](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/whiteboard/SKILL.md) | `motion html-source/html-render`、`tts synthesize`、`timeline compose` | 按解说逐笔绘制，报告声音/笔画节点偏差 | 笔画路径生成、逐词/逐笔对齐和自然成片；整图淡入不是逐笔绘制 |
| S10 | [vintage-film](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills/vintage-film/SKILL.md) | `lut register`、`timeline compose/transition`、`audio extract` | 保留人脸/事件原貌、真实日期/顺序与调色叙事 | 具体胶片材质/颗粒组合、自然美学和真实元数据；不自动修脸、扩图或生成人物动作 |

建议顺序为 **S01 / S02 / S03**。三者能直接组织已有剪辑、重构图、字幕和质量入口；先限定一段有权利的本地素材、一份明确编辑计划和独立时刻对照，完成一次真实工作流，再决定是否扩展为正式 Skill。后续若创建仍使用 `$video-cut-` 前缀，并替换上游 `npx/get/capture`、在线服务和自动下载步骤。固定本地工具、模型和资产；需要的能力未存在时明确记录缺口。

与主仓库整体代码的[当前复用决策](OpenFilm当前复用决策_2026-10-18.md)分开看：字幕、帧时钟、片段组和 HTML 参数已有产品采用；本表十套流程仍未正式接入。成本继续沿用[原同范围假设](OpenFilm_v0.2增量复用与接入建议_2026-10-18.md)，历史单流程约 1–2 人日只包含已有能力上的步骤适配和针对性核验，不包含新增模型、素材库或完整自然画质。

这十份文件来自同一份固定仓库内容，没有独立 star 计数。主仓库本次 853 stars / 91 forks 仅是[API 时点](validation/evidence/openfilm-release-review-20261018/verification.json)，不能作为十份 Skill 各自的排行榜。原代码许可、素材/模型权利与实际功能验收分别维护。
