# OpenFilm 0.2.5 可拆模块与复用成本评估

> 本页保留 R16 的 v0.2.5 快照；main 新增的导出重绘、当前拆用顺序与 Node 版本失败见 [R17 复核](OpenFilm当前复用建议与导出恢复增量_2026-10-22.md)。

**结论：有可以拆用的内容。优先复用 HTML 动效契约、检查规则、字幕、模板参数和失败夹具；这些已有本地适配。0.2.5 新增的批处理浏览器复用、转码去重、导出清理和音频修复值得按需提取。它能减少基础设施的重复设计，尚不能提供完整剪映功能或离线 AI 特效算法。**

本页为 R16 研究，承接 [R14 模块和成本清单](OpenFilm可拆模块与现有内核降本清单_2026-10-21.md)及 [R15 历史增量](OpenFilm新增提交与复用结论更新_2026-10-21.md)。数字均为本轮采集或执行结果；规划工时不是已节省工时。研究没有新增产品功能、安装依赖、运行 Studio、调用云模型或制作新视频。

## 1. 固定检查范围与证据

| 编号 | 核验项目 | 实际结果 |
|---|---|---|
| R16-01 | 官方仓库 | [openfilm/openfilm](https://github.com/openfilm/openfilm)，采集时 **1,844 stars /179 forks**，日期 2026-10-22 Asia/Taipei；固定 main [`af5756a88d362bdcd71dc870a0e02590420e6944`](https://github.com/openfilm/openfilm/commit/af5756a88d362bdcd71dc870a0e02590420e6944) |
| R16-02 | 版本与真实增量 | 最新 release **v0.2.5**，发布于 2026-10-21 22:25:58 UTC。相对 R15 固定 `419da5d…` 新增 **3 提交 /70 文件**；官方 compare 未触及 300 文件截断。与 R15 的 GUI 修复不同，本次包含渲染和导出核心变更 |
| R16-03 | 本地源码 | 固定 ZIP 重新逐项核验并解出 **788 文件**；[逐文件 SHA](validation/evidence/openfilm-reuse-20261022-r16/capture-r2/source-tree.json)、[请求时间/ZIP SHA/候选差异](validation/evidence/openfilm-reuse-20261022-r16/capture-r2/verification.json)、[完整补丁](validation/evidence/openfilm-reuse-20261022-r16/capture-r2/changed-files-and-patches.txt) |
| R16-04 | 原始上游测试 | 五份原始 MJS 测试 **35 通过 /1 跳过**；原始 TypeScript 响度测试 **6 通过**；原始浏览器池测试 **4 通过**。合计 **45 通过 /1 跳过 /0 失败**，不计入产品回归。池测试注入 mock；检查树中的 `host.mjs` 显式禁止启动真实浏览器 |
| R16-05 | 额外边界观察 | **7 组**：ProRes 参数、单/双声道图、同源音频去重、浏览器池总容量、PNG-alpha/NLE 路径、帧率/极短片段、代理缓存身份。[原始输出](validation/evidence/openfilm-reuse-20261022-r16/tests-r1/source-observations.stdout.txt) |
| R16-06 | 产品隔离 | 当前 main **282 产品输入 SHA 前后相同**；上游 788 文件也前后相同。[测试收据和命令](validation/evidence/openfilm-reuse-20261022-r16/tests-r1/verification.json)。没有把当前另行等待完整回归的浮点候选当作本轮产品交付 |
| R16-07 | 保留失败 | 首轮抓取后的核验误读 compare 响应为含 `head_commit`，产生 `KeyError`。r2 校验 `commits[-1].sha`，复核复用的五份原响应/ZIP SHA；没有重新计作五次请求。[原失败](validation/evidence/openfilm-reuse-20261022-r16/capture-r1/verification.json)、[原执行代码](validation/evidence/openfilm-reuse-20261022-r16/capture-r1/executed-capture.py.txt) |

实际使用原生 Windows Python 3.13 和 Node 22.14.0，临时目录全部在 E 盘。未使用 Docker、WSL、容器、虚拟环境或交互浏览器 tab。Node 能执行本轮纯模块测试，不代表满足上游完整开发环境版本、完整依赖安装或全部上游测试通过。跳过项仍为本机没有的 Final Cut Pro DTD/xmllint 条件，不安装专有编辑器。

## 2. 按复用价值排列的模块

上游根为 `packages/openfilm/`；下表路径均指固定提交。源文件保存在固定 ZIP，建议通过现有 Agent Project 和本地任务协议接入。

| 编号 | 模块/可拆内容 | 当前项目与取舍 | 实际能减少的开发工作 |
|---|---|---|---|
| OF16-A01 | `src/film-doc.mjs`、`host.mjs`，`frame(t)` / ready / 固定时间出帧 | HTML 动效已适配；新宿主渲染变更用失败夹具回归后逐项吸收 | 不重新设计网页动画时间契约、就绪协议和受控出帧 |
| OF16-A02 | `src/look.mjs`：乱序重画、联系表、文字/资源错误 | 已有本地看帧、严格文本边界、透明联系表和子帧快门检查 | 复用检查规则及新失败案例，减少内容检查盲点 |
| OF16-A03 | `studio/server/subtitle-segments.mjs`：字幕分句 | 已有带许可的 `openfilm_subtitle_segments.mjs`；本次源码未变 | 节省语言分句边界工程；不提供 ASR、强制对齐或说话人模型 |
| OF16-A04 | `template-controls.ts`、`component-props.ts`：有类型字段、覆盖、重置 | V79 已接 CP-01..06；字幕/模板/本地图片继续复用现有入口 | 模板可编辑参数和局部替换已有统一契约，不重复移植 |
| OF16-A05 | **新 `src/browser-pool.mjs`，85 行**：take/give/retire、每 24 次归还回收、失败分类 | 可拆单次 HTML 批处理中复用；结束关闭全部页和所属进程。新增全局容量、内存预算、取消、任务所有权及真实 Windows 故障验证 | 减少浏览器每页重复启动及池生命周期设计；本次只验 mock，未测实际提速或 RSS |
| OF16-A06 | **`src/seekable.mjs`**：共享转码 promise、独立临时文件、取消/重命名 | 借去重和清理协议；缓存身份改为内容 SHA、版本/参数绑定。H.264 浏览器代理应作为显式预览派生物，不替代原片高位深正式渲染 | 减少共享源重复转码、半成品竞争和 Windows 文件占用处理；现有缓存/任务设施优先扩展 |
| OF16-A07 | **`src/render.mjs`、`studio/server/exports.mjs`**：暂存发布、重试、进程树取消、遗留清理 | 吸收限定失败夹具；清理必须限于有记录的自有产物，验证 SHA 和状态，保留用户输入/既有输出 | 减少导出失败、强退、重启恢复等边界的重复排查。`exports.mjs` 仍耦合 Studio/浏览器，不整体搬入 |
| OF16-A08 | **`src/encoders.mjs` 的 `prores709` / `FRAMES_709`** | 可复用输出矩阵/范围与标签对齐的检查策略；正式接入仍需实际像素、alpha、软件/硬件交叉验证 | 提供 ProRes/WebM 色彩错误夹具方向。参数规划和 709 标签不能作为 sRGB 线性化、ICC、PQ/HLG/HDR 验收 |
| OF16-A09 | **`src/shared.mjs` 的 `mixGraph`，UI `loudness.ts`** | 单声道显式复制左右声道；dB/线性增益及达到上限的反馈为纯逻辑。项目已有音频路由和响度模块，采用对照夹具优先 | 减少 mono upmix 电平、增益滑块、未达到目标的报告逻辑缺陷；不是新增降噪、声源分离或母带算法 |
| OF16-A10 | **`studio/server/nle.mjs`、`fcpxml.mjs`**：轨道分配、资源规划、XML；0.2.5 新增 PNG-alpha 选择和系统路径 | 仍是可拆的交换候选；Agent Project 为作者格式，先确定目标开源编辑程序及其真实兼容格式 | 可省基础 XML 与资源分配设计；混合源帧率、效果损失报告、原片重链接和目标程序重渲染仍需开发 |
| OF16-A11 | `apps/desktop/src/pi-config.mjs` 的 `fitImages` | 仅自有 Agent 消息宿主有直接用途；当前 CLI 不托管外部 Codex 会话 | 省图片上下文预算小工具；完整宿主另计，不能从外部裁减当前 Codex 历史 |
| OF16-A12 | `src/problems.mjs`、诊断、编码器实探、官方十份创作 Skill | 已有适配/映射和 17 份 `$video-cut-` Skill | 用新增夹具维护已接能力，不再重复安装依赖官方命令/provider 的第二套工作流 |
| OF16-A13 | Electron / Studio / Agent 自动安装 / FFmpeg 自动下载 / 云 provider | 不接入本地 CLI 运行链。FFmpeg 下载测试本次仅使用注入的假 fetch，未下载任何二进制 | GUI 与云 SDK 的存在不会补齐本项目离线模型内核；沿用现有离线依赖包与本地工具登记 |

固定源码：[浏览器池](https://github.com/openfilm/openfilm/blob/af5756a88d362bdcd71dc870a0e02590420e6944/packages/openfilm/src/browser-pool.mjs)、[代理副本](https://github.com/openfilm/openfilm/blob/af5756a88d362bdcd71dc870a0e02590420e6944/packages/openfilm/src/seekable.mjs)、[导出](https://github.com/openfilm/openfilm/blob/af5756a88d362bdcd71dc870a0e02590420e6944/packages/openfilm/studio/server/exports.mjs)、[编码器](https://github.com/openfilm/openfilm/blob/af5756a88d362bdcd71dc870a0e02590420e6944/packages/openfilm/src/encoders.mjs)、[音频图](https://github.com/openfilm/openfilm/blob/af5756a88d362bdcd71dc870a0e02590420e6944/packages/openfilm/src/shared.mjs)、[NLE 规划](https://github.com/openfilm/openfilm/blob/af5756a88d362bdcd71dc870a0e02590420e6944/packages/openfilm/studio/server/nle.mjs)。

## 3. 本次发现的适配边界

| 编号 | 真实观察 | 接入约束 |
|---|---|---|
| OF16-B01 | 两次同时 `take(2)` 得到 **4 个 mock 浏览器**，close 后 4 个均关闭 | 池有回收次数，没有独立全局容量上限；批处理并发必须由宿主资源预算控制。24 页回收不是 RSS 上限 |
| OF16-B02 | 新代理身份函数仍是 `VERSION + path + size + mtime` 的截断 SHA-1。不同内容、相同路径/大小/mtime 得到同一 key | 本次执行的是原 key 函数，**没有制造真实错代理**；已足够证明 key 不绑定内容。正式缓存采用现有 SHA 验证和产物完整性门槛 |
| OF16-B03 | `alpha:'png'` 为 alpha WebM 规划出 `transcode -> png` MOV；路径使用 Windows 分隔符 | 得到计划不等于完成编码和 NLE 可读；PNG/MOV 体积、持续解码、透明混合必须实测 |
| OF16-B04 | `nleFps(48/90/120)` 仍为 **50/60/60**，30 fps 的 1 ms 片段仍量化为 `[0,0)` | 不能直接代替作者 tick/VFR 时钟或无损交换；转换与空范围必须明确报告 |
| OF16-B05 | mono 计划有 `pan=stereo|c0=c0|c1=c0`，stereo 没有；重复源两个片段只设一个 `-i` | 本轮只核验图字符串；音频合成、PCM 峰值和听感未测，不能写成真实混音验收 |
| OF16-B06 | `prores709` 对软件 YUV 明确矩阵/范围/标签；Apple 分支是 BGRA 和帧标签 | 参数检查未调用 Apple 编码器、没有实测输出像素。现有显式浮点色彩契约、alpha 与源时钟验证仍需完成 |

## 4. 预算与开发顺序

以下为一名熟悉现有 Python/Node/FFmpeg 架构开发者的**规划估计**。已适配能力不重新计入成本或收益；估计含限定错误处理、离线安装、取消和验证，未包含全剪映功能实现。

| 顺序 | 限定交付 | 原型 / 生产化接入估计 | 预计减少的重复工作 |
|---|---|---|---|
| 1 | A07/A09 的故障与音频夹具纳入既有模块；先根据本项目实际失败修复 | **0.5–1 /1–3 人日** | 边界案例发现、gain/mono 规则设计；已有功能不整体重写 |
| 2 | A05 单次 HTML 批处理池，资源总额和结束清理由本地宿主控制 | **1–2 /3–6 人日** | 池回收和失败分类；真实性能收益需同素材前后对照 |
| 3 | A06 共享代理转码去重，复用现有 SHA 缓存、任务所有权及取消 | **1–2 /3–5 人日** | 并发协议和临时产物处理；与第 2 项共享生命周期，不能简单累计作净节省 |
| 条件项 | A10 一种新基础开放 NLE 导出 | **3–6 /8–15 人日** | 基础轨道/资源/XML 规则；实际目标程序兼容、时间和效果映射仍是主要成本，维持 R14 预算 |
| 条件项 | A11 自有 Agent 宿主的图片消息预算 | **0.5–1 /2–4 人日** | 图片裁减小工具；完整会话宿主不在该预算内 |

当前建议顺序：**继续完成现有原片/浮点内核到标准 render、preview、队列和缓存的统一接入；在对应模块出现实际需求时吸收上述函数与夹具。** 本轮保存了可用源码与研究证据，没有为复用新增常驻服务、第二种作者工程或云依赖。

没有同等范围的实际工时对照，不能据此宣称“节省整个产品某个百分比”。OpenFilm 不会替我们完成自然素材上的抠像/跟踪/光流/修复质量、完整滤镜/转场、HDR、长片性能、版权素材/模板库和剪映全功能等价验收。

## 5. 许可、复现和媒体

根代码 MIT 原文与 R14 **逐字节相同**，本轮重新解包保全：[LICENSE](validation/evidence/openfilm-reuse-20261022-r16/capture-r2/LICENSE.txt)、[第三方说明](validation/evidence/openfilm-reuse-20261022-r16/capture-r2/THIRD_PARTY_NOTICES.md.txt)、[商标说明](validation/evidence/openfilm-reuse-20261022-r16/capture-r2/TRADEMARK.md.txt)。复制代码保留版权、MIT 和改造记录；依赖、字体、示例素材与模型权重分别登记。当前没有新增移植代码，不改变既有归属账。

复核脚本：[固定抓取/修复](../scripts/capture_openfilm_r16.py)、[原始/受限测试运行器](../scripts/verify_openfilm_r16.py)、[7 组观察](../scripts/probe_openfilm_r16.mjs)。历史失败和 r2 复用来源完整保存；重新执行必须使用新的证据/临时目录，并验证固定 ZIP 和原始测试 SHA。无需安装 OpenFilm 完整依赖。

R16 没有新增视觉功能或实测媒体。已采用的功能可看 V79 历史[原创输入](assets/html-components-20261021-v79-native-r2/original.mp4)、[参数修改输出](assets/html-components-20261021-v79-native-r2/edited.mp4)、[GIF](assets/html-components-20261021-v79-native-r2/comparison.gif)和[验收说明](validation/HTML组件字段与逐片段参数离线实测_2026-10-21.md)。这些不计作本轮成片、性能或离线模型结果。
