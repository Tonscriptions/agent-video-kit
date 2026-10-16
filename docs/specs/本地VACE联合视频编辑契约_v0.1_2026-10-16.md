# 本地 VACE 联合视频编辑契约 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-VACE-001 |
| 状态 | 评审中 |
| 日期 | 2026-10-16 |
| 关联差异 | #56 区域修复及生成式编辑能力；完整剪映对标仍须逐项验收 |

## 1. 目标与执行边界

通过 `media inpaint` 接入已有本地 Wan2.1-VACE-1.3B Diffusers 模型，提供提示词控制的联合视频窗口编辑。VACE 使用时空模型生成窗口内多个帧；现有 LaMa 的逐帧模式继续按其原契约执行。跨窗口重叠混合只是拼接策略，不能据此声称全视频联合推理或已解决所有闪烁、遮挡和内容一致性。

引擎 `diffusers-wan-vace-local-v1`，协议 `agent-video-wan-vace-inpainting-v1`。原生 Windows/Python，显式 CUDA/BF16，保留 Transformer 声明的 FP32 稳定性模块，使用 FP32 VAE；文本编码器按登记的 GPU/CPU 权重预算分配，生成阶段释放文本编码器。不得启动 Docker、WSL、HTTP、剪映或其他 GUI，不得联网下载、扩写提示词或回退到云服务。

