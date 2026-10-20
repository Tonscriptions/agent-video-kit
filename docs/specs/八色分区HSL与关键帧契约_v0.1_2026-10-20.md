# 八色分区 HSL 与关键帧契约 v0.1

V76 新增本地 `selective_hsl`，面向 Agent 可编辑工程。效果目录为 **0.8.0／46 项**。已有 `hsl` 保留原来的全局色相／饱和度语义；本功能提供八个色区的色相、饱和度、明度和最终强度。无需 GUI、在线请求、模型或 Python 逐帧视频进程。

<!-- V76-STATE -->
发行限定功能验收：完整原生回归 **1725/1725、2092.459 秒、0 跳过、225 冻结输入＋8 外部夹具前后相同**；17 Skills／302 本地引用，发行联接与正文均核对。性能未达到实时目标。
<!-- /V76-STATE -->

## 1. 可发现接口与参数

主名 `selective_hsl`；别名 `hsl_bands`、`eight_band_hsl`，连字符规范成下划线。`effects inspect selective_hsl` 和 `capabilities.effects.selective_hsl` 从实际规格生成参数和后端信息。后端引擎标识为 `encoded-rgb-eight-band-hsl-v1`；原来的 `numeric_effect_automation` 仍是 **10 类／34 个原生命令通道**，本功能另列 **25 个表达式通道**，不能伪报成 25 个 FFmpeg 运行时命令。

| 编号 | 色区前缀 | 原始色相中心（度） | 三个参数 |
|---|---|---|---|
| H76-01 | red | 0 | red_hue、red_saturation、red_lightness |
| H76-02 | orange | 30 | orange_hue、orange_saturation、orange_lightness |
| H76-03 | yellow | 60 | yellow_hue、yellow_saturation、yellow_lightness |
| H76-04 | green | 120 | green_hue、green_saturation、green_lightness |
| H76-05 | cyan | 180 | cyan_hue、cyan_saturation、cyan_lightness |
| H76-06 | blue | 240 | blue_hue、blue_saturation、blue_lightness |
| H76-07 | purple | 270 | purple_hue、purple_saturation、purple_lightness |
| H76-08 | magenta | 300 | magenta_hue、magenta_saturation、magenta_lightness |
| H76-09 | intensity | — | 最终 RGB 混合强度 |

`*_hue` 范围 −180..180 度；`*_saturation`、`*_lightness` 范围 −1..1；这 24 项默认均为 0。`intensity` 范围 0..1、默认 1。色区中心固定，不提供自定义宽度／羽化曲线。未知参数和未知动画通道明确拒绝；不静默忽略拼写错误。所有数字须有限、在范围内，拒绝布尔、字符串、NaN、无穷与无法安全表示的超大整数。

本轮修复通用效果验证的两处超大整数 `float()` 溢出和片段效果 Bezier 控制点检查；片段效果与区间效果现在返回结构化错误。没有把这一修复扩大成所有其他数值接口已验收的承诺。

## 2. 作者数据与时间

通过既有 `timeline compose` 的 `update_clip.patch.effects` 写入。例如 tps=90000、作者长度 180000 的片段：

```json
{
  "operations": [{
    "op": "update_clip",
    "clip_id": "picture",
    "patch": {"effects": [{
      "type": "selective_hsl",
      "parameters": {"red_hue": 0, "blue_saturation": -0.3, "intensity": 0.8},
      "keyframes": [{"property": "red_hue", "keyframes": [
        {"at_tick": 0, "value": 0, "interpolation": "linear"},
        {"at_tick": 90000, "value": 60, "interpolation": "linear"},
        {"at_tick": 180000, "value": 0, "interpolation": "linear"}
      ]}]
    }]}
  }]
}
```

效果顶层 `keyframes` 优先于 `parameters.keyframes`，支持既有属性前缀规范。相同通道的重复轨道、相同 tick、非递增／越界 tick、错误轨道结构和 Bezier 控制点均拒绝。`enabled:false` 沿用已有禁用语义。

全部 25 通道支持 hold、linear、ease_in、ease_out、ease_in_out、bezier；ease_in_out 是既有分段二次曲线，Bezier 沿用 **32 段近似**，不等于解析三次函数。表达式沿用作者时钟，把后端时间变量转为 `geq` 的帧 PTS `T`；动画求值后的越界值在表达式内钳位，不报告没有实测的钳位次数。

