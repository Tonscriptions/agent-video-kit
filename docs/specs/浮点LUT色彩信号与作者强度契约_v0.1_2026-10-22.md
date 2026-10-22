# 浮点LUT色彩信号与作者强度契约 v0.1

显式选择settings.pixel_pipeline.engine=float32-native-v1。Agent仍用effects数组，参数置于parameters；类型lut3d/lut/cube/look，path/file/lut同值别名或lut_id二选一。每个LUT必须明确input_signal与output_signal，两者均含primaries/transfer；原有effects list中的整数后端说明不替代此显式浮点契约。未知字段或未接入效果拒绝。默认渲染后端未迁移。

支持完整3D .cube，边长2..256、red-fastest、TITLE、DOMAIN_MIN/MAX、空行、注释和UTF-8 BOM。数据必须恰为size³组三个有限Float32，DOMAIN各轴有限、最大值严格大于最小值；头不重复、不得出现在样本之后；1D shaper及未知扩展拒绝。3dl/csp/dat仍属于既有整数后端范围，未自动转换或宣称本轮支持。TITLE使用带引号的单行字符串；严格安全解析不猜测厂商方言。

路径解析后必须在现有本地项目根内，不允许URL、UNC、项目外路径或file协议字符串。登记ID必须有匹配SHA，登记JSON与LUT文件一并绑定；固定表为不可改bytes上的Float32视图，编译计划不会跟随作者对象或文件变动。正式render/preview在事务核验时重查文件身份，文件变化不能以旧计划发布；持久预览键包含原文件依赖。强度0仍编译并验证本地资源，不能绕过缺失或损坏登记。库级FloatTimeline调用必须给resource_root；正式共同上下文自动提供项目根。

共同工作域须为明确线性光ColorSignal。每块先从工作域转到LUT声明输入，归一化坐标=(输入-DOMAIN_MIN)/(DOMAIN_MAX-DOMAIN_MIN)，夹到[0,1]后以Float32乘(size-1)，再按所选插值求值。nearest以floor(coord+.5)取点；trilinear八顶点；tetrahedral按分数的有序四顶点；prism为R/B平面的三角形沿G插值；pyramid为原生严格分支选择的零轴双线性面加对角校正，同分数时保留其第三轴分支约定。权重Float64、表输出Float32，保留有限负值及超1输出，无整数中间量。

查表输出按声明output_signal转回共同线性工作域，然后执行source*(1-intensity)+graded*intensity，Float64混合、Float32结果；强度1直接取变换结果，强度0逐位复制原表面。混合在工作线性RGB内，不用编码域整数blend，也不以重写CUBE近似动态强度。alpha为独立straight覆盖率，位模式保持，不参与色彩转换或LUT；后续几何/合成仍遵守自己的alpha契约。

静态intensity有限且在0..1；顶层或parameters内可有单条intensity关键帧，二者不能同时声明。支持effect./parameters./类型名前缀，1..1024递增非负整数tick，六种既有作者插值：hold、linear、ease_in、ease_out、ease_in_out、bezier。Bezier沿既有32段/8小数公共查表；控制值有限，四值时横向控制在0..1，overshoot后的实际强度夹到0..1。FloatTimeline在源作者动画tick求值，presentation_window偏移、子序列速度/反向和父序列时钟保持区分。

曝光与LUT按作者数组顺序逐项运行；曝光继续使用既有原生系数契约，所有效果在该片段几何与层混合之前处理；嵌套容器效果在子画布合成之后处理。未声明crop的mask空间与显式crop分支的父画布mask差异沿前轮契约保留，本轮不宣称完成所有组合统一验收。禁用效果跳过；未知的启用效果拒绝，不静态近似或退回整数路径。

表面为连续H×W×4 Float32，RGB有限、alpha在0..1，输入可只读。单边≤16384、总像素≤16777216。文件≤512MiB、单行≤4096字节；表解析按二份表与有界I/O估算入场，拒绝超预算后才分配。像素请求分块1..262144、默认65536，内部单块最多16384以符合共同色彩转换尺寸；估算包括三份全帧、已保留表和保守分块工作数组，上限768MiB。相同路径表共享，跨片段所有保留表合计入场。此配额不等于进程总RSS，也不覆盖项目/登记JSON、Python对象、音频、源缓存和并发总额。取消、晚块无效值、溢出和预算拒绝均保留输入，不返回部分结果。

支持既有明确D65 bt709/display-p3/bt2020与linear/srgb/bt709-oetf/gamma22/gamma24相对信号；未增加ICC、PQ/HLG、绝对nits、色域映射、色适应或HDR验收。合成像素一致不代表自然广告素材质量、实时预览、长片内存或完整剪映等价。MP4/GIF是观看副本，Float32/PCM/PNG16另核验；静态抽帧不代替连续播放与听感。
