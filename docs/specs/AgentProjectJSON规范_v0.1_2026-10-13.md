# Agent Project JSON 规范 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-PROJECT-001 |
| 状态 | 评审中 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-13 |
| 关联需求 | PRD-001、PRD-003、PRD-004、PRD-006 |
| 关联基线 | [产品需求与开发路线基线](../产品需求与开发路线基线_2026-10-12.md) |

本文档定义 Agent-first 视频项目的规范主格式。它是独立于 Concat、Shotcut、Kdenlive、FFmpeg 或任何 GUI 的领域模型。外部格式通过适配器映射到本格式；适配器必须同时生成转换报告。

对应的最小机器可校验文件是 [agent-project.schema.json](./agent-project.schema.json)。JSON Schema 负责结构、类型和基础枚举；时间范围、跨对象引用、许可证和轨道重叠等语义校验仍由项目 validator 执行。

## 1. 规范用语与版本

- **MUST**：实现必须满足，否则项目文件无效。
- **SHOULD**：默认满足；若不能满足，必须在项目警告和转换报告中说明。
- **MAY**：可选扩展，不得破坏未知字段的保留。
- `schema_version` 使用 SemVer。补丁版本只修正文档或校验错误；次版本增加向后兼容字段；主版本改变语义或删除字段。
- 解析器 MUST 保留未知字段到 `extensions` 或原始包中，不能静默丢弃。

## 2. 顶层对象

```json
{
  "schema_version": "0.1.0",
  "project": {
    "id": "proj_demo_001",
    "name": "demo-ad",
    "created_at": "2026-10-13T00:00:00Z",
    "updated_at": "2026-10-13T00:00:00Z",
    "creator": "ai-ad-editor",
    "source_revision": "local"
  },
  "settings": {
    "timebase": {"ticks_per_second": 90000, "display_fps": {"num": 30, "den": 1}},
    "canvas": {"width": 1080, "height": 1920, "pixel_aspect": {"num": 1, "den": 1}},
    "color": {"primaries": "bt709", "transfer": "bt709", "matrix": "bt709", "range": "limited"},
    "output": {"container": "mp4", "video": {"codec": "libx264", "preset": "medium", "crf": 18, "pixel_format": "yuv420p"}, "audio": {"codec": "aac", "bitrate": "192k"}}
  },
  "assets": [],
  "sequences": [],
  "templates": [],
  "outputs": [],
  "provenance": {}
}
```

顶层必须包含 `schema_version`、`project`、`settings`、`assets`、`sequences` 和 `provenance`。所有 ID 在项目内唯一，并使用稳定字符串；禁止把数组下标当作持久 ID。

## 3. 时间与坐标

1. 内部时间 MUST 使用整数 tick。推荐 `ticks_per_second = 90000`；项目可以选择其他值，但全项目只能有一个时间基准。
2. `start_tick`、`duration_tick`、`source_in_tick` 和 `source_out_tick` MUST 为非负整数；`duration_tick` 必须大于 0，除非对象明确允许零时长标记。
3. 显示用帧率允许分数，例如 30000/1001。帧号、时间码和浮点秒数只能作为输入输出表示，不能参与核心比较。
4. 画布坐标使用左上角原点，归一化值范围为 0 到 1；旋转单位为角度，缩放 1.0 表示原始大小。
5. 所有变换必须声明作用顺序。默认顺序为 anchor → scale → rotation → translation → crop → opacity。

## 4. 资产对象

每个 `assets[]` 至少包含：

| 字段 | 必须 | 说明 |
|---|---|---|
| `id` | 是 | 稳定资产 ID |
| `kind` | 是 | `video`、`image`、`audio`、`font`、`subtitle`、`effect` 或 `model` |
| `uri` | 是 | 本地绝对路径、项目相对路径或内容寻址 URI；禁止未经声明的网络 URL |
| `sha256` | 是 | 文件内容哈希；大型代理文件可另外记录 `proxy_sha256` |
| `probe` | 是 | 时长、编码、流、分辨率、帧率、色彩和音频采样信息 |
| `rights_ref` | 是 | 指向 Rights Ledger 的记录 ID；测试素材也必须有记录 |
| `proxy` | 否 | 代理关系、生成参数和可替换状态 |
| `source` | 否 | 来源 URL、下载日期、原始文件名和归档位置 |

导入阶段可以暂时使用 `rights_ref = pending:<id>`，但 `render --publish` 和 `convert --publish` MUST 拒绝未验证记录。

## 5. 序列、轨道与片段

`sequences[]` 至少包含 `id`、`name`、`duration_tick`、`tracks[]` 和 `markers[]`。轨道包含：

