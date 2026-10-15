# 本地 VACE 联合视频编辑契约 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-VACE-001 |
| 状态 | 评审中 |
| 日期 | 2026-10-16 |
| 关联差异 | #56 区域修复及生成式编辑能力；完整剪映对标仍须逐项验收 |

## 1. 目标与执行边界

通过 `media inpaint` 接入已有本地 Wan2.1-VACE-1.3B Diffusers 模型，提供提示词控制的联合视频窗口编辑。VACE 使用时空模型生成窗口内多个帧；现有 LaMa 的逐帧模式继续按其原契约执行。跨窗口重叠混合只是拼接策略，不能据此声称全视频联合推理或已解决所有闪烁、遮挡和内容一致性。

引擎 `diffusers-wan-vace-local-v1`，协议 `agent-video-wan-vace-inpainting-v1`。原生 Windows/Python，显式 CUDA/BF16、FP32 VAE；文本编码器按登记的 GPU/CPU 权重预算分配，生成阶段释放文本编码器。不得启动 Docker、WSL、HTTP、剪映或其他 GUI，不得联网下载、扩写提示词或回退到云服务。

上游 [VACE](https://github.com/ali-vilab/VACE) 和 [Wan Diffusers 权重](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B-diffusers)声明 Apache-2.0。代码声明、具体模型文件、输入素材和输出用途的权利仍分别登记；运行成功不自动授予商用许可。ProPainter 的非商用许可不作为本产品默认可商用开源内核。

## 2. 模型登记和完整性

`media adapter register --engine diffusers-wan-vace-local-v1 --device cuda` 要求已有本地完整模型目录、原生 Python `.exe` 和本地证据。模型目录只接受固定架构的 JSON、tokenizer 和 safetensors；禁止 pickle、可执行模型代码、`auto_map`、自定义 pipeline 或远程代码。登记不加载模型，不安装包。

登记记录全部模型/配置/tokenizer、Python、证据与本地执行实现的 SHA-256，推理前后核对清单、模型及蒙版。运行时只实例化固定的 UMT5、WanVACETransformer3DModel、AutoencoderKLWan、UniPCMultistepScheduler（flow prediction） 和 WanVACEPipeline，并强制 `local_files_only`、safetensors 与网络 guard。依赖包版本另存报告；文件摘要不等于整个机器/驱动环境锁定。

## 3. 提示词与窗口

VACE 要求显式非空 `--prompt`，支持 `--negative-prompt`、`--seed`、`--inference-steps`、`--guidance-scale`、`--conditioning-scale`、`--prompt-max-tokens`、`--window-frames`、`--window-overlap` 和重复的 `--scene-cut-frame`。LaMa 拒绝这些 VACE 专属选项，避免静默忽略。

提示词保留原文，不调用在线/本地 LLM 扩写；分词超出显式 token 预算时拒绝，不截断。默认 seed 0、30 步、guidance 5、conditioning 1、256 tokens、17 帧窗口、4 帧重叠。seed 固定不承诺跨设备、依赖版本或驱动字节一致。

每个模型窗口为 `4k+1` 帧；最后不足时以窗口末帧显式补齐，并在输出前裁回真实帧数。窗口最多 81 帧；显式场景切点使用范围/CFR 后的零基帧，窗口与混合均不跨越切点。重叠区域按确定性权重混合相邻窗口结果，报告窗口时钟、实际/补齐帧数、seed、ROI、缩放及拼接范围。每窗口使用同一个联合 ROI，按 16 倍数边缘补齐；非空选区缩放后消失须拒绝。

## 4. 媒体、预算与交付

沿用 [LaMa 的蒙版时钟、显示几何、alpha/luma、阈值/扩张/羽化](./本地LaMa区域修复与对象移除契约_v0.1_2026-10-16.md)。蒙版外 RGB 和全部源 alpha 必须精确保留；空选区窗口直接旁路。推理只持有有界窗口及重叠区，不把全部视频载入内存。512 MiB 是保守的自有数组预算，排除模型、Torch 激活、进程 RAM/VRAM；CUDA 峰值另记，不冒充总内存硬限制。

保留原声、显式视频/音频入轨、无损 QTRLE/ARGB MOV 往返摘要、超时/取消/输出竞争/快照/事务恢复和源/蒙版/模型权利闭包。失败不能登记半成品，未核验许可继续阻断 commercial_ad。质量报告必须保留模型生成内容、纹理、重叠接缝和自然遮挡复核要求。既有 LaMa、RVM、SAM2 需要通过完整兼容回归；实际权重、自然镜头和最终成片必须另取证，协议 mock 不能替代模型质量。
