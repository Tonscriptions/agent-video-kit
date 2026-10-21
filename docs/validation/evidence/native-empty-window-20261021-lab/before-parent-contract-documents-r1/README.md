# 原生空视频选区独立实验

此独立实验基于尚未发布的嵌套原生时钟候选，继续修复有效素材选区完全落在首帧前或实际视频 EOF 后的行为。当前 256 产品输入；专项已完成，尚未完整回归、合入 main 或发布。

| 编号 | 实际检查 | 结果与边界 | 证据 |
|---|---|---|---|
| EW-E01 | 修复前后同一 8 项原生测试 | 修复前 2 项普通正放通过、6 项报错；修复后同一断言 8 项通过。原始源码和测试快照保留。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/before-r2.json) |
| EW-E02 | 有声输入与未知 EOF | 16 项、41.686 秒、0 跳过；6 项显式音频轨的 72,000 每声道采样与独立参考逐字节一致；未知尾帧时长拒绝。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/after-r3.json) |
| EW-E03 | 相关回归 | 293 个不同方法、0 跳过；37 索引＋50 倒放＋63 序列＋22 预览＋105 嵌套＋16 空区间。32 个新嵌套方法包含于 105，16 项包含于 293。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/related-r2.json) |
| EW-E04 | 公开 CLI 与真实导出 | 17 CLI＋18 原生命令、23 检查；两个 320×180 输出各 45 帧/30000÷1001 fps，完整无损 RGBA 10,368,000 字节及 PCM 576,000 字节均与独立参考一致。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/native-r2/verification.json) |
| EW-E05 | 索引与拒绝行为 | 首次索引扫描 1 次、再次 0 次；故意损坏索引报 NATIVE_INDEX_CORRUPT/exit 6，未产生成片。计数不含最终解码、编码和 SHA 文件读取。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/native-r2/corrupt-index-empty-window-rejected.stdout.log) |
| EW-E06 | 离线隔离安装 | 161 资源源码/wheel/site 字节一致，7 个已有依赖 wheel；20 隔离 CLI＋1 来源进程/11 模块，同样完整画面与 PCM 参考一致。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/installed-r1/verification.json) |
| EW-E07 | 保留失败 | 最初空参考项目缺视频轨；有声扩展漏建音频轨；相关回归首次缺 8 个外部夹具，套件未启动；首个 CLI 请求复用 ID，被验证器拒绝。修正均未放松产品拒绝规则。 | [记录](docs/validation/evidence/native-empty-window-20261021-lab/fixture-recovery-r1.json) |
| EW-E08 | 完整回归与发布边界 | 此 256 输入候选尚未完整回归、未合入 main、未推送。父级嵌套 255 输入候选的完整回归不算本候选验收。自然/HDR、非单位变速音频、长片、总 RSS 和完整剪映等价未验收。 | [记录](docs/specs/原生视频空区间契约_实验_v0.1_2026-10-21.md) |

| 原始八帧内容 | 实际普通倒放空尾段 | 实际嵌套正放空前段 |
|---|---|---|
| ![原始八帧](docs/assets/native-empty-window-20261021-lab/native-r2/source-cards.gif) | ![实际尾段](docs/assets/native-empty-window-20261021-lab/native-r2/direct-reverse-tail.gif) | ![实际前段](docs/assets/native-empty-window-20261021-lab/native-r2/nested-forward-prefix.gif) |

输入 GIF 仅显示原始 8 帧/320 ms。[原始短视频＋2 秒声音 MKV](docs/assets/native-empty-window-20261021-lab/native-r2/source-audio-tail.mkv) 与 [视频延迟 1 秒的 MKV](docs/assets/native-empty-window-20261021-lab/native-r2/source-delayed-video.mkv) 保留真实流时钟。两段输出 GIF 来自实际 MP4 的全部 45 帧，因下层图像不变而合为 1 帧/1500 ms；MP4 为 30000/1001 fps，作者总时长 1.5 秒，最后视频显示边界可至 1.5015 秒。GIF 无声音且时间只能落在 10 ms 网格。

[实际普通倒放 MP4](docs/assets/native-empty-window-20261021-lab/native-r2/direct-reverse-tail.mp4) · [实际嵌套正放 MP4](docs/assets/native-empty-window-20261021-lab/native-r2/nested-forward-prefix.mp4) · [静态抽帧目检记录](docs/validation/evidence/native-empty-window-20261021-lab/frame-review-r1.json)。完整无损画面与音频是自动核验；只查看两张实际抽帧，未连续播放、未听音。MP4/AAC 与 GIF 为观看副本，未声称编码全像素或有损声音逐字节相同。

[实测报告](docs/validation/空视频选区与显式音频保留独立实验_2026-10-21.md) · [实验契约](docs/specs/原生视频空区间契约_实验_v0.1_2026-10-21.md)
