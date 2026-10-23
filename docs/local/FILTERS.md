# 滤镜、LUT 与调色 / Filters, LUTs and grading

核对日期 / Checked: **2026-10-24**。已安装版本 / Installed release: **`v0.1.0-alpha.1`**。

**已包含加载本地 LUT、内置风格效果、基础调色、效果叠加及部分参数关键帧。** 已安装 CLI 的 `effects list` 返回 **46 项效果**，包括调色、模糊、修复、运动和变换；这不代表 46 套独立风格预设。
The installed release supports local LUT loading, built-in effects, grading, ordered effects and selected animated parameters. Its 46-entry catalog spans multiple effect categories, rather than 46 distinct looks.

| # | 能力 / Capability | 支持情况 / Support |
|---|---|---|
| FL01 | 加载外部 LUT / External LUTs | `lut register` 复制到工程、生成稳定 `lut_id`，记录 SHA-256、来源和许可 / Copies into the project with stable ID and provenance |
| FL02 | 格式 / Registration formats | `.cube`、`.3dl`、`.csp`、`.dat`；登记支持不代表各渲染路径和强度处理等价 / Registration does not imply equal render/strength support |
| FL03 | 风格滤镜 / Looks | 黑白、复古棕、颗粒、暗角、反相、色阶分离等 / Grayscale, sepia, grain, vignette, inversion, posterization |
| FL04 | 调色 / Grading | 亮度、曝光、对比度、饱和度、色相、Gamma、色温、色彩平衡、色轮、RGB 曲线、八色 HSL / Brightness, exposure, contrast, saturation, hue, gamma, temperature, balance, wheels, curves and eight-band HSL |
| FL05 | 效果叠加与范围 / Order and scope | 片段效果，以及合成后的顺序调节；可指定序列时间区间 / Clip effects and ordered post-composite adjustments with optional sequence intervals |
| FL06 | 强度与关键帧 / Strength and animation | `lut3d` 的 `intensity` 为 `0..1`，可关键帧；其他效果以各自公布参数为准 / LUT intensity and advertised per-effect parameters |
| FL07 | 预览与导出 / Preview and output | 效果进入预览、渲染和可编辑工程；实际输出仍需质量核验 / Effects feed preview, render and editable projects; verify actual outputs |

## 格式与渲染路径边界 / Format and renderer boundaries

- 默认 FFmpeg 路径的 `lut3d` 主要用于 3D LUT。静态部分强度需完整 3D `.cube`；动态强度使用 8-bit 编码 RGB 混合。非 `.cube` 的元数据只记录扩展名，不能宣称全部格式均支持同等强度处理。
  The default path uses 3D LUTs. Static partial strength requires a complete 3D CUBE; dynamic mixing uses encoded 8-bit RGB. Non-CUBE formats have limited metadata and strength support.
- 显式 `float32-native-v1` 路径支持完整 `.cube` 的独立 1D、3D，以及 1D shaper 后接 3D。需要按 schema 声明色彩信号、域与预算；该路径不读取 `.3dl/.csp/.dat`，也不会让默认路径自动获得 1D 支持。
  The explicit Float32 path supports complete 1D/3D/combined CUBE tables with declared signal/domain/budget settings, not the other registration formats. This does not extend default-renderer 1D support.
- 内置效果目录、LUT 登记器和 Float32 能力契约是三个不同层级。当前 `lut_library` 部分旧限制字段仍写静态强度；动态能力应结合 `effects inspect lut3d`、`effects.numeric_effect_automation` 和所选渲染路径核对。
  The registry and renderer contracts have distinct scopes. Some older registry limit fields describe static handling; inspect the effect automation contract and selected renderer for dynamic behavior.
- 当前没有剪映专有滤镜包的直接兼容加载器，也没有随基础包提供在线滤镜商店或完整商业风格库。可使用自己拥有相应使用权的本地标准 LUT；任意第三方插件并不自动兼容。
  Proprietary CapCut packs, a commercial look store and arbitrary third-party plugins are not supported package formats. Use compatible local LUTs with appropriate rights evidence.

## Agent 使用 / Agent workflow

```text
$agent-ffmpeg-local-editor 给本地视频加载我提供的 .cube LUT，
将强度设为 0.6，先生成对照预览，再输出成片。
```

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk effects list
& $avk effects inspect lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
# Use the returned lut_id in a supported timeline effect. Inspect the schema/edit command before authoring JSON.
```

登记后还需把 `lut_id` 或项目内路径写入时间线的 LUT 效果，再执行预览与渲染；单纯登记文件不会改变画面。商业输出需补全实际许可和权利证据。
Registration alone does not apply the look: add the LUT effect to the timeline, then preview/render. Complete actual provenance and rights evidence before publication.

## 核对证据 / Evidence

- [本轮目录与 CLI 帮助核对 / Current capability check](../validation/evidence/filter-capabilities-20261024-r1/verification.json)、[效果原始响应 / Effect response](../validation/evidence/filter-capabilities-20261024-r1/effects.stdout.txt)、[格式与命令帮助 / Registration help](../validation/evidence/filter-capabilities-20261024-r1/lut-register-help.stdout.txt)。本轮仅查询和代码核对，未新渲染 / Catalog/help and source review only, no new render.
- [既有安装版 Float32/1D shaper 实测 / Dated installed-render evidence](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json)：[原输入](../assets/float-shaper-20261023-installed-r1/original.mp4)、[实际输出](../assets/float-shaper-20261023-installed-r1/edited.mp4)、[对照 GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif)。历史实测不计作本轮新增 / Historical media is not counted as a new run.
- [本地安装与 17 个 Skill / Installation and Skill catalog](INSTALLATION.md)、[发行版使用手册 / Release manual](../releases/v0.1.0-alpha.1/USAGE.md)。
