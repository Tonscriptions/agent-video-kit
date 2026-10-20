# OpenFilm 0.2.4 复用复核与成本更新

<!-- V79-FOLLOWUP -->
R13 后续 V79：CP-01..06 已有本地 CLI 限定实现；完整原生回归 **1796/1796、5798.792 秒、0 跳过，237 冻结输入＋8 外部夹具前后相同**。采用组件字段的设计思路，新增稳定 ID、严格类型／闭包／权利／预算校验，未复制整套 Studio 或宽松输入规则。[最终契约](specs/HTML组件字段与逐片段取值契约_v0.1_2026-10-21.md) · [实际执行和验收边界](validation/HTML组件字段与逐片段参数离线实测_2026-10-21.md)。本页此前的“待实现”与估算保留为当时研究状态；不重复计费已实现的字幕、覆盖、布局、子帧和预览。开放 NLE 适配与上下文图片裁剪仍独立待办。
<!-- /V79-FOLLOWUP -->

结论：**有可拆用的模块，适合以纯函数、测试夹具和薄适配器接入现有 Agent CLI。** 当前最有新增价值的是组件字段定义与重置、基础 NLE 交换，以及 Agent 多次看帧时的图片上下文裁剪。HTML 动效、模板覆盖、字幕和预览已有本地实现，重复迁移不能再次计作节省成本。OpenFilm 没有在这次增量中提供可直接补齐剪映全部效果的离线算法内核。

本轮为 **R13 源码研究**。产品保持 V78；没有新增产品功能、安装 Skill、模型前向或新成片验收。

## 1. 固定版本与许可证

