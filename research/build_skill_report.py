"""Create a Chinese research list from saved public-source evidence."""

import csv
import datetime as dt
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent

# Each description is an editorial summary of the selected SKILL.md files.
DETAILS = {
    "ComposioHQ/awesome-claude-skills": ("广告建议", "综合合集", "竞品广告提取、卖点和创意形式分析", "广告库资料或相应连接", "competitive-ads-extractor/SKILL.md"),
    "calesthio/OpenMontage": ("AI剪辑／混剪", "制作系统＋集成Skills", "FFmpeg裁切拼接、视频制作、音乐卡点；集成部分上游Skills", "基础剪辑用FFmpeg；生成类分支需对应模型/API", ".agents/skills/video-edit/SKILL.md", ".agents/skills/music-to-video/SKILL.md"),
    "heygen-com/hyperframes": ("AI剪辑／广告制作／混剪", "官方Skills＋渲染框架", "通用素材混剪、音乐卡点、产品宣传片、口播图形包装", "Node.js、HyperFrames；媒体、语音或云服务按工作流配置", "skills/general-video/SKILL.md", "skills/music-to-video/SKILL.md", "skills/product-launch-video/SKILL.md"),
    "coreyhaines31/marketingskills": ("广告建议", "营销Skills合集", "广告Hook、卖点角度、批量创意变体、创意测试和投放建议", "产品/客户资料；分析效果时需要真实投放数据", "skills/ad-creative/SKILL.md", "skills/ads/SKILL.md"),
    "sickn33/agentic-awesome-skills": ("广告建议／爆款拆解", "综合合集", "广告创意与投放规则；包含托管视频复刻服务的接入Skill", "ad-creative以规则为主；视频复刻分支使用付费Beatra服务", "skills/ad-creative/SKILL.md", "skills/viral-video-teardown-remake/SKILL.md"),
    "davila7/claude-code-templates": ("广告建议", "综合模板合集", "paid-ads覆盖广告策略、广告文案、受众和效果优化", "使用具体Skill；无需为阅读规则运行整个CLI", "cli-tool/components/skills/business-marketing/paid-ads/SKILL.md"),
    "browser-use/video-use": ("AI剪辑／混剪", "专门剪辑Skill", "通过对话转录、选段、剪切、调色、字幕和图形叠加", "Python、FFmpeg；转录流程声明需要ElevenLabs凭据", "SKILL.md"),
    "alirezarezvani/claude-skills": ("广告建议／视频策划", "综合合集", "广告文案和变体生成，视频脚本、短视频策略与内容再利用", "策划以规则和品牌资料为主；执行另接剪辑工具", "marketing-skill/skills/ad-creative/SKILL.md", "marketing-skill/video-content-strategist/skills/video-content-strategist/SKILL.md"),
    "Vincentwei1021/video-shotcraft": ("广告制作／卡点", "专门产品视频Skill", "镜头配方、真实页面截图、2.5D运镜、节奏卡点和声音设计", "Remotion；部分镜头需Three.js相关依赖；Windows剪映草稿分支注明未真机验证", "SKILL.md"),
    "remotion-dev/skills": ("广告制作／视频合成", "官方Skills合集", "React视频创建、动画布局、字幕、预览与渲染规则", "Node.js和Remotion项目", "skills/remotion-best-practices/SKILL.md", "skills/remotion-create/SKILL.md"),
    "irinabuht12-oss/marketing-skills": ("广告建议／竞品分析", "营销Skills合集", "广告变体、竞品创意分析、素材疲劳检测和替换建议", "分析需要广告库资料与真实投放指标；Ryze连接可用性另核实", "skills/ad-copy-variant-generator/SKILL.md", "skills/competitor-creative-analysis/SKILL.md", "skills/creative-fatigue-detection/SKILL.md"),
    "luoluoluo22/jianying-editor-skill": ("AI剪辑／剪映交付", "剪映自动化Skill", "素材导入、字幕、Web动效、录屏及剪映工程/导出流程", "剪映桌面版、Python及对应本地依赖；声明支持Windows", "SKILL.md"),
    "ericosiu/ai-marketing-skills": ("AI剪辑／高光切片", "营销与视频Skills合集", "新录口播初剪、长视频高光切片、按目标定位视频中的片段", "初剪用FFmpeg/Python；长视频和理解分支需对应模型API", "net-new-video-editor/SKILL.md", "video-clip-pipeline/SKILL.md", "agentic-video-understanding/SKILL.md"),
    "FireRedTeam/FireRed-OpenStoryline": ("AI剪辑／混剪转场", "剪辑Agent＋工作流Skills", "通用Vlog素材剪辑、用AI转场串联用户素材", "依赖OpenStoryline运行时及选定转场生成后端", ".storyline/skills/default_editing_workflow_skill/SKILL.md", ".storyline/skills/ai_transition_editing_skill/SKILL.md"),
    "Agentchengfeng/chengfeng-videocut-skills": ("中文口播剪辑", "插件＋多个Skills", "逐词审稿、口误/重复筛查、字幕和B-roll/动画包装流程", "配套本地工作台运行时；cut产出删词账本，最终成片走export流程", "plugins/chengfeng-videocut/skills/chengfeng-cut/SKILL.md", "plugins/chengfeng-videocut/skills/chengfeng-visual/SKILL.md"),
    "aaron-he-zhu/aaron-marketing-skills": ("广告建议", "营销Skills合集", "广告创意/标题批量生成、角度矩阵、A/B测试方案", "品牌资料、落地页及测试数据", "ad/orchestrate/ad-creative-builder/SKILL.md", "ad/orchestrate/ad-test-designer/SKILL.md"),
    "zubair-trabzada/ai-marketing-claude": ("广告建议", "营销命令与Skills合集", "从网站分析产品，生成广告文案、受众、预算和创意规格", "market-ads为父级market命令的一条分支", "skills/market-ads/SKILL.md"),
    "digitalsamba/claude-code-video-toolkit": ("AI剪辑／广告制作", "制作工具包＋集成Skills", "FFmpeg媒体加工、Remotion转场与品牌化视频组件", "Node.js、FFmpeg；语音和生成分支有额外服务依赖", ".claude/skills/ffmpeg/SKILL.md", ".claude/skills/remotion/SKILL.md"),
    "liuluhaixiu/DaVinci-AutoEdit-Agent": ("AI剪辑／时间线交付", "DaVinci工作流Skills", "审看/分类素材、编辑蓝图、创建并核验Resolve时间线", "DaVinci Resolve及对应编辑连接", "skills/davinci-autoedit-agent/SKILL.md"),
    "ivangfalco/ads-skills": ("广告建议", "平台广告Skills", "Meta/Google/LinkedIn广告策略、创意测试、B2B获客", "真实广告账户资料；LICENSE含Commons Clause附加条件", ".claude/skills/meta-ads/SKILL.md"),
    "ALBEDO-TABAI/video-expert-analyzer": ("素材分析／选段", "视频分析Skill", "按剪辑规则分析镜头、评分、筛选高光、拆解竞品视频", "视频访问、抽帧和模型分析依赖按实现配置", "SKILL.md"),
    "isYangs/jianying-editor-skill": ("AI剪辑／剪映交付", "剪映自动化Skill", "录屏、导入素材、生成字幕、合成Web动效和导出", "剪映桌面版、Python及相关本地依赖", "SKILL.md"),
    "znyupup/ai-video-editing-skill": ("AI剪辑／Vlog混剪", "专门自动剪辑Skill", "从旅行Vlog原始素材到成片，包含语音/视觉分析和拼接", "FFmpeg、Python、Whisper/FunASR及视觉API；文档主要给macOS/Linux示例", "SKILL.md"),
    "liyupi/ai-promo-video-maker": ("广告制作／产品宣传", "专门宣传片Skill", "产品调研、风格帧、4K页面截图、配乐卡点、旁白和成片校验", "按工作流配置截图、视频合成、语音与配乐工具", "SKILL.md"),
    "leosssvip-dot/remotion-ad-video-skill": ("广告制作", "专门广告视频Skill", "产品链接/商店页面到广告脚本、分镜、视频项目和质量检查", "Remotion默认，也支持HyperFrames；生成媒体有额外服务依赖", "skills/remotion-ad-video/SKILL.md"),
    "robonuggets/hyperframes-helper": ("AI剪辑／混剪", "HyperFrames辅助Skill", "网站转视频、分镜预览、去静音/重录片段与动效包装", "HyperFrames、FFmpeg、faster-whisper；资料许可为CC BY 4.0", ".claude/skills/hyperframes-helper/SKILL.md"),
    "kangarooking/promo-creator-skills": ("广告制作／产品宣传", "宣传片流程Skill Pack", "60–90秒产品宣传片，涵盖brief、分镜、素材、剪辑和BGM", "HyperFrames及选用的素材/音频工具", "SKILL.md"),
    "nopefallacy/vertical-video-editing-skills": ("AI剪辑／竖屏混剪", "专门竖屏剪辑Skill", "9:16口播/A-roll+B-roll，动态字幕、快切、分屏和音效层次", "HyperFrames、FFmpeg和验证工具", "skills/video-editing/SKILL.md"),
    "appergb/ClipSkills": ("AI剪辑／剪辑决策", "专业剪辑知识Skill", "剪辑判断与执行分层；支持初剪和多种软件执行路线", "按选定路线接Palmier、代码栈或NLE", "clip-skills/SKILL.md"),
    "iart-ai/ad-video-skills": ("广告制作／变体", "广告动效Skills Pack", "一个数据驱动模板批量生成广告变体、适配不同画幅与创意测试", "选定入口包含Remotion模板与CSV到视频参数的流程", "skills/ad-creative-video/SKILL.md"),
    "SamurAIGPT/Generative-Media-Skills": ("广告建议／图片素材", "生成媒体Skills合集", "广告主视觉、文案变体和不同平台裁切；偏图像广告", "muapi及对应生成服务凭据；开放Skill不代表后端开放", "library/visual/ad-creative/SKILL.md"),
    "DotanVG/video-director-skill": ("广告制作／混剪", "导演与剪辑Skill", "宣传片/预告片导演、节奏卡点、动态字体、音效和多比例交付", "HyperFrames、FFmpeg、Python；提供Windows PowerShell安装入口", "video-director/SKILL.md"),
    "Killusions/open-video-use": ("AI剪辑／混剪", "video-use的Fork", "对话式转录、裁切、字幕与混剪；与video-use来源相同", "按Fork配置模型和FFmpeg依赖；不是独立原始实现", "SKILL.md"),
    "Rajbharti06/Ultimate-Video-Editing-Skills": ("AI剪辑／剪辑规则", "综合剪辑Skill", "叙事、切镜、转场、调色、声音与动效规则的综合整理", "FFmpeg/Remotion/HyperFrames等；能力声明尚未运行实测", "skills/ultimate-video-editor/SKILL.md"),
    "xsourabhsharma/remotion-marketing-video-skill": ("广告制作／产品演示", "专门营销视频Skill", "Remotion产品演示、SaaS宣传、界面讲解和社交广告", "Node.js、Remotion和React", "SKILL.md"),
    "riffkit/skills": ("广告制作／参考视频复刻", "服务接入Skill", "UGC广告，分析参考视频后改编，或保留切镜节奏替换内容", "Riffkit账户、CLI/API和服务额度；后端未随Skills仓库公开", "ugc-ad-creative/SKILL.md"),
    "garytan023/video-content-teardown": ("广告建议／混剪素材拆解", "专门视频拆解Skill", "真实抽帧，提炼信息流广告内容公式、分镜结构和可替换元素", "视频文件与抽帧工具；分析产物不是直接剪辑成片", "video-content-teardown/SKILL.md"),
    "rendleyhq/video-editing-skill": ("AI剪辑／服务接入", "服务接入Skill", "将剪辑、字幕、重构比例和导出需求交给Rendley后端执行", "Rendley MCP/REST及账户；Skill是代理入口", "SKILL.md"),
    "fralapo/awesome-agent-skills": ("广告建议／剪辑规则", "综合规则合集", "video-editor、creative-director等规则与参考资料", "具体执行工具需按对应Skill配置", "skills/video-editor/SKILL.md", "skills/creative-director/SKILL.md"),
}

