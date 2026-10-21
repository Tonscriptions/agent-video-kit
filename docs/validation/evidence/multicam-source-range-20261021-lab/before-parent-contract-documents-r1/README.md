# 多机位源覆盖与原速同步独立候选

**状态：专项与真实 CLI/隔离实验通过，完整回归、变基与 main 发布待完成。**

这是独立候选。只在 Windows 原生工具上执行，所有新内容留在 E 盘；没有 Docker、WSL、容器、虚拟环境、浏览器调用或依赖下载。

同步仍为既有 50 Hz 能量包络的有界互相关。固定源公式为 `source_time = reference_time + relative_delay_seconds`。本轮修复的是覆盖缺失时如何规划素材，不改变同步估计算法，也不估计长片设备时钟漂移。`0.2.0` 为多机位局部协议版本，CLI 总版本保持原状。

NumPy 附加复制是本轮实验安装步骤，不是已发布的用户安装器功能；基本七 wheel 包没有 NumPy。原生和隔离程序分别实际执行，父进程的 Pillow 仅用于生成/检查证据。没有使用系统 Python 路径代替隔离产品模块。生成的声道为合成音，不以完整 PCM 相等声称声音自然或已听审。

独立 RGBA/PCM 参考来自源帧卡和确定性合成音。编码 MP4 只核验帧身份色块和 PTS；不声称完整编码 RGBA/PCM 相等。GIF 为观看副本，声音以视频/原始文件为准，未连续播放或听音。

| 编号 | 实际核验 | 结果与证据 |
|---|---|---|
| MC-01 | 修复前复现 | 3 个方法：1 个完整覆盖控制通过，2 个部分覆盖断言失败；旧代码自动钳制源起点或慢放，改变事件同步。[原始失败](docs/validation/evidence/multicam-source-range-20261021-lab/before-r1.json) |
| MC-02 | 当前专项 | 22 项 / 20.793 秒 /0 跳过，包含最初 3 项；15 个规划方法与 7 个实际双机位 CLI/渲染方法。[当前收据](docs/validation/evidence/multicam-source-range-20261021-lab/after-r3.json) |
| MC-03 | 既有兼容控制 | 原有 AAC 延迟 0.5 秒、按 1 秒轮换及应用快照控制 1 项 / 3.734 秒；与上行合计 23 个不同方法。[收据](docs/validation/evidence/multicam-source-range-20261021-lab/compatibility-r2.json) |
| MC-04 | 公开 CLI | 15 次 CLI＋11 条其他原生命令，26 条执行命令、23 个检查；原生源 50 帧/2 秒，相机 B 36 帧/1.44 秒。[完整 argv 与检查](docs/validation/evidence/multicam-source-range-20261021-lab/native-r1/verification.json) |
| MC-05 | 默认拒绝与显式 trim | 同一原始事件覆盖 0.4..1.84 秒；默认拒绝不写项目/报告/快照，trim 保留 1 倍速，前 10 帧和后 4 帧留空。[原输入](docs/assets/multicam-source-range-20261021-lab/native-r1/source-reference.mkv) · [短机位](docs/assets/multicam-source-range-20261021-lab/native-r1/source-camera.mkv) |
| MC-06 | 完整画面/PCM/PTS | 无损预览 50 帧、11,520,000 RGBA 字节与独立原始帧卡逐字节相同；显式主音轨 768,000 f32 字节、每声道 96,000 样本完全相同；两个 MP4 的全部 50 个 PTS 均为 n/25。[无损原文件](docs/assets/multicam-source-range-20261021-lab/native-r1/trim-lossless.nut) |
| MC-07 | 显式 stretch | 仅显式选择后保留旧填充行为；0.72 倍速把短机位填满 2 秒，并警告事件同步改变。实际第一帧显示事件 10，替代原本空档；不能作为同步正确的结果。[实际 MP4](docs/assets/multicam-source-range-20261021-lab/native-r1/stretch.mp4) |
| MC-08 | 应用边界 | 锁轨在音频分析前拒绝；dry-run 做音频分析但不写项目/报告；小于一个时间刻度的片段拒绝，不虚构 1 tick；原计划重叠不会因裁切而放行，较长作者时长保留。[专项](docs/validation/evidence/multicam-source-range-20261021-lab/after-r3.log) |
| MC-09 | 实际隔离安装 | 161 产品资源 source/wheel/site 相同；基础 7 wheels，另按现有 NumPy 2.4.2 安装 RECORD 复制 933 文件到 E 盘。18 次隔离 CLI＋1 来源进程/14 模块、12 安装检查，再通过同样 23 媒体检查。[安装与附加依赖](docs/validation/evidence/multicam-source-range-20261021-lab/installed-r1/verification.json) |
| MC-10 | 可视证据与 Skill | 原生/隔离共 22 文件、8 GIF；输出 GIF 从实际 MP4 解码。查看一张边界联系表，隔离图与其字节相同。4 份 video-cut Skill 草稿通过 quick_validate，尚未注册。[静态目检](docs/validation/evidence/multicam-source-range-20261021-lab/frame-review-r1.json) · [草稿](docs/validation/evidence/multicam-source-range-20261021-lab/skills-draft-r1.json) |
| MC-11 | 保留开发失败 | 扩展初轮 22 项中 4 失败/3 错误：发现 CLI 声称接受数组却调用仅对象 loader 的真实问题，另修复测试对 errors 数组的访问。原源码和日志保留；兼容控制首轮收据未识别单数 test，r2 修复并重跑。[失败原文](docs/validation/evidence/multicam-source-range-20261021-lab/after-r2.log) · [保全输入](docs/validation/evidence/multicam-source-range-20261021-lab/after-r2-failed-inputs/sha256.json) |
| MC-12 | 尚未验收/发布 | 此候选未执行完整回归、未合入 main、未推送或注册 Skill。无漂移估计、视觉/发言人导演；container duration 不代表视频流真实 EOF。长片、密集切换、峰值 RSS、自然/HDR、听审与完整剪映等价均未验收。父候选更新旧 CLI 时钟断言后仍需显式变基与新冻结收据。 |

| 原始事件 | 实际 trim 原速留空 | 实际显式 stretch |
|---|---|---|
| ![原始事件](docs/assets/multicam-source-range-20261021-lab/native-r1/source-reference.gif) | ![实际 trim](docs/assets/multicam-source-range-20261021-lab/native-r1/trim.gif) | ![实际 stretch](docs/assets/multicam-source-range-20261021-lab/native-r1/stretch.gif) |

[原始 MKV](docs/assets/multicam-source-range-20261021-lab/native-r1/source-reference.mkv) · [实际 trim MP4](docs/assets/multicam-source-range-20261021-lab/native-r1/trim.mp4) · [实际 stretch MP4](docs/assets/multicam-source-range-20261021-lab/native-r1/stretch.mp4) · [边界联系表](docs/assets/multicam-source-range-20261021-lab/native-r1/trim-event-boundaries.png)。原始 GIF 50 帧/2000 ms、短机位 36 帧/1440 ms；实际 trim GIF 合并为 38 帧/2000 ms，stretch 为 36 帧/2000 ms。

[契约](docs/specs/多机位源覆盖与显式缺口策略_实验_v0.1_2026-10-21.md) · [完整实验](docs/validation/多机位源覆盖与原速同步独立实验_2026-10-21.md)
