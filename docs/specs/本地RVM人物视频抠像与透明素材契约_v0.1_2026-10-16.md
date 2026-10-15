# 本地 RVM 人物视频抠像与透明素材契约

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-RVM-MATTING-001 |
| 状态 | 有效 |
| 日期 | 2026-10-16，Asia/Taipei |
| 范围 | 原生 Windows、显式本地 FP32 ONNX、CPU 循环推理与透明视频派生资产 |

## 1. 登记与运行边界

`media adapter register --engine rvm-onnx-cpu-matting-v1` 要求现有 `.onnx`、原生 Python `.exe` 及本地证据文件。Python 中须已有 numpy、onnx、onnxruntime；产品不安装包、不下载模型、不调用闭源服务或剪映。登记不加载模型；正式运行固定 `CPUExecutionProvider`，关闭遥测，无 GPU/其他 provider 自动回退。

登记固定线程数（1..32）与可选 `--downsample-ratio`（0<ratio<=1；默认按输出长边缩到 512 计算）。模型、Python、证据、worker、帧处理器和控制器共六个文件的路径、字节数、SHA-256 及参数进入 manifest。运行前后复核。ONNX 必须自包含，拒绝外部 tensor 和自定义算子域。

接口协议为 `agent-video-rvm-matting-v1`，输出契约 `rgba_video_v1`。抠像适配器与跟踪适配器能力不同，不能互相替用。登记元数据随项目事务、快照和项目包保留；外部模型与 Python 不随包分发。

## 2. CLI 与时间线

```powershell
python -m ai_ad_editor media adapter register --project .\work\demo `
  --adapter-id rvm_local --engine rvm-onnx-cpu-matting-v1 `
  --model-path E:\models\rvm_fp32.onnx --executable E:\python\python.exe `
  --evidence E:\models\rvm-evidence.json --threads 4 --dry-run
python -m ai_ad_editor media matting --project .\work\demo `
  --asset-id person_source --adapter-id rvm_local --derived-asset-id person_alpha `
  --output assets\derived\person_alpha.mov --max-edge 1280 --dry-run
```

正式执行去掉 `--dry-run`；可用 `--apply --track-id <video-track>` 将派生片段放入视频轨道，`--timeline-start-seconds` 指定开始时间。添加 `--audio-track-id <audio-track>` 才把原声同步放入时间线；不提供时音频保留在 MOV 内，渲染器不会自动混入视频轨道原声。两条目标轨道均提前检查类型与重叠，`--replace-track` 必须显式提供并与 `--apply` 同用，作用于本次指定的视频及音频轨道。输入要求先通过 `media ingest` 摄取并提供 `--asset-id`，以保留源哈希、权利及后续项目包依赖。

默认处理全片，支持 `--start-seconds/--end-seconds`、有理数 `--fps`、`--max-edge`（0 为保留显示尺寸）、`--max-frames`、`--timeout-seconds`、`--cancel-file` 与 `--no-audio`。无效范围、参数、源哈希变化、输出已存在、错误轨道、权利依赖缺失应在推理前拒绝；dry-run 不写快照、缓存或输出。输出必须是项目内尚不存在的 `.mov`。

## 3. 像素与时钟

解码器输出显示方向归一化、方形像素 RGBA；普通媒体的输入 alpha 为 1。逐帧 RGB 归一化到 0..1，四个循环状态由零张量初始化并在每帧之后传递，任务之间重置。保留模型前景颜色和连续软 alpha，输出 alpha 为预测 alpha 乘输入 alpha，采用 straight alpha；不进行阈值二值化或逐帧 min/max 重标定。

输出为 QTRLE/ARGB MOV 无损 8-bit RGBA 中间素材，支持现有 FFmpeg 时间线合成。帧数为选定源时长乘输出 fps 后向上取整，实际输出时长为帧数/fps；VFR 明确重采样为 CFR，并记录警告。短于完整一帧的片尾使用末帧延伸，不能静默截断超预算输入。旋转与 SAR 归一化、缩放、实际尺寸和源/输出时钟进入报告。该引擎按 SDR RGB 处理，HDR 源应先显式 tone map，不能静默转换并宣称 HDR 等价。

默认保留第一条音频流为 PCM，并按视频源起点、选定范围和实际输出时长对齐、补齐/截断；`--no-audio` 显式去音频。该路径保留音频内容和时钟，不承诺原压缩码流字节相同。

## 4. 资源、校验与恢复

三个原生子进程组成有界管道：FFmpeg 解码 → Python ONNX 推理 → FFmpeg 编码。缓存保存请求、进度、报告和待发布编码文件，不保存整片未压缩帧。Windows Job Object 在父任务退出时清理已加入的子进程；它是原生进程管理机制。取消、超时和任一阶段失败均停止全部管道并清理本次临时输出。范围、帧数、输出尺寸和循环状态有明确上限，超限报错，不降帧或改用网络。循环状态合计上限 256 MiB、单状态 128 MiB；输出画幅上限 16,777,216 像素，单边 8192；默认 18,000 帧可显式调整至 1,728,000 帧，源媒体和输出仍受项目单文件 2 GiB/两小时时长约束。worker 报告上限 128 KiB。

worker 校验输出形状、类型、有限值、循环状态预算和实际帧数。编码完成后重新解码全部 RGBA，摘要必须等于 worker 输出原始 RGBA 摘要；再核对视频尺寸、帧率、帧数与音频时钟。源、模型和 FFmpeg 哈希在执行前后核对。只有这些检查通过才以 Windows 拒绝覆盖的 rename 发布 MOV；输出路径在运行期间被外部编辑器创建时保留外部文件并失败。随后登记视频资产、权利台账、报告和操作记录；保存失败时由事务恢复元数据并删除本次输出。

## 5. 权利与验收

派生视频 Rights Ledger 依赖源素材和模型 manifest，并继承源素材的许可字段。代码许可、模型权重许可和源素材许可分别记录，不能由一次推理成功推定商业授权。`commercial_ad` 门禁须继续阻断未核验依赖。

验收需覆盖循环状态传递、软 alpha/已有 alpha、错误模型/协议/哈希、帧数与范围、换背景像素、音频对齐、取消/超时/失败清理、dry-run/幂等、快照/项目包和权利阻断。真实模型另测连续人物素材并目视检查；单一静态人像加运动只证明管道，不代表头发、快速运动、遮挡或真实广告广泛质量通过。保留 `MATTING_MODEL_REVIEW_REQUIRED`。强杀或断电的恢复仍遵循既有元数据事务范围；已发布大媒体可能成为孤立文件，须按恢复报告复核，Job Object 不提供媒体文件事务。

上游接口依据：[RVM 官方推理文档](https://github.com/PeterL1n/RobustVideoMatting/blob/master/documentation/inference.md)及[官方仓库](https://github.com/PeterL1n/RobustVideoMatting)。检索日期为 2026-10-16；本实现独立编写控制与集成逻辑，具体权重哈希和许可证据随本地登记保存。
