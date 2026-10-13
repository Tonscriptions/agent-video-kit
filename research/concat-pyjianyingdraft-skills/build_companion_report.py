"""Generate rankings from verified Skill files and public repository metadata."""
import csv
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
PREVIOUS = ROOT.parent / "agent-video-kernels"
DATE = "2026-10-11"
METADATA = json.loads((ROOT / "repository-metadata.json").read_text(encoding="utf-8"))
META = {item["repository"]: item for item in METADATA if "repository" in item}

# Each row represents one source repository. Multiple Skills do not multiply its Stars.
CANDIDATES = [
    ("jub0t/concat", "Concat 官方配套", [".claude/skills/run-concat/SKILL.md"], "run-concat", "video-cut-run-concat", "AGPL-3.0-or-later", "编译、启动、验证 Rust/Slint 桌面程序", "开发与运行验证 Skill；没有视频剪辑配方、命名运镜预设或剪辑任务编排。需要 Rust/Cargo。", "main"),
    ("luoluoluo22/jianying-editor-skill", "直接适配 pyJianYingDraft", ["SKILL.md"], "jianying-editor", "video-cut-jianying-editor", "MIT；内嵌库 Apache-2.0", "JyWrapper、草稿、特效/字幕、缩放/平移关键帧、Bezier 缓动", "已安装；1.7.0；当前上游 commit 与安装记录相同。内嵌 SDK 有修改，不能假设等同于 PyPI 0.3.0。", "main"),
    ("sun-guannan/VectCutAPI", "通过 API 适配 pyJianYingDraft", ["vectcut-skill/skill/SKILL.md", ".agents/skills/capcut-director/SKILL.md"], "vectcut-api / capcut-director", "video-cut-vectcut-api / video-cut-capcut-director", "Apache-2.0；vectcut-skill 子包 MIT", "HTTP/MCP 编排草稿、特效、视频关键帧；另有时间线指导 Skill", "公开主流程以草稿生成保存为主；云渲染/完整 Agent 应用未开源。capcut-director 有强制关闭进程/批量删除锁的示例，后续适配需改成保留用户工作与指定项目范围。", "main"),
    ("zenstory-ai/video-recap-skills", "间接配套：草稿格式兼容", ["skills/video-assemble/SKILL.md", "skills/video-recap/SKILL.md", "skills/video-cut/SKILL.md"], "video-assemble / video-recap / video-cut", "video-cut-recap-assemble / video-cut-recap / video-cut-recap-cut", "MIT", "解说、剪辑、混音、字幕、导出可编辑剪映草稿", "export_jianying.py 用标准库直接写 JSON，参考 pyJianYingDraft 格式但不调用该 SDK。音量 ducking 关键帧与画面运镜预设不是同一种能力。", "main"),
    ("isYangs/jianying-editor-skill", "直接适配 pyJianYingDraft", ["SKILL.md"], "jianying-editor", "video-cut-jianying-editor-isyangs", "MIT", "JyWrapper、素材、特效、Ken Burns/缩放/位置关键帧指导", "与已装 JyWrapper 属同类 Skill，215 Star；存在旧版导出与运行依赖假设，不是替换现有包的明显升级。", "main"),
    ("wangcanyu/daihuo-fanpai", "直接调用 SDK 的广告流水线", ["SKILL.md"], "daihuo-fanpai", "video-cut-daihuo-fanpai", "MIT", "带货视频反推、重生成、配音、拼接、剪映草稿交付", "deliver.py 实际调用 pyJianYingDraft。重点是广告生产，不提供完整命名运镜库；生成依赖即梦/Seedance 等服务。源码含 WSL 路径兼容分支，原生路径也有处理，本项目只考虑原生运行。", "main"),
    ("ops120/video-recap-skills-plus", "间接配套：草稿格式兼容", ["skills/video-assemble/SKILL.md", "skills/video-recap/SKILL.md", "skills/video-cut/SKILL.md"], "video-assemble / video-recap / video-cut", "video-cut-recap-plus-assemble / video-cut-recap-plus / video-cut-recap-plus-cut", "MIT", "解说/合成与剪映草稿输出", "独立 JSON 草稿导出器，未直接依赖 pyJianYingDraft；与 video-recap-skills 同类，不应当作新的 SDK 内核。", "main"),
    ("guoluhua38-max/jianying-editor-skill", "直接适配 pyJianYingDraft", ["SKILL.md"], "jianying-editor", "video-cut-jianying-editor-guoluhua", "MIT", "JyWrapper/关键帧规则的另一维护副本", "与最高 Star 项目结构与使用方式相近，没有核验到比已装包更强的独有运镜能力。", "main"),
    ("Xanthus-Sanslab/jianying-ai-mcp", "直接适配 pyJianYingDraft", ["skills/jianying-ai-editor/SKILL.md"], "jianying-ai-editor", "video-cut-jianying-ai-editor", "未找到项目 LICENSE；依赖库另有许可", "MCP 批量 manifest、关键帧、参考草稿、模板换料、视频观察", "pyproject 固定 pyJianYingDraft 0.3.0；项目自报 Windows 剪映 10.0.5 测试。11 Star，许可未明确，作为公开源码候选单列。", "license_unclear"),
    ("jjjane233/jianying-editor-skill-11.5", "JyWrapper 的版本专项适配", ["skills/jianying-editor-11-5/SKILL.md"], "jianying-editor-11-5", "video-cut-jianying-editor-11-5", "MIT；继承内嵌库声明", "Windows 11.5 草稿保存、增量修改、CLI、原生 DraftIO 桥", "作者仅验证 11.5.0.14471；使用本机客户端组件 ABI，2 Star。保留上游关键帧接口不等于已验证全部运镜/特效，须按本版记录核验。", "main"),
    ("DogeCoding/capcut-skill", "直接适配 pyJianYingDraft", ["SKILL.md"], "capcut-jianying", "video-cut-capcut-jianying", "MIT", "草稿、SRT、效果枚举、FFmpeg 静音粗剪", "macOS 为主，Windows 路径需适配；没有核验到命名运镜预设库。0 Star，适合作为最小示例参考。", "main"),
]

