# 连续浮点YCbCr锐化契约 v0.1

## 入口与参数

显式settings.pixel_pipeline.engine=float32-native-v1启用，正式render与preview range/frame使用同一EffectCompiler。type为sharpen或unsharp；顶层只接受id/type/enabled/parameters/keyframes。parameters必须提供input_signal、output_signal={primaries,transfer}以及matrix和range；工作信号须linear。矩阵为bt709/smpte170m/bt470bg/bt2020nc，range为full或limited；reference_bits为8/9/10/12/14/16，默认8。

luma_amount/chroma_amount/alpha_amount各为有限数-2..10，默认1/0/0。amount和la别名对应luma_amount，ca/aa对应chroma/alpha。radius默认2，范围0..11；luma/chroma/alpha各自radius_x、radius_y范围相同。radius_x/y只别名至亮度XY。静态或动态明确声明的轴覆盖master radius，其余轴在每个作者tick跟随radius；不是编译时复制master值。

luma/chroma/alpha_msize_x/y及lx/ly/cx/cy/ax/ay为静态原生尺寸别名，仅允许3..23的奇数整数，映射radius=(size-1)/2；不接受bool、浮点整数或动画尺寸。相同静态通道重复别名、同轨重复通道和未知项拒绝。intensity有限0..1默认1。arithmetic为continuous默认或native_coefficients；code_gamut和output_gamut各为preserve默认或clip。信号／矩阵／量程／参考轴／算术模式／裁切策略不动画。

```json
{"type":"sharpen","parameters":{"input_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"output_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"matrix":"bt709","range":"full","reference_bits":16,"luma_amount":1.2,"chroma_amount":0,"alpha_amount":0,"radius":2.375,"intensity":0.8}}
```

## 独立数学与原生差异

整数r=n的归一化核为C(2n,k)/2^(2n)，n=0是identity。r=n+f时把相邻整数核对齐中心，按(1-f)K_n+fK_(n+1)混合；分别做水平和垂直复制端点卷积。先blur再src+amount×(src-blur)。Y、Cb/Cr和alpha三组各用自己的amount及XY；Cb和Cr同组参数独立平面。

full轴Y=[0,2^bits-1]，色度中心128×2^(bits-8)、跨度2^bits-1。limited轴Y偏移16×scale、跨度219×scale，色度中心128×scale、跨度224×scale。矩阵系数Kr/Kb明确，Kg=1-Kr-Kb。码值轴为Float64数学单位，未生成整数图像或LUT。code_gamut=clip仅裁处理过的YCbCr平面至0..maximum；output_gamut=clip在按output_signal恢复线性工作RGB之前裁算子RGB至0..1，两者均不同于最终交付range_policy。

continuous直接使用amount。native_coefficients把原参数先按Float32存储，再trunc(value×65536)，8位除65536，高于8位除16777216，对应本机原生uint16实现额外8位移。它不复现blur逐像素舍入、最终整数floor／存储裁切、uint32递推累加溢出或signed32乘法溢出，native_bit_equivalence始终false。原生alpha非零路径已有实际崩溃证据，不作为有效参考。alpha映射是产品独立覆盖率数学，非原生逐位alpha兼容。

14位并非该原生unsharp支持的像素格式；半径0/分数、amount>5、双轴较大组合也是自有扩展。metadata分别报告原生选项形状资格、在最大参考码下的累加位数界、格式支持情况，均不等同原生执行成功或安全保证。native_fixedpoint_overflow_reproduced=false。

## 信号、alpha与作者时钟

线性工作RGB→input_signal→YCbCr→卷积／amount→RGB→按output_signal返回线性工作RGB，intensity在工作RGB和独立coverage上线性混合。持久RGBA为Float32，卷积scratch为Float64。未请求alpha时保留输入alpha位模式，包括-0和正1e-30。显式alpha算子裁coverage至0..1并报告裁切数；不是RGB预乘模糊。alpha-only、输入输出信号相同且preserve时绕过RGB转换，保留隐藏RGB位。intensity0在整图／计划验证后逐位恒等。RGB负值和超白默认保留；交付超范围而未明确clip须拒绝。

11个数值通道可动画：3amount、master radius、6独立XY、intensity。支持linear/hold/ease_in/ease_out/ease_in_out/bezier，四控制值Bezier先解时间根；严格递增非负整数键tick，支持Fraction和超过double整数精度的作者采样。规范轨道JSON及既有自动化预算适用，末键也须按工程schema声明interpolation。超原作者时长拒绝；呈现窗口与嵌套倒放保留各层作者时钟，不把裁后首帧当作新原点。

## 空间预算、生命周期与失败

输入为连续H×W×4 Float32，有限RGB、alpha0..1；边长1..16384、像素数≤16777216。fixed估算=6×完整表面字节+保留表字节+4×轨道JSON字节+max(1MiB,(max(H,W)+23)×8×6)。转换tile请求1..262144，按既有准入先限至16384和像素数，再按剩余预算每像素2048字节缩小；不提高默认768MiB上限。估算不表示进程峰值RSS、并发总内存或自然长片性能。

全尺寸Float64四平面和单通道blur只在内部作用域存活，不返回保留它们的view；输出信号转换在该作用域结束后开始。每个水平／垂直处理行复制一个输入行，支持垂直原位写回；不建立核数量倍数的整图数组。预算／整图合法性验证先于结果，对转换、核tap及行写入检查取消。取消True报RENDER_CANCELLED，回调异常原样传播；非有限、Float32溢出、晚块非法值或错误参数明确拒绝，调用者不变，允许只读输入。

## 验收、许可与发布

62新增／121关联源码、原生对照、五场景20帧真实CLI、实际三场景4K、196资源741项离线安装与2836项完整套件分开登记。目标数字不是通过数。GIF为真实输出派生；4K GIF仅三张单帧切换。未完成自然素材、长片RSS、连续播放、听感、HDR、默认全量浮点迁移、时间降噪及完整剪映功能验收。

FFmpeg原生C文件仅用于固定行为参考并附GPLv2文本，自有Python二项核与卷积未复制该C实现；FFmpeg程序、原高斯NOTICE、NumPy等依赖归属保留。研究读取网络与产品运行网络分开，产品运行及验证全本地，无Docker／WSL或虚拟环境。完整回归必须等待V108实际发布及OpenFilm R17文档发布，绑定R17 main提交和V108产品326输入；普通提交／推送，不执行新force push。