LICENSE_OVERRIDES = {
    "luoluoluo22/jianying-editor-skill": "MIT（已读LICENSE）",
    "appergb/ClipSkills": "MIT（已读LICENSE）",
    "DotanVG/video-director-skill": "MIT（已读LICENSE）",
    "robonuggets/hyperframes-helper": "CC BY 4.0（资料许可）",
    "ivangfalco/ads-skills": "MIT + Commons Clause（附加限制）",
    "garytan023/video-content-teardown": "仓库MIT，但Skill头声明Proprietary（冲突待澄清）",
    "Rajbharti06/Ultimate-Video-Editing-Skills": "Skill头声明MIT；仓库API未识别",
    "rendleyhq/video-editing-skill": "Skill头声明MIT；仓库API未识别",
}


def main():
    snapshot = json.loads((ROOT / "github-repository-snapshot.json").read_text(encoding="utf-8"))
    repositories = snapshot["repositories"] + json.loads((ROOT / "additional-public-page-snapshot.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "verified-skill-sources.json").read_text(encoding="utf-8"))
    by_key = {(r["repository"], r["path"]): r for r in sources}
    result = []
    for repo in repositories:
        name = repo["repository"]
        detail = DETAILS[name]
        verified_paths = [path for path in detail[4:] if by_key.get((name, path), {}).get("verified")]
        license_name = LICENSE_OVERRIDES.get(name) or (repo.get("license") or {}).get("spdx_id") or "未找到明确许可声明"
        if license_name == "NOASSERTION":
            license_name = "GitHub未识别，需查LICENSE"
        skills = []
        for path in verified_paths:
            source = by_key[(name, path)]
            body = Path(source["local_path"]).read_text(encoding="utf-8") if source.get("local_path") else source.get("header_excerpt", "")
            match = re.search(r"^name:\s*(.+)$", body, re.M)
            skill_name = match.group(1).strip(" '\"") if match else path.split("/")[-2] if "/" in path else name.split("/")[-1]
            skills.append({"name": skill_name, "path": path, "url": source["source_url"], "local_path": source.get("local_path"), "verification_method": source.get("fetch_method")})
        result.append({
            "repository": name, "stars": repo["stars"],
            "stars_approximate": repo.get("stars_approximate", False),
            "stars_display": repo.get("stars_display") or f'{repo["stars"]:,}',
            "url": repo["url"], "category": detail[0], "kind": detail[1],
            "summary": detail[2], "dependencies": detail[3], "license": license_name,
            "verified_skill_file": bool(skills), "skills": skills,
            "fetched_at_utc": repo.get("fetched_at_utc"),
            "metadata_source": repo.get("metadata_source", "GitHub REST API stargazers_count"),
            "fork": repo.get("fork", False),
        })
    result.sort(key=lambda r: (-r["stars"], r["repository"].lower()))
    verified = [r for r in result if r["verified_skill_file"]]
    pending = [r for r in result if not r["verified_skill_file"]]
    for index, row in enumerate(verified, 1):
        row["rank"] = index
    generated = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")
    combined = {"generated_at_asia_taipei": generated, "candidate_count": len(result), "verified_repository_count": len(verified), "ranking_scope": "本次检索发现且已读取相关SKILL.md的公开仓库，按整个仓库Star排序；不是全网穷尽排行。", "repositories": result}
    (ROOT / "curated-skill-ranking.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    def md_table(rows):
        lines = ["| 排名 | Star | 仓库 | 类型 / 用途 | 许可证 |", "|---:|---:|---|---|---|"]
        for row in rows:
            rank = row.get("rank", "待核")
            lines.append(f'| {rank} | {row["stars_display"]} | [{row["repository"]}]({row["url"]}) | {row["category"]}：{row["summary"]} | {row["license"]} |')
        return "\n".join(lines)

    sections = [
        "# AI广告剪辑：相关 Skills 仓库 Star 排名",
        f"\n采集日期：2026-10-11；报告生成时间：{generated}（Asia/Taipei）。",
        f"\n本次检索 {len(result)} 个公开候选仓库，已实际读取 {len(verified)} 个仓库的相关 `SKILL.md`。排名只覆盖已核实的候选；不是全网穷尽排行。",
        "\nStar 属于整个 GitHub 仓库，不属于合集中的单个 Skill。大型合集、制作框架和专门剪辑 Skill 的 Star 不能直接解释为单项技能效果排名。35 个候选使用 GitHub REST API 的 `stargazers_count`；补充仓库使用当日 GitHub 页面，带“约”的数值为页面四舍五入显示。",
        "\n这是公开 Skills 仓库清单：MIT、Apache、AGPL等明确许可与未声明许可分开标注。`MIT + Commons Clause` 含附加限制。开放 Skill 文件不表示其调用的Riffkit、Rendley、Beatra、muapi等服务后端开源或免费。",
        "\n检索来源：GitHub仓库搜索、项目README与实际SKILL.md。主要检索词：video skill、video editing、ad creative、advertising skill、剪辑 skill、混剪 skill、剪映 skill、Remotion、HyperFrames。只读核验，没有运行候选仓库的脚本或工作流。",
        "\n## 已核实仓库榜单\n",
        md_table(verified),
        "\n## 针对本项目的优先选择\n",
        "| 工作环节 | 优先查看 | 选择依据 |\n|---|---|---|\n"
        "| 广告创意与建议 | [marketingskills / ad-creative](https://github.com/coreyhaines31/marketingskills/blob/main/skills/ad-creative/SKILL.md) | Hook、创意角度、变体和测试框架完整 |\n"
        "| 已有视频素材剪辑 | [video-use](https://github.com/browser-use/video-use/blob/main/SKILL.md) | 对话式选段、剪切、字幕和调色 |\n"
        "| BGM卡点与素材混剪 | [HyperFrames / music-to-video](https://github.com/heygen-com/hyperframes/blob/main/skills/music-to-video/SKILL.md) 和 [general-video](https://github.com/heygen-com/hyperframes/blob/main/skills/general-video/SKILL.md) | 明确覆盖音乐节奏、素材混剪和拼接 |\n"
        "| 中文剪映工程交付 | [luoluoluo22 / jianying-editor-skill](https://github.com/luoluoluo22/jianying-editor-skill/blob/main/SKILL.md) | 提供剪映自动化入口，声明支持Windows |\n"
        "| 产品链接直接做广告 | [remotion-ad-video](https://github.com/leosssvip-dot/remotion-ad-video-skill/blob/main/skills/remotion-ad-video/SKILL.md) | 广告Brief、脚本、分镜、渲染QA对同一目标组织 |\n"
        "| 素材理解与选段规则参考 | [video-expert-analyzer](https://github.com/ALBEDO-TABAI/video-expert-analyzer/blob/main/SKILL.md) | 分析镜头和选段；未找到明确许可声明，当前作为能力参考 |",
        "\n## 具体 Skill 入口与依赖\n",
    ]
    for row in verified:
        links = "；".join(f'[{skill["name"]}]({skill["url"]})' for skill in row["skills"])
        sections.append(f'\n**{row["rank"]}. {row["repository"]} · {row["stars_display"]} Star**\n\n{row["summary"]}。\n\n入口：{links}。\n\n依赖/边界：{row["dependencies"]}。许可证：{row["license"]}。')
    if pending:
        sections += ["\n## 待补核入口的候选\n", "以下仓库已查到相关描述和Star，但本次尚未读取准确的SKILL.md入口，不混入已核实榜单。\n", md_table(pending)]
    sections += [
        "\n## 核验边界与本地文件\n",
        "已核验：仓库身份、Star快照、相关文件是否存在、Skill描述与部分依赖、明显许可证差异。未进行视频生成、安装或效果实测，不能据此保证具体环境可直接运行。本文的优先选择是依据任务适配度的判断。",
        "\n`garytan023/video-content-teardown`功能直接匹配广告/混剪素材拆解，但仓库页面标MIT，Skill头写Proprietary，故只列为公开参考，不能把它认定为许可已明确的开源Skill。",
        "\n项目运行环境为Windows，后续实现遵守本项目禁止本地Docker/WSL等虚拟化环境的约束。对macOS/Linux示例需要做原生Windows适配，不据此启动虚拟化环境。",
        "\n- `相关Skills_Star排行_2026-10-11.csv`：可以按Star或用途筛选。\n- `research/curated-skill-ranking.json`：整合的机器可读结果。\n- `research/github-repository-snapshot.json`：35个仓库的API快照。\n- `research/additional-public-page-snapshot.json`：补充公开页面快照。\n- `research/skill-file-inspections.json`：仓库树中实际发现的Skill路径；部分低Star仓库树API因限流未取到，但已用公开文件页补核。\n- `research/verified-skill-sources.json`：逐文件读取的结果与来源URL。\n- `research/sources/`：供核验的选定公开文件；不是已安装的Skills目录。",
    ]
    report_path = OUTPUT / "相关Skills_Star排行_2026-10-11.md"
    report_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    columns = ["rank", "repository", "stars", "stars_approximate", "stars_display", "category", "kind", "summary", "license", "dependencies", "verified_skill_file", "url", "skill_urls", "metadata_source", "fetched_at_utc"]
    with (OUTPUT / "相关Skills_Star排行_2026-10-11.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in result:
            record = {key: row.get(key) for key in columns}
            record["skill_urls"] = " | ".join(s["url"] for s in row["skills"])
            writer.writerow(record)
    print(json.dumps({"report": str(report_path), "candidates": len(result), "verified": len(verified), "pending": [r["repository"] for r in pending]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