上游 [VACE](https://github.com/ali-vilab/VACE) 和 [Wan Diffusers 权重](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B-diffusers)声明 Apache-2.0。代码声明、具体模型文件、输入素材和输出用途的权利仍分别登记；运行成功不自动授予商用许可。ProPainter 的非商用许可不作为本产品默认可商用开源内核。

## 2. 模型登记和完整性

`media adapter register --engine diffusers-wan-vace-local-v1 --device cuda` 要求已有本地完整模型目录、原生 Python `.exe` 和本地证据。模型目录只接受固定架构的 JSON、tokenizer 和 safetensors；禁止 pickle、可执行模型代码、`auto_map`、自定义 pipeline 或远程代码。登记不加载模型，不安装包。

登记记录全部模型/配置/tokenizer、Python、证据与本地执行实现的 SHA-256，推理前后核对清单、模型及蒙版。运行时只实例化固定的 UMT5、WanVACETransformer3DModel、AutoencoderKLWan、UniPCMultistepScheduler（flow prediction） 和 WanVACEPipeline，并强制 `local_files_only`、safetensors 与网络 guard。依赖包版本另存报告；文件摘要不等于整个机器/驱动环境锁定。

同一 CLI 命令和 worker 各自使用独立的原生 Windows 校验域：首次核验打开拒绝写入/删除共享的只读文件句柄并读取完整 SHA-256，后续校验只在该句柄持续持有、文件路径身份/大小/修改时间一致时复用摘要。已有可写句柄须导致失败；所有退出路径释放句柄，下一命令重新读取，不能使用跨命令 stat 缓存冒充内容核验。报告 `artifact_verification` 的文件数、读取字节数和持锁复用次数；worker 至少完成前后两次清单核验。17 项模型文件加 Python、证据与 10 项实现，共 29 项摘要；外部模型/Python 仍不随包分发。

文本编码器权重预算通过登记参数 `--text-gpu-budget-mib`（默认 7168）与 `--text-cpu-budget-mib`（默认 8192）显式提供。CUDA 可用量低于 GPU 权重预算加 768 MiB 时拒绝；两类权重预算不足时拒绝，不进行磁盘 offload。该预算用于设备映射，不是总进程内存硬上限；编码正负提示词后释放文本编码器，再加载视频 Transformer/VAE，报告实际映射、精度和 CUDA 分配峰值。

## 3. 提示词与窗口

VACE 要求显式非空 `--prompt`，支持 `--negative-prompt`、`--seed`、`--inference-steps`、`--guidance-scale`、`--conditioning-scale`、`--prompt-max-tokens`、`--window-frames`、`--window-overlap` 和重复的 `--scene-cut-frame`。LaMa 拒绝这些 VACE 专属选项，避免静默忽略。

提示词保留原文，不调用在线/本地 LLM 扩写；分词超出显式 token 预算时拒绝，不截断。默认 seed 0、30 步、guidance 5、conditioning 1、256 tokens、17 帧窗口、4 帧重叠。seed 固定不承诺跨设备、依赖版本或驱动字节一致。

每个模型窗口为 `4k+1` 帧；最后不足时以窗口末帧显式补齐，并在输出前裁回真实帧数。窗口最多 81 帧；显式场景切点使用范围/CFR 后的零基帧，窗口与混合均不跨越切点。重叠区域按确定性权重混合相邻窗口结果，报告窗口时钟、实际/补齐帧数、seed、ROI、缩放及拼接范围。每窗口使用同一个联合 ROI，按 16 倍数边缘补齐；非空选区缩放后消失须拒绝。

按[固定版本上游预处理约定](https://github.com/ali-vilab/VACE/blob/48eb44f1c4be87cc65a98bff985a26976841e9f3/UserGuide.md)，待重绘区域的 RGB 使用 127 灰色，白色蒙版选择生成区域。先在源 ROI 中擦除选区，再缩放，并将缩放后蒙版内再次置灰，避免被移除对象经双线性插值泄漏到条件输入。输出仍以原始源帧合成，蒙版外和全部 alpha 保持不变；报告 `conditioning=masked-rgb-127-before-and-after-resize`。提示词描述期望结果，接口不自动重写提示词。

## 4. 媒体、预算与交付

沿用 [LaMa 的蒙版时钟、显示几何、alpha/luma、阈值/扩张/羽化](./本地LaMa区域修复与对象移除契约_v0.1_2026-10-16.md)。蒙版外 RGB 和全部源 alpha 必须精确保留；空选区窗口直接旁路。推理只持有有界窗口及重叠区，不把全部视频载入内存。512 MiB 是保守的自有数组预算，排除模型、Torch 激活、进程 RAM/VRAM；CUDA 峰值另记，不冒充总内存硬限制。

保留原声、显式视频/音频入轨、无损 QTRLE/ARGB MOV 往返摘要、超时/取消/输出竞争/快照/事务恢复和源/蒙版/模型权利闭包。失败不能登记半成品，未核验许可继续阻断 commercial_ad。质量报告必须保留模型生成内容、纹理、重叠接缝和自然遮挡复核要求。既有 LaMa、RVM、SAM2 需要通过完整兼容回归；实际权重、自然镜头和最终成片必须另取证，协议 mock 不能替代模型质量。

共享媒体管道终止全部子进程、关闭日志后，清理项目内临时工作目录。原生 Windows 短暂共享/访问冲突进行最多 6 次清理尝试，累计退避 1.55 秒；持续占用或目录边界变化必须报告 `MATTING_CACHE_CLEANUP_FAILED` 及保留路径，不能静默留下目录。原生文件锁测试分别验证短暂与持续占用。

父进程以允许替换的只读句柄读取最多 64 KiB 进度快照，避免自己阻止 worker 原子替换进度文件；读取失败、畸形或超范围进度只影响显示。共享 JSON/文本原子写入遇到 Windows 短暂共享冲突时最多尝试 6 次、累计退避 1.55 秒；持续失败保留原目标内容并报错，临时文件按原契约清理。权利/项目/最终 worker 报告继续使用正式错误门禁。

`os.replace` 遇到 Windows 共享/访问冲突时，尝试原生 `SetFileInformationByHandle(FileRenameInfoEx)`，使用 `REPLACE_IF_EXISTS | POSIX_SEMANTICS`。允许删除共享的旧读取句柄继续看到旧快照，新打开的路径看到完整新文件；禁止删除共享的模型锁仍须拒绝覆盖。未支持该调用的系统回到有界重试，不提前删除目标文件，也不忽略只读属性。语义依据见 [Microsoft 文件重命名协议](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fscc/4217551b-d2c0-42cb-9dc1-69a716cf6d0c)和[原生 API](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)。原生测试覆盖同进程与跨进程旧快照、连续发布、短暂/持续占用、暂存文件清理，以及模型锁拒绝原子覆盖。

## 5. 显式采样与模型输入尺度

`media inpaint` 提供两个 VACE 专属参数，默认保留 flow_shift 3.0 和输入倍率 1：`--flow-shift` 接受 0.1..32 的有限数值，`--model-input-scale` 接受整数 1/2/4。LaMa 须拒绝这两个参数，不能静默忽略。它们进入 canonical generation、请求摘要及幂等输入，不能由 worker 自行改写。

`--model-max-edge` 约束现有 ROI 基础栅格；显式倍率作用于该栅格经 16 倍数/最小 64 边缘补齐之后的模型输入。RGB 双线性、蒙版最近邻放大，并在放大后再次将选区置为 127。模型结果以浮点缩回基础栅格，再进行既有 ROI 投影、重叠混合和一次量化，最终输出画布及选区不变。预算必须按实际放大后面积计入自有数组，超预算要在解码/模型加载之前拒绝。

固定的本地 scheduler 配置仍需完整性验证；显式 flow_shift 通过固定 UniPC 类的配置覆盖使用，不修改权重/配置文件。worker 须报告实际 scheduler flow_shift、倍率和逐窗口实际输入 `[frames,height,width]`；父进程验证请求一致性、类型、窗口数量、尺寸/16 倍数与峰值模型像素，不能把倍率仅写入元数据而保持原尺寸推理。

验证需覆盖：1/2/4 倍条件栅格与原始像素映射、选区原色隔离、alpha/选区外精确保留、放大预算前置拒绝、NaN/无效倍率、CLI dry-run 与 LaMa 参数拒绝、篡改采样/倍率/尺寸报告的回滚，以及真实本地模型/成片。开发侧五组对照只用于选择后续正式实测参数，不代替上述交付验收或广泛画质结论。

本轮执行实现摘要发生变化，旧 adapter 会按完整性契约拒绝运行。使用新的 adapter ID 显式重新登记并核验；不得手工改写旧记录摘要来跳过验证。`capabilities` 的 `generative_video_editing.generation_parameters` 提供默认值与可选范围，dry-run 报告缩放后的数组预算，执行记录实际 flow_shift、倍率和逐窗口尺寸。

五组开发侧校准均未消除受控暗补丁；4 倍输入和增加到 50 步没有在该样例上取得更好的重建指标，因此没有修改默认采样配置。详见[同源校准与正式 CLI 边界](../validation/VACE本地多帧编辑与生成填充实测_2026-10-16.md)。
