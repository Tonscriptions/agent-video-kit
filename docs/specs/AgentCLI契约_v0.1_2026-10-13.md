# Agent CLI 契约 v0.1

<!-- V71-CURRENT -->
2026-10-20 **V71（透明联系表限定验收）**：参考 OpenFilm `lookMedia`，新增原生 `media contact-sheet`；透明视频按实际 PTS 输出棋盘格、浅底、深底、Alpha 四视图。显式锚点选择请求时刻或之后的首个可解码帧，0.17 秒样例实际为 0.25 秒，不伪造精确播放定位。隔离分支完整 **1593/1593、9056.192 秒、0 跳过、217 源码输入＋8 外部夹具前后相同**，发布工作区相同相对路径字节逐项匹配；25 个联系表和 4 个原生 Job 新方法为其子集。联系表专项 **25/25、107.100 秒、0 跳过**。开发原生 **7 CLI/35 检查**；四锚点均与完整 24 帧解码对应帧逐字节一致，16 面板通过独立 Alpha 像素对照。**144 资源/7 wheels/10 隔离 CLI＋1 模块来源/38 安装检查**，安装联系表 PNG、来源帧、Alpha、PTS 和字体摘要与开发版一致。原生 Job **4/4**与受控提前退出对照通过；修复挂起创建→加入 Job→恢复主线程，8 份外部夹具显式绑定。**17 Skills/264 本地引用**。**当前 33 公开文件、6 次实际视频探测**（另留 33 历史文件）；静看开发/安装两张图，未连续播放或听审。本版无 GUI、浏览器、模型前向或网络媒体请求；8-bit 抽样预览不验收自然人像、HDR、长片性能或完整剪映等价。 [契约、原视频、实际图片及失败](../validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md)。
<!-- /V71-CURRENT -->

<!-- V70-CURRENT -->
2026-10-20 **V70（同批次结果复用限定验收）**：参考 OpenFilm 的批次规则，新增显式 `queue run --reuse-identical`，仅本次调用、同项目、单 worker。实际源字节、有效设置、权利和运行实现绑定摘要；复制另建 operation/manifest，编码证据保留来源身份。完整 **1564/1564、4147.745 秒、0 跳过、214 输入冻结**；28 新契约方法为其子集。针对性 **28/28、62.954 秒、0 跳过**。开发版 **10 次 CLI、22 项检查**；6 个作业中 5 成功/1 参数拒绝，真实 **3 次编码、2 次复制**；普通 MP4、透明 WebM 的副本逐字节、全部 24 帧、PTS、PCM 相同。**143 资源/7 wheels/13 次隔离 CLI＋1 次模块来源检查/38 项安装检查**；安装版独立重复样例，全部帧/PTS/PCM 与开发版相同。真实 ffconcat 伪装登记另 5 CLI＋1 FFprobe，在编码前拒绝；**17 Skills/260 本地引用**。本次为程序生成的 320×180/12 fps/2 秒技术素材；静看两张首帧联系图，未连续播放或听审。**未验收自然素材效果、吞吐提升、跨调用缓存或完整剪映等价**。 [契约、原片/GIF、收据与保留的失败](../validation/OpenFilm同批次结果复用实测_2026-10-20.md)。
<!-- /V70-CURRENT -->

<!-- V69-CURRENT -->
2026-10-20 **V69（CPU 人脸契约限定验收）**：本地 OpenSeeFace 66 点逐帧锚点，显式磨皮/曝光/瘦脸/眼部放大；默认零强度，缺失/切点清空几何关联，保存完整地标配方并显式重放。完整 **1536/1536、3748.515 秒、0 跳过、212 输入冻结**；16 新契约方法为子集。开发 **16 次基础 CLI/39 条原检查/24 帧，24 次真实检测＋20 次地标**；四项独立控制另 20 检查、0 新模型前向。**142 包内资源/7 wheels/19 次基础隔离 CLI＋1 模块来源检查**；开发/安装另各 1 次 worker 启动后取消核验。安装版另 24 检测/20 地标，全部 RGBA/PCM 与开发相同。**17 Skills/256 引用**。原 Alpha、范围外 RGB、中性输出、逐帧 PTS/PCM、取消/超时回滚通过；PNG 中文路径和 FFV1 色彩标签失败保留。素材为 NASA 静照生成的平移/空脸段，静看 3 帧和控制联系图，未连续播放/听审；**自然动态美颜、透明人脸边缘、美妆/身体及完整剪映等价未验收**。暂存 CRLF 检查曾中止；已保留日志并修正规则，源码与实测文件原字节保留。 [原片/GIF/失败与发行](../validation/离线人脸锚点与局部修饰实测_2026-10-20.md)。
<!-- /V69-CURRENT -->

<!-- V68-CURRENT -->
2026-10-20 **V68（CLI/协议/发行限定核验）**：显式 `media inpaint|outpaint --temporal-context previous`，把同场景、同一全局帧已经正式输出的生成选区交给后窗，保留已输出前缀；默认/`none` 保持旧路径。完整 **1520/1520、3573.275 秒、0 跳过、204 输入冻结**；65 项 VACE 定向是子集，新增 24 方法。**135 包内资源/7 wheels/28 隔离 CLI**，另 1 次安装模块契约调用；开发/安装各 8 帧真实 LaMa 控制，全部 RGBA/PCM 相同；**17 Skills/250 引用**。真实 VACE previous 在文本权重准入阶段拒绝：物理可用 5146 MiB，要求 7936 MiB；CLI 退出码 6，**0 有效 VACE 前向/无成片**，原错误和诊断保留。 当前 none/previous 的真实成片对照及自然质量仍未验收。 **完整剪映等价未验收**。 [编号核验、原片/GIF、失败及发行](../validation/VACE前窗生成上下文实测_2026-10-20.md)。
<!-- /V68-CURRENT -->

<!-- V67-CURRENT -->
2026-10-20 **V67（产品限定验收）**：共享 RVM/SAM2/LaMa/VACE 管道新增三角色退出观测、有界脱敏日志、回收前留证和 `diagnostics list/show/export`；保留原错误、operation ID 和事务回滚。完整 **1496/1496、4676.172 秒、0 跳过、202 输入冻结**，34 新专项为子集。开发 **33 CLI**：真实无效 ONNX 解析失败 1 次（0 有效模型前向），LaMa harmonic 真实 **8 次前向/8 帧**；原生离线 **134 包内文件/35 隔离 CLI**，另一次真实解析失败与 8 帧 LaMa 输出，全部解码 RGBA/PCM 与开发版相同；**17 Skills/244 引用**。受控生成区 35.578 dB，≥30 dB 单项通过，沿用原质量门槛；静看 4 帧，未连续播放/听审。**本轮没有新 VACE 模型推理或新 Torch 崩溃，原访问冲突根因/长期稳定性、自然质量及完整剪映等价仍未验收**。 [编号核验/原片/GIF/失败/发行](../validation/本地模型管道诊断与回收前留证实测_2026-10-20.md)。
<!-- /V67-CURRENT -->

<!-- V67-DIAGNOSTICS-CLI -->
## 原生管道诊断接口（V67，限定验收通过）

共享 RVM/SAM2/LaMa/VACE 原生管道在进程、响应或输出核验失败时，保留原 `errors[].code`、退出码与 `operation_id`；在 `errors[]` 的对应错误对象内可选增加 `diagnostics`，例如单错误响应读取 `errors[0].diagnostics`。`diagnostics.status=stored` 提供 `diagnostic_id`、项目相对 manifest 路径及 `manifest_sha256`；`status=unavailable` 仅提供次级 `warnings`。附件失败不会替换原业务错误。未进入管道的预检以及发布后的保存失败可能只有 operation ID；调用方须允许没有诊断字段。原有非管道错误的 JSON 字段保持不变。

| 命令 | 参数与行为 |
|---|---|
| `diagnostics list` | `--project`；可选 `--operation-id` 过滤有限历史；只读，不触发清理 |
| `diagnostics show` | `--project --diagnostic-id`；可选 `--expected-manifest-sha256`；默认只返回已核验 manifest，`--include-logs` 显式返回脱敏文本 |
| `diagnostics export` | 同 show 的 ID/SHA 参数，另需 `--output <新.zip>`；父目录须已存在、不可为联接；`--dry-run` 不写 ZIP，正式执行只写显式输出 |

命令不修改作者工程、账本或快照。缺失/已清理记录退出 3，边界/完整性失败退出 10，导出已有路径/格式无效退出 2；保留原始媒体与模型，不收集 RGBA stdout。记录默认仅保存在本项目 `renders/diagnostics/pipelines/`，不上传。保留策略在新记录写入时执行；读取过期记录不等于保留期自动后台清理。归因/预算/验收要求见[诊断契约](本地模型管道诊断与有界留证契约_v0.1_2026-10-20.md)。
<!-- /V67-DIAGNOSTICS-CLI -->

