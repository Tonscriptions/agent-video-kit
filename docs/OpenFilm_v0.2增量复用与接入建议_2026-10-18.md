# OpenFilm 0.2.0 增量复用与接入建议

| 项目 | 内容 |
|---|---|
| 文档编号 | RESEARCH-OPENFILM-INCREMENT-2026-10-18 |
| 状态 | 有效 |
| 核查时间 | 2026-10-18 00:27，Asia/Taipei；获取记录保存 UTC |
| 来源 | [openfilm/openfilm](https://github.com/openfilm/openfilm) |
| 当前固定提交 | `eefd6a8d379289102141359a4718dbab12170526`，CLI 0.2.0；2026-10-17 13:48:38 UTC 提交 |
| GitHub 当次快照 | R02 为 809 stars / 89 forks；V41 复核为 **832 stars / 90 forks**（2026-10-18 06:27，Asia/Taipei），均为时点值 |
| 比较基准 | 既有固定 `b138595d4c2d1fa5262b4a8a8c7cd98187c4b077` / CLI 0.1.7 |
| 证据 | [整树比较](validation/evidence/openfilm-refresh-20261018/verification.json)、[原生核验](validation/evidence/openfilm-increment-verified-20261018/verification.json) |
| 原研究 | [O01–O12、原生测试与工期假设](OpenFilm源码拆解与复用成本评估_2026-10-17.md) |

**最新落地状态（V41）**：固定上游提交未变；新增本地 HTML/SVG/Canvas 最小后端，原帧时钟按字节采用，其余资源封装、事务、精确 PTS 和进程回收为本项目实现。下列 R02/R03 估算和失败记录按历史保留，当前采用范围见[本页 V41](#产品增量-v41离线动效与可重建源码)与[实际视频/失败记录](validation/离线HTML动效源码与透明合成实测_2026-10-18.md)，不能把历史待办当成全部仍未实现。

后续复核：**2026-10-18 03:04（Asia/Taipei），GitHub API 为 826 stars / 90 forks，main 仍为上述固定提交**；与 R02 当时的 809/89 分别保留，不能当作独立排行榜。网页缓存当次显示 819，实时 API 原文、时间/ETag/SHA 及初次端点尾斜线 404 后修正记录见[复核证据](validation/evidence/openfilm-window-followup-20261018/verification.json)。无新增上游代码差异，未重新计算 R02 的测试通过数。

产品后续 V38 继续补齐 O02 指出的内部裁切缺口，采用本项目新实现的[输出窗口契约](specs/片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md)；不是上游时间线算法整体移植。实际核验与边界见[独立实测](validation/输出窗口裁切与作者时钟实测_2026-10-18.md)。

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

## 2. 面向项目的复用顺序（R02 研究时估算）

工期为工程估算：一名熟悉现有 Python/Node/FFmpeg 的工程师，每人日约 6 小时有效开发；包含对应范围的适配和针对性验证，不包含完整剪映等价、发行、自然广告黄金集或大规模性能。既有功能不再次计入节省，相关模块有共享工作，**各行不能简单相加**。

| 编号 | 可复用内容/固定源码 | 如何降低成本 | 当前产品关系与约束 | 建议 / 后续适配估算 |
|---|---|---|---|---|
| O01 | [subtitle-segments.mjs](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/server/subtitle-segments.mjs) | 直接复用中文/英文分句、数字单位保护、双语分段和局部回写规则 | **已进入 V34**，固定原字节 Node worker；不是 ASR、逐字对齐或翻译模型 | 已接入，不重算工期/收益 |
| O02 | [timeline-edit.ts](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/studio/ui/src/lib/timeline-edit.ts) | 关联、同步锁、主轨联动、跨轨删除/闭隙的规划规则和测试 | **整片段子集已进入 V33**；后续 V38 原生补齐完整作者输出内裁切/拆分/内部波纹插删；V39 后续原生补齐 insert/overwrite/lift/extract/roll/slide 的作者范围内规划；源范围外扩与完整磁吸仍需实现验收 | 保留既有适配；未实现部分另立契约 |
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

V38 的输出窗口为本项目新实现，不是 `timeline-edit.ts` 的整体移植；保留完整作者图后切出输出区间，补齐复杂源时钟下的内部编辑。[30 新增专项/9 组实际音画/844 完整](validation/输出窗口裁切与作者时钟实测_2026-10-18.md)；成本估算仍没有实际人时记录，不能由通过数换算工期节省。

## 后续产品增量：V39

2026-10-18 04:01（Asia/Taipei）再查 API：**829 stars / 90 forks**，main 仍为 `eefd6a8d379289102141359a4718dbab12170526`；[原请求/摘要](validation/evidence/openfilm-range-followup-20261018/verification.json)。没有新增源码差异，R01/R02 研究通过数不重算。

本轮 V39：新增本地 `insert/overwrite/lift/extract/roll/slide` 六种专业范围编辑，复用完整作者输出窗口，保留曲线/倒放/动画/音频；关联音轨、同步锁、骑乘片段、文件字幕偏移、全差异计划和批量事务共用现有入口。完整 **897/897，1510.144 秒**，0 跳过；125 Python+2 MJS+Schema+pyproject+MIT 共 130 文件冻结，53 新增专项为完整子集。八组/73 CLI（59 成功、6 当前预期拒绝、8 固定 V38 缺项拒绝），340 新主帧、1,632,000 立体声采样帧与固定同产品 V38 完整作者选区/拼接完全相同；参照不是独立渲染或变速算法。89 文件离线 wheel/30 产品隔离 CLI、14 Skills/124 引用通过；四个时刻静态对照和 CTA 移位抽查，未连续播放/听审。开发报错优先级/非法 action、生成器错误码和复制幂等历史失败保留。roll/slide 只用保留作者句柄；源范围外扩、复杂关联 slip、完整磁吸、自然质量/长片资源、Schema 随包/干净机器与完整剪映等价仍未验收。 见[专业范围编辑实测](validation/专业范围编辑与滚滑剪口实测_2026-10-18.md)与[契约](specs/范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md)。该增量沿用已借鉴关联规则并新写原生范围规划器，没有继续搬入 GUI/HTML/上游执行器。仍无实际人时记录；不能由新增测试或局部代码量宣称节省整个项目的比例。

## 历史复用落地决策（R03）

**有可复用内容，推荐保持现有 Python/FFmpeg 主内核，按模块拆入。** 2026-10-18 再查公开 GitHub API，main 仍为 `eefd6a8d379289102141359a4718dbab12170526`，快照 829 stars / 90 forks，无需重复下载同一版本。获取时刻与响应原字节见[本次机器证据](validation/evidence/openfilm-current-review-20261018/verification.json)。网页显示可能存在缓存差异，本表按记录的 API 时点描述，不作永久 star 排名。

本次重新核对固定 ZIP 与本地 702 份上游文件、V39 的 130 份产品冻结文件，原字幕算法与 MIT 完全一致；同时检查文档本地文件链接。没有运行上游 CLI、Studio、浏览器、Docker/WSL、服务商、模型、编码器或新增 Skill；无新增 tab。历史 20 项上游测试及 897 项产品回归的原证据保留，**本次没有重跑，不能相加或改记为新的功能通过数**。这是源码与落地决策复查，不新增视频/GIF。

### 已采用的部分

| 编号 | 上游内容 | 当前本地实现及采用方式 | 剩余边界 |
|---|---|---|---|
| O01 | `studio/server/subtitle-segments.mjs` | [原字节算法](../product/src/ai_ad_editor/openfilm_subtitle_segments.mjs) + [Python 桥](../product/src/ai_ad_editor/subtitle_segments.py)；已进入 `subtitle segment` | 分句不是 ASR；缺词时钟的时间估算、真实语义和对齐质量不能由通过数替代 |
| O02 | `studio/ui/src/lib/timeline-edit.ts` | [edit_planner.py](../product/src/ai_ad_editor/edit_planner.py) 适配部分关联/主轨/同步规则；[range_edits.py](../product/src/ai_ad_editor/range_edits.py) 原生补充范围编辑 | 后续 V40 补齐有限源外扩/关联 slip；完整磁吸、任意嵌套旧主体时钟保真/跟踪重规划仍开放 |
| O03 | `studio/ui/src/lib/transitions.ts` | [source_transitions.py](../product/src/ai_ad_editor/source_transitions.py) 借鉴可逆转场工作流，重新实现真实源句柄 | 未照搬上游移位换轨；受限端点、自然画质及完整转场库仍需实现/验收 |
| O13 | `studio/server/saved.mjs` + `studio/ui/src/lib/saved-insert.ts` | [fragments.py](../product/src/ai_ad_editor/fragments.py) 借鉴保存/资源闭包/相对时间/ID 隔离流程，提供可编辑组库 | 首版嵌套入轨、相同执行上下文；展开式合并、跨 FPS/色彩和权利撤回传播未完成 |

以上模块已经形成受控能力，不再按“下一步复用”重复估算收益。代码、规则适配和工作流借鉴三种采用方式各自标明，MIT 原文继续随包，详见[复用声明](third-party/OpenFilm复用声明_2026-10-17.md)。

### 仍值得拆用的部分

下列工期沿用前述同范围估算：1 名熟悉本项目、Python/Node 的工程师，1 人日约 6 小时有效开发，包含适配与针对性验收；不是实测人时，也不包含完整剪映验收或整体产品开发。

| 顺序 / 编号 | 具体可拆模块与入口 | 在本项目中的接法 | 适配 / 同范围从头 | 必须验证的内容 |
|---|---|---|---|---|
| 先做流程 / O15 | 官方 `replicate`、`screen-demo`、`long-to-short` Skill；其余 7 份见第 3 节 | 将参考片拆解、录屏追焦、长转短的任务步骤绑定现有离线 CLI；正式适配用 `$video-cut-` 前缀 | 待明确动作清单后估算；这些文字本身不提供新算法 | 固定本地入口、原素材追溯、ASR/跟踪真实输出、明确验片标准；不原样执行 npx/get/在线下载 |
| HTML 后端 / O05 | `src/host.mjs` 的 `FilmPage.open`、`src/render.mjs`、`seekable/shared` | 独立 Node worker 驱动固定本地 Chromium，把 HTML/CSS/SVG/Canvas/WebGL 动效变为可登记的本地 RGBA 帧/资产，再交 FFmpeg 主图 | **5–10 / 12–20 人日** | 所有 probe/worker 离线拦截、固定字体与依赖哈希、取消超时、进程/page/context 回收、内存预算、帧时钟与 Alpha/颜色 |
| 随 HTML / O04、O06 | `src/look.mjs`、host 的时钟机制 | 提取联系表、两种乱序重绘和字体/越界/请求诊断；通过结果写入本项目质量报告 | **3–5 / 6–10 人日**，与 O05 有共享工作 | 确定性页面、动态字体/资源、失败报告、跨次取帧；抽样一致不代表每帧或美学验收 |
| 随 HTML / O14 | `template-controls.ts`、`overrides.mjs` | 作为现有模板库的 HTML 参数适配器，保留品牌色、文字、图片及 CSS 单位；不另起第二套权威工程模型 | **增量 1–3 / 3–5 人日**，不含 HTML 后端 | 变量类型/默认值、替换资源权利、离线闭包、覆盖保留及真实渲染 |
| 按交换需求 / O07 | `studio/server/nle.mjs` 的 `planNleTimeline` | 增加 xmeml 适配与 copy/link/bake 清单，复用原帧边界量化和 lane 规划思想 | **3–6 / 7–12 人日** | 先接入本项目损失报告、relink、音画链接；烘焙结果不能冒称参数仍可编辑 |
| 后续可选 / O09、O10 | `closure.mjs`、`film-doc.mjs` | 仅在支持 OpenFilm HTML 格式时复用资源闭包和局部文本修改；现有 JSON/ticks 保持权威 | 分别 **2–4 / 4–7**、**3–6 / 6–12 人日** | 动态路径的闭包缺口、格式损失、秒/ms 与 tick 量化，以及外部资源访问门禁 |

**这是 R03 当时的下一步建议；O05 的最小离线标题卡及 O04/O06/O14 的部分受控能力已在后文 V41 落地。** O05 表中的完整网页/媒体/WebGL 范围、look 联系表、字体/越界诊断和自动模板控件仍须单独实现与验收；不能把原共享工期逐项累加，也不能把已完成的最小后端重复计入待开发。先适配 O15 的三种流程仍有价值，但流程说明不能替代动效、语音识别、跟踪或美学质量算法。原估算没有实测人时，不作为已经节省的工期。

### 不作为本地功能内核搬入的部分

React Studio、Electron 外壳不符合本项目 CLI 定位；但不能按目录整体删除 `studio/ui`，其 `lib` 下有纯规划、时间和模板算法，应先分离依赖。已有真实失败表明 `timecode.ts` 的 React Hook 与 `shared.mjs` 的顶层 host 导入会把纯数据模块拖入 React/Playwright 依赖。

服务商 `get/providers` 路由只组织云请求，不提供本地抠像、修复、生成、ASR 或 TTS 模型内核；不纳入默认本地链。`capture` 的网页导航也不自动符合离线模板需求。上游剪映草稿写出器可作为格式回归参考，但不是通用双向解析器，不解决加密工程或私有素材/特效可编辑转换。

本次还核对了 `host.mjs` 的 `offline=false` 默认值、`render.mjs` 创建 worker 时未传 offline，以及不透明截图默认 JPEG95 的路径。**不能只因源码存在 offline/close() 就宣称已经符合本项目离线与回收要求**；也不能把 JPEG 截帧、Alpha PNG 或多快门平均当作 HDR/线性光或完整剪映画质验收。

R03 历史复查脚本为 [audit_openfilm_current_review.py](../scripts/audit_openfilm_current_review.py)，其 130 文件冻结范围固定于提交 `e60c053de4306f108b22f391acca0bbeeada3555`。V40 新增源模块/测试后为 132 文件，复现 R03 产品冻结检查应在对应旧提交执行，不将旧摘要直接视为新版必须相同；在线 API 还可能变化。下列命令从对应版本仓库根目录执行，输出目录需尚不存在：

```powershell
C:\Python313\python.exe -B -X utf8 scripts/audit_openfilm_current_review.py --output docs/validation/evidence/<新的复查目录>
```

它只向两个公开 GitHub API 发 GET，保存响应原字节并核对既有源码、冻结产品和文档链接；若 main 变化则保留响应并终止，以便重新审查，不能沿用本次模块结论。整体剪映等价目标继续开放，源码 MIT、素材/模型权利和品牌使用分别管理。

## 后续产品增量：V40

本轮 V40：统一关联 `slip`、真实有限源 `extend_source` 与 roll/slide 显式 `handle_policy:source`；默认仍使用保留作者句柄，源界/关联锁/跟踪观察/转场额外句柄和原子事务统一检查，旧 compose slip 也走相同规划器。完整 **938/938，2478.552 秒**，0 跳过；127 Python+2 MJS+Schema+pyproject+MIT 共 132 文件冻结，41 新增方法为完整子集。九组/79 CLI 入口（66 成功、4 当前预期拒绝、9 固定 V39 缺项拒绝），505 新主帧/2,424,000 立体声采样帧与手工固定 V39 工程完全相同；两组另核对 100 个直接源帧身份，0 错配。同产品参照不独立验收渲染或音质。90 文件离线 wheel/26 独立进程 CLI、14 Skills/128 引用通过；四时刻静态目检，未连续播放/听审；开发失败与主动中断原记录保留。真实外扩重新求值效果/淡入淡出/retiming；嵌套曲线明确告警其时长再归一化，原主体采样不变未验收。完整磁吸、跟踪重规划、自然画质/音质、长片资源、Schema 随包/干净机器、内容库规模及完整剪映等价仍未验收。 见[源编辑契约](specs/真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md)、[正式实测](validation/真实源外扩与关联Slip实测_2026-10-18.md)。本项为已有 OpenFilm O02 关联规则之上的原生源范围规划扩展，没有继续搬入 GUI/HTML/在线执行器，也没有重新请求上游或重跑 R01/R02 研究测试；R03 的 API 星标和源码检查保持原日期记录，未测实际节省人时。

## 产品增量 V41：离线动效与可重建源码

再次读取公开 API：**832 stars / 90 forks**，main 仍为 `eefd6a8d379289102141359a4718dbab12170526`；702 上游文件与 ZIP 一致。[本轮原 API 与提取摘要](validation/evidence/openfilm-html-adoption-20261018/verification.json)记录实际获取时刻。网页缓存星标与 API 可能不同，不把历史 829 或本次 832 当作永久排名。

| 编号 | 当前采用 | 实际边界 / 成本含义 |
|---|---|---|
| O05 | 新增 `motion html-*`，把本地 HTML/CSS/SVG/Canvas 生成为普通透明视频资产，保留源码、资源和参数 | 没有搬入默认联网 host/render、Studio 或独立 HTML 时间线。NUT 精确帧时钟、权利与工程事务是本项目新实现；全 film.html/媒体/WebGL 仍未完成 |
| O04/O06 | 原 FILM_CLOCK 导出行 1066 字节完全一致；所有帧在两种全新页面顺序下重绘核对，报告保留 Job 回收和页面失败 | 联系表、缺字/越界自动诊断、跨版本确定性仍候选；静态复核脚本不冒称完整 look CLI |
| O14 | 复用已有模板变量校验，title/color 等强类型参数进入 frame(t,params)，保留配方并重建新版本 | 不是原 CSS 自动控件提取或整个 overrides.mjs 移植；换图片/字体须登记新资源/源码版本 |
| O01/O02/O03/O13 | 继续沿用既有字幕算法、部分关联规则、转场工作流和 Saved 片段组工作流；本轮实际验证 HTML 源码在工程包和片段组中的闭包/ID 重映射 | 旧轮通过数保留；新增动效不能代替原自然分割/修复质量、完整磁吸或完整剪映验收 |

本轮 V41：提取 OpenFilm 原帧时钟，新增完全本地 `motion html-register/html-source/html-inspect/html-render`；保留 HTML/CSS/SVG/Canvas 源码、固定资源/工具链、强类型参数、新版本重建和普通时间线透明叠加。完整 **975/975，1302.879 秒**，0 跳过；137 文件冻结，37 新增专项为完整子集。五组成功内容/三项页面拒绝共 30 CLI 入口调用，96 HTML 编码输入帧、192 全帧乱序重绘、24 原生时间线主帧分计；独立 RGB 合成最大差 3、均值 0.476496，工程包/片段组重建 RGBA 一致，所有实际浏览器 Job 回收。94 文件离线 wheel/11 独立进程 CLI、14 Skills/133 本地引用通过；六张静帧目检，未连续播放/听审。初始 MKV 帧时钟错位、源长和回收/工具链诊断失败原证据保留；正式采用逐帧精确 PTS 的 FFV1/BGRA NUT。完整 OpenFilm HTML 时间线/媒体/WebGL、自动模板控件/缺字越界诊断、HDR/自然广告美学、长片资源、Schema 随包/干净机器及完整剪映等价仍未验收。 见[契约](specs/离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md)、[实际原片/GIF与全部失败](validation/离线HTML动效源码与透明合成实测_2026-10-18.md)。

原 O05 的 5–10 / 12–20 人日、随行 O04/O06/O14 为包含共享工作的历史估算。本轮未记录人时，不能宣称已节省全部差额、整个项目百分比或从单行复用量推算收益；已实现最小后端不再作为全额待办。剩余优先项是完整帧/媒体格式范围、诊断、自动控件和三种官方 Skill 流程的离线绑定；NLE xmeml 按实际交换需求另行接入。
