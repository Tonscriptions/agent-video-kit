# 本地 SoulX 中文配音与声线登记契约 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-LOCAL-SOULX-TTS-001 |
| 状态 | 有效 |
| 更新日期 | 2026-10-15 |
| 引擎 | `soulx-podcast-local-v1` |
| Worker 协议 | `agent-video-soulx-tts-v1` |
| 实现 | `product/src/ai_ad_editor/local_tts.py`、`soulx_worker.py`、`cli.py` |

## 1. 能力与边界

通过显式本地 SoulX-Podcast 完整 safetensors 权重、原生 Python、源码、依赖目录、语音 tokenizer 和登记的单人参考声生成中文口播。当前执行路径为 Hugging Face LLM BF16、Flow FP16、CUDA；不回退 GGUF、CPU、其他模型或在线 TTS。原始输出为 24 kHz 单声道，母带使用本地 FFmpeg 转为指定采样率和声道的 PCM WAV。

一次 `tts synthesize` 使用一个已登记声线和一段不超过 2000 字符的文本。保留自然时长，不自动加速、压缩或填充到用户预设时长。语气、方言、多说话人批次、自动选声、语速控制、字级时间戳与剪映等级的广泛听感验收仍待扩展。默认不指定适配器时继续使用 FFmpeg flite，仅接受 ASCII/英文。

## 2. 登记数据

模型、声线记录保存在 Agent Project 的 `extensions.local_tts`，包含 `schema_version`、`adapters[]`、`voices[]`。它们随项目原子保存、快照/恢复、幂等和元数据事务一起处理，避免 registry 与项目恢复到不同版本。ID 不覆盖更新；模型或授权证据变化后以新 ID 登记并显式选择。

| 记录 | 必要输入 | 完整性证据 |
|---|---|---|
| 模型适配器 | Python `.exe`、源码目录、依赖目录、模型目录、语音 tokenizer、本地许可证据文件 | Python、完整模型配置/索引/分片/Flow/HiFT/CampPlus/文本 tokenizer、推理源码、s3tokenizer 源码及证据的文件大小和 SHA-256 manifest |
| 参考声线 | 已导入的 audio 资产、原样逐字稿、本地来源/授权证据 | 音频哈希、逐字稿哈希、证据哈希及组合哈希；依赖参考音频的 Rights Ledger 记录 |

模型索引只接受当前目录中的 `.safetensors` 分片名，缺失任何必要文件即拒绝登记。语音 tokenizer 固定为 `speech_tokenizer_v2_25hz`，受支持文件 SHA-256 为 `d43342aa12163a80bf07bffb94c9de2e120a8df2f9917cd2f642e7f4219c6f71`。不通过模型名称自动定位或下载。

依赖目录由调用者显式提供；当前记录 s3tokenizer 源码与 Python 的哈希，并在运行报告中记录 Torch、Transformers、ONNX Runtime 版本及关键模块路径。没有对整个 Python/DLL/驱动依赖闭包建立内容寻址锁定，不能宣称跨设备逐采样确定性。

参考声必须为可读的 1–60 秒单人音频，推荐干净的 5–15 秒录音。程序检查格式和时长，无法自动证明说话人同意、单人性或逐字稿准确性。逐字稿不改写、不繁简转换；UTF-8 文件仅去除 BOM。

## 3. CLI

以下路径代表调用者已准备的本地文件；命令不会下载或安装。

```powershell
.\ai-ad-editor.ps1 tts adapter register --project E:\work\ad `
  --adapter-id soulx_local `
  --python-executable E:\runtimes\python\python.exe `
  --source-root E:\models\SoulX-Podcast `
  --package-root E:\runtimes\soulx-packages `
  --model-path E:\models\SoulX-Podcast-1.7B `
  --tokenizer-path E:\models\speech_tokenizer_v2_25hz.onnx `
  --evidence E:\evidence\soulx-model-license.txt --dry-run

# 复核 planned manifest 后，同一命令去掉 --dry-run 正式登记。
.\ai-ad-editor.ps1 tts adapter list --project E:\work\ad
.\ai-ad-editor.ps1 tts adapter inspect --project E:\work\ad --adapter-id soulx_local

.\ai-ad-editor.ps1 media ingest --project E:\work\ad --input E:\voices\reference.wav
.\ai-ad-editor.ps1 tts voice register --project E:\work\ad `
  --voice-id narrator --asset-id <media-ingest返回的资产ID> `
  --prompt-input E:\voices\reference-transcript.txt `
  --evidence E:\evidence\voice-source-and-authorization.txt
.\ai-ad-editor.ps1 tts voice list --project E:\work\ad
.\ai-ad-editor.ps1 tts voice inspect --project E:\work\ad --voice-id narrator

.\ai-ad-editor.ps1 tts synthesize --project E:\work\ad `
  --adapter-id soulx_local --voice-id narrator `
  --text '让每一次创作，都变得更加简单。' `
  --asset-id narration_01 --output assets\tts\narration_01.wav `
  --sample-rate 48000 --channels 1 --seed 20261015 `
  --apply --track-id track_audio_1 --timeline-start-seconds 0 --dry-run