<!-- V66-CURRENT -->
2026-10-20 **V66（产品，10-19 开始的跨日验收）**：新增 `media outpaint`，本地 LaMa/VACE 向更大画布生成背景；显式放置、同源蒙版、归一化原区域 RGBA/PTS/PCM 保护、可编辑配方、工程包与片段组跨项目重绑定。完整 **1462/1462、4928.763 秒、0 跳过、200 输入冻结**；24 扩图专项、41 VACE 专项均为子集，后者含 8 个新增读取方法。开发 **67 CLI/3 次模型交付/24 帧**；原生离线 **133 包内文件/25 隔离 CLI**，LaMa harmonic 的全部 RGBA/PCM 与开发版相同；**17 Skills/238 引用**。生成区预先声明 ≥30 dB，实测 lama/direct 34.485 dB（通过）；lama/harmonic 35.578 dB（通过）；vace/harmonic 19.228 dB（未通过）。原画面保护通过不替代生成质量；**自然扩图、安装版 VACE 推理与完整剪映等价仍未验收**。 VACE 两次原生文本加载访问冲突保留；组件内 `pread` 后本例实际交付通过，**底层根因与长期稳定性仍未确认**。 [原片/GIF/编号核验/失败和发行](../validation/本地视频扩图与原画面保护实测_2026-10-19.md)。
<!-- /V66-CURRENT -->

<!-- V65-CURRENT -->
2026-10-19 **V65（产品）**：接入 OpenFilm 固定 `f6a65ae5` 的硬件参数/H.273 策略，保留 Python/FFmpeg 主链；独立 `off/prefer/require` 编码/解码、四帧实测、强制硬件帧与 CPU 对照、NV12/P010 输入、帧级/码流色彩标签、有限回退、队列/续跑及持久诊断。完整 **1430/1430、2566.147 秒、0 跳过、198 输入冻结**；20 新专项为子集。开发 **20 CLI/49 断言/8 成片/384 帧/768,000 立体声采样帧**；离线 **132 包内文件/22 隔离 CLI**，8 成片解码视频/PCM 均与开发版相同；**17 Skills/235 引用**。本机 RTX 3060 的 H.264 NVENC＋D3D11VA/CUDA、HEVC 10-bit NVENC＋CUDA 通过；AMF 不可用和 H.264 10-bit 设备拒绝均保留。GIF 为实际成片 8-fps 采样、16 帧/2.01 秒/无声；已查看 6 个静帧，未听审/连续播放。这是位流格式/传输与受控合成样例核验，**不验收内部全精度 10-bit 合成、所有设备、自然画质、提速或完整剪映等价**。 [原片/GIF/编号核验/失败与发行](../validation/硬件编解码与显式回退实测_2026-10-19.md)。
<!-- /V65-CURRENT -->

<!-- V64-CURRENT -->
2026-10-19 **V64（产品）**：显式 R3 `source_context_ms` 0..1000、默认 0；真实源前后句柄、有理边缘时间图、原作者采样裁切后反向。完整 **1410/1410、2079.167 秒、0 跳过、196 输入冻结**；9 新专项为子集。开发版 **144 CLI/408 最终帧/816,000 立体声采样帧**；8 次独立原生 R3 裁切 PCM 最大差 0，零上下文与固定 V62 基线解码相同。**131 包内文件/146 隔离 CLI/408 安装帧**；工程往返另 5 隔离 CLI/36 帧/72,000 采样帧；**17 Skills/232 引用**。选定 4 ms 双音 apart 从 375/819.946 改善为 400.085/799.988 Hz，**together 右声道 789.368 Hz 仍失败，apart 反相残差 0.00246022013 仍失败**。28 研究探针/旧代码基线分别计数。GIF 是实际采样统计图、3 页/6 秒、无声；静帧已看，未听审/连续播放。自然质量及完整剪映等价未验收。 [原输入/GIF/失败/发行](../validation/离线音频真实源上下文与短窗音高实测_2026-10-19.md)；[契约](离线音频真实源上下文与精确选区契约_v0.1_2026-10-19.md)。
<!-- /V64-CURRENT -->

<!-- V63-REJECTION -->
2026-10-19 **V63（真实资源拒绝）**：不变 V62 产品/原 VACE 模型流程在 `text-weights` 前因物理可用 3,718 MiB、要求 7,936 MiB 拒绝；0 新模型前向/修复视频。失败、空项目状态与事后自有进程快照保留；未终止其它任务，显存观测不预约资源。 [真实日志与限制](../validation/VACE共享显存真实重试与准入拒绝_2026-10-19.md)。
<!-- /V63-REJECTION -->

<!-- V62-CLI -->
## V62 OCR 命令契约

执行细节和预先门槛见[离线 OCR 契约](离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md)。以下 `<root>`、模型/Python/证据都是显式已有本地路径；不提供安装或下载开关。

| 命令 | 必须参数与行为 |
|---|---|
| `ocr adapter register` | `--project --adapter-id --model-path --python-executable --evidence`；可选 `--threads 1..16`、许可/用途/核验字段，默认 internal/unverified；模型目录必须含固定 det/rec 文件名；重复 ID 拒绝 |
| `ocr adapter list/inspect` | 都需 `--project`，inspect 另需 `--adapter-id`；只读并检查登记，不自动改摘要 |
| `ocr scan` | `--project --asset-id --adapter-id --output validation/<new>.json`；源帧 `--start-frame` 包含、`--end-frame` 排他，默认 step=8/max=120；dry-run 不推理或写报告 |
| `ocr scan` 执行控制 | `--timeout .1..3600` 秒；`--cancel-file <local-flag>`；预置取消退出 8，超时/worker 失败退出 6，来源/模型变化退出 10；失败不提交报告登记 |
| `ocr anchors` | `--project --report --clip-id --query --frame-index`；可选 sequence/zoom/hold/return；默认只返回计划，`--apply` 提交，支持 `--dry-run`；未识别/重复精确文字退出 2 |

```powershell
python -X utf8 -m ai_ad_editor ocr adapter register --project <root> --adapter-id ocr_local --model-path <local-model-dir> --python-executable <native-python.exe> --evidence <local-evidence.json>
python -X utf8 -m ai_ad_editor ocr adapter inspect --project <root> --adapter-id ocr_local
python -X utf8 -m ai_ad_editor ocr scan --project <root> --asset-id <video> --adapter-id ocr_local --output validation/text.json --start-frame 0 --end-frame 48 --step-frames 8 --dry-run
python -X utf8 -m ai_ad_editor ocr anchors --project <root> --report validation/text.json --clip-id <clip> --query 'Select local campaign' --frame-index 0 --zoom 1.5 --hold-seconds .5 --return-seconds .5 --apply --dry-run
```

省略 dry-run 才实际执行对应动作。`scan` 报告和 `anchors` 只消费登记本地媒体；识别出的 URL 是原样文本，不会被访问。锚点应用前校验报告登记/内封摘要/当前来源及实现，任何执行资源的远程路径都继续拒绝。查询区分大小写和空格，不自动使用最高置信度消除歧义。输出是普通 `transform.position.x/y`、`transform.scale` 作者关键帧及源/模型依赖，工程包保留报告；文字框不代表点击区域。

<!-- /V62-CLI -->

<!-- V62-CURRENT -->
历史产品 2026-10-19 **V62（产品）**：新增本地 PP-OCRv4 CPU `ocr adapter/scan/anchors`，源帧/PTS、原文字/多边形、唯一精确查询生成可编辑位置/缩放和回全景。完整 **1401/1401、2428.911 秒、0 跳过、195 文件冻结**；27 OCR 专项为全量子集。开发版 **42 CLI /192 最终帧 /1,152,000 立体声采样帧**；32 聚焦帧边缘最大差 1.484375 px，160 全景帧 RGB 最大差 2，PCM 0。英文四个选定目标/中文四个目标通过，原生前向分别 6 det+60 rec /1 det+4 rec；**英文首帧全十行仅 5/10 完全一致，7/255 字符编辑**，保留空格错误，非盲测。**131 包内文件 /44 隔离 CLI /192 安装帧**，同源预测/解码音画一致；**17 Skills /228 引用**。冒号文本误判、静音夹具/字体缺字、标点阈值参考与旧回归中断保留。静帧已看，未连续播放/听审；文字框不代表点击区域，全隐私、自然 OCR/语义、VACE 修订版完整交付与完整剪映等价仍未验收。 [原片/GIF/识别错误/安装与范围](../validation/离线OCR与文字锚点真实成片实测_2026-10-19.md)。
<!-- /V62-CURRENT -->

<!-- V58-CURRENT -->
2026-10-19 **V58（产品）**：色温、基础色彩平衡、三向色轮、曝光、色阶共 **19 数值通道**逐帧执行，保留作者时钟和可编辑字段；独立实例、递归配额、运行时能力及缓存摘要门禁。**1357/1357、2022.398 秒、0 跳过、186 文件冻结**；28 新增专项为全量子集。**64 CLI /14 组 /262 帧 /1,158,528 立体声采样帧**；13 组独立参数参考 RGB 最大差 1，文字另验实际颜色变化、Alpha 0 与同编码音频一致；全部 PCM 0。**124 包内文件 /65 隔离 CLI /282 安装帧 /1,254,528 采样帧；14 Skills /206 引用**。另验复合容器自身效果：6 隔离 CLI/20 帧/96,000 采样帧，RGB/Alpha/PCM 0，重复实例时钟重置。原曝光参考失配与文字夹具修正保留，未放宽误差门槛。原生静态参考共用 FFmpeg 算法及相同交付边界；Kelvin/基础平衡仍为阴影映射，物理白平衡、HDR、自然质量、连续播放/听审、另一台机器及完整剪映等价未验收。[契约](逐帧调色参数自动化契约_v0.1_2026-10-19.md)、[原输入/MP4/GIF/失败/安装](../validation/逐帧调色参数自动化实测_2026-10-19.md)。
<!-- /V58-CURRENT -->

