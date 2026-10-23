# 连续浮点 1D LUT 与组合 shaper 实测

日期：2026-10-23。本轮通过发布前完整门禁；仍有下列能力/质量边界。

## 1. 实现

新增独立 1D CUBE（每通道 2–65,536 点）与 Resolve 1D→3D 组合 shaper，复用项目 LUT 注册、明确输入/输出信号、原作者强度关键帧、线性混合及共享正式/预览内核。支持 1D nearest/linear/cosine/cubic/spline，3D 保留原五种插值；输入范围明确归一化，输出保留 Float32 过冲与 alpha 位。

## 2. 实际证据

- **V112.1** 1D 五种插值、25 个 1D/3D 原生对照、注册、时钟及正式/预览/PCM/PNG16。通过：118 项；[原始记录](evidence/float-shaper-20261023-lab/native-r2/verification.json)。
- **V112.2** 首轮源码回归：118 项，2 失败、0 错误、0 跳过；用例修正后 3 项边界复核通过。历史失败保留；[原始记录](evidence/float-shaper-20261023-lab/fixture-correction-r1/verification.json)。
- **V112.3** 原创 20 帧/2 秒、320×180，2 个正式渲染和 3 个独立预览 CLI；完整与选区 PCM、PNG16。通过；[原始记录](evidence/float-shaper-20261023-lab/media-r1/verification.json)。
- **V112.4** 3 个 3840×2160 单帧、8 次公开 CLI；每项正式输入与预览、独立行参考。通过；[原始记录](evidence/float-shaper-20261023-lab/4k-r1/verification.json)。
- **V112.5** 8 个离线 wheel、197 源码/包/安装资源及 NumPy 原始文件，安装后 118 项相关回归。通过：118 项；[原始记录](evidence/float-shaper-20261023-lab/installed-r1/verification.json)。
- **V112.6** 完整回归目标 2,930；发现方法数与实际运行通过数分别记录。通过：2930 项；[原始记录](evidence/float-shaper-20261023-lab/full-r1.json)。
- **V112.7** 5 个时刻/10 面板静态目检；未连续播放或听审。已静态查看；[原始记录](evidence/float-shaper-20261023-lab/static-review-r1/verification.json)。

当前源码：118 项、848.077 秒、0 失败/0 错误/0 跳过；冻结输入 331 项。

真实 CLI：20 次子进程调用，31 项检查；2,419,200 个选区 RGB 值最大绝对误差 0，预设上限 2e-6。完整 96,000 与选区 67,200 个立体声采样帧按字节核验；PNG16 按既有 1 码上限核验。

4K：实际完成 3 个单帧案例，比较 99,532,800 个 RGBA 分量；最大误差 0。这不是连续 4K 动画、吞吐或总 RSS 验收。

## 3. 原片、成片与来源

- [原片](../assets/float-shaper-20261023-r1/original.mp4)
- [正式成片](../assets/float-shaper-20261023-r1/edited.mp4)
- [实际预览](../assets/float-shaper-20261023-r1/range.mp4)
- [GIF](../assets/float-shaper-20261023-r1/comparison.gif)
- [作者项目](../assets/float-shaper-20261023-r1/author-project.json)
- [版权记录](../assets/float-shaper-20261023-r1/rights-ledger.json)
- [原创素材声明](../assets/float-shaper-20261023-r1/LICENSE.txt)

所有新 LUT、图像、合成音频均由当轮本地脚本原创生成，声明 CC0-1.0；未调用模型或线上推理。[独立数学与表生成](../../scripts/shaper_media_oracle.py)、[CLI 复现](../../scripts/smoke_float_shaper_media.py)、[4K 复现](../../scripts/smoke_float_shaper_4k.py)。

## 4. 失败保留与边界

首轮实际 118 项、803.659 秒、2 失败、0 错误、0 跳过，331 输入前后相同。极值十进制超出解析范围，以及把采样式 Bezier 误作精确中点，均为当轮新用例设置错误；修正用例后先独立核验三项边界，再从头执行相关套件。运行时和像素误差阈值没有为修正用例而改变。原日志、执行源码与[修正说明](evidence/float-shaper-20261023-lab/fixture-correction-r1/verification.json)保留。

注册库元数据仅为保守计数/范围信息；严格渲染准入仍由有界 CUBE 解析器完成。DOMAIN 与 Resolve INPUT_RANGE 混用、组合文件 DOMAIN、缺失/多余/非有限数据和预算超限明确拒绝。完整 4K 连续播放/自然质量/听审、HDR、ICC、逆 LUT、非均匀表、`.3dl/.csp/.dat` 和剪映等价均未验收。


本轮旧 R2 完整回归与发布 owner 在套件启动前消失，尚未执行完整方法；保留[原状态与中断记录](evidence/float-shaper-20261023-lab/execution-interruption-r1/verification.json)。源码 118 和安装 118 的成功证据不变；新 owner 仍等待实际父版本发布后才执行完整回归。

恢复 owner 首次仍引用旧父 owner 名称，因旧记录已封存而在启动套件前被拒绝；[R3 原状态与引用修正](evidence/float-shaper-20261023-lab/owner-reference-r1/verification.json)保留，实际方法数为零。产品源码及已通过的源码/安装收据不变。
[完整契约与一手格式来源](../specs/连续浮点1D-LUT与组合shaper契约_v0.1_2026-10-23.md)；[固定 tag/blob SHA、文件哈希与许可证](evidence/float-shaper-20261023-lab/source-reference-r2/verification.json)。上游 C/C++ 为参考快照，没有复制进入运行时。

父版本已通过 2,897 项全量，但首次发布因空树暂存检查把历史空白认作新增而停止，未修改主工程。因此本版本此前完整回归尚未启动，安装 118 项成功收据保持有效。另开所有者复用已有成功收据，在父版本真正发布后才执行本版第一次完整回归；原失败链完整保留。[父暂存恢复记录](evidence/float-shaper-20261023-lab/parent-stage-recovery-r1/verification.json)。
