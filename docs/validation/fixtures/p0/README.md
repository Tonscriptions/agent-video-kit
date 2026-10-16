# P0 Fixture 目录

| 项目 | 内容 |
|---|---|
| 文档编号 | VALIDATION-FIXTURE-001 |
| 状态 | 有效 |
| 日期 | 2026-10-13 |
| 关联计划 | [P0黄金样例与验收计划_v0.1_2026-10-13.md](../../P0黄金样例与验收计划_v0.1_2026-10-13.md) |

本目录预留 P0 黄金样例。当前只提交目录规则，不提交未经核验版权的媒体文件。

每个样例使用独立目录，并至少包含：

```text
<fixture-id>/
├─ input/              # 固定输入媒体或生成脚本
├─ project.json        # Agent Project JSON
├─ request.json        # CLI 请求或变更集
├─ expected.json       # 结构、状态和质量期望
├─ commands.txt        # 原生 Windows 复现命令
└─ README.md           # 来源、许可证、哈希和人工检查说明
```

样例媒体必须先写入 Rights Ledger。生成式测试媒体也要保存生成脚本、工具版本和输入参数。样例完成后，把结果报告放在 `docs/validation/`，不要把临时渲染文件提交到文档目录。经过来源/发布权利和大小核对的固定演示允许发布到 `docs/assets/<批次>/`，同时提交摘要、复现脚本与核验记录；见 [README 功能核验与实测演示](../../README功能核验与实测演示_2026-10-16.md)。

当前可复现的临时 P0 fixture 由 [`product/tests/test_cli.py`](../../../../product/tests/test_cli.py) 在测试运行时用 FFmpeg `lavfi` 生成，不把媒体文件写入仓库；对应命令和边界见 [产品实现入口与 P0 使用说明](../../../产品实现入口与P0使用说明_v0.1_2026-10-13.md)。
