# 本地质量 Golden 清单规范 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-QUALITY-GOLDEN-001 |
| 状态 | 有效 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-14 |
| 运行边界 | 原生 Windows、Python、FFmpeg；默认离线 |

本规范定义无 GUI Agent 流水线如何把通过质量门禁的本地媒体固定为可复核的回归基准。它解决“同一项目后续输出是否发生哈希、设置或质量指标漂移”，不把单机字节一致性解释为跨设备视觉等价。

## 1. CLI

```powershell
python -m ai_ad_editor quality golden --project .\work\demo --input .\work\demo\renders\ad.mp4 --mode capture --require-audio --expensive
python -m ai_ad_editor quality golden --project .\work\demo --input .\work\demo\renders\ad.mp4 --mode verify --require-audio --expensive
```

`--mode` 为 `capture` 或 `verify`，省略时默认为 `verify`。`--manifest` 省略时写入项目内 `validation/golden-quality.json`；自定义路径必须位于项目根目录内。`capture` 先运行 `quality check` 等价门禁，失败时不会写入清单。`verify` 只读清单和媒体，不覆盖任何文件。

## 2. 清单字段

| 字段 | 语义 |
|---|---|
| `golden_version` | 当前固定为 `0.1.0` |
| `project_id` / `sequence_id` | 捕获时的项目和可选序列身份；验证会检查项目 ID 与期望时长 |
| `profile` / `canvas` | 输出档案和实际检查画布；验证省略档案时沿用捕获档案 |
| `artifact.sha256` / `artifact.bytes` | 本地媒体的 SHA-256 和字节数；哈希是主要漂移门禁 |
| `settings_sha256` | 规范化质量设置的 SHA-256，覆盖画布、编码和色彩设置 |
| `expected_duration_seconds` | 序列期望时长；没有序列时为 `null` |
| `constraints` | 音频、黑帧、A/V 差、LUFS 和 true peak 检查参数 |
| `metrics` / `metric_tolerances` | 稳定质量指标及可解释的数值容差；不保存完整 ffprobe 日志 |
| `created_at` | 捕获时间，仅供审计，不参与媒体或设置哈希 |

验证报告中的 `mismatches` 使用 `QUALITY_GOLDEN_*` 错误码，例如 `QUALITY_GOLDEN_HASH_MISMATCH`、`QUALITY_GOLDEN_SETTINGS_MISMATCH`、`QUALITY_GOLDEN_METRIC_MISMATCH` 和 `QUALITY_GOLDEN_METRIC_MISSING`。成功返回 `0`；漂移或质量门禁失败返回 `2`。

## 3. 运行与证据

1. 先用 `$video-cut-quality` 执行 `quality check`、Scope 和 Rights 检查。
2. 仅在输出通过门禁后捕获 golden；把清单与 render manifest、probe、Scope、Rights 发布清单一起保存。
3. 后续重渲染必须在相同本地媒体、项目设置和 FFmpeg 构建上执行 `verify`；若哈希变化，Agent 必须把结果标为漂移并交给人工或上层策略处理。
4. 不得把 `golden-quality.json` 当作许可证证明。媒体、字体、模板和模型仍受 Rights Ledger 与本地策略门禁约束。

## 4. 边界

当前清单只覆盖单个本地媒体和结构化质量指标；扩展 VFR/HDR/坏文件边界、多字体字幕视觉、透明播放器兼容、跨设备编码、跨 FFmpeg 版本容差和人工视觉样例仍需独立 fixture。它也不提供自动调色、语义质量判断或剪映项目兼容性证明。