<!-- V57-CURRENT -->
历史 **V57（产品，2026-10-19）**：完整作者输出的相对变速、曲线、反向、定格与主轨自动随动，保留可编辑作者子序列；局部关联音画共用宿主时钟，连续 BGM 可选保持速度波纹或显式变速。**1329/1329、2092.274 秒、0 跳过、184 文件冻结**；40 新增专项、66 旧磁吸集成为完整子集，不叠加。**62 CLI /344 主帧 /1,651,200 立体声采样帧**，RGB 最大差 1、PCM 0；**123 包内文件 /51 隔离 CLI /454 安装帧 /2,179,200 采样帧**；**14 Skills /202 引用**。原曲线 PCM 失败已修复；文件头部与总线尾部选样参考分开，开发失败全数保留。未连续播放/听审、自然质量、动态外部 blend、全手势、长片/HDR、另一台机器及完整剪映等价未验收。[契约](完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md)、[原输入/MP4/GIF/失败/发行](../validation/完整作者输出变速与磁吸联动实测_2026-10-19.md)。
<!-- /V57-CURRENT -->

V56 调用示例（JSON 请求交给现有 `timeline edit --input <本地文件>`）：

```json
{"action":"magnet","enabled":true}
```

```json
{"action":"shift","clip_ids":["shot_c"],"delta_tick":-180000}
```

```json
{"action":"reorder","clip_ids":["shot_c"],"before_clip_id":"shot_a","sync_span_policy":"split"}
```

`sequence.editing.magnetic` 为严格布尔值；开启时主轨从零连续排列，未显式设置的 sync 缺省 true。普通模式下 sync 与跨剪口策略仍沿用旧缺省。磁吸主轨 compose append/remove/slide/trim 统一规划；副轨保留既有语义。shift 根据所选块最早起点加 delta_tick 选择剩余主轨最近的原始剪口，等距取较早边界。trim 不同时接受独立 timeline_start；标记/序列自动化不改作者时钟。输出计划包含切分源区间、宿主位移、分段和关联 ID、最终轨道及字幕变化，仍支持 dry-run、预期摘要、快照与幂等。局部磁吸片段组保存报告全序列选择扩展。更多字段/拒绝与未实现行为以本轮磁吸契约和实测为准。

2026-10-18 **V56（产品）**：持久主轨磁吸、剪口吸附及 append/remove/shift/trim 联动，跨不同位移剪口的连续音频/字幕/嵌套输出自动分段。完整 **1289/1289，1986.638 秒**、0 跳过、**181 文件**冻结；66 磁吸专项含 26 新增与 40 旧重排，为完整子集。**44 CLI /236 主帧 /1,132,800 立体声采样帧**，RGB 最大差 1、PCM 0；**121 包内文件 /39 隔离 CLI /316 安装帧 /1,516,800 采样帧**，开发版与安装版解码一致；**14 Skills /198 引用**通过。局部片段组真实失败与旧回归中断保留；复杂音频/字形参考使用同版完整作者图，独立原源参考另计。未连续播放/听审；速度/曲线/定格长度自动随动、全手势、自然质量、长片/HDR、另一台机器及完整剪映等价未验收。[契约](主轨磁吸模式与跨剪口同步拆分契约_v0.1_2026-10-18.md)、[原输入/MP4/GIF/失败/发行](../validation/主轨磁吸模式与跨剪口同步拆分实测_2026-10-18.md)。

2026-10-18 V55 扩展：[命名音频路由契约](命名音频总线发送返回与侧链契约_v0.1_2026-10-18.md)。现有 `timeline compose` 的 `add_sequence.audio_routing` 与 `update_sequence.patch.audio_routing` 写入序列局部 DAG，null 恢复旧树状混音；字段、引用、循环与配额随事务校验。`render` 产生 `sequence-audio-routing` 清单，随后执行 `policy audit`。完整子音频先于祖先时间映射；图选择/外部交换边界与[真实原输入、PCM、发行及失败记录](../validation/命名音频总线发送返回与侧链实测_2026-10-18.md)单列。没有增加 GUI 或在线处理命令。

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-CLI-001 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-16 |
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
| `timeline edit --project PATH --input REQUEST [--sequence-id ID] [--expected-project-sha256 SHA]` | 关联、闭隙/shift、范围 insert/overwrite/lift/extract/roll/slide、源 slip/extend_source、reorder/magnet、完整输出 retime 的整数 tick JSON 请求 | dry-run 只返回计划/候选校验；正式执行创建 before-timeline-edit 快照，在原事务中保存/记录；摘要过期拒绝，幂等重放不重复修改 |
| `timeline edit` 的 `action: retime` / compose 的 `op: retime_clip` | clip_ids（compose 可用 clip_id）、transform、options、sync_content | 对当前完整可见作者输出变速；保留可编辑子序列，主轨时长自动随动。与原绝对源参数入口不同，见[完整输出契约](./完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md) |
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
| `audio separate --project PATH (--asset-id ID\|--input FILE)` | 本地音频、可选 adapter、两个输出资产、采样率和 audio 轨道/stem | 无模型时输出 mid/side 近似；native HDemucs 输出 vocals/accompaniment 浮点 WAV，支持显式 CPU/CUDA、精确分段采样、源/模型权利依赖；正式执行快照、登记并可应用选定 stem，dry-run 不推理或写入；详见 [HDemucs 契约](./本地HDemucs人声伴奏分离契约_v0.1_2026-10-16.md) |
| audio adapter register/list/inspect --project PATH | 已存在的本地模型文件/目录、可选执行器、许可证和证据 | 登记或检查 models/audio-adapters.json；保存确定性模型/执行器哈希、Rights Ledger model-adapter 记录、network=disabled 和 before-audio-adapter-register 快照；未知 runner 只登记 metadata，audio separate --adapter-id 会结构化拒绝，不静默 fallback |
| media adapter register/list/inspect --project PATH | 已存在的本地视觉模型文件/目录、argv-only 执行器、许可证和证据 | 登记或检查 models/visual-adapters.json；保存确定性模型/执行器哈希、Rights Ledger model-adapter 记录、network=disabled 和 before-media-adapter-register 快照；支持 command-json-tracking-v1 单目标和 command-json-tracking-multi-v1 多目标 runner，未知 engine 不执行 |
| `media inpaint --project PATH --asset-id ID --mask-asset-id ID --adapter-id ID --derived-asset-id ID` | 已摄取的源视频、本地 image/video 蒙版、登记 LaMa 或 VACE | 共用 alpha/luma、蒙版时钟/几何、扩张/内部羽化/ROI、蒙版外 RGB/源 alpha 保留、无损 MOV、源/蒙版/模型权利及显式音视频入轨；[LaMa](./本地LaMa区域修复与对象移除契约_v0.1_2026-10-16.md) 是 CPU/CUDA 逐帧修复；[VACE](./本地VACE联合视频编辑契约_v0.1_2026-10-16.md) 要求 CUDA 和原文 prompt，显式 seed/steps/guidance/conditioning/token 预算、窗口/重叠/切点；LaMa 拒绝 VACE 专属参数 |
| `media smart-cut --project PATH --track-id ID --clip-id ID` | 直接媒体片段、FFmpeg 静音检测参数、可选项目内字幕和显式 `--remove-phrase`、联动轨道 | 合并本地 `silencedetect` 与字幕 cue 粒度的短语删除区间生成计划；`--apply` 在 `before-smart-cut` 快照后切片视频/音频片段、关键帧和时间线；默认不写回；短语匹配不宣称语义理解 |
| `media relink --project PATH --search-root DIR` | 丢失资产和本地搜索目录 | 优先内容哈希精确重链接；`--match-by-name` 仅允许唯一文件名近似匹配并生成报告 |
| `media track --project PATH ... --roi X,Y,W,H [--adapter-id ID] [--object-id ID\|--all-objects]` | 本地视频、归一化 ROI、可选已登记视觉适配器 | 默认本地模板匹配；v1 runner 校验单目标框，v2 runner 校验唯一 `object_id` 轨迹；`--object-id` 选择一个对象生成可应用关键帧，`--all-objects` 只生成报告且不能与 `--clip-id` 联用；`--clip-id` 写回前创建快照 |
| `media track-bind --project PATH (--asset-id ID\|--input PATH) --roi X,Y,W,H --target-clip-id ID --target-track-id ID [--adapter-id ID] [--object-id ID]` | 本地跟踪源、归一化 ROI、独立视觉目标片段、可选视觉适配器 | 将模板、v1 或选定的 v2 对象关键帧映射到独立文字/贴纸/效果片段，可选 ROI 相对缩放；v2 必须指定 `--object-id`；`--apply` 在 `before-track-bind` 快照后写回，音频和嵌套序列目标结构化拒绝 |
| `media reframe --project PATH --asset-id ID --roi X,Y,W,H --clip-id ID --track-id ID [--adapter-id ID] [--object-id ID]` | 本地视频、目标画幅和直接媒体片段、可选视觉适配器 | 将模板、v1 或选定的 v2 对象跟踪转换为归一化 `crop.*` 动态关键帧；v2 必须指定 `--object-id`；`--apply` 在 `before-reframe` 快照后写回，变速/倒放/嵌套片段结构化拒绝 |
| `ad plan --project PATH --input BRIEF.json` | 本地广告 brief 和可选分析报告 | 写入钩子、卖点、证明、CTA 的节拍计划和序列标记 |
| `subtitle validate --input FILE` | SRT/VTT/ASS/SSA/TTML | 解析、时长、顺序和重叠报告；TTML 只接受本地时钟/offset 语法并拒绝外部实体 |
| `subtitle normalize --input FILE --output FILE` | 字幕文件 | 通过校验后规范化为 SRT；项目模式下输出必须位于项目内 |
| `subtitle transcribe --project PATH (--asset-id ID\|--input FILE) --model-path PATH` | 本地音视频、显式离线 ASR 模型、可选字幕轨道 | 使用 Transformers 或 FFmpeg `whisper.cpp` 生成时间戳 SRT；`--apply` 继承已登记源素材权利，创建字幕资产、独立字幕片段、快照、校验和操作记录；无源资产权利时拒绝应用 |
| `subtitle segment --project PATH --input FILE --output FILE` | 本地字幕、ASR 报告或源 JSON；可选规则/双语/纠正 | 固定原算法、Unicode 码点/整数 tick；新的 assets 内 JSON/SRT；可选 apply 到字幕轨；新文字默认未核验，源权利依赖/快照/锁/事务/幂等 |
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
| `quality mask --project PATH --asset-id ID` | 已登记图像/视频、显式 alpha/luma 及可选本地检查点 JSON | 逐帧面积/半开包围框/原始 IoU、正负点与切点；失败保存报告并退出 2；不推断完整对象或接受分割画质 |
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