EXCLUDED = [
    ("mcncarl/yichen-skills", "有 yichen-jianying-edit，但 LICENSE 是个人学习/非商业许可，原生剪映流程又偏 Apple Silicon Mac；不列为可用于本广告项目的开源 Skill。"),
    ("mcncarl/jianying-headless", "同样为个人学习/非商业许可；有配套 Skill，主要原生链路为 macOS，Windows FFmpeg 分支与原生剪映草稿不同。"),
    ("OpenDemon/Pilipili-AutoVideo", "skills/SKILL.md 是说明文档，缺少 name/description YAML frontmatter；也未找到项目 LICENSE。保留为流水线参考，未列为可直接注册的开源 Skill。"),
    ("YGtemple/jianying-editor-skill", "有 Skill 入口，但当前仓库缺少对应执行脚本/资源包，未找到项目 LICENSE；是文档/规则参考。"),
    ("DreamLab-AI/agentbox", "找到 23 Star 的 Concat 实验集成 concatcontainer，交付的是 Docker/Compose 构建选项，没有独立的 Concat 命名 Skill；不符合本项目禁止 Docker/WSL 的运行约束。"),
]


def locate(repository):
    for base in [ROOT, PREVIOUS]:
        directory = base / "sources" / repository.replace("/", "__")
        for filename in ["source-snapshot.json", "selected-source-snapshot.json"]:
            path = directory / filename
            if path.exists():
                return directory / "code", json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(repository)


def skill_file_record(repository, relative):
    code, snapshot = locate(repository)
    path = code / relative
    content = path.read_text(encoding="utf-8-sig")
    match = re.match(r"^---\s*\r?\n(.*?)\r?\n---", content, re.S)
    if not match or not re.search(r"^name:\s*\S", match[1], re.M) or not re.search(r"^description:\s*\S", match[1], re.M):
        raise ValueError(f"Nonstandard Skill entry: {repository}/{relative}")
    name = re.search(r"^name:\s*(.+)", match[1], re.M).group(1).strip()
    return {"path": relative, "name": name, "local_path": str(path), "frontmatter_verified": True,
        "url": f"https://github.com/{repository}/blob/{snapshot['source_commit']}/{relative}"}


