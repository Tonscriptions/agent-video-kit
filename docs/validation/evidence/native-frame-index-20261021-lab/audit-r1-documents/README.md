# agent-video-kit 原生帧索引独立实验

此目录用于原生帧索引缓存实验，尚未合入 main。主线仍以已发布 README 的版本及完整回归为准。

<!-- NATIVE-INDEX-LAB-20261021 -->
| 编号 | 实际构建/核验进度 | 结果与边界 |
|---|---|---|
| NI-E01 | 原生时间索引、渲染/预览复用、清理 | 37 方法通过；254 输入不变。减少命中时的源帧扫描，保留 VFR 与小数源区间 |
| NI-E02 | 既有倒放缓存清理 | 13 方法通过；属于倒放专项子集，不重复累计 |
| NI-E03 | 倒放、嵌套与预览相邻检查 | 50＋63＋22 方法通过；与 37 项组成 172 个不同方法，均 0 跳过；13 项清理不重复累计 |
| NI-E04 | 实际 4K 输入、成片及缓存重建 | 17 CLI /26 原生命令 /24 检查通过；8 帧/0.32 秒，原生像素和独立无损预览一致；二次渲染源索引扫描计数为 0 |
| NI-E05 | 离线隔离安装 | 161 资源/7 现有 wheels、20 隔离 CLI＋1 来源探针通过，10 模块位于安装目录 |
| NI-E06 | 完整回归与发布 | 尚未执行该实验版本完整回归，尚未合入或推送；不代表剪映等价、长片/RSS/HDR/自然质量已验收 |

[详细核验与证据](docs/validation/原生帧索引缓存独立实验_2026-10-21.md) · [格式与 CLI 契约](docs/specs/原生帧索引缓存契约_实验_v0.1_2026-10-21.md) · [原视频](docs/assets/native-frame-index-20261021-lab/native-r1/source-review.mp4) · [实际成片](docs/assets/native-frame-index-20261021-lab/native-r1/reverse-review.mp4)。

| 实际编码源 | 实际编码输出 |
|---|---|
| ![原输入](docs/assets/native-frame-index-20261021-lab/native-r1/source.gif) | ![实际输出](docs/assets/native-frame-index-20261021-lab/native-r1/reverse.gif) |

GIF 为实际 MP4 解码结果，8 帧/320 ms；已静态抽帧目检，未连续播放或听音。全源 SHA 读取仍然存在，源索引扫描计数不代表整个流程零解码。
<!-- /NATIVE-INDEX-LAB-20261021 -->