audio adapter register/list/inspect 接受既有本地模型/执行器及证据，登记阶段不下载、复制或推理。可执行引擎为 ffmpeg-local-mid-side-v1、command-json-v1 和 torchaudio-hdemucs-local-v1。native HDemucs 要求兼容 .pt/.pth、原生 Python .exe、--evidence，配置 --device cpu/cuda、--threads、--segment-seconds 和 --overlap；六项文件及配置被 manifest 绑定。分离使用 --vocals-asset-id/--accompaniment-asset-id、对应 --vocals-output/--accompaniment-output，入轨选择 --stem vocals/accompaniment。旧 center/side 参数保留；legacy demucs-local-v1、UVR、Open-Unmix、ONNX 无 runner 时仍返回 AUDIO_SEPARATION_ADAPTER_UNAVAILABLE，禁止隐式回退或网络服务。质量与许可门禁见 [registry 契约](./本地模型适配器注册与音频分离门禁契约_v0.1_2026-10-15.md)和 [HDemucs 契约](./本地HDemucs人声伴奏分离契约_v0.1_2026-10-16.md)。

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

时间使用项目 `settings.timebase.ticks_per_second`。关键帧和 `split_clip.at_tick` 是片段内时间；`ripple_insert/ripple_delete.at_tick` 是所选序列时间，不能混用。关键帧必须单调递增，插值可用 `hold`、`linear`、`ease_in`、`ease_out`、`ease_in_out` 或带合法控制点的 `bezier`。

`timeline compose` 变更集支持 `append_clip`、`update_clip`、`remove_clip`、`split_clip`、`trim_clip`、`ripple_insert`、`ripple_delete`、`slip_clip`、`slide_clip`、`set_clip_speed`、`set_clip_speed_curve`、`reverse_clip`、`freeze_frame`、`retime_clip`、`linked_edit`、`source_transition`、`add_sequence`、`update_sequence`、`append_sequence_clip`、轨道增删改、标记增删和序列时长调整。任何变更保存前都会重新执行 Schema、引用、时间范围、嵌套循环和 Rights 语义校验。

V57 当前完整输出变速示例：`{"action":"retime","clip_ids":["b"],"transform":{"speed":2},"sync_content":"ripple"}`。`transform` 可包含 speed、speed_curve、reverse、freeze；原可见窗/字幕/动画/总线先完成，再接受新时钟。主轨多选从后向前处理；关联局部成员按共同宿主时钟分段。其它连续同步 BGM 默认保持自身速度波纹调整，可显式 retime。根标记和总线自动化维持绝对时钟，缩短后越界拒绝。动态外部 blend-opacity、跟踪引用和真实转场端点的直接包装拒绝。声音尾部选样规则与自然质量范围见[实际音画和失败](../validation/完整作者输出变速与磁吸联动实测_2026-10-19.md)。

V38 的拆分、内部波纹插删和 `trim_clip` 使用持久 `presentation_window`：保留完整作者处理，随后选取可见区间。`trim_clip.start_tick/end_tick` 相对当前可见片段，默认新落点为旧落点加 start，可用 `timeline_start_tick` 显式重新放置；不是源范围外扩或完整磁吸。旧关键帧仍在完整作者轴上，运镜预设的可见局部范围在写入时加窗口 offset。部分窗口的高层速度/倒放/定格、跟踪、智能剪辑及受影响转场有明确拒绝，详见[输出窗口契约](./片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md)及[实测边界](../validation/输出窗口裁切与作者时钟实测_2026-10-18.md)。

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

图层变换支持 `transform.anchor.x/y` 或 `anchor_x/anchor_y`，取值为 `0..1`，默认 `(0.5,0.5)`；位置表达式会把该点放到 `transform.position`，同名片段关键帧可逐帧改变锚点。媒体和独立文字旋转使用固定画布逆向采样保持作者 anchor。嵌套容器先隔离合成完整子画布，再围绕容器画布的 anchor 变换，见[隔离合成契约](./嵌套序列隔离合成契约_v0.1_2026-10-17.md)。

遮罩使用归一化参数。`rectangle/circle/ellipse` 支持几何标量、`invert`、`feather` 和 `mask.*` 关键帧；动态 feather 通过 alpha-only 软边表达式执行，范围为 `0..0.5`。`path/polygon` 可以使用固定点数 `points`，点坐标可以用 `points.0.x`、`points.0.y` 关键帧驱动；也可以使用 `segments`/`curve_segments`/`curves`，每段支持 `line` 或 `cubic`，cubic 的 `samples` 范围为 `2..16`，总采样点限制为 `3..32`，渲染器将曲线采样成固定多边形并以固定点边缘的内侧距离近似生成 alpha 软边。曲线段不能与 `points` 同时声明；曲线控制点可以使用片段或 mask 内局部关键帧，例如 `mask.segments.1.control1.x`、`mask.segments.1.control2.y`，渲染器在 FFmpeg `geq` 中先缓存控制点表达式再逐帧生成固定采样点。动态 feather 也可以用 `feather`/`mask.feather` 关键帧驱动。`transform.opacity`、正常层 `blend.opacity` 以及 RGB blend 的 `blend.opacity` 都可以用片段关键帧驱动；片段 `crop` 支持 `pixels`/`normalized` 单位和 `fit`/`fill`/`stretch` 模式，`crop.keyframes` 的 `x`/`y`/`width`/`height` 或片段级 `crop.x`/`crop.y`/`crop.width`/`crop.height` 可以逐帧移动和缩放裁切窗口；动态尺寸由 CPU `geq` 固定画布逆向采样保持输出帧尺寸稳定，宽高关键帧必须大于 0。非法点数、坐标、尺寸、时间或属性必须在写入前拒绝。正式嵌套渲染按“子层合成→父 crop→父 TRS/opacity→父 effects→父 mask→父 fade”执行，父 blend 再与外层混合；容器动画使用所属序列的原作者时钟，子轨道顺序不越过父轨道槽位。父子 mask 分别在各自画布阶段生效；manifest 的 `sequence-composite` 输入记录隔离节点，见[隔离合成契约](./嵌套序列隔离合成契约_v0.1_2026-10-17.md)。时间映射仍见[解析时间映射契约](./嵌套序列解析时间映射契约_v0.1_2026-10-16.md)。序列可声明独立 canvas.width/height，原生子画布裁切/锚点与父画布位置/蒙版分开处理，见[独立画布契约](./独立序列画布与父级投影契约_v0.1_2026-10-17.md)。任意音频路由、嵌套定格、独立子级 FPS/色域/SAR、孤立容器空间转场、通用字体/色彩与完整群组等价继续未验收。

## 6. 渲染、质量和进度

