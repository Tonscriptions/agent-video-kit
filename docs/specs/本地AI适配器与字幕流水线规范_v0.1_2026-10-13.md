# 本地 AI 适配器与字幕流水线规范 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-AI-001 |
| 状态 | 评审中 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-13 |
| 关联需求 | PRD-003、PRD-005、ENG-MUST-001、ENG-MUST-003 |
| 运行约束 | 原生 Windows；模型、推理库和字体必须已存在于本地；默认无网络 |

## 1. 目标与边界

本规范定义 Agent 调用本地 AI 能力时的可复现边界，首个适配器是基于 Transformers 的离线 ASR。它负责把本地音视频解码为转写文本和可选时间段，供字幕、镜头检索和编辑计划消费；它不负责下载模型、调用云端 API、生成广告文案或替代时间线渲染器。字幕入口同时支持 SRT、VTT、ASS/SSA 和本地 TTML/DFXP 时码解析，TTML 不允许外部实体或网络引用。

当前实现入口为：

```powershell
python -m ai_ad_editor media understand `
  --project <项目目录> --input <本地音视频> `
  --transcribe --model-path <本地模型目录> `
  [--language zh] [--srt validation/captions.srt]
```

`--model-path` 必须指向完整的本地 Transformers 模型目录。加载使用 `local_files_only=True`，进程设置 `HF_HUB_OFFLINE=1`，不接受缺失文件后自动下载。没有模型目录或模型文件不完整时，命令必须失败并输出结构化错误。

## 2.1 本地基线 TTS

P0 还提供一个不依赖模型下载的语音基线：`tts synthesize` 调用当前原生 FFmpeg 构建内置的 `flite` 音频滤镜，写入项目目录内的 PCM WAV，并生成操作记录、文本 SHA-256、采样率、声道数和 `ffprobe` 摘要。该路径不调用在线服务、不启动容器，也不会把文本写入网络端点。

```powershell
python -m ai_ad_editor tts synthesize `
  --project <项目目录> `
  --text "Hello local advertising voice" `
  --voice kal `
  --output assets/voice.wav
