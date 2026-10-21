# 多机位原生视频覆盖实验

状态：**独立候选，未合入 main、未推送、未注册 Skill**。当前 258 输入的相关回归 104 方法、244.335 秒、0 跳过；实际原生与新离线安装媒体均通过。完整 2019 方法仅为未来预计数量，尚未启动，须先绑定真实发布的 V86 父版。这里不是完整剪映验收。

| 编号 | 实际执行 | 结果与边界 | 证据 |
|---|---|---|---|
| SV-01 | 父输入与当前代码 | 257 父输入；只修改 multicam/cli/capabilities，并新增 24 方法；当前 258 输入 | [创建记录](docs/validation/evidence/multicam-stream-coverage-20261021-lab/foundation-r1.json) |
| SV-02 | 修复前/后同断言 | 原 8 方法：修复前 1 控制通过、7 方法失败，共 9 断言；修复后 8/8 通过 | [修复前](docs/validation/evidence/multicam-stream-coverage-20261021-lab/before-r2.json)、[修复后](docs/validation/evidence/multicam-stream-coverage-20261021-lab/after-r1.json) |
| SV-03 | 当前相关回归 | 104 个不同方法；24 本实验＋22 父多机位＋16 空选区＋32 嵌套时钟＋10 既有 CLI。完整套件子集，旧 102 不累计 | [当前收据](docs/validation/evidence/multicam-stream-coverage-20261021-lab/related-r2.json) |
| SV-04 | 当前原生真实媒体 | 33 CLI＋25 其他命令、54 检查；两组完整 50 帧 RGBA 各 11,520,000 字节、显式 PCM 各 768,000 字节独立一致 | [原生收据](docs/validation/evidence/multicam-stream-coverage-20261021-lab/native-r1/verification.json) |
| SV-05 | 新离线隔离安装 | 161 资源源码/包/安装同字节，36 CLI＋1 次 14 模块来源探针；14 安装检查，媒体另有相同 54 检查 | [安装收据](docs/validation/evidence/multicam-stream-coverage-20261021-lab/installed-r1/verification.json) |
| SV-06 | 缓存与只读 | 真实 dry-run 缓存命中、0 源帧探针；损坏索引明确拒绝，工程/报告/快照不变。仍读取 SHA，不能称 0 I/O | [实际媒体检查](docs/validation/evidence/multicam-stream-coverage-20261021-lab/installed-r1/media/verification.json) |
| SV-07 | 原片/观看副本/GIF | 两组各有原生和隔离安装输出；源 GIF 只呈现 8 解码帧 320 ms，实际 PTS 及 2 秒音轨保存在原 MKV；输出 GIF 来自实际 MP4 解码、2000 ms | [媒体 SHA 清单](docs/validation/evidence/multicam-stream-coverage-20261021-lab/media-manifest-r1.json) |
| SV-08 | 目检及 Skill | 两张边界图静态目检、安装图像素相同；4 个 Skill 增量仅本实验验证，未注册，发布时只合并增量到实际父版 | [静态记录](docs/validation/evidence/multicam-stream-coverage-20261021-lab/static-review-r1.json)、[草稿](docs/validation/evidence/multicam-stream-coverage-20261021-lab/skills-draft-r1.json) |
| SV-09 | 未完成及校验自身失败 | 完整套件、生产合入/17 Skills 总审计与发布未完成；自然多机位/HDR/长片/RSS/漂移/非零音频流起点/播放听审及完整剪映效果未验收。首次汇总因夹具清单文件名错误在写文档前失败；修正为实际 foundation 清单，产品代码及媒体不变 | [独立审计](docs/validation/evidence/multicam-stream-coverage-20261021-lab/audit-r1.json)、[原失败](docs/validation/evidence/multicam-stream-coverage-20261021-lab/finalize-public-media-failed-r1.json) |

原生样例：尾部视频仅 `[0,0.32)` 秒，后续 42 帧保留背景；延迟视频仅 `[1,1.32)` 秒，前 25/后 17 帧保留背景。主音轨均显式保持 2 秒。默认策略拒绝覆盖不足；trim 保持原速与参考事件位置，显式 stretch 的速度为 0.16，保留事件同步变化警告。

| 场景 | 原片 | 原速实际输出 | 显式拉伸实际输出 |
|---|---|---|---|
| 尾部无视频 | [MKV](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/source-tail.mkv) · [源 GIF](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/source-tail.gif) | [MP4](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/tail-trim.mp4) · [GIF](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/tail-trim.gif) | [MP4](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/tail-stretch.mp4) · [GIF](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/tail-stretch.gif) |
| 延迟视频 | [MKV](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/source-leading.mkv) · [源 GIF](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/source-leading.gif) | [MP4](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/leading-trim.mp4) · [GIF](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/leading-trim.gif) | [MP4](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/leading-stretch.mp4) · [GIF](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/leading-stretch.gif) |

![尾部原速输出](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/tail-trim.gif)

![延迟原速输出](docs/assets/multicam-stream-coverage-20261021-lab/native-r1/leading-trim.gif)

完整字节一致仅指无损 RGBA 和显式 PCM；编码 MP4 的全部 PTS 为 n/25，身份色块最大误差为 1，没有声明编码整帧或 AAC 字节一致。GIF 会合并相同黑帧，帧数不是 MP4 帧数。

原素材为本项目原创 CC0 色卡、七段数字矩形及确定性音频，不使用外部字体/图片。基础 7 wheel 不含 NumPy；隔离实验从既有本地 NumPy 2.4.2 只读复制 933 个经 RECORD 核对的文件及许可，不能视为产品安装器已解决 NumPy 发行。

[详细实测](docs/validation/多机位原生视频覆盖独立实验_2026-10-21.md) · [实验契约](docs/specs/多机位原生帧覆盖与只读索引契约_实验_v0.1_2026-10-21.md)。