`render` 只接受项目内本地媒体和已验证计划。输出容器为 MP4、WebM 或 MKV；编码器由本机 FFmpeg 能力决定。渲染先写 `renders/.tmp/<operation_id>/`，成功后原子移动最终文件；失败、取消和输入哈希变化不会留下可发布的最终文件。

`--progress jsonl` 的事件写到 stderr，至少包含 `event_id`、`operation_id`、`type`、`stage`、`percent`、`message` 和 `at`。`render --cancel-file FILE` 在启动前和运行中都检查取消；`render --resume OPERATION_ID` 只有在项目和所有素材指纹未变化时才允许重建计划。

### 6.1 本地持久化渲染队列

`queue` 将批量输出作业保存为项目内 `operations/render-queue.json`，默认由同一个本地 FFmpeg 渲染器顺序执行；显式 `--workers N --continue-on-error` 时只并发 FFmpeg/质量检查阶段，项目输出、操作记录和队列状态由主线程串行提交。项目写入命令持有 `operations/project-write.lock`，覆盖队列读改写和状态提交；锁冲突返回 `PROJECT_WRITE_LOCKED`、退出码 6、`retryable=true`。作业状态、取消标记、尝试次数、错误、警告和 render 操作 ID 都可在进程退出后恢复；不引入服务、守护进程、数据库、Docker、WSL 或网络调度。无 `--job-id` 的 `queue run` 只执行 `pending`，失败或取消作业必须显式指定 ID 重试；并发批次允许已启动的 worker 完成，因此要求 `--continue-on-error`；重复输出路径返回 `QUEUE_OUTPUT_CONFLICT`。`queue cancel` 不等待项目写锁，锁被占用或作业运行中时写入 `operations/queue-cancel/<job_id>.cancel`，响应中的 `acknowledged=true, confirmed=false` 表示已递交、终态待确认；`queue list/inspect` 会反映 `cancel_requested=true`。完整字段和状态机见[本地渲染队列与任务状态契约](./本地渲染队列与任务状态契约_v0.1_2026-10-14.md)。

`quality check` 可用 `--require-audio`、`--max-av-sync-ms`、`--expensive`、`--target-lufs`、`--lufs-tolerance`、`--fail-on-black` 和 `--max-true-peak-dbfs`。质量报告失败时，发布调用必须停止；质量检查不会修改原始媒体或项目。

`quality mask` 默认 `--channel alpha --threshold 127 --max-edge 1280 --max-frames 4096 --budget-mib 256`；阈值为严格大于，解码存储预算不含总 RAM。`--expectations` 与可重复 `--scene-cut-frame` 仅采用显式输入；静态图不接受 `--fps`。`--report` 限项目 `validation/` 内 JSON，不能覆盖源/期望。失败检查点仍落盘且退出 2；不修改项目或台账，也不自动改动现有渲染发布门禁。格式、时钟和语义限制见[蒙版核验契约](./本地蒙版逐帧核验与检查点契约_v0.1_2026-10-16.md)。

## 2026-10-16 蒙版驱动跟踪与应用

`media track/track-bind/reframe` 增加 `--mask-asset-id`，与 ROI/adapter/object-ID/input 互斥，需要已登记源视频及蒙版视频。模板/模型模式继续要求 `--roi`。蒙版模式默认 alpha/127，黑白输入显式 `--mask-channel luma`；`--mask-source-start-seconds` 定义帧零对应源秒数。公共预算参数为 `--mask-max-edge 1280 --mask-max-frames 4096 --mask-budget-mib 256`，可选 `--mask-expectations` 与重复 `--mask-scene-cut-frame`。

dry-run 仅预检；正式解码后按源时钟生成包围框轨迹和关键帧。范围中的空选区、跨切点或明确检查点失败均退出 2；报告限制在项目 `validation/` 内 JSON，正常异常回滚仍保留实际失败报告。源/蒙版摘要或探测不符退出 6，缺少匹配权利记录/发布不许可退出 7。持久绑定保留 source+mask/model 权利闭包，沿用现有画布重算限制。`confidence=1` 仅表示非空；姿态/身份/完整分割质量不由该值推断。详见[契约](./本地分割蒙版轨迹与锚定契约_v0.1_2026-10-16.md)与[实际功能、透明补边修复及失败实测](../validation/本地蒙版驱动锚定与重构图实测_2026-10-16.md)。

### 6.2 本地效果目录与渲染契约

Agent 在生成项目 JSON 或变更集前应先调用 `effects list`，需要精确参数时调用 `effects inspect --name NAME`。当前目录版本为 `0.4.0`，记录 45 项由本机 FFmpeg 提供的效果，包括 HSL、RGB 曲线、三向色轮和 `frame_interpolation` 光流补帧；每项至少包含 `id`、`aliases`、`category`、`backend`、`source=ffmpeg-local`、`keyframable`、`parameters` 和 `limits`。目录不会下载滤镜包，也不会访问网络。

`brightness`、`contrast`、`saturation`、`gamma` 和 `vignette` 允许效果参数使用 `eval=frame` 关键帧，`hue`/`hsl` 使用 FFmpeg `hue` 的帧表达式（该滤镜没有 `eval` 选项）。V58 的 `color_temperature`、`color_balance`、`color_wheel`、`exposure`、`color_levels` 共 19 数值通道通过有界 `sendcmd`/独立滤镜实例逐帧执行，精确属性由 0.5.0 目录返回；未知动态属性拒绝。RGB 曲线、降噪、时域混合等未列通道仍保持原静态/告警行为。作者时钟、区间局部时钟、Bezier 截断、缓存及配额见[调色参数契约](逐帧调色参数自动化契约_v0.1_2026-10-19.md)。`frame_interpolation` 使用本地 `minterpolate` 生成目标帧率，运动补偿参数受目录白名单约束但可能消耗较多 CPU，场景切换和遮挡伪影必须进入质量复核。每项还返回 `license=inherit-local-ffmpeg-build`，发布时仍需按实际 FFmpeg 构建核对许可证和 notice。曲线只接受白名单校验后的 `0..1` 范围 `x/y` 点字符串，框线颜色只接受安全的 FFmpeg 颜色 token，非法值返回 `EFFECT_PARAMETER_INVALID`，对应滤镜会跳过或回退到安全默认值。

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

`media track-bind` 增加成对 `--source-track-id/--source-clip-id` 与 `--rotation-mode none|source`。指定源片段时保存源观测和哈希，按源裁切/变换/时钟及输出画布生成可重算绑定；dry-run 不推理/写项目，正式应用保留原快照与权利门禁。`timeline compose` update_clip 支持 `tracking_binding:null` 解除关系；外部格式导出烘焙且报告损失。拒绝无效几何、源篡改/引用循环和超过 20,000 显示帧的编译，详见[坐标空间契约](./本地跟踪绑定坐标空间与渲染重算契约_v0.1_2026-10-15.md)。

`media adapter register` 新增 `--engine yolov10-onnx-cpu-tracking-v1`；`--executable` 为原生 Python `.exe`，`--model-path` 为自包含 YOLOv10 COCO-80 ONNX，`--evidence` 为现有本地文件。显式参数含 `--threads`、`--confidence`、`--low-confidence`、`--match-iou`、`--max-gap-seconds` 和可重复 `--class-id`。`media track --all-objects` 复核后，以 `--object-id` 驱动 track/track-bind/reframe；正式应用要求已摄取 `--asset-id`，保留片段模型权利。报告已存在时拒绝覆盖，native 不回退模板。详见[专用契约](./本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md)。

## 2026-10-16 本地人物抠像增量

`media adapter register --engine rvm-onnx-cpu-matting-v1` 接受现有 FP32 ONNX、原生 Python `.exe`、本地证据、`--threads 1..32` 和可选 `--downsample-ratio`。登记、检查不执行推理，六项文件哈希和固定 CPU provider 进入 manifest；抠像适配器不能作为跟踪适配器使用。

`media matting --project <项目> --asset-id <已摄取视频> --adapter-id <ID> --derived-asset-id <新ID>` 生成项目内无损 QTRLE/ARGB `.mov`，支持范围、分数帧率、画幅/帧数预算、timeout/cancel、dry-run 和幂等。`--apply --track-id <video>` 应用透明视频，`--audio-track-id <audio>` 显式同步原声，`--replace-track` 才可清空本次指定的目标轨道。发布输出前完整验证 RGBA 编码往返哈希，保留源及模型权利依赖；失败清理输出并由项目事务恢复元数据。SDR、CFR、部分片尾延伸和人物模型质量边界见[专用契约](./本地RVM人物视频抠像与透明素材契约_v0.1_2026-10-16.md)。

## 2026-10-16 SAM2 对象分割增量

`media adapter register --engine transformers-sam2-video-local-v1 --model-path <已有完整视频safetensors目录> --executable <原生Python.exe> --evidence <本地文件> --device cpu|cuda --threads 4` 登记 SAM2；默认 cpu，FP32、1..32 线程、512 MiB 会话张量预算。register/list/inspect 使用既有许可、dry-run、幂等、registry/快照/事务/项目包门禁。仅登记本地配置/权重及执行实现，不安装依赖或下载权重。