| 字段 | 说明 |
|---|---|
| `id` | 稳定轨道 ID |
| `kind` | `video`、`audio`、`subtitle`、`data` |
| `order` | 从后向前的合成顺序；值越大越靠前 |
| `muted`、`locked` | 编排和渲染行为 |
| `clips[]` | 片段、生成层或嵌套序列引用 |

片段至少包含 `id`、`asset_id` 或 `sequence_id`、`timeline_start_tick`、`duration_tick`、`source_in_tick`、`source_out_tick`。可选 `crop` 使用 `pixels`/`normalized`/`relative` 单位和 `fit`/`fill`/`stretch` 模式；其坐标与尺寸必须是有限非负数，归一化值不得超过 1。`crop.keyframes` 可以驱动 `x`/`y`/`width`/`height`，或在片段级关键帧中使用 `crop.x`/`crop.y`/`crop.width`/`crop.height`；动态尺寸使用 CPU `geq` 固定画布逆向采样保持输出帧尺寸稳定，并以 `fit`/`fill`/`stretch` 规则计算窗口，宽高关键帧仍必须大于 0。必须满足：

- 源出点大于源入点，且不能超过资产可用时长；
- 同一轨道中片段重叠必须显式声明 `overlap_policy`，不能依赖数组顺序猜测；
- 视频片段的画布、变换和效果继承关系必须可计算；
- 音频片段必须声明声道、采样率或让探测器补齐，并记录静音/ducking 包络；
- 嵌套序列必须声明父子关系和循环检测结果，禁止递归环。

## 6. 关键帧、效果与转场

关键帧对象使用：

```json
{
  "property": "transform.position.x",
  "keyframes": [
    {"at_tick": 0, "value": 0.5, "interpolation": "linear"},
    {"at_tick": 45000, "value": 0.62, "interpolation": "ease_in_out"}
  ],
  "default_value": 0.5
}
```

`at_tick` 是片段内时间，不能混用源媒体时间和序列时间。允许的插值包括 `hold`、`linear`、`ease_in`、`ease_out`、`ease_in_out` 和 `bezier`。Bezier 必须携带有限数字控制点：`[y1, y2]` 表示两个纵向控制值，或 `[x1, y1, x2, y2]` 表示归一化 cubic 控制点，其中 `x1/x2` 必须位于 `0..1`；参数错误必须在写入或渲染前拒绝。

效果和转场必须含 `type`、`version`、`parameters`、`scope`、`enabled` 和 `source`。外部或社区效果需要 `package_id`、依赖版本和许可证引用；无法解析依赖时必须进入 `Unsupported` 或 `Failed`。效果对象可以额外声明 `keyframes`，每条轨道的 `property` 使用效果参数名或 `effect.<parameter>` 命名，`at_tick` 仍相对于片段局部时间。当前本地 FFmpeg 后端对 brightness/contrast/saturation、hue、gamma 和 vignette 使用 `eval=frame` 逐帧执行；其他效果参数关键帧会保留并在渲染报告中标记为静态近似，不得静默伪装成逐帧效果。

本地效果的规范 ID、别名、FFmpeg 后端和参数范围以 CLI `effects list`/`effects inspect` 的目录版本 `0.2.0` 为准。目录当前包含 41 项 `source=ffmpeg-local` 效果，新增原生滤镜包括 `exposure`、`color_levels`、`curves`、`hqdn3d`、`smartblur`、`avgblur`、`tmix`、`tblend`、`lens_correction`、`draw_box`、`color_contrast`、`solarize`、`threshold`、`deflicker` 和 `dctdnoiz`。参数必须使用目录声明的类型和范围；`curves` 的 `all/master` 只允许空格分隔的 `0..1` 范围 `x/y` 点，`draw_box.color` 只允许安全颜色 token。未知效果仍在验证或渲染阶段进入 `RENDER_FEATURE_UNSUPPORTED`，本地目录不引入网络、插件下载或闭源运行时。

本地 FFmpeg 转场目录通过 `crossfade`/`dissolve`、方向 `wipe`/`slide` 和 `circlecrop`、`radial`、`pixelize`、`zoomin`、`cover*`、`reveal*`、`slice`、`wind`、`blur`、`fadeblack` 等 xfade 类型执行。复杂转场默认需要相邻片段的重叠句柄；若两个片段严格相邻，可在转场对象中设置 `auto_handle: true` 或 `handle_policy: "auto"`，由本地渲染器执行并保持原时长，尾部最后一帧填充会写入 `RENDER_FEATURE_APPROXIMATE`。其他缺少句柄的情况保留项目并返回结构化近似/不支持警告。

`settings.adjustments` 是所有导出序列共用的调节栈。每项可以直接是效果对象，也可以是 `{id, enabled, effects[]}`；渲染器在完成所有视频轨道、转场、遮罩和混合后按数组顺序执行。效果参数关键帧的 `at_tick` 相对于当前调节层的局部时钟；省略 `start_tick`/`duration_tick` 时覆盖整个导出序列，也可以用 `start_tick` 与 `duration_tick` 声明序列时钟区间。区间层在本地视频链上执行 trim、效果和 concat，音频不被调节层修改；区间必须位于序列时长内。调节层复用片段效果的参数关键帧与近似警告；`enabled=false` 跳过对应层或效果。

