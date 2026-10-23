# 连续浮点八色HSL与显式色域策略契约 v0.1

选择settings.pixel_pipeline.engine=float32-native-v1，公共render、preview range/frame共用原作者时间线和有序效果链。原有8位geq/frei0r工程保持原语义。默认后端迁移、其他浮点算子、自然素材和离线AI质量以及完整剪映功能仍需继续实现与验收。

## 参数与作者时间

类型selective_hsl/hsl_bands/eight_band_hsl。八色中心依次red=0、orange=30、yellow=60、green=120、cyan=180、blue=240、purple=270、magenta=300度。每色具有_hue[-180,180]、_saturation[-1,1]、_lightness[-1,1]，默认0；intensity[0,1]默认1。全部25通道可用同名keyframes编辑。参数均为有限JSON数值，布尔、字符串、非有限、越界、未知字段拒绝。

parameters.input_signal和output_signal须明确primaries/transfer，使用已有D65相对RGB信号集合；线性工作表面先转换到input_signal，HSL结果按output_signal解释再转回工作表面。颜色标签不能隐式选择transfer；无物理白点匹配、绝对nits、ICC、PQ/HLG或HDR感知承诺。

每轨1..1024键，总16384键、序列化4MiB；作者tick严格递增非负整数，采样支持非负有限实数、大整数和Fraction；关键帧不得超过原作者时长。支持linear/hold/ease_in/ease_out/ease_in_out/bezier；二控制Bezier直接取值，四控制Bezier先解时间根。父/子/倒放与presentation_window继续使用既有原作者时钟，不重置到预览起点。轨道可位于effect.keyframes或parameters.keyframes之一。

```json
{
  "type": "selective_hsl",
  "parameters": {
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "red_hue": 20, "orange_saturation": -0.2, "blue_lightness": 0.1,
    "intensity": 0.7, "input_gamut": "reject", "output_gamut": "preserve"
  },
  "keyframes": [{"property": "red_hue", "keyframes": [
    {"at_tick": 0, "value": -20, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 20, "interpolation": "linear"}
  ]}]
}
```

## HSL与分色

bounded RGB的max/min决定L=(max+min)/2，delta=max-min；非灰阶S=delta/(max+min)或delta/(2-max-min)，按L<=.5分支，灰阶S=0。H为标准RGB HSL色相。每色在相邻中心之间线性下降至0，左右宽度不同；原始色相同时决定全部权重，灰阶全部权重0，不对前一色调节后的色相重新选带。三个加权delta分别汇总。H按360度环绕；S和L在delta>=0时v+(1-v)delta，否则v(1+delta)，最后限制0..1并重建RGB。极暗色度不用1e-12地板；chroma=2min(L,1-L)S避免1-|2L-1|的消去。

## 显式色域与混合

input_gamut默认reject：算子输入信号的RGB超出0..1时拒绝，不加容差或偷偷量化。clip：先明确裁切到bounded RGB再调HSL。preserve_residual：B=clip(RGB,0,1)，在HSL(B)结果上加回RGB-B；这是可复现的创意扩展，不能称为HDR感知模型或专业色域映射。output_gamut默认preserve，明确clip时在算子输出域裁切。实际越界、裁切和残差分量计数写入效果收据。

最终强度混合在线性工作RGB执行source*(1-intensity)+graded*intensity。intensity=0在验证源表面后逐字节恒等，明确跳过HSL色域策略。相同输入/输出信号下未选色像素和灰阶保留原始RGB；显式输入或输出clip确实改变的像素仍按策略处理。alpha不参与HSL或强度运算，源alpha位级保留，包括signed-zero与有效次正规数。渲染合成和最终编码边缘沿用各自已有策略。

## 资源、取消与边界

连续H×W×4 Float32、边长1..16384、总像素<=16777216。请求tile_pixels为1..262144，实际每块<=16384。工作区估算=3×表面字节+保留LUT字节+每块像素×2048+4×轨道JSON字节+524288，不超过768MiB；这不是整个进程峰值RSS保证。先检查预算和整张表面的有限RGB/alpha范围，再分块处理；输入保持只读，晚块错误、取消及转换溢出不修改调用者数据或发布半成品。取消回调返回True或抛异常均会传播。

原始8位对照、新连续参考、公开CLI媒体、8-wheel隔离安装和完整2623项是独立门槛。未执行/运行中不记通过，不累计测试数作为剪映完成率。未验收自然画质、HDR、全套AI效果、长片RSS、连续播放/听审或完整剪映等价。