`media matting` 在选定 SAM2 adapter 时必须提供 `--prompts <JSON>`；可重复 `--object-id <整数>`、选择 `--mask-mode binary|probability`（默认 binary）、`--logit-threshold -20..20`（默认 0）。提示为归一化输出坐标和范围/显示归一化/CFR 后的零基帧；第 0 帧至少有一个选中对象，后续修正只影响未来帧。显式 reset 清除镜头状态，须重新提供所有已激活对象的提示。RVM 不接受这些 SAM2 专用参数，SAM2 不接受 RVM downsample-ratio。

输出与音频、应用、取消/超时和事务沿用 RGBA MOV 契约，报告增加提示摘要、选中对象、模式、修正/重置、设备与状态预算。概率不是物理透明度；重置可能改变对象范围，保留质量警告。详细格式见[SAM2 契约](./本地SAM2对象分割与提示修正契约_v0.1_2026-10-16.md)，真实边界见[实测](../validation/SAM2本地对象分割与提示修正实测_2026-10-16.md)。

## 透明素材普通缩放

渲染器根据登记像素格式，为具有 alpha 的媒体普通 fit/fill/stretch、图层标量 scale，以及独立文字标量 scale 自动使用浮点预乘/反预乘，输出仍为 straight RGBA；没有新增 CLI 参数。源时钟、锚点和发布门禁不变。前轮仿射/动态尺寸 crop 当时另行验收；后续 v0.2 已补入相应 alpha 插值和文字源，线性光/性能仍另行验收。见[契约](./透明素材缩放与预乘Alpha契约_v0.1_2026-10-16.md)与[实测](../validation/透明素材缩放边缘与标签精度实测_2026-10-16.md)。

## 透明仿射、动态裁切和独立文字

无新增 CLI 参数。媒体/文字的仿射、alpha 动态 crop 和最终 resize 自动保持浮点预乘，独立文字绘制后先归一为 straight alpha；透明 fit 补边与不透明黑条分别按原素材接口处理。时钟/锚点/权利不变，一般特效畸变和线性光/HDR/性能另验收。见[当前 v0.2 契约](./透明素材重采样与文字Alpha契约_v0.2_2026-10-16.md)和[实际成片](../validation/仿射动态裁切与文字透明合成实测_2026-10-16.md)。

## 嵌套源时钟增量（2026-10-16）

沿用既有 timeline compose/render 参数。内部解析时钟不写回作者字段；manifest 输入保留 nested_time_mapping 和 NESTED_SOURCE_CFR_NORMALIZED。音频仍为分窗近似，超 16384 窗或不足一采样点时在执行前返回 NESTED_AUDIO_TIME_MAPPING_LIMIT。详见[契约](./嵌套序列解析时间映射契约_v0.1_2026-10-16.md)和[真实前后成片](../validation/嵌套变速倒放与关键帧时钟实测_2026-10-16.md)，不能将该结果扩大到 VFR、速度 easing、定格/字幕或完整群组。

## 速度 easing/Bezier 增量（2026-10-16）

无新增 CLI 参数。speed_curve 支持实际 ease_in/out/in_out 与二/四元 Bezier；Bezier 现在必须显式提供合法 control_points，缺失句柄不再线性回退。内部零/负速度及编译超预算在写入/执行前结构化拒绝；manifest 保留 SPEED_CURVE_COMPILED 与原/归一化时钟界。详见[契约](./速度曲线Easing与Bezier契约_v0.1_2026-10-16.md)与[正式成片](../validation/速度Easing与Bezier原时钟实测_2026-10-16.md)，VFR、定格/字幕、群组和音频相位的旧边界继续适用。

## 2026-10-16 字幕时间基准

完整 **470/470，1150.472 秒**；92 份产品源码/测试及 Schema 前后摘要一致；18 项新增专项为子集，固定旧版同测 18 方法失败（19 个失败记录，含 subTest）。八组主场景 448 新帧的源帧误差为 0，四份校准另计 288 帧、最大差 1；105 次正式 CLI 含 20 次渲染、12 次质量，0 新模型实测推理。逐字状态、打字机和透明度对应通过；旋转只接受 6 个选定姿态。高亮字形定位仍偏移，动态尺寸内嵌透明度、定格、VFR、群组、自然画质及整体剪映等价未验收。见[实测、原片与复现](../validation/嵌套字幕与文字动画原时钟实测_2026-10-16.md)。

## 2026-10-16 原生逐词排版与 manifest

完整 **491/491，887.673 秒**；94 份 Python 产品源码/测试及 1 份 Schema（共 95 份）执行前后字节摘要一致；21 项新增专项为完整套件子集，固定旧版同测 21 方法失败。九组真实旧版/新版/普通字幕对照，632 个新版主帧与 632 个普通对照帧；R/G 轮廓最大差由 51–255 降至 2（阈值 3），逐词激活/串色、源帧与音频脉冲检查均无不匹配。90 次生成 CLI 含 27 次渲染、9 次质量检查，另有 9 次本地策略审计；0 新模型实测推理。受控字体/字幕排版子项通过；自动换行仍由 Pillow 选行，CJK 仅四个确认字形。动态尺寸内嵌高亮显式降级，任意颜色透明度、复杂文字动画、RTL、定格/VFR、群组、自然质量和整体剪映等价未验收。 见[实测与复现](../validation/逐字高亮原生排版与真实成片实测_2026-10-16.md)和[机器证据](../validation/evidence/word-layout-20261016.json)。

无新增顶层 CLI 参数；继续通过 `timeline compose` / `render` 使用 `subtitle.word_timing`。`start_char` 是原文本 Unicode 码点索引。manifest 的 `subtitle_time_mapping.text_layout` 保存原生字体/执行器摘要、协议与布局证据；未知指标拒绝回退，内部时钟不写回项目。RTL、拆分 grapheme、内部连字边界、状态式位置等按[原生排版契约](./逐字高亮原生排版与颜色选择契约_v0.1_2026-10-16.md)结构化拒绝；动态尺寸内嵌高亮明确 warning 并显示普通完整字幕。

## 2026-10-16 V23 文字颜色与透明度

没有新增顶层参数。`subtitle.style` 已有颜色字段由实际本地 FFmpeg 解析并绑定执行器摘要；固定栅格内嵌/独立文字使用组件覆盖率与 straight RGBA。`subtitle_time_mapping.text_paint` 记录引擎、颜色 RGBA、组件顺序和工作色域；动态尺寸内嵌返回 `subtitle_inline_dynamic_color` 近似警告，不能忽略。非法/随机颜色规划阶段返回 `SUBTITLE_COLOR_INVALID` / `SUBTITLE_COLOR_NONDETERMINISTIC`，退出 2，不产出/改写作者时间线及权利；探针异常 `SUBTITLE_COLOR_PROBE_FAILED`。外部 libass 和已有逐词+动画警告保留。见[契约](./文字颜色透明度与独立覆盖率契约_v0.1_2026-10-16.md)、[506 项和真实成片](../validation/文字颜色透明度与实际合成实测_2026-10-16.md)。

## 2026-10-17 V24 字幕动画联合调度

完整 **524/524，1027.580 秒**；98 份 Python 源码/测试加 1 份 Schema（共 99 份）原始字节前后不变；18 项新增专项为完整套件子集，固定旧版同测 18 方法失败、含 subTest 共 28 条失败记录。12 组正式 CLI 实测，160 次调用包含 50 次渲染、12 次质量和 12 次本地策略审计；846 新主帧（其中 52 帧属于未通过交付）与 1818 控制帧分计，794 帧来自 11 组通过交付。文字组合最大 R/G 差为 2，独立前缀/词状态均无不匹配；各组变体解码 PCM 一致。裁切+倒放+Bezier 样例末尾第 50/51 帧背景消失，源帧最大差 5，保留失败成片，整组交付未验收。29.97 fps 仅验明确 90 帧/3.003 秒时间线；任意非整帧时长、动态内嵌、通用塑形/RTL、VFR/定格/HDR、长片性能和完整剪映等价仍未验收。 [契约](./文字动画高亮组合与原生打字机契约_v0.1_2026-10-17.md)、[实测](../validation/文字动画高亮组合与原生打字机实测_2026-10-17.md)。

保持完整段落锚点/基线，原生完整前缀、源空格步骤与逐组件命令一并验收；manifest 的 `text_layout.typing` 保存帧/作者时钟、组件目标、命令摘要。没有新增顶层 CLI 参数/GUI/线上服务。相关错误、资源预算和动态降级按新契约执行，既有测试和媒体的历史边界不回写。

## 2026-10-17 V25 渲染帧采样与 EOF

