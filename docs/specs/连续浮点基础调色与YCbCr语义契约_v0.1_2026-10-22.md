# 连续浮点基础调色与YCbCr语义契约 v0.1

## 选择与参数

显式settings.pixel_pipeline.engine=float32-native-v1，正式render、preview range/frame共用有序内核。类型：brightness/lightness、contrast、saturation、color、gamma/gamma_adjust、hue/hue_rotate、hsl/hsl_adjust、grayscale/black_white/blackandwhite。默认8位后端及其现有工程保持原实现；本接口不自动迁移旧工程。

所有类型parameters均须input_signal/output_signal={primaries,transfer}、matrix、range。RGB基色/transfer使用既有明确D65相对信号集合；matrix可bt709/smpte170m/bt470bg/bt2020nc，range为full/limited。矩阵不能替代RGB基色/transfer声明，两者允许创意组合且不隐式猜测。reference_bits默认8、可10；表示分数码值轴，不代表中间像素量化。

brightness[-1,1]默认0；contrast[0,4]默认1；saturation[0,4]默认1；gamma[.1,10]默认1；hue[-360,360]默认0；hsl.lightness[-1,1]默认0；各类型intensity[0,1]默认1。color只包含brightness/contrast/saturation。单独brightness/contrast/saturation/gamma支持amount/value别名；hue支持degrees/angle/value；hsl支持degrees/angle→hue和brightness→lightness。静态或轨道重复声明同一通道别名拒绝。灰度只有intensity。未知字段、布尔/非有限/字符串数字/越界拒绝。

arithmetic为continuous（默认）或native_coefficients。output_gamut为preserve（默认）或clip。effect顶层仅id/type/enabled/parameters/keyframes；轨道可放effect.keyframes或parameters.keyframes一个层级。enabled=false由效果宿主跳过。

```json
{"type":"color","parameters":{"input_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"output_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"matrix":"bt709","range":"limited","brightness":0.03,"contrast":1.1,"saturation":0.8,"arithmetic":"continuous","intensity":0.7}}
```

## 码值与算子

令M=2^bits-1、S=2^(bits-8)。full的Y=亮度×M、Cb/Cr中点=128S、幅度=M；limited的Y=16S+亮度×219S、Cb/Cr中点128S、幅度224S。RGB先按声明input_signal解释；Y使用所选矩阵的Kr/Kb，Cb=(B-Y)/(2(1-Kb))、Cr=(R-Y)/(2(1-Kr))。连续码值没有取整、色度抽样或整数LUT。

continuous eq在Y归一化码值上计算contrast×(x-.5)+.5+brightness，然后改变的平面clip到0..1并使用幂1/gamma。饱和度是Cb/Cr平面的contrast。未改变的平面直接保留，不隐式裁掉其headroom。eq饱和度实际按旧原生路径夹到3，sampled_values保留作者值并以effective_eq_saturation另报有效值。

native_coefficients对原生eq参数使用单精度；Gamma为1时采用标量固定点contrast系数与brightness偏置，保留连续像素，不执行原生每像素整数floor。Gamma非1时保留连续幂函数；原生8位LUT的输出取整不能逐位相同。10位eq只允许continuous，明确为独立连续扩展；FFmpeg eq没有原生10位后端可作为兼容依据。

hue/hsl围绕中性色度128S旋转Cb/Cr并乘饱和度；grayscale把色度置中点、Y保持。hsl.lightness通过旧hue亮度幅度改变Y：8位每单位25.5码，10位102.4码；与eq brightness不是同一幅度。native_coefficients使用单精度角度及16位标量三角系数。全局HSL不是RGB HSL；八色selective_hsl使用另外的模型。

改变后的平面裁切至0..M，计入changed_plane_clipped_components。逆矩阵恢复RGB后可负值或超白；output_gamut=clip显式裁切算子RGB并报告，preserve保留。算子RGB按output_signal解释，再转换回线性工作信号，最后按intensity与原始工作RGB混合。算子输出clip不等于最终交付clip。intensity=0在完整有限值/alpha/预算检查后逐位返回输入；同信号、无效果及无实际裁切的identity也保留原RGB位模式。alpha从输入逐位复制，不参与码值和信号转换。

## 作者时间与资源

各类型现有数值及intensity可动画，6种插值linear/hold/ease_in/ease_out/ease_in_out/bezier。每轨1..1024键，总16384键、规范JSON最多4MiB；轨道数不超过当前类型通道数。tick严格递增非负整数，采样允许非负有限实数、大整数与Fraction；Bezier须2或4控制值，4控制先解时间根；插值越界按通道边界限幅。超过原作者时长拒绝。预览窗口、父子嵌套与倒放均沿用原作者时钟，编译计划不保留可变作者字典。

输入为连续H×W×4 Float32，边长1..16384、像素<=16777216。请求tile_pixels为1..262144、实际<=16384。工作区估算=3×表面字节+保留表字节+每块像素×2048+4×轨道JSON字节+524288，最多768MiB；它不是整个进程峰值RSS保证。预算与整张有限RGB/alpha0..1检查完成后再构造输出；只读输入可用，取消返回True或异常、晚块非法值、传递溢出均不修改调用者输入。

## 验收边界

真实YUVA444 eq/hue原生对照、独立连续数学、公开CLI全像素/PCM/PNG16、8-wheel隔离安装和完整2667项分别验收；未执行/运行中不记通过，不累加作为剪映功能完成率。未完成默认后端迁移、所有其他浮点效果、自然素材/离线AI质量、HDR感知/绝对nits、ICC/白点适配、长片RSS和完整剪映等价。媒体记录的静态抽帧查看不能替代连续播放或声音听审。