trim／split 保留完整作者相位；完整输出反转重排已栅格的子图帧。区间效果使用区间局部时间；直接祖先变速按现有作者时钟解释，不能把连续时间求值和已有栅格反转混为一谈。文字、嵌套、工程包和跨项目片段保留原始参数与作者轨道；目标项目重新构建派生表达式，缓存路径不是作者数据。

## 3. 数学与颜色语义

输入为 **8 位编码 RGB**；R/G/B 先除以 255。按标准 HSL 求原始 H、L=(max+min)/2、S=(max−min)/(1−abs(2L−1))；无色差时 S=0。色区权重由**原始色相**所在两个相邻中心之间的线性距离决定，环形连接 300→360/0，橙色／紫色色区采用其实际不等距中心。所有色区同时从该原始色相计算权重，不依次改变色相后重新选区。无彩色 S=0 时全部权重为 0，灰阶保持原样。

三个调整量分别按权重求和。色相加偏移后环绕到 0..360。对饱和度或明度 v，正偏移 d 使用 `v+(1-v)*d`，负偏移使用 `v*(1+d)`；限制到 0..1，再转换回 RGB。最后按 `intensity` 在该结果与输入编码 RGB 之间混合，最近整数舍入成 8 位；不是对 H/S/L 参数强度简单相乘。

采用本地 FFmpeg `geq` RGB 表达式，所有临时寄存器每个像素都先初始化；线程切片不共享隐含历史状态。Alpha 明确写成 `alpha(X,Y)`，逐字节保留进入该效果的覆盖，包括全透明像素的 Alpha；不承诺隐藏 RGB 不变。多实例依工程顺序执行，各阶段独立量化。

FFmpeg 的 `huesaturation` 是 HSI，不能用六色选择开关冒充八色 HSL。本实现没有这类语义替换，也没有 LUT 采样量化。`geq` 的时间、Alpha 和切片表达式规则见 [FFmpeg 官方文档](https://ffmpeg.org/ffmpeg-filters.html#geq)。独立像素参照使用 Python 标准库 `colorsys` 与相邻中心插值，没有复用产品表达式求值器。

## 4. 有界执行与可观测性

每个实际执行的实例最多 **64 KiB 表达式**，根图共用 **16 MiB 分色表达式**；与已有原生命令动画共享 **1,024 个执行实例和 2,000,000 个状态样本**。状态按实际 CFR 帧数乘作者动画轨道数计入，静态执行至少按一个通道计入。原生命令的命令数／文本预算、RGB 抠像的独立 Alpha 合成节点预算保留。

静态中性调整以及无强度动画的静态 intensity=0 精确旁路，记录 sampled_frames，但 instance=null、state_samples=0、kernel_bytes=0；即使其他实例已耗尽预算或作者区间很长，旁路也不消耗执行配额。动态零值轨道目前仍执行内核，已核验中性像素，但不承诺自动简化所有动态恒等表达式。

Manifest 记录 `kind=selective-hsl`、引擎、中心、静态参数、动画通道、颜色空间、选区／灰阶／Alpha／舍入策略、kernel SHA-256 与字节数、实例、帧数、状态样本、帧率、作者时钟、片段及区间。根预算摘要包含 selective_hsl_instances、selective_hsl_expression_bytes 和 effect_instances_total。超预算在执行前明确拒绝。

## 5. 验收边界

受控色带和随机 RGBA 的像素、Alpha、作者相位、包／片段重建、完整 PCM 与 PTS 是分开的验收项；MP4/GIF 为有损预览，精确判断使用 FFV1 RGBA／PCM。这里只核验本项目明确的 HSL 算法，没有复制或实测证明剪映的专有选区、肤色保护、色彩管理、HDR、自然素材视觉质量或实时性能。1080p CPU 探针保留实际执行成本，不把可导出写成可实时预览。

结果、原输入、4 组 MP4/GIF、历史失败和离线安装证据见 [实测报告](../validation/八色分区HSL与离线发行实测_2026-10-20.md)。完整剪映等价目标仍未验收。