```

也可以用 `--input <本地 UTF-8 文本文件>` 替代 `--text`。输出路径必须位于项目根目录内并使用 `.wav`；可选采样率为 8000、16000、22050、24000、32000、44100 或 48000，声道为 1 或 2。当前 FFmpeg flite 声音库存和语言由本机编译决定，项目适配器在调用前拒绝非 ASCII 文本，以避免把不支持的中文/Unicode 输入送入原生滤镜；多语言、情绪和可控语速 TTS 仍需另一个显式的本地模型适配器，并且必须单独登记权重许可证和真实模型验收证据。

`doctor` 的 `data.checks.local_features.flite_tts` 报告当前 FFmpeg 是否暴露 `flite` 滤镜；为 `false` 时命令返回 `DEPENDENCY_UNAVAILABLE`，不会自动安装或联网恢复。

## 2. 模型与许可证登记

每个模型在进入项目或发布包前都要在 Rights Ledger 和依赖清单中登记：

| 字段 | 要求 |
|---|---|
| `model_id` | 项目内稳定 ID，不直接依赖可变远程别名 |
| `local_path` | 绝对路径或受控模型目录的相对路径 |
| `revision` | 上游 revision、文件清单和 SHA-256 |
| `runtime` | `transformers`、`torch` 及 Python 版本 |
| `task` | `automatic-speech-recognition` 或后续明确任务 |
| `license_spdx` | 模型权重、代码和词表分别记录；未知时阻断发布 |
| `language` | 支持语言和实际调用语言 |
| `quantization` | 精度、量化方式和设备；CPU/GPU 差异需要单独验证 |
| `network` | 固定为 `disabled`；若未来支持显式下载，必须另有批准的下载命令 |

模型权重许可证、训练数据限制和字体许可证不因代码采用 MIT/Apache 而自动继承。商业广告发布前必须通过 Rights Ledger 的目标用途检查。

## 3. 转写输出契约

成功结果写入 `media.understand` 的 `result.transcription`：

```json
{
  "status": "ok",
  "provider": "transformers-local",
  "model_path": "E:/models/whisper-small",
  "language": "zh",
  "text": "完整转写文本",
  "segments": [
    {"start": 0.0, "end": 1.24, "text": "第一句"}
  ],
  "timed": true,
  "network": "disabled"
}
```

`segments` 的时间单位为秒，起点小于终点，按时间升序排列；`text` 是去除模型特殊标记后的文本。模型不能稳定返回时间戳时仍可返回整段 `text`，但 `timed` 必须为 `false`，不得伪造字幕时间。

`--srt` 只有在存在带时间戳的 `segments` 时才写入。SRT 输出必须位于项目目录内，并使用临时文件加原子替换；没有时间戳时返回 `LOCAL_ASR_TIMESTAMPS_MISSING`，不留下空的 SRT 文件。

## 4. 错误与退出码

| 错误码 | 退出码 | 触发条件 | 处理 |
|---|---:|---|---|
| `ARGUMENT_INVALID` | 2 | `--transcribe` 未提供 `--model-path` | 修正调用参数 |
| `LOCAL_ASR_MODEL_MISSING` | 10 | 模型目录不存在或不是目录 | 准备并登记本地模型 |
| `DEPENDENCY_UNAVAILABLE` | 10 | `numpy`、`torch` 或 `transformers` 不可用 | 安装已锁定依赖 |
| `LOCAL_ASR_MODEL_LOAD_FAILED` | 10 | 模型文件、配置或词表不完整 | 修复模型快照/版本 |
| `LOCAL_ASR_AUDIO_FAILED` | 3/6 | FFmpeg 无法解码或超时 | 检查媒体；超时可重试 |
| `LOCAL_ASR_FAILED` | 6 | 本地推理失败 | 按 `retryable` 决定重试 |
| `LOCAL_ASR_TIMESTAMPS_MISSING` | 4 | 请求 SRT 但模型未返回可用时间段 | 改用时间戳模型或导入已有字幕 |

错误响应仍遵循 [Agent CLI 契约](./AgentCLI契约_v0.1_2026-10-13.md) 的 JSON envelope，不输出模型内部路径以外的敏感日志，不尝试联网恢复。

## 5. 字幕与时间线接入

ASR 结果进入字幕轨道前必须经过以下步骤：

1. 检查音频采样率、媒体哈希和模型 provenance；
2. 删除空段、修正同一序列内的边界重叠，并保留原始转写 JSON；
3. 对 CJK 字体、换行、安全区和每行最大字符数执行项目校验；
4. 由模板或时间线变更集显式引用字幕文件，不把模型输出隐式写进渲染器；
5. 渲染后用 `quality check` 和人工抽样核对文字、时间码、字形及音画同步。

字幕文件在接入时间线前使用 `subtitle validate` 检查；TTML/DFXP 的 `begin`、`end`、`dur` 支持常用 clock time、`ms/s/m/h`、帧和 tick offset，规范化输出统一为项目内 SRT。外部实体、DTD、负时码和没有结束时间的 cue 必须结构化拒绝。ASR 文本可以帮助检索和广告编辑计划，但不等于完成语义镜头理解、对象跟踪、口型校正或逐字动画。此类能力必须以独立适配器和独立验收项登记。

## 6. 离线验收

- 无 `--model-path`：退出码 2，错误码 `ARGUMENT_INVALID`；
- 不存在模型目录：退出码 10，错误码 `LOCAL_ASR_MODEL_MISSING`；
- 模型目录完整但未启用网络：模型加载和推理只读取本地文件；
- 带时间戳结果：SRT 可解析、cue 有序且全部落在媒体时长内；
- 无时间戳结果：整段文本可保存，SRT 请求明确失败且不产生伪文件；
- 重复调用使用相同项目和幂等键时重放既有 JSON 结果，不重复写入字幕；
- 失败后项目、验证目录和渲染目录没有可被误发布的半成品。

没有真实的本地模型快照、固定音频、输出哈希和质量报告前，本适配器只能标记为 `implemented`，不能在能力矩阵中标记为 `verified`。
