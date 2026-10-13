"""Write the local Skill inventory and invocation guide from the verified manifest."""
from collections import Counter
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
manifest = json.loads((PROJECT / "video-cut-install-manifest.json").read_text(encoding="utf-8"))
validation = json.loads((PROJECT / "research" / "video-cut-validation.json").read_text(encoding="utf-8"))
assert manifest["status"] == "registered"
assert not validation["failures"] and not validation["unresolved_markdown_links"]
assert all(item["registration_same_file"] for item in validation["skills"])

USES = {
    "ai-video-gen": "文生视频、图生视频与生成服务路由",
    "avatar-video": "数字人口播、多场景讲解视频",
    "create-video": "通过 HeyGen Video Agent 从描述生成视频",
    "ffmpeg": "转码、裁切、缩放、压缩与音频加工",
    "hyperframes-animation": "动效、镜头衔接、场景转场与运行时适配",
    "hyperframes-cli": "HyperFrames 项目、预览、检查与渲染命令",
    "hyperframes-core": "HTML 视频合成结构、时间线与确定性规则",
    "hyperframes-creative": "视觉方向、字体、配色与品牌表现",
    "hyperframes-media": "旁白、配乐、音效、转写与字幕资源",
    "hyperframes-registry": "视频组件与动画区块安装、接线规则",
    "hyperframes": "HTML 视频工作流入口与本地能力路由",
    "media-use": "音乐、音效、图片和图标素材检索与登记",
    "music-to-video": "以音乐节拍驱动的卡点与素材混剪",
    "remotion-to-hyperframes": "已有 Remotion 项目迁移到 HyperFrames",
    "video-download": "通过 yt-dlp 获取视频、音频、字幕与元信息",
    "video-edit": "已有素材裁切、拼接、叠加、变速与成片加工",
    "video-toolkit": "综合制作流程参考；独立运行时尚未配置",
    "video-translate": "视频翻译、配音与多语言版本",
    "video-understand": "抽帧、转写、内容理解与素材分析",
    "website-to-video": "网页捕获与网站展示视频",
    "demo-video": "产品演示、功能展示、广告叙事与场景设计",
    "ad-creative": "广告 Hook、标题、文案与创意变体",
    "campaign-analytics": "归因、漏斗、ROI 与投放效果分析",
    "marketing-demand-acquisition": "获客、预算、渠道与需求增长规划",
    "paid-ads": "广告策略、受众、投放结构与效果优化",
    "video-content-strategist": "视频脚本、短视频策略与长内容再利用",
    "remotion-best-practices": "Remotion 官方总入口，按需求读取完整规则",
    "remotion-captions": "转写、字幕呈现与字幕动画",
    "remotion-create": "创建 Remotion 项目与新视频",
    "remotion-docs": "Remotion 官方 API 文档查询",
    "remotion-interactivity": "可编辑参数与交互式预览结构",
    "remotion-maps": "地图、地理线路与地理动画",
    "remotion-markup": "React 视频结构、动画、布局、字体与媒体",
    "remotion-multimedia": "浏览器媒体处理与 Mediabunny",
    "remotion-render": "导出视频与静态帧",
    "remotion-saas": "基于 Remotion 的应用与视频自动化架构",
    "remotion-studio": "启动和使用交互式预览",
    "remotion-upgrade": "升级框架及相关包的规则",
    "jianying-editor": "剪映工程、素材导入、字幕、动效、录屏与导出",
}