完整 **537/537，1282.599 秒**；99 份 Python 源码/测试加 1 份 Schema（共 100 份）原字节冻结。新增 13 项与 79 项关联回归均为完整套件子集；固定旧版同测 13 项，8 失败、5 控制通过。10 组正式实测，85 次 CLI 含 22 渲染、10 质量、10 策略；83 次成功、2 次质量失败。496 新主帧与 116 控制帧分计，视频可见性 0 不匹配、源帧最大差 1；V24 第 50/51 帧背景缺失已在同源重验中恢复，误差 0。8 组整体交付通过，2 组极短音频变速后全静音，交付失败。4 毫秒音频拉伸到 250 毫秒仍未验收；非整帧项目时长、VFR/嵌套定格、完整群组、HDR、自然 AI 画质、内容库、性能及完整剪映等价继续未完成。 [契约](./嵌套视频帧区间与结束时钟契约_v0.1_2026-10-17.md)、[实测](../validation/嵌套视频帧区间与结束时钟实测_2026-10-17.md)。

没有新增 GUI、线上调用或顶层 CLI 命令；inputs[].nested_time_mapping.frame_sampling 增加可审计的源/输出帧区间和 EOF 计划。短音频错误未修复，不能因已通过视频检查或 render --publish 而关闭整体交付失败。

## V26：本地音频伸缩与 PCM

完整 **555/555，1598.173 秒**，0 跳过；102 份 Python 源码/测试加 1 份 Schema（共 103 份）原字节冻结。18 项新增与 61 项关联回归均为完整套件子集；固定旧版的 1 项恒速控制也通过，不记作旧版失败。8 组正式实测、72 次 CLI 含 24 渲染/8 质量/8 策略全部成功；210 新主帧、210 精度控制与 210 旧帧分计，三路视频像素相等，源帧身份无误。4 组受控通过；4 组 4 ms→250 ms 已有声，但音高失败：原 400 Hz 脉冲约 386.72 Hz，双声道 400/800 Hz 两路主峰均约 797.24 Hz。瞬态/相位/听感、默认 atempo 极短窗、长片性能和完整剪映等价继续未验收。 [契约](./离线音频伸缩与PCM输出契约_v0.1_2026-10-17.md)、[实测](../validation/离线音频伸缩与真实采样实测_2026-10-17.md)。

`render --container mkv --audio-codec` 接受 `pcm_s16le`、`pcm_s24le`、`pcm_s32le`、`pcm_f32le`。项目 `settings.audio_stretch` 登记已有本地 R3、sndfile.dll、许可及 SHA-256 后启用；null 或未配置继续默认 atempo，1 倍旁路。dry-run 不解码；manifest audio input 增加 audio_stretch 计划和执行证据；计划含端点，原生时间图只传内部锚点。

## V27：显式 R3 声道策略与实际相位边界

完整 **565/565，2302.693 秒**，0 跳过；103 份 Python 源码/测试加 1 份 Schema（共 104 份）原字节冻结。10 项新增与 71 项关联回归均为完整套件子集；固定 V26 对照中，新增 apart 配置 1 项按预期拒绝、恒速控制 1 项通过，分开计数。20 组正式实测、180 次 CLI 含 60 渲染/20 质量/20 策略全部成功；516 新主帧、516 精度控制与 516 旧帧分别核对，三路视频像素相等、源帧身份无误。默认 together 的 10 组控制通过：9 组 float 缓存与 V26 字节一致、1 组恒速 AAC 解码一致。11 组受控交付通过，9 组内容检查未通过：8 组极短音高失败、1 组 apart 反相单声道混合失败。声道策略是明确取舍；瞬态/相位/听感、默认 atempo 极短窗、3..8 声道、长片性能和完整剪映等价继续未验收。 [契约](./R3声道策略契约_v0.1_2026-10-17.md)、[20 组实测](../validation/R3声道策略与立体声权衡实测_2026-10-17.md)。

## V28：隔离子序列合成与父画布操作

本轮 V28：嵌套序列先在透明画布隔离合成，再执行父级 crop/TRS/opacity/effects/mask/fade，父级枢轴与轨道槽位独立生效。完整 **582/582，1358.132 秒**，0 跳过；104 份 Python 源码/测试加 1 份 Schema（共 105 份）原字节冻结。17 项新增与 96 项关联回归均为完整套件子集；固定 V27 同测 17 项，14 失败、3 控制通过。14 组正式实测、112 次 CLI 全部成功，含 28 渲染、14 质量、14 策略；360 新主帧、360 固定 V27 帧与 360 独立参考帧分计。新版全部像素最大 RGB 误差 3（阈值 5），14 组受控通过；旧版 12 组失败、2 组控制通过。另保留 57 帧开发缩放回归对照：缺失行 2→0、最大可测宽度误差 78.8494→0.9864 px，单独计数。原视频、旧/新/参考视频、GIF/MP4、开发失败与摘要已公开。未连续播放或听审；组级音频、独立子画布、嵌套定格/VFR、HDR/线性光、长片性能、自然 AI 画质及完整剪映等价继续未验收；既有音高/相位失败保留。 见[契约](./嵌套序列隔离合成契约_v0.1_2026-10-17.md)和[实际成片](../validation/嵌套序列隔离合成与逐帧像素实测_2026-10-17.md)。

## V29：分层音频与采样包络

本轮 V29：片段→轨道→子序列→父容器分层混音，轨道/容器效果在各自求和之后执行；音频 mute/solo 按序列作用，音量包络逐采样计算。完整 **606/606，2333.520 秒**，0 跳过，105 Python+1 Schema 共 106 份原字节冻结；24 新增与 83 关联方法均为完整子集。固定 V28 同测 24 方法：23 失败、1 控制通过；31 条失败记录包含参数子测试。12 组/102 次正式 CLI 全成功，含 24 渲染、12 质量、12 策略；1,152,000 个新立体声采样帧（2,304,000 个通道数值）全部检查，最大绝对差 0，阈值 2e-6。旧版采样、独立参考分别同量另计；288 新主视频帧与旧版逐像素一致。旧版 11 组内容失败、1 控制通过。另保留非线性 atempo DC 诊断：幅度偏差 0.30517578125、检查区内 82 个零采样帧，包络对照通过不能关闭该内容失败。多轨由自动归一化改为浮点求和，旧工程音量可能改变；无自动限幅。命名 send/return、空间音频、通用效果自动化、嵌套 freeze/VFR、长片性能和完整剪映等价未完成；既有极短音高/相位失败保留，未连续播放或听审。 继续使用既有 timeline compose / render 接口；见[契约](./分层音频总线与采样包络契约_v0.1_2026-10-17.md)和[实际成片](../validation/分层音频总线与真实采样实测_2026-10-17.md)。

## V30：分段音频上下文、末端与资源门限

本轮 V30：默认分段 atempo 使用作者选区内的 float32 上下文，末段从实际伸缩结果取尾；超过 64 MiB 估算末端 PCM 时在规划阶段拒绝。完整 **618/618，1529.147 秒**，0 跳过，107 Python+1 Schema 共 108 文件原字节冻结；12 新增及 94 关联方法均为完整子集。固定 V29 同测 12 项为 6 失败/6 控制。11 组、88 次正式 CLI 全成功；396 新视频帧与旧版像素一致。1,584,000 新立体声采样帧检查长度/有限性及各自声明的内容条件；六组 DC 完整有效区间均通过，T01 检查区零采样帧 82→0。S01 资源拒绝另计 6 次 CLI；开发尾部缺样和错误参考预览保留。未连续播放或听审，通用音高/相位/瞬态、极短输入、自然声音及完整剪映等价仍未验收。 既有 `timeline compose / render` 接口不变；manifest 新增 `audio_tempo_context`（engine v2、选区/上下文/输出范围、实际末端截取模式、质量未接受标志）。超估算门限返回 `AUDIO_TEMPO_CONTEXT_LIMIT`、退出码 2。末端模式的实际裁切起点未知，字段为 null；恒速/单位控制可无上下文节点。见[契约](./分段音频变速上下文契约_v0.1_2026-10-17.md)和[正式实测](../validation/分段音频上下文与完整尾部实测_2026-10-17.md)。

## V31：独立序列画布与选中子级输出

`timeline compose` 的 `add_sequence.canvas` 及 `update_sequence.patch` 支持序列像素尺寸，后者只允许 name/duration_tick/canvas/markers 且不得为空。`canvas: null` 清除显式尺寸；画布缺省/null 继承有效工程输出，非直接父容器。无效后续操作整体回滚，dry-run 不落盘。

render/quality/golden/queue 选中子序列时默认使用其有效画布；显式输出尺寸只覆盖本次选中根，不改作者项目或其他显式子画布。2..8192 整数内部画布允许奇数；自定义 CLI 输出仍 64..8192，420 宽高/422 宽对齐不满足返回 `OUTPUT_CANVAS_ALIGNMENT_INVALID`（退出 2，任务创建前拒绝），非法作者画布返回 `SEQUENCE_CANVAS_INVALID` 或 Schema 错误。manifest 的 sequence-composite 记录源 canvas/parent_canvas、cropped-child-canvas anchor、工作栅格及原生一次采样；没有新增顶层 GUI 或远程服务。见[空间顺序与继承契约](./独立序列画布与父级投影契约_v0.1_2026-10-17.md)。

