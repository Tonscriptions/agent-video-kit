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

本规范定义 Agent 调用本地 AI 能力时的可复现边界。当前 ASR 适配器包括：需要 Python 模型目录的 Transformers 离线路径，以及使用本地 FFmpeg `whisper.cpp` 滤镜和显式模型文件的原生路径。它们负责把本地音视频解码为转写文本和时间段，供字幕、镜头检索和编辑计划消费；它们不负责下载模型、调用云端 API、生成广告文案或替代时间线渲染器。字幕入口同时支持 SRT、VTT、ASS/SSA 和本地 TTML/DFXP 时码解析，TTML 不允许外部实体或网络引用。

当前实现入口为：

```powershell
python -m ai_ad_editor media understand `
  --project <项目目录> --input <本地音视频> `
  --transcribe --model-path <本地模型目录> `
  [--language zh] [--srt validation/captions.srt]

python -m ai_ad_editor media understand `
  --project <项目目录> --input <本地音视频> `
  --transcribe --transcribe-engine ffmpeg-whisper `
  --model-path <本地-whisper.cpp-模型文件> --language zh `
  --srt validation/captions.srt

python -m ai_ad_editor subtitle transcribe `
  --project <项目目录> --asset-id <已登记音视频资产> `
  --transcribe-engine ffmpeg-whisper --model-path <本地模型文件> `
  --track-id <subtitle轨道> --apply
```

`--transcribe-engine=transformers` 时，`--model-path` 必须指向完整的本地 Transformers 模型目录；加载使用 `local_files_only=True`，进程设置 `HF_HUB_OFFLINE=1`。`--transcribe-engine=ffmpeg-whisper` 时，`--model-path` 必须是非空的本地 whisper.cpp 模型文件，且本机 FFmpeg 必须暴露 `whisper` 滤镜；模型不会转换、下载或从网络读取。两条路径都在缺少模型、依赖或时间戳时返回结构化错误。

FFmpeg Whisper 路径使用 `destination=<项目内 SRT>` 写出字幕，音频输出丢弃；默认 `use_gpu=false`，只有显式 `--use-gpu` 才允许本机 FFmpeg 使用 GPU。`doctor.data.checks.local_features.ffmpeg_whisper_asr` 只报告当前 FFmpeg 是否包含滤镜，不代表模型已登记或质量已验证。

## 2.1 本地基线 TTS

P0 还提供一个不依赖模型下载的语音基线：`tts synthesize` 调用当前原生 FFmpeg 构建内置的 `flite` 音频滤镜，写入项目目录内的 PCM WAV，并生成操作记录、文本 SHA-256、采样率、声道数和 `ffprobe` 摘要。该路径不调用在线服务、不启动容器，也不会把文本写入网络端点。

```powershell
python -m ai_ad_editor tts synthesize `
  --project <项目目录> `
  --text "Hello local advertising voice" `
  --voice kal `
  --output assets\tts\voice.wav
```

