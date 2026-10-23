# 浮点RGBA色阶与动态曝光契约 v0.1

选择`settings.pixel_pipeline.engine=float32-native-v1`；公共`render`、`preview frame/range`共用原作者时间线。正式输出仍执行工程交付范围策略。默认后端尚未迁移，其他算子、离线AI质量与完整剪映功能继续开发。

## 作者数据

色阶type为color_levels/levels/colorlevels；parameters须明确input_signal/output_signal的primaries/transfer，转换使用现有相对D65模型，共同工作信号须为linear。共享RGB端点input_black/input_white范围[-1,1]，output_black/output_white范围[0,1]，默认0/1/0/1。独立red_/green_/blue_/alpha_加上述端点名覆盖各自通道，允许反向输入或输出范围。共享RGB不会改变alpha。

旧rimin/rimax/romin/romax作者别名继续广播RGB；独立红色使用red_input_black等规范名。gimin/gimax/gomin/gomax、bimin/bimax/bomin/bomax、aimin/aimax/aomin/aomax分别为对应独立通道别名。重复别名数值不同拒绝；重复关键帧别名即使值相同也拒绝。

```json
{
  "type": "color_levels",
  "parameters": {
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "input_black": 0,
    "input_white": 1,
    "output_black": 0.03125,
    "output_white": 0.9375,
    "red_output_white": 0.875,
    "alpha_output_white": 0.9,
    "preserve": "lum",
    "intensity": 0.75,
    "zero_span": "reject"
  },
  "keyframes": [{"property": "red_output_white", "keyframes": [
    {"at_tick": 0, "value": 0.75, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 0.9375, "interpolation": "linear"}
  ]}]
}
```

## 自动端点、计算与保留模式

任何负输入端点表示按该通道完整输入表面自动检测，含透明像素隐藏RGB。最小值从1、最大值从0开始；统计基于输入信号转换后的Float32，是共享时钟采样时刻该层完整表面，不是片段全时长、整条最终序列或当前分块。RGB/alpha分别统计，跨分块结果逐位相同。未声明的独立通道实时继承共享RGB值；显式alpha独立于共享值。

端点转Float32；系数使用Float32端点差后binary64相除并写回Float32，RGB执行独立减/乘/加，无整数中间量、不裁切负值/超白。输入跨度为0默认报FLOAT_LEVELS_ZERO_SPAN；显式zero_span=output_black将该通道映射到其输出黑点。极小跨度/输出溢出拒绝。零强度验证输入后逐位复制，不为平坦自动端点制造NaN。

preserve/preserve_color支持none/lum/max/avg/sum/nrm/pwr。lum=max+min，max=最大值，avg=(R+G+B+1)/3，sum=和，nrm=平方和开根，pwr=立方和的实立方根；都在当前输入/输出信号的RGB数值上比较。输出度量>0才用输入/输出比缩放，否则保持映射结果。这些是公开模式的精确定义，不宣称加权亮度、感知色恒定或HDR。bool/0/1/off别名按旧契约映射none或lum。

本机FFmpeg8.1的GBRAPF32自动端点已实测出现跨通道依赖，产品按各自通道完整表面计算。明确端点/保留模式的原生对照与自动模式的独立数学对照分别留证；不能宣称所有输入逐位复制FFmpeg或剪映。

## 动态曝光与作者时间

曝光type=exposure，amount/exposure范围[-3,3]，black范围[-1,1]；曝光在共同线性RGB上工作。动态amount/black可在effect.keyframes或parameters.keyframes之一声明。原静态协议/系数不变，动态协议为author-clock-native-coefficient-float32-exposure-v1。白点=Float32(exp2(-Float32(amount)))，差为绝对Float32白点减黑点；零差增益1024，否则取倒数Float32。每像素两次Float32减/乘，alpha原位型保留。

所有色阶端点、intensity与曝光两通道支持linear/hold/ease_in/ease_out/ease_in_out/bezier；前缀effect./parameters./当前类型.可用。Bezier两控制值直接计算，四控制值按x求根；超范围时间插值结果按通道范围限制后采样。固定不可变规范JSON轨道，每轨1..1024关键帧、总16384、最多通道数、序列化4MiB，严格递增非负整数at_tick。超2^53整数/有理偏移保留；窗口及嵌套倒放用原作者时钟和左极限。未知字段/通道、重复、非法数字、控制点或超作者时长拒绝。

## 表面、alpha、预算与失败

输入连续H×W×4 Float32，RGB有限，alpha在0..1；单边≤16384、总像素≤16777216。独立alpha端点仅在显式声明/轨道时启用，强度与原覆盖率在线性覆盖域混合；最终越界拒绝，默认alpha逐位保留。RGB转回共同线性工作域后以binary64混强度再写Float32。

请求分块1..262144，实际≤16384。工作区估算=3倍表面字节+保留LUT+实际块像素×2048+4倍轨道JSON字节+524288，最大768MiB；不含整个Python对象图、解析器、音频、缓存、并发或总RSS。只读输入可用；取消回调抛异常或返回true均中止新动态运算，失败不改输入。效果链按作者顺序执行，禁用效果跳过；色阶自动检测可能需要额外整帧遍历，不声称实时。

尚未验收绝对nits、ICC/PQ/HLG、广泛自然素材与模型质量、长片/RSS、连续播放/听审或完整剪映功能等价。
