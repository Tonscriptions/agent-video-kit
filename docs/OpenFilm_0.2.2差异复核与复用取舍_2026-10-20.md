# OpenFilm 0.2.2 差异复核与复用取舍

**结论：继续拆取算法、协议和测试夹具；保留本项目现有的 Agent CLI、工程模型与本地执行链。** 新版没有改变此前关于可复用模块的主要判断，也没有提供可直接替代剪映全部本地 AI 效果的内核。

## 固定来源与执行边界

本次 GitHub API 请求时间为 **2026-10-20 10:26:27 Asia/Taipei**；仓库为 **1343 stars /137 forks**。这是一次时间快照，不能与先前 R09 的 1269/128 混写为同一时点。

- 新版本：CLI/desktop **0.2.2**，[固定提交 695f4a887a97258d45ffe5715eadf537b6d2579b](https://github.com/openfilm/openfilm/commit/695f4a887a97258d45ffe5715eadf537b6d2579b)。提交时间为 2026-10-19 20:56:06 UTC。
- 对照版本：[71922644da5d6b67db2cc796d4e057f98999944f](https://github.com/openfilm/openfilm/commit/71922644da5d6b67db2cc796d4e057f98999944f)，即 [R09 已检查版本](OpenFilm最新复用评估与成本取舍_2026-10-20.md)。
- 新源码：[固定 ZIP](../sources/upstream/openfilm-022-20261020-r11/repo.zip)，11,539,861 字节，SHA-256 `2786c4b06d90f112aba12c013ee7aaa3d8bf75f14b40d59e86e36f2a917c300e`。MIT 原文与旧版逐字节相同，保留在 ZIP 和 [许可副本](validation/evidence/openfilm-022-20261020-r11/LICENSE.txt)。
- [原始仓库 API](validation/evidence/openfilm-022-20261020-r11/repository.json)、[提交 API](validation/evidence/openfilm-022-20261020-r11/head.json)、[比较 API](validation/evidence/openfilm-022-20261020-r11/compare.json)、[获取记录](validation/evidence/openfilm-022-20261020-r11/acquisition.json)、[最终研究收据](validation/evidence/openfilm-022-20261020-r11/run-r2/verification.json)。

网络仅用于用户要求的公开源码研究。离线复核脚本没有下载、安装依赖或启动上游 CLI、GUI、浏览器、provider。运行现有原生 Node **22.14.0** 的一个纯函数原测试；该版本满足 CLI 的 `>=22.2` 声明，但不满足 monorepo 根的 `>=22.18` 声明。因此不把所选测试当作整个工作区的兼容性验收。没有模型或 GPU 前向、Docker、WSL、容器或虚拟环境。

## 编号检查结果

| 编号 | 实际检查 | 观察及对当前项目的影响 |
|---|---|---|
| R11-01 | 两个固定 ZIP 的全部文件字节 | 757→757 文件：**718 不变、6 新增、33 修改、6 删除**。保留 [新树 SHA 清单](validation/evidence/openfilm-022-20261020-r11/run-r2/new-tree.json) 与 [完整文本差异](validation/evidence/openfilm-022-20261020-r11/run-r2/source.diff)；文件数相同不代表代码不变 |
| R11-02 | 九个所选复用入口 | `look/problems/exports/preview-cache/fcpxml/diagnostics` 六个文件字节不变；`render/nle` 修改，`rate.mjs` 新增。新版没有修复 R09 已观察到的预览缓存内容失效问题，复用时仍须重写 key |
| R11-03 | Skills 和 provider 两组完整文件 | **31 个 Skill 文件、29 个 provider 文件**与旧版全部字节相同。这是文件数量，不是 31 个独立 Skill 或 29 个本地模型；本轮不重复安装或计算收益 |
| R11-04 | 新帧率模块的原始单元测试 | [原 `rate.test.mjs`](validation/evidence/openfilm-022-20261020-r11/run-r2/original-rate.test.mjs.txt) 在原生 Node 下 **1 个方法通过、0 失败**；[原输出](validation/evidence/openfilm-022-20261020-r11/run-r2/rate.test.mjs.stdout.log)。没有执行上游需要浏览器的 render 测试，不宣称其成片时间戳或吞吐已在本机通过 |
| R11-05 | 八个真实函数观察值 | NTSC 十进制别名会转成 `num/1001`，12.5 保留。启发式也把 **1.99 改成 2000/1001≈1.998002**，把 23.98 改成 24000/1001。见 [八个输出](validation/evidence/openfilm-022-20261020-r11/run-r2/probe.mjs.stdout.log)。这些是观察，不把全部行为判作产品正确性通过 |
| R11-06 | 与本项目帧率表示对照 | 本项目 HTML 清单已经要求显式整数 `fps.num/fps.den`，向 FFmpeg 传递该分数；快门算术使用 `Fraction` 并记录实际 JavaScript binary64 时间。**没有必要移植自动猜 NTSC 的启发式**；既有分数帧率测试不在本次重复运行或另计为通过 |
| R11-07 | 发布说明与新增路径审读 | 新增项集中于帧率规则与桌面安装/更新。在线官方安装器、Agent 应用发现和桌面自动更新不进入本地纯 CLI 产品；没有通过这些封装获得新的抠像、美颜、美体或重光照模型 |
| R11-08 | 执行与源码完整性 | 研究前后 **219 个候选产品输入摘要相同**。该数字只说明本次研究没有改变当时的快门候选源码，不代表全量产品验收，也不将此前发布版本的通过数转移给候选版本 |

0.2.2 的 `render.mjs` 修改主要是让十进制帧率经过 `exactRate/ffmpegRate` 后进入输入帧率、输出帧率和 `setpts`；子帧快门公式仍沿用旧版。`nle.mjs` 改为调用共同的 NTSC 判断，非 NTSC 的 NLE timebase 取整是已有逻辑，不能描述成这版新引入的问题。

## 十套创作 Skill 的可拆内容

已实际读取十份 Skill 正文。31 个文件由 **10 份 SKILL.md、10 张封面、10 份元数据与 1 份 SOURCE** 组成；不是 31 套程序。`SOURCE` 声明同步自 `openfilm/skills` 的固定提交 `1111136608bfd7fda174ba0fe7c5b6f87138f8c7`。名称、正文/封面/元数据 SHA 和描述见 [静态清单](validation/evidence/openfilm-022-20261020-r11/workflow-inventory.json)。本次没有另行下载、执行或安装该 Skill 仓库。

| 编号 | 上游工作流 | 可以复用的创作约束 | 本项目接法与限制 |
|---|---|---|---|
| R11-S01 | replicate | 同时刻对照参考片；原参考与重建素材分开；明确复刻范围 | 已有 `video-cut-reference-remake`，继续维护，不重复安装 |
| R11-S02 | long-to-short | 保留问题、条件和否定；按真实词时间截取；竖屏安全区 | 已有 `video-cut-long-to-short`；转接本地字幕/对齐，不调用上游在线 ASR |
| R11-S03 | screen-demo | 真实界面、动作锚点、等待删减和诚实速度 | 已有 `video-cut-screen-demo`；使用本地录屏和可编辑运镜 |
| R11-S04 | keynote | 每次一个产品主张，屏幕内给真实证据，文字可编辑 | 可加到现有广告/模板工作流；它不是产品截图、网页捕获或品牌素材生成器 |
| R11-S05 | presenter-pip | 画面跟随讲者词时间；小窗避开内容和字幕 | 可用既有画中画、字幕和锚点编排；自然人像抠像质量须独立验收 |
| R11-S06 | motion-graphics | 品牌、数据、画面与旁白相符；文字和数值可改 | 可作 HTML 模板创作检查点，不提供一套现成动效算法或模板素材库 |
| R11-S07 | lyric-video | 逐字落在歌声上；要求独立测量误差，保留可编辑歌词 | 对接本地歌词与对齐；上游“两帧内”是要求，不是已实现或本次已通过的指标 |
| R11-S08 | whiteboard | 笔画随词时间逐步绘出；来源事实与用户原声保持可编辑 | 对接已有描线/字幕/本地语音能力；说明文字不等于手写生成和中文自然笔画质量 |
| R11-S09 | collage | 素材各自有叙事用途，来源清楚，文字可读 | 可整理成拼贴模板与参数；替换在线图片检索，封面和第三方图片不直接入权利库 |
| R11-S10 | vintage-film | 记忆事实和人物不被擅改，运镜保留重要人物 | 可整理成照片运镜/调色配方；现有原始人物、日期与音乐须由本地授权素材提供 |

剩余七套宜按真实创作需求作为现有 Skill 的配方补充，避免再维护七套执行宿主。这些正文普遍引用 `openfilm get` 或外部服务；可采用创作约束，执行部分必须改写为本项目已登记的本地资源。没有把“顶级工作室”“值得发布”等提示词当作已经达到的画质证明。

## 复用清单与剩余投入

下表区分已有工作与未来可选工作。工时是熟悉当前工程的一名开发者、约六小时有效开发/人日的**规划估计**，不是已经测得的节省比例；交付状态和真实质量以链接的逐版实测为准。

| 编号 | 可拆内容 | 当前决定 | 对应实现或剩余投入 |
|---|---|---|---|
| R11-A01 | 字幕分句、双语段落规则 | 已采用，维护 | 不再计为待迁移收益；ASR、翻译和声学对齐分别验收 |
| R11-A02 | HTML `frame(t)` 时钟、模板参数 | 沿用已有后端 | 减少协议设计；保留本地资源登记、明确布局检查和确定性要求 |
| R11-A03 | 参考片复刻、长转短、录屏演示工作流 | 已改写为三份本地 `video-cut-` Skill | 不引入在线下载、云 provider 或第二套 Agent 会话宿主 |
| R11-A04 | 编解码探测、错误摘要和诊断 | 已有限定接入 | 维护本项目原生进程归因、脱敏和取消；不重建第二个执行器 |
| R11-A05 | 同规格批次结果复用 | 对应 [V70 实测](validation/OpenFilm同批次结果复用实测_2026-10-20.md) | 内容摘要与有效设置明确绑定；同次调用、同项目、单 worker。原 2–4 人日为此前原型规划，不再列作剩余收益 |
| R11-A06 | 透明多帧联系表与时间锚点 | 对应 [V71 实测](validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md) | 借用 alpha decoder 与先缩放规则，重写实际 PTS 抽帧、预算与事务；不移植浏览器拼图。原 1–2 人日仅为限定原型估计 |
| R11-A07 | HTML 子帧快门 | 对应 [V72 实测](validation/HTML子帧快门与透明混合实测_2026-10-20.md) | 采用重新绘制思路，自行实现中心中点采样、显式切点和预乘 Alpha；不能直接沿用编码域直通 RGBA `tmix`。原 3–5 人日不包括自然素材、HDR 或长片质量 |
| R11-A08 | 新 `rate.mjs` | 不移植启发式 | 当前已经使用显式有理数。可借其边界输入做人工审查，不增加一层隐式改帧率规则 |
| R11-A09 | FCPXML/xmeml 字段映射与夹具 | 可选，按开源互操作需求提取 | **3–6 人日**的基本剪切/轨道/字幕映射原型；保留现有中立工程模型，避免引入剪映目录探测。复杂效果须烘焙或报告损失，目标开源 NLE 实际打开验证另计 |
| R11-A10 | 预览区间缓存的队列/取消状态机 | 后置，重写内容 key | **2–4 人日**的限定内容寻址原型；配额、损坏、取消和输入变化验证不能省略。当前纯 CLI 没有必要照搬 UI 播放调度 |
| R11-A11 | 桌面 GUI、Agent 安装器与云 providers | 不接入产品运行时 | 不降低本地视频算法和模型效果的开发成本，也不符合当前无 GUI、以本地资源执行的产品范围 |

真正的降本来自复用独立协议与已验证规则，接回本项目已有的工程事务、权利台账、队列和发布链。OpenFilm 的 MIT 代码许可不自动覆盖第三方字体、素材、模型权重或云生成内容；素材和模板仍进入现有权利台账。

## 保留的研究失败与复现

首轮脚本错误地假设两个 ZIP 都使用完整 commit 作为根目录名；旧 GitHub API ZIP 实际为 `openfilm-openfilm-7192264/`。因此在运行 Node 前拒绝，保留 [失败收据](validation/evidence/openfilm-022-20261020-r11/verification.json) 与 [实际执行脚本](validation/evidence/openfilm-022-20261020-r11/executed-review.py.txt)。没有把该次失败改写为通过。

修正为分别绑定**已知 ZIP SHA 与实际根目录名**后，第二轮才完成全树比较、一个原始测试及八个观察。最终 [执行脚本副本](validation/evidence/openfilm-022-20261020-r11/run-r2/executed-review.py.txt) 与 [探针正文](validation/evidence/openfilm-022-20261020-r11/run-r2/executed-probe.mjs.txt) 均保存。源码获取与该离线复核分开留证。

从本项目根目录，使用已存在的原生 Python/Node 和新的输出位置复现：

```powershell
C:/Python313/python.exe -E -B -X utf8 scripts/review_openfilm_r11.py `
  --old-zip sources/upstream/openfilm-refresh-20261020-r08/repo.zip `
  --new-zip sources/upstream/openfilm-022-20261020-r11/repo.zip `
  --snapshot docs/validation/evidence/openfilm-022-20261020-r11/snapshot.json `
  --output docs/validation/evidence/openfilm-022-20261020-r11/reproduction-r3/verification.json
```

本次没有新增独立画质素材。V70/V71/V72 的原输入、实际 MP4/GIF 和失败边界由各自报告保留，不将原有样例重新算作 R11 新的成片验收。自然视频效果、美颜美体、重光照、完整权利素材库和剪映完整质量仍须按 [能力覆盖矩阵](validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md)逐项解决。