也可以用 `--input <本地 UTF-8 文本文件>` 替代 `--text`。输出路径必须位于项目 `assets/` 内且为新 `.wav`；相对路径以项目根为基准。支持 8000/16000/22050/24000/32000/44100/48000 Hz、1/2 声道。默认 flite 在调用前拒绝非 ASCII 输入。中文通过显式登记的 SoulX 适配器运行，见下方增量契约。

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
  "engine": "transformers-local",
  "model_path": "E:/models/whisper-small",
  "model_sha256": "sha256:...",
  "language": "zh",
  "text": "完整转写文本",
  "segments": [
    {"start": 0.0, "end": 1.24, "text": "第一句"}
  ],
  "timed": true,
  "network": "disabled"
}
```

FFmpeg Whisper 返回相同的 `segments`/`timed` 形状，`provider` 和 `engine` 为 `ffmpeg-whisper-local`，并额外记录 `use_gpu`、模型文件 SHA-256 和生成的 `srt` 路径。`subtitle transcribe` 在需要 `--apply` 时把这些 cue 转成 `generator.type=text` 的独立字幕轨道片段；它同时登记 `kind=subtitle` 的派生资产，引用源资产的 Rights Ledger 依赖，并写入 `before-subtitle-transcribe` 快照、验证报告和操作记录。未提供已登记源资产时可以生成 standalone SRT，但拒绝 `--apply`，防止绕过权利门禁。

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
| `LOCAL_ASR_WHISPER_UNAVAILABLE` | 10 | FFmpeg 没有 `whisper` 滤镜 | 改用已登记 Transformers 本地模型或准备支持 whisper.cpp 的本地 FFmpeg |
| `LOCAL_ASR_WHISPER_FAILED` | 6 | whisper.cpp 模型加载、推理或 SRT 写出失败 | 检查本地模型格式、音频流和 FFmpeg 构建；不会联网恢复 |
| `LOCAL_ASR_TIMESTAMPS_INVALID` | 6 | 生成 SRT 的 cue 时间范围或排序无效 | 保留错误证据，修复模型/输入后重试 |
| `LOCAL_ASR_TIMESTAMPS_MISSING` | 4 | 请求 SRT 但模型未返回可用时间段 | 改用时间戳模型或导入已有字幕 |
| `SUBTITLE_APPLY_SOURCE_ASSET_REQUIRED` | 7 | 自动字幕应用没有已登记源资产 | 先 `media ingest` 并补齐 Rights Ledger，再应用 |
| `SUBTITLE_TRANSCRIBE_TRACK_OVERLAP` | 2 | 目标字幕轨道已有重叠片段 | 审阅后使用 `--replace-track` 或调整起点 |

错误响应仍遵循 [Agent CLI 契约](./AgentCLI契约_v0.1_2026-10-13.md) 的 JSON envelope，不输出模型内部路径以外的敏感日志，不尝试联网恢复。

## 5. 字幕与时间线接入

ASR 结果进入字幕轨道前必须经过以下步骤：

1. 检查音频采样率、媒体哈希和模型 provenance；
2. 删除空段、修正同一序列内的边界重叠，并保留原始转写 JSON；
3. 对 CJK 字体、换行、安全区和每行最大字符数执行项目校验；
4. 使用 `subtitle transcribe` 时先 dry-run，再由 `--apply` 显式写入独立字幕轨道；模型输出不得隐式写进渲染器；
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

## 本地 SoulX 中文模型执行

现有 `tts adapter/voice register/list/inspect` 与 `tts synthesize --adapter-id --voice-id` 已形成专用本地 runner，支持原样参考逐字稿、完整 safetensors/语音 tokenizer 与源码哈希、隔离 Python、网络调用阻断、自然 WAV 时长、资产/音轨和模型/声源权利依赖。契约见[本地 SoulX 中文配音](./本地SoulX中文配音与声线登记契约_v0.1_2026-10-15.md)；真实中文音频、实际渲染和未核验发布阻断见[实测记录](../validation/SoulX中文离线配音实测_2026-10-15.md)。CPU/GGUF、情绪/多声线/语速和广泛中文质量仍待扩展。

## 2026-10-15 原生登记路径

Whisper safetensors 已新增 `asr adapter register/list/inspect`，登记显式 Python、模型/证据文件哈希、CPU/CUDA 和线程预算；生成字幕依赖源素材及模型权利。新 worker 禁止下载、自定义远程代码和 Python 网络调用，保留超过 30 秒的输入，真实短句/原始参考/38.04 秒重复录音已完成入轨与音画渲染。完整契约见[Whisper 登记与验收](./本地Whisper模型登记与转写验收契约_v0.1_2026-10-15.md)，真实证据见[实测](../validation/Whisper中文离线转写实测_2026-10-15.md)。旧直接模型路径与 FFmpeg Whisper 继续可用，不自动获得新登记路径的进程隔离保证。`subtitle evaluate` 提供 CER 门禁；逐字强制对齐、说话人、多语言和广泛广告语料仍未验收。
