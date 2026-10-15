# 本地 LaMa 区域修复与对象移除契约

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-LAMA-INPAINTING-001 |
| 状态 | 评审中 |
| 日期 | 2026-10-16，Asia/Taipei |
| 范围 | 原生 Windows、本地 TorchScript、CPU/CUDA、视频区域修复与对象移除 |

## 1. 目标与边界

推进差异 #56 的对象移除、局部修复，并复用 #55/#94 的 SAM2 分割结果。输入原视频与本地蒙版资产，使用 LaMa 对选定区域补全，保留蒙版外 RGB 和原始 alpha；输出无损 MOV、音频及可应用时间线的派生资产。

本引擎逐帧执行图像修复，不能将它描述成跨帧联合视频修复、真实背景恢复、提示词生成填充或完整剪映等价。时序一致性、遮挡、复杂纹理和商业广告质量须另行取得证据；完整目标不缩减为本轮功能。

## 2. 登记与命令

视觉 engine `torchscript-lama-local-v1`，协议 `agent-video-lama-inpainting-v1`。登记要求已有本地 LaMa TorchScript `.pt`、原生 Python `.exe`、本地证据与 `--device cpu|cuda`（默认 cpu）。固定 FP32；Torch/numpy/Pillow 必须已安装。模型、Python、证据和执行实现进入摘要清单，不调用下载器、HTTP 服务、IOPaint GUI 或容器。

`media inpaint --project <项目> --asset-id <源视频> --mask-asset-id <蒙版图像或视频> --adapter-id <LaMa> --derived-asset-id <新ID>` 默认读取蒙版 alpha，适配 SAM2 QTRLE/ARGB 输出；`--mask-channel luma` 读取黑白蒙版亮度。阈值默认 0.5，白/高 alpha 为修复区域；`--mask-grow` 扩大区域，`--mask-feather` 在区域内部柔化混合。空蒙版帧原样通过。

源范围、帧率、画幅、帧数、音频、超时和取消复用 RGBA 管道。蒙版帧从其显示起点加 `--mask-start-seconds`（默认 0）取样，必须覆盖本次输出时长；静态图明确循环。源与蒙版都执行显示方向/SAR/CFR 归一化。默认拒绝几何不匹配，显式 `--mask-resize nearest` 才允许相同比例缩放；不猜测裁切、变速、透视或绑定关系。执行前核对 dry-run 时钟。

每帧只对蒙版包围框及 `--context-pixels` 上下文推理，最大模型长边由 `--model-max-edge` 限制；模型输入补齐到 8 的倍数。超大区域会显式缩放并报告，输出画幅不因此改变。保留源 alpha，最终只在扩大的修复区域混合，区域外 RGB 必须逐字节一致。

## 3. 执行与完整性

FFmpeg 将源 RGBA 与归一化蒙版 RGBA 横向堆叠后流式传入隔离 worker，布局为每行 source RGBA + mask RGBA，不缓存整段视频。worker 核验源/蒙版/模型/请求摘要、设备与参数，输出逐帧 RGBA、修复/空蒙版计数、实际模型区域预算、区域外不变和 alpha 摘要。输出完整解码后的 RGBA 必须与 worker 摘要一致。

父进程使用 Windows Job 管理解码、推理和编码进程，取消/超时停止全部子进程；输出拒绝覆盖，失败清理媒体并由项目事务恢复元数据。源视频、蒙版及其依赖、LaMa 模型共同约束发布；模型代码许可证不自动授权权重或素材。

## 4. 验收

必须有提示蒙版和静态/动态蒙版、alpha/luma、阈值/扩大/羽化、空帧、几何/时钟/路径/哈希拒绝、真实 FFmpeg、权利依赖、幂等/快照/项目包、失败回滚与进程清理测试。真实模型须验证 CPU/CUDA、受控真值及 SAM2→修复→成片，目视和时序缺口单列，不能用 mock 或无损编码摘要证明画质等价。
