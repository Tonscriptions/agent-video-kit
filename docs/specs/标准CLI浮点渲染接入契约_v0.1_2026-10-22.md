# 标准 CLI 浮点渲染接入契约 v0.1

<!-- FLOAT-CUMULATIVE-DELIVERY-NOTE -->
> 合并交付说明：最终300输入已实际通过完整 **2355方法 /5277.023秒 /0跳过**。 以下保留该候选当时的分项、安装和失败记录；296/298输入早期快照未各自执行2320/2337项完整回归。当前验收以[合并实测](../../docs/validation/原片浮点渲染与预览合并交付实测_2026-10-22.md)及其实际收据为准。
<!-- /FLOAT-CUMULATIVE-DELIVERY-NOTE -->

本页约束 R96 候选。它把已实现的原始帧窗口、作者时钟与 Float32 合成接入既有 `render` 执行器，复用音频图、编码器、质量检查和任务记录。公开发布以完整回归与串行发布收据为准；独立原型、定向实测、安装验证和完整回归分别计数。完整剪映功能仍是产品目标，不由本契约限定的验收代替。

## 1. 显式选择

在 Agent Project 的 `settings.pixel_pipeline` 中设置：

```json
{
  "engine": "float32-native-v1",
  "working_signal": {"primaries": "bt709", "transfer": "linear"},
  "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
  "background_signal": {"primaries": "bt709", "transfer": "srgb"},
  "range_policy": "reject",
  "window_frames": 16,
  "max_source_cache_bytes": 268435456,
  "max_open_sources": 64,
  "native_timeout_seconds": 300,
  "sources": {
    "asset_video": {
      "source_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
      "display_geometry": "square-unrotated",
      "yuv_spec": {"matrix": "bt709", "range": "limited", "chroma_location": "left"},
      "scan": "progressive",
      "alpha_association": "straight"
    }
  }
}
```

示例资产 ID 必须对应实际登记的本地资产；信号和色度配置必须来自对原片的明确解释。RGB 源不填写 `yuv_spec`。输出 `settings.color` 的基色、传递函数、矩阵和范围必须与实际交付一致。`linear/srgb/bt709-oetf` 对应 `linear/iec61966-2-1/bt709` 标签。

源信号支持既有 D65 相对基色/传递函数，工作域要求线性光；当前正式交付边界要求 BT.709 基色。调用者声明不能替代 ICC、绝对亮度、PQ/HLG/HDR 或隔行转换。源已知非方形像素、显示矩阵或旋转会拒绝执行；未知 SAR 需要上述方形未旋转声明。未实现的操作明确失败。

## 2. 共用执行链

1. 公开 CLI 校验作者工程、本地策略、Schema 与权利账。
2. 原片 SHA 与实际探测绑定；原生 Windows 读句柄限制执行期间写入/删除。
3. 原始帧索引保留 PTS、time_base、容器起点和真实 EOF；视频窗口按需读取。
4. 作者时间映射在浮点宿主上逐帧取样，执行已有嵌套、变换、混合与受支持蒙版。
5. 音频使用独立的既有共同音频图，保留显式音轨及本地派生作业。
6. 相对 RGB 在 Float32 工作域合成；到最终整数交付边界才量化为 16-bit RGB。目标透明视频另将 alpha 明确量化为 8-bit 并扩展到 16-bit 传输平面。
7. 有界 stdin 队列送入既有标准编码器；RGB 使用显式 `zscale` 转为目标 YCbCr 矩阵/范围，alpha 独立合入。
8. 输出结构质量检查、输入复核后发布，保留命令、指纹、工具 SHA、源窗口与传输收据。

音频尾点为 `ceil(作者秒数 × 48000)`，视频帧数为 `ceil(作者秒数 × 输出帧率)`。不得通过相同的输出 `-t` 意外裁掉独立音频尾点。透明画面若实际 alpha 小于 1，不允许无提示丢弃到不透明输出；应设置不透明背景，或选已有 WebM/VPX 透明输出组合。

## 3. 范围与预算

| 编号 | 约束 |
|---|---|
| FSR-01 | 当前宿主支持既有精确作者时钟、原始 VFR hold、倒放、定格、速度映射、嵌套、变换关键帧、32 种混合模式、基础矩形/圆/椭圆蒙版；每种能力的真实组合以实测收据为准 |
| FSR-02 | 效果、转场、crop、字幕/生成器、跟踪绑定、蒙版羽化、部分关键帧属性等尚未连接此宿主时必须拒绝，不能默默套用旧 8-bit 中间路径 |
| FSR-03 | 窗口 1–256 帧；默认 16。总源缓存默认 256 MiB，上限 8 GiB，按源分摊且每源上限 256 MiB；不足一帧拒绝 |
| FSR-04 | 默认最多 64 个源，上限 256；单次原生操作默认 300 秒，上限 3600 秒。源信号表最多 4096 项 |
| FSR-05 | 投影/合成单次工作区受已有 sequence sampling 配额及 768 MiB 上限约束；这些配额不等于进程峰值 RSS 或并发总内存上限 |
| FSR-06 | 每次仅有自有编码进程、有限 stdin 缓冲与自有读写线程；成功、取消和失败均需关闭。不得结束无关任务或浏览器 |
| FSR-07 | 仍受既有原片探测大小/时长、索引和表达式边界限制；长 GOP seek 可能重解码前段，不保证倒放总成本线性 |
| FSR-08 | 硬件编码/解码、area 采样、全局调整与 HDR 色调映射尚未连接时明确拒绝；默认渲染迁移、preview/cache 全面统一另行验收 |

## 4. 真实核验与尚缺验收

见[标准 CLI 浮点交付实测](../validation/标准CLI浮点交付实测_2026-10-22.md)。首次失败和独立色彩/alpha 边界观察均需保留。灰阶码值、alpha、逐采样 PCM、队列/续跑和资源清理分别证明对应行为，不代替自然画面观感、听感、长片性能、HDR 或完整剪映等价验收。
