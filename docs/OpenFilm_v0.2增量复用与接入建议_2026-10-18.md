# OpenFilm 0.2.0 增量复用与接入建议

| 项目 | 内容 |
|---|---|
| 文档编号 | RESEARCH-OPENFILM-INCREMENT-2026-10-18 |
| 状态 | 有效 |
| 核查时间 | 2026-10-18 00:27，Asia/Taipei；获取记录保存 UTC |
| 来源 | [openfilm/openfilm](https://github.com/openfilm/openfilm) |
| 当前固定提交 | `eefd6a8d379289102141359a4718dbab12170526`，CLI 0.2.0；2026-10-17 13:48:38 UTC 提交 |
| GitHub 当次快照 | **809 stars / 89 forks**，时点值，不是持久排名 |
| 比较基准 | 既有固定 `b138595d4c2d1fa5262b4a8a8c7cd98187c4b077` / CLI 0.1.7 |
| 证据 | [整树比较](validation/evidence/openfilm-refresh-20261018/verification.json)、[原生核验](validation/evidence/openfilm-increment-verified-20261018/verification.json) |
| 原研究 | [O01–O12、原生测试与工期假设](OpenFilm源码拆解与复用成本评估_2026-10-17.md) |

**可以拆用，建议继续保留现有 Agent Project + Python/FFmpeg 主链，按模块复用。** 最新增量中，跨项目片段组库最有直接价值，模板参数和参考片复刻流程其次。HTML 动效可弥补复杂标题、SVG/Canvas/WebGL 的表达能力，但需要额外浏览器后端；它并不补齐本地分割、修复、声音或完整剪映能力。

R02 是源码与数据研究，**没有把 0.2 新模块接入产品，也没有新增模型推理或编码视频**。R02 交付时最近完整产品基线是 V35 的 764/764；后续 V36 嵌套转场与 V37 本地片段组库另见末节及各自产品实测，不计入这批研究结果。

## 1. 这次比此前多检查了什么

此前复查只覆盖八个文件，本轮下载固定提交的完整 ZIP，与旧版 ZIP 逐路径/原字节比较，并对解包源码逐文件冻结：

| 编号 | 检查 | 结果 |
|---|---|---|
| R02.1 | 整棵源码而非选定八文件 | 旧版 619 → 新版 702 文件；**489 不变、126 改变、87 新增、4 删除**；净增 83 |
| R02.2 | 已采用/候选核心是否变更 | 字幕分句、timeline-edit、transitions、look、render、host、nle 与 MIT 原文均与旧固定版相同 |
| R02.3 | 新增业务内容 | 跨项目 Saved、片段组入轨、模板参数、十份官方 Skill、网页 capture，以及桌面/界面更新 |
| R02.4 | 获取溯源 | 新 ZIP 11,289,603 字节，SHA-256 `7af40e33f59a43c4426fcb4332a964bf3f814b63b954d375d557c964160dcee2`；请求/原 API/126 份补丁保留 |
| R02.5 | 原树完整性 | 702 文件在实跑前后 SHA-256 全部相同；独立副本只改 2 个依赖边界文件 |

[源码 ZIP](../sources/upstream/openfilm-0.2.0/repo.zip)、[请求记录](validation/evidence/openfilm-refresh-20261018/requests.json)和[逐文件摘要/完整差异清单](validation/evidence/openfilm-refresh-20261018/verification.json)可复查。ZIP 是研究材料，产品没有安装/升级上游 runtime。

## 2. 面向当前项目的复用顺序

工期为工程估算：一名熟悉现有 Python/Node/FFmpeg 的工程师，每人日约 6 小时有效开发；包含对应范围的适配和针对性验证，不包含完整剪映等价、发行、自然广告黄金集或大规模性能。既有功能不再次计入节省，相关模块有共享工作，**各行不能简单相加**。

| 编号 | 可复用内容/固定源码 | 如何降低成本 | 当前产品关系与约束 | 建议 / 后续适配估算 |
|---|---|---|---|---|
| O01 | [subtitle-segments.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/server/subtitle-segments.mjs) | 直接复用中文/英文分句、数字单位保护、双语分段和局部回写规则 | **已进入 V34**，固定原字节 Node worker；不是 ASR、逐字对齐或翻译模型 | 已接入，不重算工期/收益 |
| O02 | [timeline-edit.ts](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/ui/src/lib/timeline-edit.ts) | 关联、同步锁、主轨联动、跨轨删除/闭隙的规划规则和测试 | **整片段子集已进入 V33**；完整源边缘裁切、插入/覆盖、磁吸重排仍需专门实现与验收 | 保留既有适配；未实现部分另立契约 |
| O03 | [transitions.ts](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/ui/src/lib/transitions.ts) | 添加/调整/移除转场及关联音频的操作流程 | **V35 已借鉴工作流**，本地真实源句柄为新实现；不能称为原算法整体移植 | 无需重复接一套移位/换轨模型 |
| O13 | [saved.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/server/saved.mjs)（316 行）+[saved-insert.ts](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/ui/src/lib/saved-insert.ts)（40 行） | 跨项目保存片段组、收集资源、保留相对轨道/时差、重新生成 link ID；可做可复用片头、CTA、字幕包装组 | **后续 V37 已实现受控子集**：本地不可变片段组、作者 tick/嵌套/字体/LUT/字幕与权利历史闭包、独立 ID 跨工程可编辑插入；相同执行上下文、嵌套入轨，展开多轨/来源撤回传播未验 | R02 原估算 3–5 人日、同范围从头约 6–10；已接入子集见末节，未记录实际人时，不宣称实测节省 |
| O14 | [template-controls.ts](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/ui/src/lib/template-controls.ts)（127 行）+ overrides | CSS 变量类型/单位、文字、图片替换与覆盖恢复；可让 Agent 批量改 HTML 标题卡品牌色/文案/产品图 | 本项目 JSON 模板变量已有；这是将来 HTML 模板桥，不能当新增全套模板系统；需资源/字体权利与离线闭包 | **随 HTML 后端，1–3 人日增量**；同范围从头约 3–5；不含 HTML 渲染 |
| O04/O06 | [look.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/src/look.mjs) + host 的时钟/乱序机制 | 联系表、两种乱序重复绘制、字体/页面错误/越界检查；减少 Agent 只生成而不验片的缺口 | 适用于 frame(t) 页面；当前 FFmpeg 普通视频不是同一执行模型；抽样确定性不证明美感/每帧质量 | **质量工具候选，3–5 人日**；从头约 6–10；与 O05 共享工作 |
| O05 | [render.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/src/render.mjs) + host/seekable | HTML/CSS/SVG/Canvas/WebGL 动效、透明层、时间采样与运动模糊编排 | 可独立于 React/Electron，但仍需要 Node + Playwright + Chromium；输出登记为本地资产，再交现有 FFmpeg 主链 | **第二批可选后端，5–10 人日**；同范围从头约 12–20；不含完整色彩/HDR/性能验收 |
| O07 | [nle.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/server/nle.mjs) | xmeml v4、帧边界量化、重叠 lane、可表达参数与烘焙任务计划 | 当前已有 OTIO/Kdenlive/明文草稿，增量主要是 XML；原路径会烘焙旋转/速度/网页效果，需能力损失报告 | **按互操作需求，3–6 人日**；从头约 7–12；未在 Premiere/Resolve 打开实测 |
| O15 | [官方十份 Skill](https://github.com/openfilm/openfilm/tree/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/skills) | 参考片拆解、节奏对照、录屏追焦、长转短、产品发布片等创作流程和交付标准 | 原文使用 `npx openfilm`/`get`/服务商，不能原样接入；需改成本地资产、现有 CLI、受检模型与实际对照。Skill 是任务指导，不会自动新增视觉理解/模型算法 | **参考片/录屏/长转短优先，单套流程 1–2 人日**；从头约 2–4；不含缺失功能实现 |
| O16 | [capture.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/src/capture.mjs)（51 行） | 页面全图/元素截图、视口/主题和点击隐藏编排 | 默认接受网络页面，不符合本项目默认离线；已有浏览器工具时净收益小。将来仅显式本地静态页面，输出再登记 | **低优先，不进默认运行时**；无本轮功能/截图实测 |

**R02 当时的下一批建议为先建设 O13，再适配 O15；O13 已于后续 V37 接入受控子集，详见末节。HTML 动效仍独立设为可选后端里程碑。** O13 先支持现有模型中可无损表达的片段组，对不支持的总线、绑定及动态闭包明确报错，不能悄悄丢失。无需因引入 O13 替换现有素材索引、模板、权利台账或事务系统。

## 3. 新官方 Skills 的可借鉴内容

主仓库 `packages/openfilm/skills/SOURCE` 指向独立 [openfilm/skills 固定提交](https://github.com/openfilm/skills/commit/702f16944c14d64a87fc5149cb865bd5c95c895f)。独立仓库当次 API 为 **0 stars / 0 forks**，代码/文档 MIT；不能把主仓库的 809 stars 当成每份 Skill 的星数。十份都是同一套仓库内容，不存在独立 star 排名。

| 编号 | 原 Skill | 适合借鉴的内容 | 本地接入前需替换 |
|---|---|---|---|
| S01 | replicate | 先拆参考片的镜头/字幕/运动/声音节点，再按同时间点对照输出；保留参考与制作资产的区别 | 远程取片、npx/get；实际视觉理解、素材授权和图像差异标准需由本地链提供 |
| S02 | screen-demo | 录屏死时间裁切、动作追焦、局部放大、步骤可读性 | Web 动效/录屏来源映射为已有跟踪、重构图与关键帧 CLI；语义检测不能由文字流程冒充 |
| S03 | long-to-short | 保持原说话含义、完整问答、停顿切口、竖屏安全区 | 上游在线 ASR 改为显式注册的本地 ASR；逐字时钟质量仍单独验收 |
| S04 | keynote | 产品发布片结构、单一主张、产品展示节奏 | 依赖素材/模型、网页动效与实际产品画面来源 |
| S05 | motion-graphics | 为主题设计标题/图表动效与每秒运动 | HTML 后端尚未集成；现有 FFmpeg 参数能力与生成模型边界需分清 |
| S06 | presenter-pip | 讲解画中画与信息画面编排 | 本地人物抠像、重构图、音画同步和画面安全区 |
| S07 | lyric-video | 歌词节奏/字词进出与歌曲专属视觉 | 本地逐字对齐、歌词/音乐权利和声学误差 |
| S08 | collage | 拼贴构图/纸片运动方向 | 授权贴图/字体与现有运动/蒙版能力 |
| S09 | whiteboard | 讲解、绘制与配音节点编排 | 笔画路径/动画渲染与已授权本地配音 |
| S10 | vintage-film | 记忆片叙事、旧胶片质感与转场节奏 | 效果参数、素材权利及受控画质验证 |

本轮只读这些上游说明，**没有按其中指令调用服务商、安装 Skill 或开启浏览器**。后续正式创建/适配仍使用 `$video-cut-` 前缀，绑定固定本地入口，不引入 latest 自动获取。

## 4. 实际执行及隐藏依赖

原生 Windows；Node **v22.14.0**，现有原生 Python 3.13。CLI package 声明 Node≥22.2，上游源码开发文档要求≥22.18；这里只能说明选定子集在所记录 Node 下的结果。没有 npm/pnpm install、prepare/postinstall、完整构建、上游 CLI/Studio/Electron、浏览器、线上模型、Docker 或 WSL。

| 编号 | 执行与结果 | 含义/限制 |
|---|---|---|
| N01 | 原树四文件：**12 条通过，1 个文件加载失败** | 模板 8、overrides 1、官方 Skill 结构 3 通过；saved.test 经 files→shared→host 间接导入，缺 `playwright-core`；6 个 Saved 业务测试尚未开始执行，不能写作“片段库算法失败” |
| N02 | 原树 saved-insert.test：**1 个文件加载失败** | 经 timeline-edit→timecode 间接导入，缺 React；2 个业务测试尚未开始 |
| N03 | 只改两处依赖边界的独立副本：**20/20，0 skip/cancel** | 6 Saved + 8 模板 + 1 overrides + 3 Skill 结构 + 2 groupInsert；N01 已通过的 12 在这批重跑，是子集，不能相加为 32 |
| N04 | **两组实际文件/数据样例** | 保存并取用片头/Logo 组，保留相对轨道/0.5 秒时差，新 link 避免碰撞，修改目标副本不改变原文件；模板换色/文案/图片保留未改样式与单位 |
| N05 | 原树 702 文件前后全部 SHA-256 相同 | 原始目录未修改；副本只有 `timecode.ts` 与 `shared.mjs` 不同，未改 Saved、插入规划、模板业务算法或测试 |
| D01 | 首次自动脚本期望 N01 全通过，实际 **12 pass + 1 load failure**，脚本停止 | 暴露此前未计入的间接 Playwright 耦合；[原始日志](validation/evidence/openfilm-increment-20261018/N01-original-data.stdout.log)和[执行记录](validation/evidence/openfilm-increment-20261018/N01-original-data.json)保留。随后按真实依赖分离、在新目录重跑，未覆盖失败 |

两处副本改动：[React Hook 移除补丁](validation/evidence/openfilm-increment-verified-20261018/react-hook-only.patch)；[host 延迟导入补丁](validation/evidence/openfilm-increment-verified-20261018/lazy-host-import.patch)。后者只把 host 导入移到 `open()` 内，未替换其浏览器功能，也没有伪造 Saved 的执行结果；这批测试/样例没有调用 `open()`。

数据：[片段组保存/取用/入轨计划](validation/evidence/openfilm-increment-verified-20261018/S03-saved-group.json)、[模板覆盖原值/实际结果](validation/evidence/openfilm-increment-verified-20261018/S04-template-overrides.json)。这是文件与结构化数据核验，**没有编码帧/连续播放/听审、DOM/CSS 像素检查或自然广告内容验收**，因此不发布冒充实测成片的 GIF。此前产品演示仍见 README 的 V33/V34/V35。

20 项为本轮选定上游研究子集；此前原研究 58/65、产品 V35 764 各自保留，不累加通过数。本轮未重跑完整产品套件，未验证上游全套测试或跨 Node/跨设备兼容。

## 5. 运行时、许可与产品接入约束

1. **不整体替换内核。** `film.html` 以秒/ms 和网页页面组织时间线，不等同于现有 90k ticks、独立画布、嵌套时钟、音频总线、事务/锁/队列及权利闭包。GUI 目录含可拆的纯算法，删 GUI 前需先提取。
2. **HTML 是额外后端。** `FilmPage.open` 的 `offline` 默认 false；当前 `render.mjs` 的 probe/worker 未全面传该参数。新 capture 默认外网导航。正式引入必须统一所有探测/worker/字体/CDN/WS/Service Worker 的离线策略，固定浏览器与本地资源，补超时/取消、进程/页面 finally 回收与配额。源码存在 close() 不代表本轮已实测回收。
3. **画质另验。** 不透明截图默认 JPEG95，透明 PNG，多快门样本平均不是自动获得 HDR/线性光或剪映运动模糊等价；乱序双绘只是抽样确定性。先测 CFR 帧时钟、Alpha 边缘、颜色/字体与高频纹理，再谈自然内容。
4. **AI 云连接不复用。** `get` 与 provider 连接没有提供可直接替换本地 SAM2/RVM/LaMa/VACE/SoulX 等的离线算法，不能把服务商路由当作本地特效内核。既有本地模型的自然质量负担仍在。
5. **保留版权和来源。** 主仓库与独立 Skill 仓库均 MIT，完整许可原文保存于源码 ZIP 与 [Skill 许可](validation/evidence/openfilm-refresh-20261018/skills-LICENSE.txt)；品牌/Logo 按 TRADEMARK，Playwright/Chromium/字体/FFmpeg 各自许可。源码 MIT 不替代素材、模型、配音、模板的权利台账。现有复用声明见 [third-party 记录](third-party/OpenFilm复用声明_2026-10-17.md)。

按此路径能减少局部设计、边界处理和测试数据构建的重复工作。没有实际开发人时记录，不能宣称本轮已经节省表中工期，也不能据源码量估算整个剪映差异关闭比例。

## 6. 复现

以下命令由本仓库根目录执行，要求输出目录尚不存在。第一步属于显式源码研究联网，第二步只用已获取的本地源码，不安装任何 npm 包。

```powershell
C:\Python313\python.exe -B -X utf8 scripts/audit_openfilm_refresh.py --fixed sources/upstream/openfilm/repo.zip --archive sources/upstream/<新固定快照>/repo.zip --output docs/validation/evidence/<新整树证据目录> --work product/.runtime/<新源码目录>
C:\Python313\python.exe -B -X utf8 scripts/audit_openfilm_increment.py --source product/.runtime/<新源码目录>/source --output docs/validation/evidence/<新模块证据目录> --work product/.runtime/<新模块临时目录>
```

[获取/整树比较脚本](../scripts/audit_openfilm_refresh.py)保存固定提交原始 ZIP、API、逐文件摘要与文本补丁；[独立模块核验脚本](../scripts/audit_openfilm_increment.py)保存缺失依赖日志、两处补丁、原测试和实际数据。没有调用浏览器，故本轮无新增 tab 需要关闭。

## 后续产品增量：V36

本研究之后，V36 已原生补充含转场子序列的父级裁切/倒放/恒速/曲线合成，见[契约](specs/嵌套转场合成与作者时钟契约_v0.1_2026-10-18.md)和[22 组/完整回归实测](validation/嵌套转场与父级重映射实测_2026-10-18.md)。这是既有 O03 工作流实现的后续扩展，没有接入 O13 Saved/HTML/其他 0.2 新 runtime；R02 原 20 项研究与 V36 完整产品套件分计。

## 后续产品增量：V37

O13 的本地可复用片段组工作流已进入产品：`fragment save/list/inspect/apply`，保存已编辑内容、自动补全关联/转场/绑定源、递归资源及权利闭包，并在另一工程以独立 ID 的可编辑嵌套组使用。见[契约](specs/可复用片段组库与跨项目插入契约_v0.1_2026-10-18.md)与[六组/五项拒绝/814 完整实测](validation/可复用片段组库与跨项目插入实测_2026-10-18.md)。340 新主帧和 163.2 万立体声采样帧与固定 V36 手工作者工程完全一致；这项参照不能独立证明既有渲染算法或剪映等价。

适配没有引入上游 GUI、HTML、在线资源或执行器，也没有自动安装十份上游 Skill；四份现有 `$video-cut-` 技能已加入库的使用流程。首版要求相同执行上下文，只做嵌套入轨；展开式合并、跨 FPS/色彩、部分闪避总线、自动传播权利变更及大规模内容库仍开放。R02 的 3–5 人日是原估算，不能以本次代码量或测试通过数倒算实际节省。下一步可结合 O15 做参考片/录屏/长转短任务工作流；HTML 后端继续单独评估成本。