效果 `type` 为 `lut`/`lut3d`/`cube`/`look` 时，可以使用项目内路径 `parameters.path`（兼容 `file`/`lut`），也可以使用 `parameters.lut_id` 引用 `lut register` 登记的项目 LUT。两种形式都必须落在项目根目录内已存在的 `.cube`、`.3dl`、`.csp` 或 `.dat` 文件；`lut_id` 还会复核清单中的 SHA-256。运行时只调用本地 FFmpeg `lut3d`，禁止网络 URL、项目外路径和缺失文件。`parameters.interpolation` 可选 `nearest`、`trilinear`、`tetrahedral`、`pyramid` 或 `prism`，默认 `tetrahedral`；可选 `parameters.intensity` 为 `0..1` 的有限数字，默认 `1`。`.cube` 的静态部分强度会由源 LUT 与 identity 表生成项目内 `cache/luts/` 派生表，`0` 为精确跳过；`.3dl/.csp/.dat` 部分强度和强度关键帧保留结构化降级。预览缓存、HDR LUT 色域转换仍属于后续版本；项目 LUT 登记契约见 [本地 LUT 资产库与效果引用契约](./本地LUT资产库与效果引用契约_v0.1_2026-10-15.md)。

片段级 `mask` 使用归一化参数，当前支持 `rectangle`（`x/y/width/height`）、`circle`（`cx/cy/radius`）、`ellipse`（`cx/cy/rx/ry`）和 `path/polygon`；rectangle/circle/ellipse 的位置、尺寸和 `feather` 可通过 `mask.*` 关键帧驱动，动态羽化使用 alpha-only 软边表达式，`feather` 限制在 0 到 0.5；path/polygon 可以保持固定点数，点坐标可用 `mask.points.0.x`、`mask.points.0.y` 这类片段关键帧或 mask 内局部关键帧驱动，点坐标限制在 0 到 1，动态 `feather` 也可由关键帧驱动，使用固定点边缘的内侧距离近似生成 alpha 软边；静态 `segments`/`curve_segments`/`curves` 可声明 `line` 或 `cubic` 段，cubic 的 `samples` 限制在 2 到 16，总采样点限制在 3 到 32，渲染器将其采样为固定多边形。曲线段不能与 `points` 同时声明，曲线段逐点动画和 GUI 路径编辑器仍未提供。片段级 `blend` 使用 `mode` 与可选 `opacity`，`blend.opacity` 和 `transform.opacity` 可通过片段关键帧驱动；混合模式必须属于本地能力清单，未知模式在验证阶段拒绝。

固定点数路径的最小关键帧形状如下；`points.N.*` 的 `N` 必须与初始 `points` 数组对应，不能在时间轴中增删点：

```json
{
  "mask": {
    "type": "polygon",
    "points": [[0.10, 0.20], [0.40, 0.20], [0.25, 0.80]],
    "keyframes": [
      {"property": "points.0.x", "keyframes": [{"at_tick": 0, "value": 0.10, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.60, "interpolation": "linear"}]}
    ]
  }
}
```

## 7. 字幕、音频与模板