```

`--adapter-id` 与 `--voice-id` 必须一起提供；flite 的 `--voice` 不用作 SoulX 声线选择。`--input` 可替代目标 `--text`；`--prompt-text` 可替代 `--prompt-input`。相对输入路径以项目根目录为基准，配音输出必须在项目 `assets/` 中且不能覆盖已有文件。支持 8000/16000/22050/24000/32000/44100/48000 Hz、1/2 声道。`--apply` 需要 audio 轨道，以实际探测时长写入 source in/out 与时间线范围，并重算序列长度。音频可与既有音轨混音；本命令不会清空轨道。

`--dry-run` 仍检查参数、目标轨道、模型/参考声/逐字稿/证据完整性，但不加载模型、不生成 WAV、不写快照或项目。`list/inspect` 只读。正式变更遵守项目写锁和 `--idempotency-key`。

## 4. 原生推理与网络约束

1. 父进程重新核验所有登记文件和参考声，并检查对应权利记录的哈希。
2. 在项目 `cache/tts/<operation_id>/` 写入 request，使用显式 Python 的 `-I -B -X utf8` 启动内置 worker，隔离用户 site 和外部 `PYTHONPATH`。
3. Worker 再次核验模型/源码/参考音频，使用项目内 TEMP、HF/Torch/cache 和 HF/Transformers 离线变量。
4. Python 审计钩子阻止 DNS、connect、bind、sendto、urllib/HTTP 连接。关闭本进程的 IPv6 可用性标志以避免 urllib3 导入时的 `::1:0` 探测，不放开端口。上游 s3tokenizer 下载函数被替换为只返回登记本地文件的 resolver。
5. 仅导入推理库，不启动 SoulX Web/API、Docker、WSL 或 GUI。任何实际网络尝试导致生成失败；审计钩子是 Python 层运行约束，不是 OS 安全沙箱，也不宣称能约束任意恶意原生代码。
6. 成功 response 必须匹配协议、状态、输出路径、零网络事件和 raw SHA-256；原始音频必须为非空 24 kHz 单声道。Worker 拒绝非有限或近乎全静音数据，并记录样本数、RMS、峰值、GPU 峰值内存与运行版本。
7. 本地 FFmpeg 写临时母带，探测成功后原子落盘；不会用强制时长或 `atempo` 修正。默认 worker 超时为 900 秒。

## 5. 资产、权利与失败处理

每次成功生成登记 audio 资产、SHA-256、实际时长、操作、快照、provenance 和 `validation/tts_<operation_id>.json`。报告关联 worker 哈希、模型 manifest、声源哈希、随机种子、原始 WAV、日志和实际依赖版本。缓存中保留 request、response、原始 WAV，供项目内诊断；可移植项目包不携带模型、运行时和缓存，跨机重生成需重新准备并登记环境。

Rights Ledger 依赖为：`生成音频 → tts_adapter_<id> + tts_voice_<id> → 参考声原始资产`。这些是本地记录 ID，不使用 URI 形式，也不放宽远程引用审计。登记默认 `unverified/internal`；代码的 Apache-2.0 许可证不会自动成为权重或声源商用许可。生成音频同样默认未核验，需要模型、声源、文本和输出使用权复核后才可发布。来源记录按项目规则保存在 `docs/`，生产项目则在本地登记记录中引用证据文件。

| 错误 | 行为 |
|---|---|
| `TTS_MODEL_INCOMPLETE` / `TTS_SOURCE_INCOMPLETE` | 登记前拒绝缺失权重/源码，不降级 |
| `TTS_TOKENIZER_HASH_MISMATCH` | 拒绝不受支持的本地 tokenizer |
| `TTS_INPUT_INTEGRITY_FAILED` | 模型、参考声、逐字稿或证据变化，推理前拒绝 |
| `TTS_RIGHTS_HASH_MISMATCH` | 登记与权利记录不一致，拒绝生成 |
| `TTS_WORKER_FAILED` | 协议、网络或模型执行失败，保留本地诊断，无可发布最终 WAV |
| `TTS_OUTPUT_INVALID` | raw 哈希、声道/采样率、时长或母带无效，拒绝落盘 |
| `TTS_APPLY_INVALID` | 项目校验失败，回滚元数据并删除本次新建最终 WAV |

取消/异常时不覆盖旧音频，常规失败清理临时母带；强制终止/断电后的大型媒体副作用恢复仍受[事务恢复边界](./跨文件项目事务恢复契约_v0.1_2026-10-15.md)约束。失败操作与 cache 诊断可保留，不能把它们视为可发布资产。

## 6. 验证入口

常规回归见 `product/tests/test_local_tts.py`，以小型显式模型夹具测试登记/哈希/回滚，并以真实 PCM/FFmpeg 测试母带、入轨与渲染；夹具 runner 不作为真实模型听感证据。

真实模型 smoke 使用 `scripts/smoke_soulx_local.py`，必须显式提供全部本地路径和参考逐字稿文件，并选择不存在的新项目目录。流程包含登记 dry-run、正式登记、生成 dry-run、真实推理、合成底板、CLI 时间线编排、实际渲染、质量/项目/本地策略校验以及未核验权利发布阻断。不能因观察超时而重复启动同一工作；先确认当前进程已终止。真实结果与限制登记在[回归验证记录](../validation/回归验证记录_2026-10-13.md)。
