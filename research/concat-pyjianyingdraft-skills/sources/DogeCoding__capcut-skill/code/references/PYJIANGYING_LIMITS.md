# pyJianYingDraft（PyPI）能力与限制摘要

本 Skill 通过 **`pip install pyJianYingDraft`** 生成剪映可打开的草稿，行为以该库文档为准（作者 GuanYixuan，与参考仓库无代码依赖）。

## 已验证方向

- **新建草稿**、添加本地视频/音频、**导入 SRT 字幕**、多轨与特效等：见库 README。
- **跨平台**：macOS / Linux 可 **生成草稿**；库内 **Windows 专用** 的 `JianyingController` 自动导出在 macOS 上不可用。
- **剪映 6+ 模板**：若 `draft_content.json` 被加密，**模板模式**可能无法加载；**从零 `create_draft` 生成**一般仍可用于较新版本（以你本机剪映实测为准）。

## 使用建议

- 生成草稿后若列表未刷新：**重启剪映**或进出一次其它草稿。
- 竖屏工程：`--width 1080 --height 1920`（或 720×1280）。
- 自动导出：在 Mac 上请 **手动在剪映内导出**；或自行使用其它自动化（AppleScript 等），不在本 Skill 保证范围内。
