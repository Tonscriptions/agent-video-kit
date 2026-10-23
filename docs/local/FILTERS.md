# 滤镜与风格库 / Filters and looks

当前本机版本为 **`v0.1.0-alpha.2`，CLI `0.1.1`**。已内置 **100 个离线 MIT 风格预设**，分别有稳定 ID、独立 LUT、预览、锁定来源与许可；17 个 `$agent-ffmpeg-local-` Skills 已绑定新安装版。
The current local build includes 100 offline MIT creative looks and updated Skills. [完整编号目录 / Full catalog](LOOK_PRESETS.md) · [新使用逻辑 / Usage](../releases/v0.1.0-alpha.2/USAGE.md) · [本轮核验 / Verification](../validation/LOOK_PRESETS_20261024.md).

| 类别 / Category | 数量 / Count |
|---|---:|
| 黑白胶片 / B&W film | 12 |
| 彩色负片 / Negative film | 24 |
| 反转片 / Slide film | 15 |
| 电影年代 / Cinema eras | 8 |
| 风景 / Landscape | 10 |
| 创意色彩 / Creative | 24 |
| Lomo | 5 |
| 红外 / Infrared | 2 |
| **合计 / Total** | **100** |

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list --query '黑白'
& $avk look inspect --id t3-kodak-gold-200
& $avk look preview --id t3-kodak-gold-200 --output 'E:/video-work/gold.png'
& $avk look apply --project 'E:/video-work/ad' --id t3-kodak-gold-200 --global --strength 0.65
```

![真实原图与预设对比 / Actual comparisons](../assets/look-presets-20261024-r1/comparison.gif)

`look apply` 首版用于默认 FFmpeg 的 SDR encoded RGB 管线。Float32、Log/HDR 明确拒绝；已有底层 LUT/Float32 功能仍按各自契约使用。49 个 CUBE 保留上游网格，51 个原生 RGB8 Hald 转换为 33³ CUBE，目录披露采样误差。默认替换同一作用域内的内置预设并保留手工效果；`--append` 为显式叠加。许可与来源被复制进项目，内置预设支持包往返。
Apply supports the default SDR FFmpeg pipeline, with explicit refusal for Float32/Log/HDR. CUBE grids are retained; dense RGB8 Hald data is resampled with measured approximation. Replace is the default; append is explicit. Portable LUT/license/provenance records accompany the project.

本次新增的是色彩风格库；46 项基础处理算子是另一种计数。未提供官方徕卡或剪映专属滤镜，不宣称品牌算法/自然画质等价。原始 `alpha.1` 安装包的 LUT 库存为 0 是[历史核对结果](../validation/evidence/filter-library-20261024-r1/inventory.json)，不再代表本机当前库存。
The 100 looks are separate from the 46 processing operators. No official Leica/proprietary CapCut pack or perceptual parity is claimed. The earlier zero-LUT alpha.1 inventory remains dated evidence.

## 格式与渲染路径边界 / Format and renderer boundaries

- 默认 FFmpeg 路径的 `lut3d` 主要用于 3D LUT。静态部分强度需完整 3D `.cube`；动态强度使用 8-bit 编码 RGB 混合。非 `.cube` 的元数据只记录扩展名，不能宣称全部格式均支持同等强度处理。
  The default path uses 3D LUTs. Static partial strength requires a complete 3D CUBE; dynamic mixing uses encoded 8-bit RGB. Non-CUBE formats have limited metadata and strength support.
- 显式 `float32-native-v1` 路径支持完整 `.cube` 的独立 1D、3D，以及 1D shaper 后接 3D。需要按 schema 声明色彩信号、域与预算；该路径不读取 `.3dl/.csp/.dat`，也不会让默认路径自动获得 1D 支持。
  The explicit Float32 path supports complete 1D/3D/combined CUBE tables with declared signal/domain/budget settings, not the other registration formats. This does not extend default-renderer 1D support.
- 内置效果目录、LUT 登记器和 Float32 能力契约是三个不同层级。当前 `lut_library` 部分旧限制字段仍写静态强度；动态能力应结合 `effects inspect --name lut3d`、`effects.numeric_effect_automation` 和所选渲染路径核对。
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
& $avk effects inspect --name lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
# Use the returned lut_id in a supported timeline effect. Inspect the schema/edit command before authoring JSON.
```

登记后还需把 `lut_id` 或项目内路径写入时间线的 LUT 效果，再执行预览与渲染；单纯登记文件不会改变画面。商业输出需补全实际许可和权利证据。
Registration alone does not apply the look: add the LUT effect to the timeline, then preview/render. Complete actual provenance and rights evidence before publication.

## 首版历史核对证据 / Historical alpha.1 evidence

- [本轮目录与 CLI 帮助核对 / Current capability check](../validation/evidence/filter-capabilities-20261024-r1/verification.json)、[效果原始响应 / Effect response](../validation/evidence/filter-capabilities-20261024-r1/effects.stdout.txt)、[格式与命令帮助 / Registration help](../validation/evidence/filter-capabilities-20261024-r1/lut-register-help.stdout.txt)。本轮仅查询和代码核对，未新渲染 / Catalog/help and source review only, no new render.
- [既有安装版 Float32/1D shaper 实测 / Dated installed-render evidence](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json)：[原输入](../assets/float-shaper-20261023-installed-r1/original.mp4)、[实际输出](../assets/float-shaper-20261023-installed-r1/edited.mp4)、[对照 GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif)。历史实测不计作本轮新增 / Historical media is not counted as a new run.
- [本地安装与 17 个 Skill / Installation and Skill catalog](INSTALLATION.md)、[发行版使用手册 / Release manual](../releases/v0.1.0-alpha.1/USAGE.md)。
