# 真实源范围外扩与关联 Slip 契约

| 项目 | 内容 |
|---|---|
| 文档编号 | SOURCE-EDIT-001 |
| 状态 | 有效；V40 受控源编辑通过，完整剪映等价未验收 |
| 日期 | 2026-10-18，Asia/Taipei |
| 实现 | [source_edits.py](../../product/src/ai_ad_editor/source_edits.py)、[range_edits.py](../../product/src/ai_ad_editor/range_edits.py) |
| 关联 | [范围编辑](范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md)、[输出窗口](片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md)、[真实源转场](真实源句柄转场与可逆编辑契约_v0.1_2026-10-17.md) |

## 1. 入口与选择范围

使用现有 `timeline edit --project <工程> --input <请求.json> --dry-run` 规划，正式写入时去掉 dry-run。`--expected-project-sha256` 绑定计划中的规范 JSON 摘要，不是原文件字节 SHA；`--idempotency-key` 保证相同参数重试不会重复滑移。`timeline compose` 可通过 `{op: "linked_edit", edit: <请求>}` 放入原子批次，后续操作失败则整批不保存。

| action | 请求字段 | 行为 |
|---|---|---|
| `slip` | `clip_id`、有符号 `delta_source_tick` | 同量移动源入/出点；时间线落点、可见时长、速度、曲线、定格、动画和输出窗口保持原数据 |
| `extend_source` | `clip_id`、非负 `head_tick` / `tail_tick`，缺省 0 | 可见起点减 head、时长加 head+tail；先恢复已有作者窗口，再扩到真实输入范围 |
| `roll` | 既有左右片段和 `delta_tick`，可选 `handle_policy` | 缺省 `retained`；显式 `source` 才允许扩展不足的完整作者源范围 |
| `slide` | 既有中间片段和 `delta_tick`，可选 `handle_policy` | 中间主体整体移动，调整两侧邻居；缺省 `retained`，显式 `source` 可使用真实源句柄 |

`slip` 的正负号始终表示物理源时间方向；倒放不翻转该符号。两个新 action 沿用 `sequence.editing.linked`（未配置时默认 true），决定是否扩展同序列的完整 `link_id` 组；请求可用 `options.linked` 明确覆盖，false 时只编辑目标。任何选中成员锁定都拒绝整组；不跳过失败成员，不自动移动未关联音轨或骑乘字幕。序列 movement 默认中的 sync/linkage 不参与源操作；请求显式将其设为 true 会报错，避免默默忽略用户选择。

旧 `timeline compose` 的 `slip_clip` 使用同一源规划器，保留原来缺省单片段语义；可加 `linked:true`。不再通过旧 `int()` 强制转换接受布尔或小数，也不再绕过跟踪引用/转场句柄检查。新 planner 同时支持有限的直接媒体和嵌套序列源。旧 `slide_clip` 仍是单片段时间线移位，专业三片段滑动使用上述 `timeline edit:slide`。

## 2. 源边界与整数时钟

真实输入为已登记本地 video/audio 资产，或有限 `sequence.duration_tick`。媒体边界以登记的 `probe.duration_seconds × ticks_per_second` 作有理数比较，不将非整数末尾向上取整。静态图片/文字时长继续使用普通时间线接口，不能冒称为有限视频句柄。

每个请求 tick 必须是整数，不能是布尔/小数；两个新 action 限定绝对值≤2^53−1，以保留原生编译时钟的精度。源范围非空且位于输入界内。源编辑不调用 FFmpeg、ASR、模型、下载器或服务商；规划和验证只读取既有工程数据，实际渲染仍使用原本地 FFmpeg 路径。

头部外扩按作者边界速度换算为源 tick，不能精确表达为整数时拒绝，不静默舍入。尾部首先使用已有输入中尚未展示的输出；确需增加输入时包含覆盖目标时钟的最少整数源 tick，再由输出窗口选择准确可见时长。不会补帧、补静音、循环或截短用户请求来冒充句柄。

若作者时长已经超出真实处理内容、依靠填充凑长，外扩要求先明确重建作者范围；定格点超出真实内容钟也拒绝。处理内容/定格边界检查沿用 1 tick 的原生编译容差，不能理解为任意补长许可。此前已有的填充仍可通过保留输出窗口恢复；“恢复既有作者结果”和“生成新的真实输入范围”分开处理。

## 3. 作者范围与重处理

旧窗口偏移为 O、完整作者时长为 D、可见时长为 V；请求头尾增加 H/T。真实作者需要增长 `h=max(0,H−O)`、`t=max(0,O+V+T−D)`。新窗口偏移 `O+h−H`，可见时长 `V+H+T`。只有 h/t 非零才重建真实作者源范围；原保留范围内的恢复不改变源点或处理数据。

新作者对原 source-relative 速度关键帧按新增物理左侧源 tick 平移；外部区域保持边界速度。补全原本隐含的起点/终点，保留原控制值、插值及 Bezier 控制点。倒放的输出头对应物理源尾。重编译最多八次，检查现有有界曲线编译器实际覆盖的输出；不能满足时给出复杂度错误，不变成平均速度或合成缺失帧。

