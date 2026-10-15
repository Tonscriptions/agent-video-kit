# 本地长滤镜图与 Windows 命令长度契约 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-LONG-FILTER-GRAPH-001 |
| 状态 | 有效 |
| 日期 | 2026-10-15 |

动态裁切、密集跟踪关键帧和复杂效果会生成较长的 FFmpeg filtergraph，不能依靠减少关键帧来规避 Windows CreateProcess 的命令行上限。执行计划按 `subprocess.list2cmdline` 的 UTF-16 单元数（含终止符）估算参数长度，超过 28,000 时把完整图外置。

图文件使用 UTF-8 无 BOM，存于项目 `cache/render-filtergraphs/<SHA256>.ffgraph`，内容摘要必须与文件名及 manifest 一致。执行命令以 FFmpeg 的 `-/filter_complex <文件>` 读取，当前验收版本为原生 FFmpeg 8.1；不自动替换或下载 FFmpeg。已有同名文件摘要不一致时返回 `RENDER_FILTER_GRAPH_HASH_MISMATCH`，保留既有成片。

dry-run 返回完整逻辑图、执行命令与 `filter_graph_transport`，不会写入图缓存。正式渲染原子创建缓存，允许相同内容复用。图缓存属于可再生项目缓存，不纳入项目包；manifest 同时保留完整 `filter_complex` 和 SHA-256，以便缓存缺失时重建。续跑从原项目和设置重新构图，继续执行既有输入指纹门禁。

`filter_graph_transport` 记录 inline/local-file 模式、UTF-8 字节数、图摘要、逻辑命令长度；文件模式另含本地路径和执行命令长度。移除图参数后仍超过 28,000 单元时返回 `RENDER_ARGUMENT_LIMIT`，要求调用方拆分输入序列，不启动 FFmpeg 或静默丢弃输入。

验收包含中文项目路径、32 点动态裁切、真实 FFmpeg 编码、图文件/manifest 一致性、dry-run 不写缓存、缓存篡改拒绝和既有输出保留。真实 YOLO 样例另复现并修复原 WinError 206，保留原失败记录和成功续跑证据。