- 字幕 cue 使用整数 tick，含 `text`、`language`、`style_ref`、`speaker`、`word_timing`（可选）和 `source_ref`。
- `kind=subtitle` 轨道可以使用 `generator: {"type": "text"}` 加内联 `subtitle.text/style`，不需要占位媒体资产；它与 `asset_id`、`sequence_id` 互斥。渲染器会把文字先绘制到本地透明层，独立文字轨道的 `rotate` 动画执行实际像素旋转；片段 transform/keyframes、mask 和 blend 也作用于该透明层，并按 `track.order` 与视频轨道共同排序合成；序列无视频片段时使用黑/透明基础画布输出纯文字序列。已登记的 `subtitle` 资产仍可作为外部字幕文件引用。
- 内联 `subtitle.style` 可声明 `fontsize`、`fontcolor`、`fontfile`、`line_spacing`、`borderw`/`bordercolor`、`shadowx`/`shadowy`/`shadowcolor`、`box`/`boxcolor`/`boxborderw`、`text_align`、`text_shaping`、`fix_bounds`、`expansion` 以及 `max_width`/`wrap_width`。`max_width` 优先使用本地字体 advance width 换行，没有字体度量时才使用平均字宽并写入 approximate warning；复杂排版和逐字遮罩仍需 golden render 验收。文本样式必须引用字体资产和回退链；发布前检查字体许可证与机器可用性。
- `style.font_asset_id` 必须引用本地 `font` 资产；显式 `style.fontfile` 必须是存在的本地文件。若有本地字体度量，换行和逐字定位使用其 advance width；没有字体度量时才回退平均字宽并写入 warning。`word_timing` 可以使用 `start_char` 消除重复词歧义，源文本不匹配时拒绝保存或渲染。
- 片段的 `freeze` 对象由 `at_tick` 和正数 `duration_tick` 组成，可选 `audio_mode` 为 `silence` 或 `continue`。`at_tick` 位于冻结前的片段时长内，保存时片段 `duration_tick` 已包含冻结增量；渲染在变速/倒放/裁切映射完成后插入冻结帧。默认 `audio_mode=silence` 会在同一局部时间点插入等长的本地静音，使音频和画面同步停顿；`continue` 保留视频冻结而让音频继续播放，并在尾部补齐冻结增量。非法定格对象、模式或越界时间必须在语义校验阶段拒绝。
- 音量、声像、滤波器和 side-chain 使用与画面关键帧相同的 tick 规则；`audio.pan`/`pan` 取值为 `-1..1`，表示左到右的声像自动化，也可保留受控的 raw FFmpeg pan 表达式。数值声像对单声道输入执行立体声复制后再平衡，对立体声输入保留左右通道的独立内容。
- 模板只存放结构和变量声明；每个变量必须有类型、是否必填、默认值、约束和来源。
- 模板实例化后必须写入 `provenance.template_id`、版本、变量快照和生成时间。

## 8. 输出与来源追踪

`settings.output` 记录默认容器和编码策略；当前本地后端允许 `mp4`、`webm`、`mkv`，以及本机 FFmpeg 可用的视频/音频编码器。视频像素格式支持 `yuv420p`、`yuv422p`、`yuv444p` 及对应的 `10-bit` little-endian 变体；透明交付额外支持 `yuva420p`，但只允许 WebM + VP9/VP8。最终是否可编码取决于本机 FFmpeg 编码器和容器。`settings.color` 的 `primaries`、`transfer`、`matrix`、`range` 会显式传递给 FFmpeg，支持 bt709 基线及 bt2020/PQ/HLG 等 HDR 元数据值；显式设置 `tone_map`（`linear`/`gamma`/`clip`/`reinhard`/`hable`/`mobius`）时，视频输入按 `input_transfer`、`input_primaries`、`input_matrix`、`input_range` 经过本地 `zscale + tonemap` 转到 bt709，透明画布与 tone map 组合会被拒绝为近似能力。该链路仍不等价于已经完成 HDR 显示、代理和跨设备色彩一致性验收。`outputs[]` 记录实际容器、编码器、分辨率、帧率、像素格式、音频规格、目标平台、输出路径和质量门禁引用。`provenance` 至少记录：

批量输出的队列状态不写入 `project.json` 核心 schema，而是保存为项目运行产物 `operations/render-queue.json`；其中的 `job_id`、作业状态、尝试次数、取消标记、错误、警告和关联操作 ID 由 [本地渲染队列契约](./本地渲染队列与任务状态契约_v0.1_2026-10-14.md) 管理。队列作业引用本规范中的序列、资产、输出和权利语义，成功后仍通过 `outputs[]` 和 `provenance.change_log` 登记实际成片。

- 工具版本、引擎版本、模型版本和运行平台；
- 输入资产哈希、项目文件哈希、命令参数和随机种子；
- 人工确认点、Agent 请求 ID、变更列表和失败重试；
- 生成的渲染清单、验证报告、转换报告和 Rights Ledger 快照。

## 9. 校验与迁移

加载顺序为：JSON 语法 → schema 版本 → ID/引用完整性 → 时间范围 → 轨道约束 → 资产/权利 → 外部依赖 → 输出规格。每一层返回结构化错误位置，例如 `sequences[0].tracks[2].clips[1].source_out_tick`。

迁移器必须是纯函数：输入版本、输出版本和变更说明固定；`project migrate` 会在旧项目写入前创建 `before-migrate` 快照，在 provenance 中记录迁移链，并将候选项目通过 schema/语义校验后才原子保存。不得在普通加载项目时偷偷改写原文件；无法定位资产或遇到高于当前版本的 schema 时必须拒绝迁移。

## 10. 最小有效性判定

项目只有同时满足以下条件才是 `valid`：

1. 顶层必填字段、ID 和 schema 版本有效；
2. 所有片段和效果引用可解析，所有资产可定位；
3. 时间与轨道约束通过，关键帧单调递增；
4. 所有资产有 Rights Ledger 引用，发布目标所需的许可证检查通过；
5. 输出规格与项目色彩、音频和画布设置兼容；
6. 外部扩展即使未被当前引擎支持，也被保存在原始包或 `extensions` 中。


