# Agent Video Kit 文档 / Documentation

[中文 README](../README.md) · [English README](../README.en.md) · [Release](https://github.com/Tonscriptions/agent-video-kit/releases/tag/v0.1.0-alpha.1)

当前入口以 `v0.1.0-alpha.1` 为准。首版关闭本地 CLI 试用闭环；完整剪映等价仍未验收。Release-specific onboarding is bilingual; historical research and specifications are mainly Chinese.

| 阅读目标 / Goal | Document |
|---|---|
| 安装、结构、命令、渲染路径、故障与恢复 / Install and operate | [USAGE](releases/v0.1.0-alpha.1/USAGE.md) |
| 17 个 Skill 的输入输出和组合 / Skill routing | [SKILLS](releases/v0.1.0-alpha.1/SKILLS.md) |
| 原视频、输出、GIF、响应与复现 / Complete examples | [CASES](releases/v0.1.0-alpha.1/CASES.md) |
| 范围、验收、风险与下一阶段 / Release scope and gates | [RELEASE](releases/v0.1.0-alpha.1/RELEASE.md) |
| 许可与依赖 / Notices | [THIRD_PARTY](releases/v0.1.0-alpha.1/THIRD_PARTY.md) |
| 本地案例阅读页 / Local documentation gallery | [Demo page](demo/index.html), serve locally as described in CASES |
| 需求与路径基线 / Product baseline | [产品需求与开发路线基线](产品需求与开发路线基线_2026-10-12.md) |
| 模块边界 / Architecture | [系统边界与模块契约](architecture/系统边界与模块契约_v0.1_2026-10-13.md) |
| Agent Project 合同 / Schema | [JSON schema](specs/agent-project.schema.json) |
| 当前基线完整回归 / Frozen baseline | [2930-method receipt](validation/evidence/float-shaper-20261023-lab/full-r1.json) |
| 本轮发布验证 / New release checks | [Release gate](validation/evidence/release-v0.1.0-alpha.1-r2/release-verification.json) |
| 远端发布与 6 个附件下载核验 / Published assets verified | [Publication receipt](validation/evidence/release-v0.1.0-alpha.1-r2/publication.json) |
| 历史编号功能与核验 / Complete historical numbered checks | [Archived README](releases/v0.1.0-alpha.1/history/README.zh.pre-release.md) |
| 历史全部文档入口 / Historical document catalog | [Archived index](releases/v0.1.0-alpha.1/history/docs-index.pre-release.md) |

专项合同保留在 `specs/`，真实实测和失败记录在 `validation/`，媒体在 `assets/`，第三方来源在 `third-party/`，版本发布文档在 `releases/`。不将历史测试、当轮案例和研究检查累计为一个“完成度”。
Contracts remain in specs; raw successes/failures in validation; media in assets; upstream evidence in third-party; milestone guides in releases. Historical tests, new cases and research checks retain separate scopes.
