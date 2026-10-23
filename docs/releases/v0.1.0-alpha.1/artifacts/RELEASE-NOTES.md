# Agent Video Kit v0.1.0-alpha.1

面向 Agent 的原生 Windows 本地视频编辑 CLI 首个 alpha 预览版。首版闭环包含离线安装、结构化时间线、预览/渲染、权利与质量核验、模板、项目包，以及 17 个 `$video-cut-` Skills。

The first native Windows alpha preview of the local video editing CLI for Agents: offline installation, editable timelines, rendering/previews, rights/quality checks, templates, project packages and 17 prefixed Skills.

## 下载 / Downloads

- `cp313-win_amd64.zip`: 8-wheel offline application bundle. Requires existing native CPython 3.13 x64 and ffmpeg/ffprobe on PATH. No Python/FFmpeg/model weights included.
- `examples.zip`: original fictional CC0 media, actual rendered MP4/GIFs, complete CLI responses, project-package round trip and reproducer.
- `skills.zip`: 17 Skills with resources/notices and current manuals. Use the source checkout for historical linked contracts/evidence. No Agent host or models included.
- `version.json` and `SHA256SUMS.txt`: provenance and artifact digests. Digests are not an author signature.

## 验证 / Verification

Unchanged 331 product inputs match the **2,930 passed / 0 skipped** full baseline. Previous targeted fresh installation passed 118 methods / 197 resources (overlapping counts). This release newly rebuilt and installed 8 wheels, verified 197 installed resources, executed **28 isolated CLI calls: 27 successes + 1 expected refusal**, rendered two examples, round-tripped a package and checked all 17 Skill formats. The local documentation page passed 14 interaction checks with desktop/mobile screenshots and a real-response replay recording.

## 安装 / Installation

```powershell
Set-Location E:\tools\agent-video-kit-v0.1.0-alpha.1
$avkPython = 'C:\Python313\python.exe'
$avkManifest = (Get-Content .\version.json -Raw | ConvertFrom-Json).manifest_sha256
& $avkPython -I -B -X utf8 .\bundle\install.py --target E:\tools\avk-alpha1 --manifest-sha256 $avkManifest
& $avkPython -I -S -B -X utf8 E:\tools\avk-alpha1\run.py doctor
```

先对照 SHA256SUMS 校验下载内容。Verify downloaded files against SHA256SUMS first.

## 文档 / Documentation

[中文 README](https://github.com/Tonscriptions/agent-video-kit/blob/v0.1.0-alpha.1/README.md) · [English README](https://github.com/Tonscriptions/agent-video-kit/blob/v0.1.0-alpha.1/README.en.md) · [Manual](https://github.com/Tonscriptions/agent-video-kit/blob/v0.1.0-alpha.1/docs/releases/v0.1.0-alpha.1/USAGE.md) · [Cases](https://github.com/Tonscriptions/agent-video-kit/blob/v0.1.0-alpha.1/docs/releases/v0.1.0-alpha.1/CASES.md) · [Skills](https://github.com/Tonscriptions/agent-video-kit/blob/v0.1.0-alpha.1/docs/releases/v0.1.0-alpha.1/SKILLS.md)

## 边界 / Boundaries

这是本地 CLI 的开发预览版，不宣称已达到完整剪映功能、素材生态或自然画质/听感等价。可选 AI 功能需要已有本地环境、权重和权利证据。截图与录制来自案例文档页；响应录制是实际日志回放，不是实时终端录像。

This preview does not establish full CapCut feature/ecosystem/perceptual equivalence. Optional AI adapters require existing local weights, runtimes and rights evidence. Screenshots/recording show the documentation page; the recording replays actual logs, not a live terminal. Natural-media playback/listening, HDR/ICC, long-form resources, other platforms/ABIs and universal draft compatibility remain open. R113/R114 and later experimental candidates are excluded.

Original code/docs are MIT; third-party components and media retain separate terms. No Docker, WSL or containers are required or used for this release.
