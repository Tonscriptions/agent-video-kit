# 100 个离线风格预设 / 100 offline look presets

本地后续构建 `v0.1.0-alpha.2`，CLI `0.1.1`。该版本在首版闭环上增加 100 个有来源、MIT 许可、缩略图与稳定 ID 的预设；首次公开发布的 `alpha.1` 标签和附件保持原样。

This local follow-up build adds 100 attributable MIT creative looks. The public alpha.1 assets are immutable. Native Windows CPython 3.13 x64 and existing FFmpeg/ffprobe are required. Python, FFmpeg and AI weights are not bundled. No Docker, WSL, containers or virtual environments are used.

## 安装 / Install

先核对 `artifacts/SHA256SUMS.txt`。本仓库已有机器可执行以下命令；安装程序保留旧版目录并备份旧运行配置。其他位置可以解压发行 ZIP 后使用其 `bundle/install.py` 与 `version.json` 中的 manifest SHA。

```powershell
& C:/Python313/python.exe -E -B -X utf8 scripts/install_look_release.py --activate --evidence 'E:/dev/sandbox/AI广告剪辑/docs/validation/evidence/my-look-install'
```

The installer verifies the local release ZIP, installs into a new E: directory and, with `--activate`, backs up and switches runtime configuration. Existing installation targets are preserved. Skill pins must be updated with `scripts/update_agent_ffmpeg_local_skills.py` after a reviewed installation. A digest is an integrity check, not an author signature.

## 查询、预览、应用 / Discover, preview, apply

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list
& $avk look list --query '黑白'
& $avk look list --category cinema
& $avk look inspect --id t3-kodak-gold-200
& $avk look preview --id t3-kodak-gold-200 --input 'E:/media/frame.png' --output 'E:/media/gold-preview.png' --strength 0.65
& $avk look apply --project 'E:/video-work/ad' --id t3-kodak-gold-200 --clip-id clip_1 --strength 0.65 --dry-run
& $avk look apply --project 'E:/video-work/ad' --id t3-kodak-gold-200 --clip-id clip_1 --strength 0.65
& $avk preview frame --project 'E:/video-work/ad' --frame 0
& $avk render --project 'E:/video-work/ad' --output 'E:/video-work/ad/renders/gold.mp4'
```

没有 `--input` 时，`look preview` 使用随包合成测试卡。输出要求为新 PNG 文件。默认强度 1，范围为有限数值 0–1。`--clip-id` 需要已有视频轨片段；`--sequence-id` 选择其序列。`--global` 则作用于项目全局调整链，影响全部序列。两种目标必须明确选择一种。

Preview uses a bundled synthetic reference if no image is supplied; it writes a new PNG. Apply targets an existing video clip or the explicit project-wide `--global` adjustment chain. Strength is a finite value in 0–1. The default replaces existing built-in look effects at their first position and preserves manual effects; `--append` explicitly stacks looks. Reuse an `--idempotency-key` for retry safety. `--dry-run` writes no project LUT, registry or snapshot.

预设应用会先核对随包 LUT/许可哈希，复制到项目内 `assets/luts/` 和 `assets/look-evidence/`，登记项目 LUT 库和 Rights Ledger，保存编辑前快照并验证项目。再次应用会检查原有内容；已被修改的 LUT/许可不会被覆盖。项目包携带内置预设 ID、库登记、LUT、许可和相对证据路径。

Application copies verified LUT/license/provenance into the project, registers rights, snapshots and validates the edit. Modified project copies are refused and preserved. Built-in look IDs, their registry and relative license evidence survive project-package round trips. Render caches and copied asset files are not deleted by snapshot recovery.

## 色彩与使用边界 / Color and usage limits

这是创意 SDR encoded RGB 风格库。上游未完整声明输入/输出传递函数和基色，不能视为相机校准 LUT。`look apply` 首版明确拒绝 Float32、Log/HDR 项目；需先完成显式 SDR 转换。图片预览也要求事先准备好的 SDR 图片，不执行 ICC 或 Log/HDR 自动管理。

49 个 CUBE 保留上游网格，51 个 Hald 按原生位深读取后用四面体插值转换为 33³ CUBE。每个预设记录原始 SHA、网格、转换方式及 8,192 个 RGB 样本上的误差；采样误差不是全色域上界。Hald 转换属于近似，不承诺与原始 Hald 逐像素一致。部分强度在 encoded RGB 中与 identity LUT 混合，不是线性光混合。

These are creative SDR looks, not calibrated camera transforms. Float32/Log/HDR application is explicitly refused. Prepare SDR stills before preview; ICC/HDR management is not performed. Original CUBE grids are retained; dense Hald tables are resampled to 33³ with measured approximation. Each preset discloses an 8,192-sample error estimate, not a worst-case proof. Partial strength mixes the LUT with identity in encoded RGB.

本次增加的是色彩风格预设，不包含空间颗粒、光晕、美颜或 AI 特效。社区胶片名称不代表厂商背书，未提供“官方徕卡”或剪映专有滤镜包。不同自然素材仍需逐片调色与观看验收；合成测试卡的自动检查不能代替人像、风景、夜景及听感验收。

The library adds color looks. It does not establish proprietary filter parity, official Leica reproduction, spatial grain/bloom, beauty or AI effects. Synthetic automated tests do not replace review on natural footage or listening. See [catalog](../../local/LOOK_PRESETS.md), [third-party notices](THIRD_PARTY.md) and [validation](../../validation/LOOK_PRESETS_20261024.md).
