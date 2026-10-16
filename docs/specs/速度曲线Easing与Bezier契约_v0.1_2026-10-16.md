# 速度曲线 Easing 与 Bezier 契约

| 字段 | 内容 |
|---|---|
| 状态 | 有效 |
| 版本 | v0.1 |
| 日期 | 2026-10-16 |
| 实现 | [曲线编译器](../../product/src/ai_ad_editor/speed_curves.py)、[时钟映射](../../product/src/ai_ad_editor/time_mapping.py)、[渲染器](../../product/src/ai_ad_editor/render.py) |
| 模型 | [Agent Project Schema](./agent-project.schema.json)，沿用 speed_curve 字段，无新增 CLI 参数 |
| 测试 | [独立积分与编码像素专项](../../product/tests/test_speed_easing.py) |
| 与已有契约关系 | 补充[嵌套解析时钟契约](./嵌套序列解析时间映射契约_v0.1_2026-10-16.md)，修正其初版的速度 easing 线性化限制 |

## 1. 作者格式与数学语义

`speed_curve.keyframes` 或数组中的 `at_tick` 仍相对于裁切后的源范围，`speed` 是源位置处的瞬时正速率；左关键帧的 interpolation 控制到右关键帧的一段。缺省为 linear，同 tick 保持既有的最后一项生效规则，作者顺序仍须单调。缺失起点按片段常速补入 hold，缺失终点保持末速率。

设源段归一化位置为 x，左右速率为 a/b，实际速率为 a+(b−a)·E(x)。hold 使用 a；linear 的 E(x)=x；ease_in 为 x²；ease_out 为 1−(1−x)²；ease_in_out 在 x<0.5 时为 2x²，否则为 1−2(1−x)²，与现有属性动画的定义一致。

Bezier 必须提供 `control_points: [y1,y2]` 或 `[x1,y1,x2,y2]`。二元写法的 x 句柄固定为 1/3、2/3；四元写法按归一化 CSS 曲线求 x(u) 对应的 y(u)，两个 x 分别位于 0..1，允许 x1>x2。所有值必须是有限数字，布尔值无效。允许 y 超出 0..1，只要整条速率曲线保持正值；检查包含三次多项式的内部驻点，不只检查控制点或端点。

既有“声明 bezier 但不提供句柄”的内容现在明确拒绝，不自动补造曲线。非法句柄、内部零/负速度和精度/资源超限均在写入或 FFmpeg 执行前返回结构化错误；不能悄悄退回端点连线。

## 2. 本地编译及误差上界

源时间 F(s)=∫1/v(s)ds。hold/linear 继续按常速/对数积分执行；ease/Bezier 使用原生 Python 的 de Casteljau 细分，将真实曲线编译成可解析积分的线性速率段。

对一个子段，速率与其源坐标弦线之差同样为三次 Bernstein 多项式，其绝对值不超过四个控制差值的最大值 d。设真实曲线控制速率下界为 m>0，弦线下界为 l>0，源宽为 w，则该段积分误差不超过 w·d/(m·l)。控制速率下界暂不为正时继续细分；整条曲线先经过真实内部最小值检查。

每段按自身源宽分配误差预算，总的**未归一化源积分误差上界为 0.00025 秒**。这不是采样点的拟合残差，也不是任意嵌套/编码输出的总误差。达到 1024 个编译段或 28 层细分仍不能满足精度时返回 `SPEED_CURVE_COMPLEXITY_LIMIT`；不截断段、不放宽精度。

编译清单包含 method、authored_interpolations、segment_count、source_clock_error_bound_seconds、requested_max_error_seconds 和 maximum_segments。在显式片段时长内归一化后，使用保守的 `2 × 源积分误差上界 × curve_scale` 记录该层 normalized_clock_error_bound_seconds；多个祖先的总误差还会随外层时钟改变，不能把单层 250 μs 原样声称为整条嵌套保证。

既有端点/常速的最小 0.01 归一化保留并写入 certificate；本轮不宣称任意低端点速率。Bezier 内部允许低于端点，只要为正且能在预算内编译。一般极慢速、极端句柄与超长曲线继续需要独立资源验收。

接近常速但不相等的端点仍按真实变化积分，不能以绝对速差阈值替代成常速。数值计算使用 log1p/expm1；FFmpeg 在相对速差≤1e-5 时使用五项稳定级数，避免 log/exp 的小差相消。额外用 10000 源秒、0.01→0.010000004 的解析积分与 3 帧 FFmpeg PTS 诊断验证；这只是三帧空输出诊断，没有编码 10000 秒视频。[实际错误与修复记录](../validation/evidence/speed-easing-stability-20261016.json)分别保留旧数值约 6.185 ms 超界、修复后约 65.104 μs，以及实际 PTS 约 66.699 μs 的结果；不据此验收长视频性能。

## 3. 视频、关键帧与嵌套执行

直接 eased 片段与嵌套片段共用原源域裁切、各层 reverse 和公共输出帧网格。曲线编译子段不展开为几百个独立媒体输入；一个可见叶片保留完整时钟。已有 hold/linear 嵌套的历史分段接口保持适用。

FFmpeg 的分段选择使用平衡表达式，避免线性 if 链随段数增加解析深度。专用 setpts 表达式可以使用它自己的临时寄存器，逐层求值以避免多个曲线的文本笛卡尔膨胀；geq/蒙版/crop/属性时钟仍使用无寄存器表达式，避免覆盖空间采样寄存器。复杂属性时钟的单个中间表达式超过 4 MiB 时返回 `TIME_MAPPING_EXPRESSION_LIMIT`，不生成不可控过滤图。

保留原作者关键帧及祖先逆时钟，允许非线性速度下的子层/父层插值跟随原时钟。实际输入仍按登记 fps 建立 CFR 显示时钟，VFR 原始时间戳等效继续未验收；原有 CFR 提示必须保留。`SPEED_CURVE_COMPILED` 记录已应用的曲线及其 certificate，原 `speed_curve_easing_linearized` 不再描述本版本支持的曲线。

## 4. 音频及原子性

eased 音频使用同一复合映射计算 atempo 短窗速率和累计 48 kHz 边界；沿用最多 16384 窗、单窗至少一个样本的门限。音频仍保留 `audio_speed_curve_piecewise`，包络对应不证明相位无接缝、无音色变化或自然听感通过。

曲线校验失败不得修改 project.json 或 Rights Ledger。正常 render 仍会登记 outputs/provenance；核对作者 assets/settings/sequences 规范摘要与台账原始摘要，不要求整个项目文件字节不变。素材/字体/模型权利、本地策略、取消和输出事务规则继续有效。

## 5. 验收范围

专项使用独立的源坐标 Simpson 积分、Bezier x 反算、编码帧号、原关键帧几何及脉冲音频；正式媒体通过[生成脚本](../../scripts/smoke_speed_easing.py)执行固定旧版和当前 CLI。源帧门槛≤1、几何≤3 px、脉冲边界排除和质量门禁需与实际媒体记录一同审阅。

无定格 CFR 字幕时序后续见[字幕契约](./嵌套字幕与文字动画时钟契约_v0.1_2026-10-16.md)。本契约自身不关闭容器/叶片定格、字幕完整排版与联合效果、群组枢轴/坐标与音频总线、自然模型画质、4K/长曲线性能、发行和完整剪映功能/效果对标。