新增输出前缀 h 后，片段顶层关键帧、效果关键帧、音频效果关键帧和定格点加 h。文件字幕的序列钟偏移在作者起点重定位时显式修正。片段源和子序列内部的动画数据不清零，未关联字幕不擅自跟随源内容。

**真实源外扩是重新编写作者范围，不能套用 V38/V39 的旧输出逐帧不变承诺。** 边缘淡入淡出、效果求值、速度近似与采样可能重新计算；原生曲线编译误差和 atempo/R3 音质限制继续存在。独立嵌套曲线仍按照新声明时长归一化，旧主体的采样时钟可能变化：计划列出 `before_nested_curve_scale` / `after_nested_curve_scale`，同时输出 `SOURCE_EDIT_NESTED_CURVE_RENORMALIZED` 警告。未将这种再归一化验收为剪映等价或原主体保真；精确保持任意嵌套曲线旧主体的外扩时钟仍是后续工作，归一化嵌套曲线与定格的组合也未单独验收。

源 `slip` 本身不重建上述处理字段，只改变同一形状的输入范围；它选择了新的内容，定格/动画在既有作者输出钟上求值。

## 4. 锁、引用、冲突与事务

跟踪源或目标的非零源改变会使观察失效，因此拒绝；不把旧蒙版或轨迹挂到新内容。部分真实源转场端点外扩仍沿用范围裁切门禁。转场端点可以做不改变时长的 slip，但操作后重新调用真实转场分析，连同额外头/尾句柄一并验证；片段本身仍在素材界内，并不保证转场所需句柄也存在。

主轨新增碰撞拒绝；副轨沿用原 lane 规则，保留处理语义，有效果/闪避的音频总线不能静默换轨。roll/slide 继续要求完整连续的关联左右对/三元组。片段或源不够、头部进入负时间、任何锁/引用/布局失败都会丢弃 detached candidate。markers 保持绝对序列 tick，序列不因源滑移变长；外扩仅在必要时增长序列末尾，不隐式清除既有尾部空白。

零增量规划保留完整工程数据，但仍检查目标存在和关联锁。正式 CLI 继续创建 before snapshot、操作记录和项目来源变更日志；原权利依赖沿用，源编辑不赋予新的发布许可。

## 5. 可评审计划与错误

计划沿用完整 before/after 差异，并新增 `source_changes`，记录源 ID/种类/有限边界、源入出点、真实左右增量、作者时长、边界速度、重编译次数、关键帧/定格偏移、嵌套归一化比例与再处理策略。转场源不足可返回原 `SOURCE_TRANSITION_*` 错误。`capabilities.source_edits` 和四份现有 `$video-cut-*` 技能公布入口与边界。

| 错误 | 含义 |
|---|---|
| `SOURCE_EDIT_HANDLE_SHORTFALL` | 实际视频/音频/子序列范围不足 |
| `SOURCE_EDIT_BOUND_UNKNOWN` / `SOURCE_EDIT_REFERENCE` | 未登记有限源时长或源序列丢失 |
| `SOURCE_EDIT_KIND_UNSUPPORTED` | 不是有限 video/audio/sequence 输入 |
| `SOURCE_EDIT_CLOCK_INVALID` | 源速度不是有限正数 |
| `SOURCE_EDIT_SOURCE_GRID` | 新输出前缀不能精确换算成整数源 tick |
| `SOURCE_EDIT_PADDED_AUTHOR` | 原作者含超出真实处理内容的填充 |
| `SOURCE_EDIT_FREEZE_CLOCK_INVALID` | 原定格点已越过实际内容钟 |
| `SOURCE_EDIT_CURVE_BUDGET` | 八次重编译后仍不能覆盖目标输出 |
| `EDIT_RANGE_HANDLE_SHORTFALL` | 没显式选择真实源模式，已有作者句柄不足 |
| `EDIT_RANGE_BINDING_UNSUPPORTED` / `EDIT_RANGE_TRANSITION_UNSUPPORTED` | 现有跟踪或端点编辑语义尚不支持 |
| `EDIT_TRACK_LOCKED` / `EDIT_RANGE_EMPTY_SIDE` | 关联成员锁定、负落点或空片段 |

## 6. 验证与交付范围

单元/CLI/实际图覆盖见 [test_source_edits.py](../../product/tests/test_source_edits.py)。公开媒体由 [smoke_source_edits.py](../../scripts/smoke_source_edits.py) 生成，使用既有 CC0 计数器和声音；固定 V39 的手工作者工程是兼容性参照，另外用直接解码的源画面核对两组帧身份。FFmpeg 仍是共同底层，不独立接受原有渲染、时钟、Alpha、音高或自然质量算法。

完整冻结回归、发行 wheel、音画逐项比较、原开发失败和 README 证据须齐全后才更新为有效。[实测记录](../validation/真实源外扩与关联Slip实测_2026-10-18.md)区分当前结果、历史研究和未验收项。全量剪映能力、完整磁吸、任意嵌套旧主体保真、跟踪重规划、自然模型质量、HDR/VFR、听审、长片 RSS、干净机器与完整素材/模板库均不由本项验收关闭。
