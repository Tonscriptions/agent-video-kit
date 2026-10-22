# 连续浮点RGB曲线与后置总曲线契约 v0.1

显式settings.pixel_pipeline.engine=float32-native-v1。effects数组类型curves/curve或rgb_curves/rgb_curve/channel_curves，参数必须在parameters中；明确input_signal/output_signal，各含primaries/transfer。共同工作域必须是明确线性ColorSignal。旧整数effects catalog的曲线网格限制不覆盖这个显式能力；默认后端未迁移。

以下为片段effects数组的一项；示例作者时基90000 tick/秒、原作者时长至少1秒。工程还需按既有契约声明原片信号与本地素材，不修改素材本身：

```json
{
  "type": "rgb_curves",
  "parameters": {
    "all": "0/0 0.5/0.4 1/1",
    "red": "0/0 0.4/0.45 1/1",
    "post_master": "0/0 0.5/0.55 1/1",
    "interpolation": "natural",
    "intensity": 0.8,
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"}
  },
  "keyframes": [{"property": "all.1.y", "keyframes": [
    {"at_tick": 0, "value": 0.4, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 0.6, "interpolation": "linear"}
  ]}]
}
```

all为未独立声明通道的默认曲线；curves/curve拒绝独立RGB，使用rgb_curves声明red/green/blue。master是all的旧别名，二者冲突拒绝；真正后置总曲线用post_master，在独立RGB映射后执行一次。每条曲线为1..256个0..1有限x/y字符串点；x以binary64严格递增，不受8位格限制。1点为常量，2点为直线；所有曲线在首末点外作常量延伸，输出夹0..1。natural为自然三次样条，pchip为保形分段三次Hermite。极近点造成非有限系数时明确拒绝，不静默替换成整数表。

关键帧属性all/red/green/blue/post_master.<index>.x或.y，以及intensity。master.<index>归一化为all别名；支持effect./parameters./本类型名前缀。动画独立通道没有静态点时，从静态all完整分叉；后置总曲线没有静态点时从0/0 1/1分叉。固定拓扑，不动态增删点；重复轨道、未知点、每轨超1024关键帧、总数超65536或超2561轨道拒绝。关键帧tick为递增非负整数，值0..1；每个实际作者采样时刻再次校验x顺序，交叉/重合中止事务。

六种时间插值hold/linear/ease_in/ease_out/ease_in_out/bezier。本浮点曲线直接计算Bezier，不沿旧32段/8位小数查表；两值控制为固定横向1/3、2/3的三次式，四值横向控制0..1并用48次二分求根，纵向控制有限。overshoot后的点和强度夹0..1，再检查几何。完整作者tick和有理偏移传入，presentation_window、子序列速度/倒放与父容器分别求值，倒放端点保留左极限。库级省略interpolation默认linear；公开CLI验证仍要求关键帧显式填写interpolation。

每块从共同线性工作信号转入声明input_signal，独立通道和可选post_master以Float64坐标/系数计算，映射后写Float32，再按output_signal转回工作域。intensity为有限0..1，可动画，混合在工作线性straight RGB中用Float64累加后写Float32。强度0逐位复制原RGB，包括域外值；强度1直接取结果。alpha是覆盖率，不参与曲线或传递函数，其原始Float32位型保留，包括负零、透明像素隐藏RGB。

曝光、LUT与曲线按作者effects顺序运行，片段几何和混合前求值；嵌套容器效果在子画布合成后求值。启用的未知效果明确拒绝；未承诺序列区间调节层、所有其他算子或蒙版空间已全部迁入此路径。源与作者工程只读，缓存由作者字段、信号、实际输入和实现SHA绑定。

表面必须连续H×W×4 Float32，有限RGB、alpha0..1，单边≤16384，总像素≤16777216。请求块1..262144、内部最多16384像素。工作数组估算含三份表面、保留LUT、分块数组、序列化作者轨道和固定余量，最多768MiB；估算不是实测总RSS，不包括全部Python对象、JSON解析、音频、源缓存和并发总额。只读输入允许，预算拒绝、非法晚块、取消和数值溢出都不修改源或返回部分结果。

原生FFmpeg RGB16是独立交叉观察：自然曲线的整数格起点/输出截断、后置曲线第二次量化单独建模；PCHIP两点域外直线延伸与本契约的常量端点存在明确差异。连续浮点曲线的通过依据是独立数学参考，不能声称与原生整数后端所有像素相同。自然广告素材、ICC/PQ/HLG/绝对nits、色域映射、HDR质量、实时预览、长片总RSS及完整剪映等价均未验收。
