# 连续浮点 1D LUT 与组合 shaper 契约 v0.1

日期：2026-10-23。范围：独立候选；正式发布须经过当轮源码、真实公开 CLI、离线安装、完整回归和普通推送门禁。本文不代表已达到剪映效果等价。

## 1. 产品目的与入口

让 Agent 在现有可编辑时间线中复用本地调色表，不必先将 1D 调色或组合 shaper 烘焙为低位深视频。继续使用 `type: lut`（兼容 `lut3d/cube/look`）和原有 `render`、`preview range`、`preview frame`。只有明确选择 `settings.pixel_pipeline.engine = float32-native-v1` 的浮点路径获得本契约能力；旧编码渲染路径的能力保持独立说明。

两级处理顺序固定为：工作信号 → 声明的输入 RGB 信号 → 1D（若有）→ 3D（若有）→ 声明的输出 RGB 信号转换为工作信号 → 在线性工作 RGB 中混合 intensity。1D 和 3D 的阶段边界保留 Float32，不经过整数图像。

```json
{
  "type": "lut",
  "parameters": {
    "path": "assets/looks/original.cube",
    "input_signal": {"primaries": "bt709", "transfer": "linear"},
    "output_signal": {"primaries": "bt709", "transfer": "linear"},
    "interpolation_1d": "linear",
    "interpolation": "tetrahedral",
    "intensity": 0.8
  }
}
```

可用项目内路径，或以 `lut_id` 绑定本地注册库中的 SHA-256；两种绑定方式不能混用。不从文件猜测 RGB 原色、传递函数、HDR 峰值或模型。

## 2. 文件语义

| 编号 | 文件类型 | 样本排列 | 输入范围 |
|---|---|---|---|
| S01 | 独立 Iridas 1D CUBE | `LUT_1D_SIZE N` 后 N 行 RGB | 各通道 `DOMAIN_MIN/MAX`，默认 0–1 |
| S02 | 独立 Resolve 1D CUBE | N 行 RGB | `LUT_1D_INPUT_RANGE min max`，默认 0–1 |
| S03 | 独立 3D CUBE | N³ 行 RGB，R 最快、G 次之、B 最慢 | 原有 RGB DOMAIN，或 Resolve `LUT_3D_INPUT_RANGE` |
| S04 | Resolve 1D shaper + 3D | 先 N1D 行，再 N3D³ 行；两维尺寸头先声明 | 两级各自的 `LUT_*D_INPUT_RANGE`，默认各自 0–1 |

`DOMAIN` 与 `INPUT_RANGE` 混用，以及组合文件中的 `DOMAIN`，都拒绝，避免一个范围被解释为两个不同阶段。缺少对应维度的范围头、重复头、数据后的头、缺少或多余数据、未知扩展、非法编码、非有限数和倒序/零宽范围都拒绝。保留既有 BOM、引号标题和注释支持。

1D 的各通道独立执行 `(value - min) / (max - min)`，在输入坐标端夹取至 0–1，然后使用 Float32 网格坐标。支持不同通道的非零原点。明确区别于部分旧滤镜仅缩放、忽略 DOMAIN 原点的历史行为；这类差异不能声称逐字节等价。

## 3. 插值与自动化

`interpolation_1d` 默认 `linear`，允许 `nearest/linear/cosine/cubic/spline`。nearest 的半格选上一个索引；cubic 使用单位有限差分切线，spline 使用半切线。两种三次插值在边缘复制端点，允许过冲，结果不在 LUT 内裁剪。

`interpolation` 保留五种 3D 插值。纯 1D 文件没有 3D 阶段；`interpolation_1d` 显式用于纯 3D 文件会报错，避免悄悄忽略用户声明。文件维度由明确的尺寸头识别，不进行格式推测或运行时格式转换。

intensity 的 0–1 范围和六种原作者时钟插值沿用原有契约。零强度保留全部 RGB/alpha 位；任意强度保持输入 alpha 位，隐藏 RGB 独立参与调色。父子序列、展示窗口与剪辑后的强度仍按原作者时间采样。

## 4. 资源与失败边界

1D 每通道 2–65,536 点；3D 每轴 2–256 点。单文件最多 512 MiB，单行最多 4096 字节；表数据和冻结副本必须在分配前满足编译工作区预算。1D 与 3D 共用一个不可写字节载荷，缓存和渲染预算同时计入两个阶段，不漏算 shaper。

沿用最多 768 MiB 的算术工作区预算、有限像素和分块限制。预算是估算，并非进程峰值 RSS 验收。读取、分块、信号转换和进入第二阶段都检查取消。1D 输出一旦超出 Float32 有限范围，在访问 3D 索引之前明确失败。

表文件与注册库在编译后仍由依赖 SHA-256 绑定；正式发布前验证。预览缓存必须因 shaper 文件变化失效。输出诊断报告 `protocol=explicit-signal-float32-cube-lut-v2`、阶段列表、两级尺寸、范围、插值、工作信号和强度。

## 5. 验收与未覆盖项

必须实际检查五种 1D 的独立 Hermite 数学、原生 Float32 参照、25 个 1D/3D 插值组合、范围/边界、资源身份、预算、取消、原时钟和真实正式/预览/PNG16/PCM。可公开演示使用当轮原创数值 LUT、合成图像与合成音频，保留原片、结果、GIF、项目和版权记录。

本轮不包括 `.3dl/.csp/.dat`、非均匀采样 1D、逆 LUT、ICC、PQ/HLG/nits、色域映射、自然素材审美质量、长时 4K 性能或剪映等价。单帧 4K 准入与连续 4K 动画/峰值 RSS 验收分别记录。

## 6. 一手依据

格式语义参考 [OpenColorIO v2.4.2 ResolveCube](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/v2.4.2/src/OpenColorIO/fileformats/FileFormatResolveCube.cpp) 与 [IridasCube](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/v2.4.2/src/OpenColorIO/fileformats/FileFormatIridasCube.cpp)，均为 BSD-3-Clause。插值参照 [FFmpeg n8.1 lut1d/lut3d](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavfilter/vf_lut3d.c)，LGPL-2.1-or-later。原始参考快照、blob SHA、文件 SHA-256 与完整许可证保存在 [source-reference-r2](../validation/evidence/float-shaper-20261023-lab/source-reference-r2/verification.json)。本轮运行时使用自行表达的通道权重公式，不复制上游 C/C++ 运行时代码，也不增加运行时联网请求。