| 编号 | 本轮检查 | 结果 / 原始证据 |
|---|---|---|
| R13-01 | 仓库、社区快照 | [openfilm/openfilm](https://github.com/openfilm/openfilm)，**1546 stars /154 forks**，采集于 **2026-10-21 00:31:16 Asia/Taipei**；以[原始响应与 HTTP 日期](validation/evidence/openfilm-024-20261021-r13/acquisition-r1/verification.json)为准，星数不是固定属性 |
| R13-02 | 固定源码版本 | [53156ac5818d8bad3f2c356043b376b3eebd95ba](https://github.com/openfilm/openfilm/commit/53156ac5818d8bad3f2c356043b376b3eebd95ba)；CLI、desktop、shared 的 package version 均为 **0.2.4**；提交时间 **2026-10-20 16:30:10 UTC** |
| R13-03 | 源码版本与发行版区分 | 此时 GitHub `releases/latest` 返回 **v0.2.2**，发布时间 **2026-10-19 21:18:21 UTC**；不把 main 的 package version 当作已下载或已验收的发行包。见[原始 release 响应](validation/evidence/openfilm-024-20261021-r13/acquisition-r1/release.json) |
| R13-04 | 0.2.3 → 0.2.4 全树 | 前进 **3 个提交**；**781 → 781 文件，756 不变、25 修改、0 新增、0 删除**。[全树摘要与测试收据](validation/evidence/openfilm-024-20261021-r13/run-r1/verification.json)、[完整文本差异](validation/evidence/openfilm-024-20261021-r13/run-r1/source.diff) |
| R13-05 | 完整源码保全 | [固定 ZIP](../sources/upstream/openfilm-024-20261021-r13/repo.zip)，**11,656,737 字节**；SHA-256 `c106830d98d75080f2aba64ad41cb7d95bee606a48c0cd4d913bf3166cbdb192`；未安装上游工作区 |
| R13-06 | 许可 / 商标 / 第三方说明 | 根目录、CLI、shared 的 **7 份许可证或说明文件均未变**。[MIT、商标与第三方原文](validation/evidence/openfilm-024-20261021-r13/run-r1/legal/LICENSE.txt)。复制源码保留版权和 MIT 原文；本项目继续使用自身名称。字体、Chromium、Playwright 等依赖和示例素材仍按各自许可登记，不能由根 MIT 推导所有外部资产授权 |

获取脚本保留请求 URL、最终 URL、HTTP Date、ETag、响应摘要及本地接收时间。源码研究下载与产品执行政策分开：产品运行时仍使用登记的本地资源与本地工具，不增加在线下载或云 provider。

## 2. 0.2.4 的两项实际变化

**音频预览改为浏览器播放。** [`derived.mjs`](https://github.com/openfilm/openfilm/blob/53156ac5818d8bad3f2c356043b376b3eebd95ba/packages/openfilm/studio/server/derived.mjs) 移除了 `soundOf(root, rel, speed)` 的 speed 参数、每个速度的缓存文件和服务端 `atempo` 预编码；现在只为源文件准备小型音频副本。[`player.ts`](https://github.com/openfilm/openfilm/blob/53156ac5818d8bad3f2c356043b376b3eebd95ba/packages/openfilm/studio/ui/src/editor/player.ts) 以 `Audio`、`preservesPitch`、`playbackRate` 和 Web Audio 混音播放变速声音，另有漂移纠正。它依赖浏览器播放与设备时钟，不能直接替换 CLI 的离线音频输出或据此验收保调质量。本项目继续使用已有 FFmpeg / 本地 Rubber Band 源上下文处理；V78 的音频区间、PCM 与包重放证据保持独立。

**Agent 图片上下文有了预算。** [`pi-config.mjs#L69`](https://github.com/openfilm/openfilm/blob/53156ac5818d8bad3f2c356043b376b3eebd95ba/apps/desktop/src/pi-config.mjs#L69) 的 `fitImages` 保留最近 **5 个带图片的工具结果**，按图片 base64 字符长度设置 **32 MiB** 默认预算，旧图片替换为含文件名的可重读提示，原会话不删除。`pi-agent.mjs` 另处理 413 后缩减图片重试。可借裁剪纯函数和原测试供本地多模态 Agent 使用；**32 MiB 不是完整 JSON 请求大小、token 预算或进程内存上限**。本次未执行 Agent SDK、请求重试或任何模型服务。

16 个选定候选模块中 **13 不变、3 修改**：修改的是 derived、player、pi-config。组件字段、预览缓存、FCPXML 与诊断候选均与 0.2.3 字节相同。因此，[R12](OpenFilm_0.2.3增量复用与开发成本评估_2026-10-20.md) 对旧版服务端“按速度缓存音频”的描述只保留为历史，不能继续当作当前版本接入方案。

## 3. 可拆清单与工程量

以下是**一名熟悉本项目的工程师的规划估计，并非实测耗时或已节省人日**。生产化列只覆盖表内限定功能，包含本地输入校验、失败恢复、包重放和离线安装验证；共享设施不重复计费。已有功能不再次分配整套迁移预算。

| 编号 / 优先级 | 上游模块或内容 | 本项目现状与具体接法 | 原型 / 生产化估计 | 取舍 |
|---|---|---|---|---|
| OF13-A01 / 高 | [`component-props.ts`](https://github.com/openfilm/openfilm/blob/53156ac5818d8bad3f2c356043b376b3eebd95ba/packages/openfilm/studio/ui/src/lib/component-props.ts)：字段命名、去重、重命名、逐项 / 全量重置；text、image、boolean、var | 通用 HTML 覆盖已有；新增稳定字段 ID、可发现 Schema、逐片段值及显隐恢复。提取纯规则和 3 个原测试；图片用本地资产 ID，接入既有权利、事务和资源闭包。**CP-01..06 仍待实现** | **1–2 /3–5 人日** | 首选；可以减少字段语义设计和边界夹具编写 |
| OF13-A02 / 中 | [`nle.mjs`](https://github.com/openfilm/openfilm/blob/53156ac5818d8bad3f2c356043b376b3eebd95ba/packages/openfilm/studio/server/nle.mjs)、[`fcpxml.mjs`](https://github.com/openfilm/openfilm/blob/53156ac5818d8bad3f2c356043b376b3eebd95ba/packages/openfilm/studio/server/fcpxml.mjs)：轨道、基本剪切、源区间、XML 和字幕夹具 | 本项目 `convert.py` 已有基础 OTIO / Kdenlive-MLT 与损失报告，不再从零复制。仅为需要的新交换适配器提取序列化规则；先确定目标开源 NLE 的实际格式支持，再验可打开 / 重链接 / 重渲染。复杂效果、速度曲线和嵌套逐项报告损失或烘焙 | **3–6 /8–15 人日**，仅基础新适配器 | 有明确交换需求再做；不等于全部效果无损双向互通，不引入剪映安装目录探测 |
| OF13-A03 / 中 | `pi-config.mjs` 的 `fitImages` 与相关 13 个原测试中的图片预算场景 | 为本地 Agent 多次看帧添加“留最近、保原档、可重读”的内容裁剪；提取纯函数，不接 Electron / Pi SDK / 云服务。需另补总 JSON 字节、文本 / token 和本地上下文窗口限制 | **0.5–1 /2–4 人日** | 新的降本候选；服务视频理解工作流，不是剪辑或特效算法 |
| OF13-A04 / 已接入思路 | `preview-cache.mjs` 的任务去重、状态、取消 | **V78 已有帧 / 区间 CLI 和内容缓存**；继续现有 `preview.py`。上游仍为路径、大小、mtime 身份；R12 同大小同 mtime 变更未失效的观察仍适用于字节相同的该文件，本次没有重跑该反例 | **0 新迁移预算** | 不复制旧 key；实时播放性能另验，不把 V78 宣称为实时播放器 |
| OF13-A05 / 只参考 | `derived.mjs` 音频副本；`player.ts` 调度 / 漂移 / 淡入淡出规则 | 当前版变速在浏览器执行。可借时钟与淡变测试场景；纯 CLI 继续本地完整精度处理。以后新增独立可选播放器时，才评估浏览器播放策略 | **0.5–1 人日审读**；不立项迁移播放器 | 撤销把旧版服务端速度音频缓存当作新任务的建议 |
| OF13-A06 / 已有限接入 | `host.mjs` 的 `frame(t)`、`overrides.mjs`、`template-controls.ts`、`problems.mjs` | 已有[离线 HTML 源码 / 透明合成](validation/离线HTML动效源码与透明合成实测_2026-10-18.md)、[模板覆盖恢复](validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)、[文字布局](validation/HTML文字布局与字体覆盖实测_2026-10-18.md)、[子帧快门](validation/HTML子帧快门与透明混合实测_2026-10-20.md)。继续现有沙箱、离线资源和作者工程 | **0 新整套迁移预算** | 保留局部 MIT 代码和固定来源，不增加第二套宿主 / 工程格式 |
| OF13-A07 / 已有限接入 | `subtitle-segments.mjs` 字幕分段、双语和局部回写规则 | 已有[本地字幕分段与回写](validation/本地字幕分段与双语回写实测_2026-10-17.md)。当前打包模块与新快照原文件字节相同；不把分段规则当 ASR / 翻译模型 | **0 新迁移预算** | 保持本地 ASR 与既有字幕结构；自然语言质量单独验 |
| OF13-A08 / 已接入思路 | `diagnostics.mjs` 与错误摘要、编解码探测、联系表 | 已有[模型诊断](validation/本地模型管道诊断与回收前留证实测_2026-10-20.md)、[透明联系表](validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md)。沿用有字节上限读取、脱敏、工具 / 资源 SHA 和失败留证；不照搬完整日志读入 | **0 新整套迁移预算** | 只补本项目缺少的场景；重复审查不再次统计采用 |
| OF13-A09 / 已适配三条主线 | 10 套创作 Skill /31 文件：参考片、长转短、录屏等 | 三条主线已有 `$video-cut-reference-remake`、`$video-cut-long-to-short`、`$video-cut-screen-demo`。[本地适配与实片记录](validation/OpenFilm三套本地创作Skill与实片核验_2026-10-19.md)。本轮全部未变，安装数为 0 | 其余流程按明确需求补；无整包重装预算 | 作为创作步骤参考；不能把 Skill 文本计成底层功能 |
| OF13-A10 / 低 | `steps.ts` 的 100 步内存撤销栈与外部编辑失效场景 | 已有持久快照、事务与重放；仅借 3 个原测试的失效场景。内存栈不足以替代跨进程恢复与资产引用处理 | **0.5–1 人日审查**，不移植整栈 | 减少重复维护 |
| OF13-A11 / 不接入 | Studio、desktop、在线 providers、安装器 | 无 GUI 本地 CLI 无需完整 React / Electron 宿主；云生成、转写、配音仍由本地登记的模型替代。29 个 provider 文件本轮全部未变 | 不计入本地内核降本 | 只拆纯规则；不导入在线执行链 |

建议顺序：**先做 A01，再按实际需求选择 A02 或 A03**。A01 能直接改进 Agent 使用模板的可发现性与可编辑性；A02 解决与现有开源剪辑器的交付；A03 减少反复看帧的上下文负担。没有同条件从零 / 移植的工时对照，不能给出“已降低 X% 总研发成本”。

## 4. 实际运行了什么

| 编号 | 原始测试文件 | 方法通过数 | 适用边界 |
|---|---|---|---|
| R13-T01 | `src/film-doc.test.mjs` | 30/30 | 纯工程文档读写规则 |
| R13-T02 | `src/rate.test.mjs` | 1/1 | 有理数帧率 |
| R13-T03 | `component-props.test.ts` | 3/3 | 组件字段命名、重复与重置 |
| R13-T04 | `template-controls.test.ts` | 9/9 | 模板值类型、范围和默认处理 |
| R13-T05 | `steps.test.ts` | 3/3 | 内存撤销 / 重做与失效 |
| R13-T06 | `player.test.ts` | 6/6 | 淡变、时钟 / 预调度、速度 / 源时间纯函数；没有构造播放器、调用音频设备或听审 |
| R13-T07 | `apps/desktop/src/pi-config.test.mjs` | 13/13 | 配置与消息格式 / 图片预算 / 错误识别纯函数；没有运行 SDK、HTTP 重试或发送请求 |

共 **7 份原文件，65/65 方法通过，0 跳过**。以现有原生 Node **22.14.0** 的实验性类型擦除运行，源码及相对路径未改写；不是完整上游安装 / 工作区测试，也不证明完整工作区兼容。逐次 argv、stdout / stderr 及原文件 SHA 在[执行收据](validation/evidence/openfilm-024-20261021-r13/run-r1/verification.json)；首五份的 46 个方法与 R12 存在重复，不应跨轮累加为独立覆盖数。

获取与离线研究各自前后 **235 个产品输入 SHA 完全相同**，并与 V78 全量收据的冻结输入核对。当前目录中 6 个 `openfilm_*.mjs` 的来源也逐一登记：其中完整文件逐字节匹配新上游的有 `overrides` 与 `subtitle-segments` 两个；其余四个是此前提取 / 适配，**不声称它们等于上游整文件**。这轮没有替换运行时代码。

本轮没有新增视频 / GIF。可视能力沿用上述历史实测中的原输入与实际输出，不用研究源码测试冒充新成片验收；V78 的 **1768/1768** 为已发布历史回归，本轮未重跑或加上 65 项重新统计。完整剪映效果等价、自然人像处理质量、HDR、实时播放和完整素材 / 模板库仍按[覆盖矩阵](validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md)逐项开发验收。

## 5. 离线复现与接入门槛

```powershell
C:/Python313/python.exe -E -B -X utf8 scripts/review_openfilm_r13.py `
  --output docs/validation/evidence/openfilm-024-20261021-r13/reproduction-r2/verification.json
```

必须使用全新的输出目录；脚本校验两份固定 ZIP 的 SHA，拒绝覆盖已有结果，全部 scratch 留在 E 盘，不下载、不安装、不运行浏览器或上游 SDK。[获取脚本](../scripts/capture_openfilm_r13.py)、[离线核验脚本](../scripts/review_openfilm_r13.py)及各次执行副本保留。

后续 A01 继续遵循[CP-01..06](specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md)：稳定 ID / 定义值分离、本地资产与权利、128 项 /64 KiB 覆盖预算、可见性恢复、失败原子性、包 / 片段 / 队列重放与真实离线安装。不能直接采用上游静默丢弃无效输入、任意图片字符串或宽松的 CSS 变量 / 匹配序号。

本轮使用原生 Windows Python / Node。没有 Docker、WSL、容器或虚拟环境；没有打开本地浏览器 tab。网页检索与源码 HTTP 获取均不启动本地 UI。
