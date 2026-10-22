<!-- R16-OPENFILM-025-REUSE -->
### R16 OpenFilm 0.2.5 可拆模块复核（研究）

固定 `af5756a…` /v0.2.5，采集时 **1,844 stars /179 forks**；相对 R15 新增 **3 提交 /70 文件**，本地逐项核验 **788 源文件**。已有 HTML/字幕/模板字段/看帧等适配继续复用；新增池/转码/导出修复按现有内核接口接入。

| 编号 | 本次执行 | 实际结果与边界 | 证据 |
|---|---|---|---|
| R16-01 | 上游纯模块测试 | **45 通过 /1 跳过 /0 失败**；35 原始 MJS＋6 TS 响度＋4 mock 池；不累计产品回归 | [执行收据](docs/validation/evidence/openfilm-reuse-20261022-r16/tests-r1/verification.json) |
| R16-02 | 7 组边界观察 | 池未内建全局容量；代理 key 仍未绑定内容；alpha/NLE 只验规划，音频只验图，色彩只验参数 | [原输出](docs/validation/evidence/openfilm-reuse-20261022-r16/tests-r1/source-observations.stdout.txt) |
| R16-03 | 复用及预算 | 新池 3–6、代理去重 3–5 人日；条件性 NLE 8–15、自有 Agent 图片预算 2–4 人日。均为估算，存在共享工程，不是已节省工时 | [编号模块/取舍/成本](docs/OpenFilm_0.2.5可拆模块与复用成本评估_2026-10-22.md) |
| R16-04 | 产品/执行边界 | 282 main 产品输入前后相同；未新装依赖、未启动浏览器/GUI、未调用 provider/模型、未新增视频/GIF。完整剪映目标仍未完成 | [固定源码收据](docs/validation/evidence/openfilm-reuse-20261022-r16/capture-r2/verification.json) |
| R16-05 | 历史失败与媒体 | 保留首次 compare 字段误读失败；既有 V79 原片/GIF 属历史实测，不列作本轮媒体 | [失败](docs/validation/evidence/openfilm-reuse-20261022-r16/capture-r1/verification.json) · [V79 原输入](docs/assets/html-components-20261021-v79-native-r2/original.mp4) · [V79 GIF](docs/assets/html-components-20261021-v79-native-r2/comparison.gif) |

<!-- /R16-OPENFILM-025-REUSE -->
