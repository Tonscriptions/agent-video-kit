# 本地音频 mid/side 与源分离适配器边界契约 v0.1

| 项目 | 内容 |
|---|---|
| 状态 | 有效 |
| 适用版本 | `audio.separate` / `AUDIO_SEPARATION_VERSION=0.1.0` |
| 运行方式 | Windows 原生 Python + 本地 FFmpeg |
| 网络 | 禁用；不下载模型、不访问云端 |
| 结果 | center mono WAV + side stereo WAV 两个派生资产 |

## 1. 目的

`audio separate` 为 Agent 提供一个可重复的本地音频 stem 入口：把第一条音频流规范化为 stereo，再生成中心声道的 mono `center` 和左右差分的 stereo `side`。它可以用于粗略降低居中的人声、保留侧边环境声或验证下游音频轨道流程。

该入口是声道相位近似，不是 Demucs、UVR、Open-Unmix、Spleeter 或其他 AI 源分离模型。中心声泄漏、相位抵消、单声道素材降级和混响残留必须在 Agent 结果中保留为 warning；不能把它描述成人声/伴奏已经被准确分离。

## 2. CLI

先检查计划，确认输出路径和要应用的 stem：

```powershell
python -X utf8 -m ai_ad_editor audio separate `
  --project E:\\dev\\sandbox\\AI广告剪辑\\workspace\\demo `
  --asset-id camera_source `
  --center-asset-id camera_center `
  --side-asset-id camera_side `
  --track-id track_audio_1 --stem center --apply --dry-run
```

确认后执行：

```powershell
python -X utf8 -m ai_ad_editor audio separate `
  --project E:\\dev\\sandbox\\AI广告剪辑\\workspace\\demo `
  --asset-id camera_source `
  --center-asset-id camera_center `
  --side-asset-id camera_side `
  --track-id track_audio_1 --stem center --apply
```

也可以用 `--input` 直接处理本地音频/视频文件；直接输入需要通过 `--license-spdx`、`--verification-status`、`--evidence` 等参数补齐权利记录。`--apply` 必须同时提供 `--track-id` 和 `--stem`，一次只把选择的一个 stem 追加到 audio 轨道；两个 stem 都会登记为项目资产。

可选参数：

- `--center-output`、`--side-output`：项目目录内的 `.wav` 输出路径；默认写入 `assets/derived/`。
- `--sample-rate`：使用本地白名单采样率重采样；不提供时保留 FFmpeg 默认结果。
- `--replace-track`：应用前清空目标 audio 轨道，必须和 `--apply` 一起使用。
- `--timeline-start-seconds`：写入所选 stem 的时间线起点，必须不小于零。

## 3. 处理与证据

实现使用一次本地 FFmpeg 解码和 `aformat=channel_layouts=stereo`，然后通过 `pan` 生成：

- `center`：`0.5*L + 0.5*R`，mono、16-bit PCM WAV；
- `side`：`0.5*(L-R)` 与 `0.5*(R-L)`，stereo、16-bit PCM WAV。

结果会记录输入/输出 SHA-256、输入/输出 probe、引擎 `ffmpeg-local-mid-side-v1`、`network=disabled`、派生关系、`before-audio-separate` 快照、验证报告、provenance change log 和操作记录。项目资产和 Rights Ledger 的两个 stem 都继承源资产当前有效权利记录；直接输入则使用本地 CLI 提供的权利字段。

dry-run 只执行本地文件存在检查和 probe，不创建 WAV、快照、资产、Rights Ledger 记录、报告或时间线片段。正式执行拒绝覆盖已经存在的输出和资产 ID。

## 4. 错误与边界

| 代码/边界 | 含义 |
|---|---|
| `AUDIO_STREAM_MISSING` | 输入没有第一条可读音频流 |
| `AUDIO_SEPARATION_FAILED` | 本地 FFmpeg 分离失败，部分输出会清理 |
| `AUDIO_SEPARATION_INVALID` | 输出 probe 没有可读音频流 |
| `AUDIO_SEPARATION_APPLY_INVALID` | 写入资产或片段后项目校验失败 |
| `AUDIO_SEPARATION_APPROXIMATE` | 声道差分不是 AI stem 分离，必须人工试听 |
| `RIGHTS_RECORD_MISSING` | 项目资产没有可继承的当前 Rights Ledger 记录 |
| `.wav` 与输出覆盖 | 输出必须是项目内 `.wav`，已有文件拒绝覆盖 |
| 模型级分离 | 当前版本不执行未知模型或外部命令；Demucs/UVR/Open-Unmix 等需未来注册离线适配器并单独验证模型哈希、许可证和网络禁用状态 |

## 5. Agent 门禁

1. 先执行 `--dry-run`，检查输入 probe、两组输出路径、资产 ID、时间线起点和 `AUDIO_SEPARATION_APPROXIMATE` warning。
2. 只有确定需要一个 stem 时才使用 `--apply --track-id --stem`；另一个 stem 仍可作为项目资产在后续轨道中显式使用。
3. 发布前试听 center/side，检查中心声泄漏、相位伪影、单声道素材和混响；不能只依据文件成功生成判定质量。
4. 需要真正人声/背景声分离时，必须停在当前边界并等待一个显式注册、哈希可验证、模型和许可证均在本地的离线适配器；不得自动 fallback 到网络服务。
