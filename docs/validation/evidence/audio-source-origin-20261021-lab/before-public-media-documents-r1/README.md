# 原生音频源起点实验

<!-- AUDIO-RELATED-R1 -->
当前相关回归 **226 个不同方法、508.261 秒、0 跳过**：父候选 104＋新 12＋既有音频 110。259 输入、8 夹具、6 验证脚本前后相同；这是相关子集，不是完整套件。
实际产品 CLI 新媒体正在另行执行，隔离安装、Skill、完整回归及生产发布仍待完成。下表保留较早专项阶段的实际记录，完整状态以本段及对应收据为准。
<!-- /AUDIO-RELATED-R1 -->


状态：独立候选，**未合入 main、未推送、未注册 Skill，尚未完整回归**。多机位协议由父候选 0.3.0 扩展为 0.4.0。当前相同 12 方法全部通过，8.890 秒、0 跳过；当时相关回归仍在运行；现已通过，见文首最新记录。完整 2031 方法只是未来预计数量，须等待真实发布的 V87 父版及新媒体/安装验收。

| 编号 | 实际执行 | 结果及边界 | 证据 |
|---|---|---|---|
| AO-01 | 固定父候选 | 258 父输入、8 既有外部夹具和 3 验证脚本，共 269 文件同字节复制；只改 4 运行时模块并加 12 方法，当前 259 输入 | [创建记录](docs/validation/evidence/audio-source-origin-20261021-lab/foundation-r1.json) |
| AO-02 | 实际修复前观察 | MKV 视频从 0 开始、音频首 PTS=1000、TB=1/1000、容器 3 秒；实际同步误报 0 秒，渲染丢开头静音 | [有效原生观察](docs/validation/evidence/audio-source-origin-20261021-lab/before-r2/observations.json) |
| AO-03 | 相同 12 控制修复前 | 14.337 秒，7 FAIL /1 ERROR /4 通过，0 跳过；R3 报实际源采样数不足。包含原本就通过的零起点、反向及空窗控制 | [原始日志](docs/validation/evidence/audio-source-origin-20261021-lab/before-controls-r1.log) |
| AO-04 | 中间失败保留 | first_pts 修正后 11/12 通过，置信度仍约 .9156；仅改重叠归一化后同一断言仍失败。没有降低 .95 置信度断言 | [中间 r1](docs/validation/evidence/audio-source-origin-20261021-lab/after-controls-r1.json)、[中间 r2](docs/validation/evidence/audio-source-origin-20261021-lab/after-controls-r2.json) |
| AO-05 | 当前相同控制 | 12/12、8.890 秒；测试正文、运行器未改。普通/选区/反向/曲线/嵌套、非零容器原点、实际 R3、同步分别核对 | [当前收据](docs/validation/evidence/audio-source-origin-20261021-lab/after-controls-r3.json) |
| AO-06 | 实际完整 PCM | 3 秒、立体声 48 kHz、1,152,000 float32 字节；原生渲染与“1 秒静音＋原 2 秒 PCM”独立预期全部相同，原内容字节未变 | [修复后观察](docs/validation/evidence/audio-source-origin-20261021-lab/after-r1/observations.json) |
| AO-07 | 同步时钟及置信度 | 实际偏移恢复 1 秒，生成音频得分 1.0；按真实重叠做 Pearson，排除缺少共同前史的首个一阶差分点。不能外推自然音频校准质量 | [原始同步报告](docs/validation/evidence/audio-source-origin-20261021-lab/after-r1/actual-sync.json) |
| AO-08 | 相关回归启动时记录（历史） | 226 个不同相关方法：父候选 104＋新 12＋既有音频 110；6 份脚本与 8 夹具固定，尚未接收终态结果 | [运行收据](docs/validation/evidence/audio-source-origin-20261021-lab/related-r1.json) |
| AO-09 | 尚缺交付 | 没有本候选的新公开 MP4/GIF/音频资产、离线安装、Skill 增量、完整回归或生产发布；不复用父版媒体冒称本轮执行 | [实验契约](docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md) |

[详细原生实测](docs/validation/原生音频起点与同步独立实验_2026-10-21.md) · [作者采样时钟契约](docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md)。
