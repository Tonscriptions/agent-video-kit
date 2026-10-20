# 片段有理数时间基与 CFR 边界契约 v0.1

V81与未发布V80候选合并，当前发布状态以[实测记录](../validation/有理数视频时钟与曲线候选合并实测_2026-10-21.md)及根README为准。本契约修复CFR-01及请求源剪入相位，不宣称完整剪映等价。

|编号|约束|
|---|---|
|VC-01|读取登记流的原生 `time_base`；缺失时只读本地重新探测。已由编译器归一化的表面使用实际CFR时间基。普通VFR输入保留原PTS，不以平均fps替代。|
|VC-02|映射前的工作时钟分母为原生时间基分母、作者TPS、实际fps分子的公倍数，并取不超过2147483647的整数倍以降低非线性量化。三类原始格点精确表示；非线性映射仍有显式有限分辨率。不能表示时返回 `VIDEO_CLOCK_TIMEBASE_UNREPRESENTABLE`。|
|VC-03|可见视频为全局半开格点 `[ceil(start*fps), ceil(end*fps))`；fps转换使用round=up／eof_action=pass。普通真短视频不补帧，末尾不泄漏到更长音轨。|
|VC-04|普通正向媒体保留请求源入点之前的解码前缀，先映射原PTS减请求入点，再在全局CFR采样；不以首个被截出的解码帧重启作者相位。非线性速度积分同样以请求源入点为锚。代价是累计解码，未接受实时或长片性能。|
|VC-05|公开 `trim_clip`／`split_clip` 创建展示窗口；`update_clip` 的白名单不支持直接写 `presentation_window`。窗口先编译完整作者图，再按作者CFR的ceil／ceil半开帧区间切出，重置局部PTS并移至目标作者tick。重相位时完整窗口的最后一帧可保持至窗口结束，真正短源不因此填充。裁切不会隐式缩短已指定的主序列时长，需显式 `set_sequence_duration`。|
|VC-06|效果时钟与媒体时钟分开；RGB控制点在真实CFR显示时刻取值，固定拓扑和已有六种时间插值。音频保持既有48kHz样本路由，视频修复不得改变PCM。冻结、嵌套、窗口与区间调节层的通过只限相应证据。|
|VC-07|原素材、真实MP4、lossless FFV1 BGRA/PCM NUT、GIF、每帧PTS、独立RGBA与完整PCM参考均保全。解码VFR必须显式 `-fps_mode passthrough`，避免工具自动补帧改变核验样本。媒体演示不代表新模型或自然质量验收。|
|VC-08|文件SHA用预留并复用的最多64KiB字节缓冲和无缓冲 `readinto`；预留失败依次尝试8KiB、1KiB，全失败在打开文件前返回 `FILE_HASH_MEMORY_EXHAUSTED`。支持短读，I/O失败不返回部分摘要。不宣称解决全进程OOM；注入测试不是操作系统OOM实测。|

原生FFmpeg倒放对VFR内容和持续时间的反向对应尚未实现验收；源剪入叠加倒放也未验收。嵌套仍有已记录的标称CFR表面路径；任意VFR嵌套、HDR、自然运动质量及完整剪映特效不借用本轮通过数。

`capabilities.render.video_frame_clock` 输出协议 `rational-local-video-clock-v1`、时间格点、源锚点及未验收限制。实际渲染manifest记录输入／工作时间基、原生探测来源、输出帧区间与完整窗口EOF边界，作者工程不被重写。