def evidence(repository, relative, pattern):
    code, snapshot = locate(repository)
    path = code / relative
    hits = [{"line": n + 1, "text": line.strip()} for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines()) if re.search(pattern, line)][:6]
    if not hits:
        raise ValueError(f"Missing evidence {repository}/{relative}: {pattern}")
    return {"repository": repository, "file": relative, "matches": hits, "local_path": str(path),
        "url": f"https://github.com/{repository}/blob/{snapshot['source_commit']}/{relative}#L{hits[0]['line']}"}


def main():
    rows = []
    for repo, relation, paths, names, local_names, license_name, scope, limits, group in CANDIDATES:
        code, snapshot = locate(repo)
        item = META[repo]
        rows.append({"repository": repo, "stars": item["stars"], "relation": relation, "skill_names": names,
            "suggested_local_names": local_names, "license": license_name, "capabilities": scope, "limits": limits,
            "group": group, "url": item["url"], "source_commit": snapshot["source_commit"],
            "skill_files": [skill_file_record(repo, path) for path in paths], "runtime_tested": False,
            "installed": repo == "luoluoluo22/jianying-editor-skill"})
    rows.sort(key=lambda item: item["stars"], reverse=True)
    excluded = [{"repository": repo, "stars": META[repo]["stars"], "url": META[repo]["url"], "reason": reason} for repo, reason in EXCLUDED]
    excluded.sort(key=lambda item: item["stars"], reverse=True)
    proofs = [
        evidence("jub0t/concat", ".claude/skills/run-concat/SKILL.md", 'name:|Build, launch|cargo run|workspace root'),
        evidence("jub0t/concat", "src/crates/concat-cli/src/main.rs", 'Api \\{|Serve \\{|JSON-RPC requests'),
        evidence("jub0t/concat", "src/crates/concat-project/src/commands/properties.rs", 'SetClipKey|SetClipCutout|clip.set_key'),
        evidence("jub0t/concat", "src/crates/concat-core/src/animate.rs", 'fraction of the clip|fraction of its length'),
        evidence("GuanYixuan/pyJianYingDraft", "README.md", '相对片段头部|fallback_loader|剪映7及以上|10.8 ❌'),
        evidence("luoluoluo22/jianying-editor-skill", "scripts/jy_wrapper.py", 'import pyJianYingDraft|class JyProject'),
        evidence("luoluoluo22/jianying-editor-skill", "rules/keyframes.md", 'Absolute Timeline Time|t_start = start_time|add_keyframe|EASE_IN_OUT'),
        evidence("sun-guannan/VectCutAPI", "create_draft.py", 'import pyJianYingDraft'),
        evidence("sun-guannan/VectCutAPI", "vectcut-skill/skill/SKILL.md", 'name:|add_video_keyframe'),
        evidence("zenstory-ai/video-recap-skills", "skills/video-assemble/scripts/export_jianying.py", 'stdlib|informed by|implemented locally'),
        evidence("isYangs/jianying-editor-skill", "scripts/jy_wrapper.py", 'import pyJianYingDraft|class JyProject'),
        evidence("wangcanyu/daihuo-fanpai", "deliver.py", 'import pyJianYingDraft|def to_wsl|默认|Windows 原生'),
        evidence("ops120/video-recap-skills-plus", "skills/video-assemble/scripts/export_jianying.py", 'stdlib|reimplemented from|JSON is built directly'),
        evidence("Xanthus-Sanslab/jianying-ai-mcp", "src/jianying_ai_mcp/draft_ops.py", 'import pyJianYingDraft|segment.add_keyframe'),
        evidence("Xanthus-Sanslab/jianying-ai-mcp", "pyproject.toml", 'pyJianYingDraft==0.3.0'),
        evidence("jjjane233/jianying-editor-skill-11.5", "skills/jianying-editor-11-5/SKILL.md", '11.5.0.14471|DraftIO|jy_wrapper.JyProject'),
        evidence("DogeCoding/capcut-skill", "SKILL.md", 'name:|pyJianYingDraft|macOS'),
        evidence("mcncarl/yichen-skills", "LICENSE", 'non-commercial|No commercial use'),
        evidence("mcncarl/jianying-headless", "LICENSE", 'non-commercial|No commercial use'),
        evidence("DreamLab-AI/agentbox", "concatcontainer/README.md", 'EXPERIMENTAL|This image builds|AGENTBOX_ENABLE_CONCAT'),
    ]
    environment = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "python": shutil.which("python"),
        "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"), "cargo": shutil.which("cargo"),
        "system_python_modules": {name: importlib.util.find_spec(name) is not None for name in ["pyJianYingDraft", "pymediainfo", "uiautomation"]},
        "scope": "Only current PATH/system Python; no full installed-Skill bootstrap or rendering test."}
    (ROOT / "local-environment.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((PROJECT / "video-cut-install-manifest.json").read_text(encoding="utf-8"))
    installed = next(item for item in manifest["source_repositories"] if item["repository"] == "luoluoluo22/jianying-editor-skill")
    current = next(item for item in rows if item["repository"] == installed["repository"])
    installed_matches = installed["commit_from_github_zip_comment"] == current["source_commit"]
    if not installed_matches:
        raise ValueError("Installed version has changed; rewrite the version conclusion.")
    result = {"date": DATE, "scope": "Concat + pyJianYingDraft; Stars belong to whole source repositories, not individual Skills", "ranked_skills": rows,
        "excluded_or_reference_only": excluded, "evidence": proofs, "installed_version_matches_current_upstream": installed_matches,
        "runtime_tested": False, "no_virtualization_used": True}
    (ROOT / "companion-skill-findings.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    main_rows = [item for item in rows if item["group"] == "main"]
    csv_path = PROJECT / f"Concat与pyJianYingDraft_配套Skills_Star排行_{DATE}.csv"
    keys = ["repository", "stars", "relation", "skill_names", "suggested_local_names", "capabilities", "license", "limits", "group", "url", "source_commit", "installed", "runtime_tested"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    report = INTRO + CHECKS + "\n\n## 可核验配套 Skill，按仓库 Star 排序\n\n"
    report += "Star 为 2026-10-11 GitHub API 查询结果，按整个仓库统计；同仓多个 Skill 只列一次。这里包括直接 SDK 配套与间接草稿输出配套，并在关系栏注明。\n\n"
    report += "| 排名 | 仓库 / Skill | Star | 适配关系 | 关键帧、运镜及用途 |\n|---|---|---:|---|---|\n"
    for rank, item in enumerate(main_rows, 1):
        skill_links = " / ".join(f"[{entry['name']}]({entry['url']})" for entry in item["skill_files"])
        report += f"| {rank} | {item['repository']} · {skill_links} | {item['stars']:,} | {item['relation']} | {item['capabilities']} |\n"
    report += "\n\n## 各项边界、许可与本地名称\n\n新候选仅作为研究源码读取，未注册为本地 Skill。建议安装名均使用 `video-cut-` 前缀，调用时在名称前加 `$`。只有已装 `video-cut-jianying-editor` 当前可以按该名称调用。\n\n"
    for item in rows:
        report += f"- **{item['repository']}**（{item['stars']:,} Star，{item['license']}）：{item['limits']} 建议本地名：`{item['suggested_local_names']}`。\n"
    report += "\n\n## 公开源码候选及未纳入排行的项目\n\n"
    report += "Xanthus-Sanslab/jianying-ai-mcp（11 Star）有真实 `jianying-ai-editor` Skill、MCP 服务和固定 pyJianYingDraft 0.3.0 依赖，配套关系明确；目前未找到项目 LICENSE，不能直接当作许可明确的开源包。[Skill 源码](https://github.com/Xanthus-Sanslab/jianying-ai-mcp/blob/main/skills/jianying-ai-editor/SKILL.md)\n\n"
    report += "| 项目 | Star | 核查结论 |\n|---|---:|---|\n"
    for item in excluded:
        report += f"| [{item['repository']}]({item['url']}) | {item['stars']:,} | {item['reason']} |\n"
    report += RECOMMENDATIONS
    report += "\n\n## 源码证据\n\n以下链接固定到本次读取的 commit，避免后续主分支更新造成混淆。\n\n"
    for proof in proofs:
        report += f"- [{proof['repository']} · {proof['file']}]({proof['url']})\n"
    report += "\n\n## 本地产物与验证范围\n\n"
    report += "- `research/concat-pyjianyingdraft-skills/repository-metadata.json`：17 个相关仓库的元数据。\n"
    report += "- `research/concat-pyjianyingdraft-skills/github-repository-search.json`：GitHub 检索查询与候选结果；结合公开网页搜索补充。\n"
    report += "- `research/concat-pyjianyingdraft-skills/release-checks.json`：Concat 0.2.6、pyJianYingDraft 0.3.0 发布与 PyPI 依赖信息。\n"
    report += "- `research/concat-pyjianyingdraft-skills/companion-skill-findings.json`：Skill 入口、YAML 核查、适配关系、commit、源码行号和排除理由。\n"
    report += "- 同目录 `sources/`：新增候选的文本/代码快照；已有 Concat、pyJianYingDraft、VectCutAPI 快照复用 `research/agent-video-kernels/sources/`。\n"
    report += "\n完成公开源码、标准 Skill 入口、许可文件、SDK 调用关系、版本与本机基础依赖检查。没有安装候选程序或新 Skill，没有启动 Docker/WSL，没有实际打开编辑器或渲染样片。源码文本快照不是完整可运行安装包；编译/运行依赖与素材未包含。网页检索使用检索工具，没有打开浏览器标签页。\n"
    report_path = PROJECT / f"Concat与pyJianYingDraft_配套Skills_Star排行_{DATE}.md"
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps({"report": str(report_path), "csv": str(csv_path), "main_ranked_repositories": len(main_rows),
        "main_verified_skill_entries": sum(len(item["skill_files"]) for item in main_rows), "source_proofs": len(proofs),
        "public_candidate_license_unclear": 1, "installed_matches_upstream": installed_matches}, ensure_ascii=False, indent=2))


INTRO = """# Concat 与 pyJianYingDraft 检查及配套 Skills Star 排行

核查日期：2026-10-11。用户所指“1、2”按上一份核心列表解释为 **jub0t/concat** 与 **GuanYixuan/pyJianYingDraft**。重点为用户确认的“关键帧与运镜预设”。所有本地产物在 `E:/dev/sandbox/AI广告剪辑/` 下。

**结论：两个程序都有真实编辑接口；Concat 有一个官方开发/运行验证 Skill，pyJianYingDraft 则有多套真正用于视频草稿制作的社区 Skill。** 若希望现在批量套用缩放、平移和缓动，已安装的 `$video-cut-jianying-editor` 是最值得先验证的入口。

检索和源码检查包含隐藏目录 `.claude/skills/`、`.agents/skills/`，不能只搜索普通 `skills/`。初查遗漏了 Concat 的隐藏 Skill，现已更正。"""

CHECKS = """

## 1. Concat 检查

- 仓库：4,777 Star；AGPL-3.0-or-later。最新发布 **v0.2.6**，2026-10-06 发布，提供原生 Windows x86_64 / ARM64 的 EXE 和 MSI 安装包。
- 实际编辑内核：`concat-cli api/serve`、JSON-RPC、可选 gRPC；支持 `edit.apply`、模板、效果目录、预览、最终导出。`SetClipKey`、`SetClipCutout` 在源码中有实现。
- 关键帧：支持位置、缩放、旋转、透明度等；时间 `at` 按片段长度的比例表达，不能直接套用剪映 SDK 的微秒时间。命名运镜配方需要结合这些操作与模板构建。
- 官方 Skill：**run-concat**，路径 `.claude/skills/run-concat/SKILL.md`。文件有规范 frontmatter，但用途是编译、启动和验证桌面程序；它没有提供“制作一条广告 → 套推拉平移 → 导出”的创作流程或完整命名运镜库。
- MCP：官方开发文档与本次源码表明完整 MCP 服务仍未合入；CLI/JSON-RPC 是现阶段可用接口。不能将 JSON-RPC stdio 直接当作 MCP stdio。
- Windows 运行准备：本机当前 PATH 没有 Cargo。本次只核验发布包与源码，未安装/编译/启动 Concat。官方 `run-concat` 依赖 Rust 工具链，与下载 Windows 安装包使用 GUI 是两条路线。

[发布包](https://github.com/jub0t/concat/releases/tag/v0.2.6)、[官方 Skill](https://github.com/jub0t/concat/blob/main/.claude/skills/run-concat/SKILL.md)、[MCP 当前状态](https://concatenate.pages.dev/docs/transports/mcp/)

## 2. pyJianYingDraft 检查

- 仓库：4,527 Star；Apache-2.0。GitHub 发布与 PyPI 当前版本均为 **0.3.0**；PyPI 要求 Python >=3.8，并依赖 pymediainfo、imageio，Windows 另依赖 uiautomation。
- 它是剪映草稿 SDK，最终原生效果由剪映客户端渲染。官方 README 自报 10.8 支持素材、关键帧、字幕、特效/滤镜/转场等；蒙版目前标记不支持，模板读取可能需 `fallback_loader`。
- 自动导出是另一模块：旧 UI 控制器验证 5.9/6.8，对剪映 7+ 的表格标记不支持。这不否定新版草稿生成能力。
- 原始主仓库快照未发现标准 `SKILL.md`；配套 Skill 来自社区封装、API 项目和专项工作流。
- 本机当前系统 Python 3.13 没找到 PyPI 的 pyJianYingDraft、pymediainfo 或 uiautomation；但已有 JyWrapper 带内嵌库，因此“系统 Python 无包”不能推断“已装 Skill 缺源码”。实际运行必须按该 Skill 的 bootstrap 和依赖核验。
- 已安装的 `$video-cut-jianying-editor` 为 1.7.0，安装记录 commit **32c56928ded4f9e2c2b80e099dc7abb793d2c30b** 与当前上游相同，无需重复下载同一版本。内嵌 SDK 提供了 Bezier 缓动扩展，不能混用未修改的 PyPI 包假设所有参数相同。

[官方 SDK 与兼容矩阵](https://github.com/GuanYixuan/pyJianYingDraft)、[PyPI](https://pypi.org/project/pyJianYingDraft/)、[已装 Skill 的来源](https://github.com/luoluoluo22/jianying-editor-skill)
"""

RECOMMENDATIONS = """

## 针对关键帧与运镜预设的优先顺序

1. **制作内容、继续剪映：先验证现有 `$video-cut-jianying-editor`。** 已包含缩放、位置、Ken Burns 类动画与 Bezier 缓动的指导及接口；可以把“推近/拉远/横移”等保存为项目内参数配方，再复用到批量素材。
2. **希望由 MCP/HTTP 批量执行：评估 VectCutAPI 的 vectcut-api Skill。** 服务与 Skill 均存在，参数化关键帧适配关系明确；需要核对草稿结构和目标客户端版本。
3. **建立独立内核：Concat 适合继续评估，但 run-concat 是开发运行 Skill。** 对广告剪辑还需要围绕 JSON-RPC 补充创作 Skill 与命名运镜配方；本次没有发现可核验的独立社区创作 Skill 可直接替代这层。
4. **广告内容流程：daihuo-fanpai 更贴近带货制作；解说流程看 video-recap-skills。** 两类管线的关键帧图片生成、音量 ducking 和相机运镜预设应分别评估，不能因为都有“关键帧”字样就视为同一能力。

### 本次发现的运镜示例问题

已装 Skill 的 `rules/keyframes.md` 示例把“绝对时间线时间”传给 `add_keyframe`；底层 API 与官方文档定义的是**相对片段头部的时间偏移**。例如片段在时间线 1 秒开始、持续 4 秒，关键帧应为片内 `0s → 4s`，而不是绝对 `1s → 5s`。批量运镜应按片内时间建立配方，避免直接照搬该示例。

Concat 的比例时间、剪映 SDK 的片内微秒、API 接口的时间字段也需要分别转换；建议统一项目配方为“片段时长比例 + 起止变换 + 缓动”，由各内核适配器转换。该建议是基于接口检查的实施判断，本次没有渲染样片证明视觉一致性。
"""

if __name__ == "__main__":
    main()
