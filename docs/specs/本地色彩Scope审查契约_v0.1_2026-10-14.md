# 本地色彩 Scope 审查契约 v0.1

| 字段 | 内容 |
|---|---|
| 文档编号 | SPEC-COLOR-SCOPE-001 |
| 状态 | 有效 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-14 |
| 适用范围 | `ai-ad-editor quality scopes` |
| 后端 | 本机 FFmpeg；网络关闭 |

## 1. 目标

无 GUI 的 Agent 编辑流水线需要可复核的曝光、色彩分布和色相范围证据。`quality scopes` 在指定时间点从本地视频生成 waveform、vectorscope 和 histogram 三张 PNG，并写一个带输入哈希、FFmpeg 探测结果、时间点和产物哈希的 JSON 报告。Agent 可以把这些图交给人工或上层视觉检查器，不必启动剪辑 GUI。

## 2. CLI

```powershell
python -m ai_ad_editor quality scopes --project .\work\demo --input .\work\demo\renders\ad.mp4 --at-seconds 1.25
python -m ai_ad_editor quality scopes --project .\work\demo --input .\work\demo\renders\ad.mp4 --output-dir .\work\demo\cache\scopes\shot-01
```

`--output-dir` 必须位于项目目录内；省略时使用 `cache/scopes/<scope_id>`。`--at-seconds` 必须在 `0..duration` 范围内。输入没有视频流、时间点越界或 FFmpeg scope 滤镜失败时，CLI 返回结构化错误，不留下成功报告。

## 3. 报告和产物

报告 `validation/scopes_<scope_id>.json` 至少包含：

| 字段 | 语义 |
|---|---|
| `scope_version` | 当前为 `0.1.0` |
| `source` / `source_sha256` | 输入路径和内容指纹 |
| `at_seconds` | 实际抽帧时间点 |
| `probe` | 本地 `ffprobe` 媒体信息 |
| `engine` | 固定为 `ffmpeg-local` |
| `artifacts[]` | `waveform`、`vectorscope`、`histogram` 各自的 PNG 路径、字节数和 SHA-256 |
| `network` | 固定为 `disabled` |

命令 envelope 还返回 `operation_id`，并在项目 `operations/` 写入产物清单，便于 Agent 在进程中断后定位报告。

## 4. 能力边界

scope 图是审查证据，不是自动调色结论。当前契约不提供色彩轮 GUI、自动肤色校正、镜头间 shot match、显示器校准、HDR 参考显示或模型级语义判断；这些能力必须通过独立本地滤镜/模型和视觉 golden 样例接入。scope 图也不替代 `quality check` 的流、画布、时长、黑帧、响度和 true peak 门禁。

## 5. 许可与复现

产物由本机 FFmpeg 生成，不下载滤镜或素材。发布前仍须按实际 FFmpeg 构建核对许可证和 notice；报告中的输入与 PNG 哈希用于复现，不等于素材获得了商业授权。
