# AI广告剪辑项目约定

- 后续项目内容在 `E:/dev/sandbox/AI广告剪辑/` 下构建，按任务建立子目录。
- 项目文档、评估报告、需求、架构、路线图、验收记录和研究结论统一放在 `E:/dev/sandbox/AI广告剪辑/docs/`；根目录仅保留工作区约束、脚本、安装清单和运行配置。
- 严禁调度本地 Docker、WSL、容器或其他虚拟化环境；使用原生 Windows 工具。
- 使用浏览器完成调用后，关闭所有不用的 tab，释放内存。
- 本项目下载并注册的本地 Skills 统一使用 `video-cut-` 前缀，调用形式为 `$video-cut-技能名`。
- 可编辑技能正文、脚本与资源保存在 `skills/`；`C:/Users/carzy/.codex/skills/` 中的对应项是 Windows 目录联接，供 Codex 发现技能。
- 原始仓库快照与 ZIP 保存在 `sources/`，版本、来源与安装映射见 `video-cut-install-manifest.json`。
- Git 主分支使用 `main`，`origin` 固定为 `git@github.com:Tonscriptions/agent-video-kit.git`。每轮产品更新同时维护根目录 `README.md` 和相关 `docs/` 文档，通过验证后提交并自动推送；首轮初始化已按用户要求 force push，后续使用普通推送。