本轮 V31：序列可声明独立像素画布，子级先在本地画布合成，父级按原生子坐标一次预乘双线性投影；选中子序列的 render/quality/queue 默认使用其画布。完整 **643/643，1128.545 秒**，0 跳过，109 Python+1 Schema 共 110 文件原字节冻结；25 新增/114 关联方法均为完整子集。固定 V30 同测 25 方法：20 失败、5 控制通过，含子测试 30 条失败记录。九组/65 次正式 CLI 全成功，216 新主帧、216 旧帧、216 参考帧与 24 个单独子级帧分计；C01–C08 最大 RGB 误差 2（门槛 5），C09 与旧版字节一致。168 帧为空间独立参考，24 帧只验字形投影，24 帧只验继承兼容。开发配置失败和错误参考保留，0 新模型推理；未连续播放或听审。独立子 FPS/色域/SAR、高频抗锯齿、长片资源、自然质量和完整剪映等价仍未验收。 [九组实际视频及失败](../validation/独立序列画布与原生坐标投影实测_2026-10-17.md)、[机器证据](../validation/evidence/sequence-canvas-20261017.json)。

## V32：序列面积核与工作配额

render、quality check/golden 支持 `--sequence-sampling bilinear|area` 和 `--sequence-memory-mib 1..65536`，只覆盖本次输出。队列用 `sequence_sampling` / `sequence_memory_mib`，非法值入队前原子拒绝。作者 `settings.sequence_sampling` 可声明 method/max_working_bytes（1 字节..64 GiB），省略/null 默认 bilinear 与 1 GiB。配置属于输出指纹，取消续跑无覆盖时恢复原值；显式改值仍执行既有指纹检查。

manifest `sequence-projection-budget` 保存可达节点与分量，`sequence-composite` 保存采样核及估算。超限 `SEQUENCE_PROJECTION_BUDGET_EXCEEDED`、退出 2，在任务/大型数组/FFmpeg 启动前拒绝；dry-run 也受约束。估算不构成全进程 RSS 上界。配置校验报告 SEQUENCE_SAMPLING_INVALID，render 的作者工程错误可能以 PROJECT_INVALID 包装并保留具体 cause；外部格式导出明确报告采样契约 Unsupported。

默认 bilinear 九组与固定 V31 像素一致，area 的一般旋转使用源轴矩形核。见[契约](./序列面积采样与工作栅格预算契约_v0.1_2026-10-17.md)和[九组真实成片及失败](../validation/序列面积采样与工作配额实测_2026-10-17.md)。

## V34：字幕分段、双语与摘要绑定纠正

`subtitle segment` 使用已有原生 Node ≥22.2 调用固定纯算法，无 npm/npx、GUI、浏览器或网络。`--mode original|translation|bilingual`，后两者要求明确提供译文；`--corrections` 必须绑定本次输入原字节 SHA，`part` 从 0 起，规则及纠正文件均进入幂等指纹。`--apply --track-id` 才入轨，`--replace-track` 显式替换；输出始终为项目 assets 内新文件，不覆盖已有文件。无 apply 的正式执行仍登记 JSON/SRT 资产，新文字许可默认未核验。

无词标时估时；有起点标记仍估算词内部，不作强制对齐或模型翻译。字幕输入只迁移纯文字及时钟。详见[完整参数、输入与边界](./本地字幕分段与局部回写契约_v0.1_2026-10-17.md)、[实测/失败](../validation/本地字幕分段与双语回写实测_2026-10-17.md)。

## V35：真实源句柄转场编辑

`timeline transition --project --input [--sequence-id] [--expected-project-sha256] --dry-run` 支持 add/resize/remove；正式执行建立快照并加入既有锁、事务、幂等和 Rights Ledger 路径。compose 可批量执行 `source_transition`。输入采用整数 tick、显式同轨片段引用；linked 音频在添加时推导并冻结。

作者片段和工程时长不变；渲染副本扩展真实源范围，缺少余量即拒绝，不使用旧 auto_handle 的末帧复制。原作者动画、字幕和音频包络时钟保留；新增淡化与之相乘。支持非交叠多剪口链，黑白场在原剪口达到不透明黑/白。首版拒绝嵌套、曲线/定格、跟踪绑定、片段 blend、图片/生成器与旧式转场冲突；原生数据可往返，外部格式明确 Unsupported。见[完整契约](./真实源句柄转场与可逆编辑契约_v0.1_2026-10-17.md)。

## V39：专业范围编辑与既有基础操作

`timeline edit` 新增 `insert/overwrite/lift/extract/roll/slide`；也可作为 `compose.linked_edit` 原子批量的一步。详见[范围编辑契约](./范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md)与[实际证据](../validation/专业范围编辑与滚滑剪口实测_2026-10-18.md)。incoming 片段的落点相对新组，旧片段的完整作者源/动画/音频字段保持，窗口只选可见区间；计划列出创建/删除/修改、关联剪口和闭包。无新增持久 Schema 字段。roll/slide 只使用保留作者输出句柄。

既有 `compose.slip_clip` 为直接媒体源入/出点整体偏移，`compose.slide_clip` 只改单片段落点；本轮 `timeline edit` 的 slide 调整连续左右邻居并处理关联组，不能混用。复杂关联 slip、源作者范围外扩、全磁吸仍待统一规划，不能因命令名称相近推定等价。

## V40：后续真实源编辑模式

上述历史版本的保留作者窗口/缺项边界保持原记录；后续 V40 详见[真实源编辑契约](./真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md)和[实测](../validation/真实源外扩与关联Slip实测_2026-10-18.md)。`timeline edit:slip/extend_source` 支持关联源闭包，roll/slide 缺省 retained、显式 source 才能补真实有限输入句柄。旧 compose slip_clip 统一使用源规划器，缺省仍只改单片段，可加 linked:true；不再绕过跟踪/转场检查。无新增持久 Schema 字段。真实外扩会重新求值效果/retiming，嵌套曲线时长再归一化有明确警告；完整磁吸、跟踪重规划和任意旧主体时钟保真仍未验收。

## V43 编码蒙版显式修正

`media mask-edit --project PATH --asset-id MASK --derived-asset-id NEW` 要求互斥的 `--edits FILE` 或 `--edits-from-asset EDITED`。源 SHA/尺寸/通道/CFR 帧网格严格绑定；alpha 默认，黑白图选 luma。默认 max-frames=4096、storage-budget-mib=512、buffer-budget-mib=256、work-budget-million=200；预算不包含整体进程 RSS/FFmpeg/模型。输出新 PNG 或 QTRLE MOV，不覆盖版本，保留 source.mask_edit 计划及权利闭包。项目写锁退出 6、取消/超时退出 8、非法计划/预算退出 2。支持 dry-run、幂等、取消、进度与事务回滚；不自动入轨。

[完整几何/关键帧契约](本地蒙版笔刷与关键帧修正契约_v0.1_2026-10-18.md)、[真实像素/工程包/模型消费核验](../validation/本地蒙版笔刷与关键帧修正实测_2026-10-18.md)。

## V45 HTML 模板增量

`motion html-controls --project --source-asset-id|--from-asset-id [--params] [--overrides] [--frame-index 0] [--timeout-seconds 120] [--cancel-file]`：单个 CFR 帧/两个新上下文的实际控件检查，不编码或登记资产，返回 controls/effective_controls/采样摘要和回收报告；dry-run 不启动浏览器。`motion html-render` 新增 `--overrides <本地 JSON>`，保存到新输出的 html_motion.template_overrides；省略项继承，null 删除已有覆盖。图片使用 asset_id、独立摘要及权利依赖，可随工程包/片段组重映射。CSS 数值单位必须明确，无效/缺失目标和错图片类型运行时拒绝；dry-run 不冒充 DOM 验收。

字段与预算、逐帧恢复/动画时钟和实际发布边界见[契约](./离线HTML模板控件与覆盖恢复契约_v0.1_2026-10-18.md)、[原片/终态/失败](../validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)。这两个命令继续执行原生 Windows/离线工具链、超时取消和 Job 回收约束。

## V46 HTML 全帧布局与字体质量

`motion html-quality --project --source-asset-id|--from-asset-id [--params] [--overrides] [--timeout-seconds 600] [--cancel-file] [--dry-run]`：逐个有理 CFR 帧绘制，并在独立上下文反序重绘、核对 PNG/布局。只写 validation 报告和 cache/html-quality 预览，最多 8 帧，不修改工程/资产/权利；dry-run 不运行浏览器。实际字体来源、Unicode cmap 与 DOM 行矩形分别记录，未知来源/复杂布局/序列不冒充通过。

`html-render --layout-check off|strict`：省略继承既有配方，未配置/旧配方 off。strict 在编码之前重新执行同计划的全帧门禁，与编码共享总期限；失败/未核验返回 `HTML_QUALITY_FAILED` 退出 2，实际报告和 PNG 在事务回滚后仍保留，工程/台账/新编码资产不变。运行/超时错误 6、取消 8。成功输出保存 layout_check 和绑定摘要的 layout_evidence；不把系统字体 fallback 自动登记为有商业权利。

[范围/预算契约](./HTML文字布局与字体覆盖核验契约_v0.1_2026-10-18.md)、[实际缺字/裁切/继承/发行](../validation/HTML文字布局与字体覆盖实测_2026-10-18.md)。