counts = Counter(skill["repository"] for skill in manifest["skills"])
lines = [
    "# video-cut 本地技能使用指南", "",
    "已下载原榜单第 **2 / 8 / 10 / 12** 项的完整源码，并注册 **39 个相关 Skills**。所有新注册技能的目录名、SKILL.md 中的 name，以及界面调用名均以 `video-cut-` 开头。", "",
    "`$` 是调用标记，不属于目录名。例如 `$video-cut-ad-creative` 对应 `skills/video-cut-ad-creative/`。下一轮对话可使用这些调用名。", "",
    "## 常用入口", "",
    "| 需求 | 调用 |", "|---|---|",
    "| 现有素材剪辑、拼接 | `$video-cut-video-edit` |",
    "| BGM 卡点与素材混剪 | `$video-cut-music-to-video` |",
    "| 广告创意与文案建议 | `$video-cut-ad-creative` |",
    "| 视频脚本与短视频规划 | `$video-cut-video-content-strategist` |",
    "| Remotion 视频合成 | `$video-cut-remotion-best-practices` |",
    "| 剪映工程与成片交付 | `$video-cut-jianying-editor` |", "",
    "可复制的调用示例：", "",
    "```text",
    "$video-cut-ad-creative 为这款产品设计 5 个短视频广告开头和创意角度。",
    "$video-cut-video-edit 将我提供的素材剪成 30 秒竖屏广告。",
    "$video-cut-music-to-video 根据这首 BGM 和提供的素材制作卡点混剪。",
    "$video-cut-remotion-best-practices 根据已确认的脚本制作产品广告视频。",
    "$video-cut-jianying-editor 将分镜和素材组织成可编辑的剪映工程。",
    "```", "",
    "## 来源与范围", "",
    "| 原排名 | 仓库 | 已注册 Skills | 源码提交 |", "|---:|---|---:|---|",
]
for record in manifest["source_repositories"]:
    commit = record["commit_from_github_zip_comment"]
    lines.append(f"| {record['rank_in_saved_report']} | [{record['repository']}]({record['repository_url']}) | {counts[record['repository']]} | [`{commit[:12]}`]({record['repository_url']}/tree/{commit}) |")
lines += [
    "", "OpenMontage 加载视频、媒体和 HyperFrames 相关条目；claude-skills 加载六个广告与视频策划条目；Remotion 加载完整十二个官方 Skills；剪映加载完整包。OpenMontage 内重复的 Remotion 条目由官方版本承担。", "",
    "## 本地文件位置", "",
    f"- 项目根目录：`{PROJECT}`",
    f"- 可编辑技能库：`{PROJECT / 'skills'}`",
    f"- Codex 发现目录：`{manifest['codex_skills_directory']}`，通过 Windows 目录联接指向项目内技能库。",
    "- 原始仓库与 ZIP：[sources](sources/)。",
    "- 来源、版本、目录映射与修改清单：[安装清单](video-cut-install-manifest.json)。",
    "- 本地校验结果：[校验记录](research/video-cut-validation.json)。",
    "- 注册脚本：[register-video-cut-skills.ps1](register-video-cut-skills.ps1)。", "",
    "目录联接依赖项目当前路径；移动或删除技能库后需重新注册。更新源码时需重新应用前缀和本地路径适配。", "",
    "## 环境与已完成校验", "",
    "本次安装包含技能说明、脚本、模板、参考资料与上游许可文件。已验证 39 个技能的格式、名称与调用元数据；已核验全部注册入口指向相同的项目文件；技能文档中的本地链接无缺失；剪映两个 Python 引导器能从项目外路径找到新技能目录。", "",
    "执行具体制作流程仍需相应运行环境：基础剪辑需 FFmpeg，素材下载需 yt-dlp，本地转写需 Whisper，Remotion/HyperFrames 需对应 Node.js 工程，剪映需客户端与 Python 依赖，HeyGen 等生成/翻译分支需对应服务配置。本次尚未执行媒体生成、剪辑或渲染。", "",
    "`video-cut-video-toolkit` 上游声明 macOS/Linux 支持，且依赖单独的制作工具仓库；目前作为流程参考注册。OpenMontage 的 HyperFrames 路由中，未随该仓库打包的工作流已在本地说明中标注，并提供可用入口。", "",
    "后续制作遵循 [项目约定](AGENTS.md)：所有内容在本项目路径下构建，严格禁止本地 Docker/WSL 等虚拟化环境，浏览器调用结束后关闭所有不用的 tab。", "",
    "## 完整调用清单", "",
    "| 来源 | 调用名 | 用途 |", "|---|---|---|",
]
for skill in manifest["skills"]:
    lines.append(f"| {skill['repository']} | `{skill['invocation']}` | {USES[skill['original_name']]} |")
guide = PROJECT / "video-cut_本地Skills使用指南.md"
guide.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Saved guide: {guide}")
