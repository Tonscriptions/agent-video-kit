"""Build a dated research report and a reproducible source-evidence index."""
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
DATE = "2026-10-11"
METADATA = json.loads((ROOT / "repository-metadata.json").read_text(encoding="utf-8"))
META = {item["repository"]: item for item in METADATA if "repository" in item}

# Capabilities below are observations from source/documents, not runtime certifications.
PROFILES = [
    ("browser-use/video-use", "Agent 剪辑工作流", "Skill + Python/FFmpeg 脚本", "转录、词级剪辑、混剪、字幕、调色、动画叠加", "脚本组合；没有统一多轨编辑器内核", "可移植；README 安装偏 macOS，Windows 未实测", "MIT", "28k Star 属于整个工作流仓库。默认转录依赖 ElevenLabs Scribe；不能按完全离线内核理解。"),
    ("jub0t/concat", "独立编辑器及内核", "CLI / JSON-RPC / gRPC；MCP 尚未合入", "多轨剪辑、关键帧、特效、模板、本地抠像、字幕/TTS", "自身 Rust/GPU/FFmpeg 渲染", "提供 Windows 发行版；API/CLI 源码可用", "AGPL-3.0-or-later", "Beta。README 的 MCP 宣传宽于当前交付状态；官方开发文档明确 MCP 未合入，应先用 JSON-RPC。"),
    ("GuanYixuan/pyJianYingDraft", "剪映草稿 SDK", "Python API；可封装成 Agent 工具", "多轨、素材替换、特效/滤镜/转场、字幕、关键帧", "剪映客户端渲染；另有旧版 UI 导出控制器", "原生 Windows；客户端版本需匹配", "Apache-2.0", "项目自报 10.8 支持多项草稿功能，但蒙版尚有兼容问题；模板可能需 fallback_loader。自动导出矩阵对 7+ 标记不支持。"),
    ("sun-guannan/VectCutAPI", "剪映/CapCut 草稿服务", "HTTP / MCP stdio", "11 个公开 MCP 工具；素材、字幕、特效、关键帧", "公开部分主要保存草稿，完整云渲染模块未开源", "原生 Python + FFmpeg 路径可用", "Apache-2.0", "mcp_server.py 是真实实现；完整 Agent 应用、Web 客户端、云渲染模块与它不是同一交付物。"),
    ("Hommy-master/capcut-mate", "剪映批量编辑 API", "FastAPI / OpenAPI / Coze 插件", "批量素材、特效、关键帧、蒙版关键帧、参数生成", "剪映 Windows UI/RPA 导出", "README 有原生 uv 路线及 Windows extras", "Apache-2.0", "keyframes_infos 可批量产生关键帧数据。自动导出调用桌面控制器且串行，不是独立无界面渲染。其控制器修改过，需单独实测兼容版本。"),
    ("renezander030/capcut-cli", "Agent 可用的草稿 CLI", "CLI / JSON 输出 / 批量编译", "批量关键帧/缓动、模板、字幕样式预设、特效/转场、枚举采集", "客户端最终渲染 + FFmpeg 近似预览", "Node 原生支持 Windows；剪映建议 5.9.x", "MIT", "CLI 对剪映 6.0+ 草稿有写入保护；只检测加密，不负责解密。make-preset 是文字样式预设，不保存动画；关键帧走 keyframe --batch。预览忽略特效、转场、关键帧等，带 fidelity 清单。"),
    ("GuanYixuan/pyCapCut", "国际 CapCut 草稿 SDK", "Python API", "CapCut 草稿生成及编辑", "CapCut 客户端导出", "需核对国际版客户端与草稿结构", "未检出明确 LICENSE", "GitHub API license=null，源码快照未见许可证文件；不因同作者或相似代码而推定 Apache 授权。"),
    ("Monet-AI-Editor/Monet", "面向 coding agent 的编辑器", "editorctl CLI / HTTP / MCP", "时间线、转录、剪辑、字幕、设计画布、导出", "应用自己的导出流程", "当前 macOS-first；不作为本机 Windows 首选", "MIT", "明确面向 Claude Code/Codex，但当前官方打包与安装路径集中于 macOS。仅选择性核查 README、包配置和许可证。"),
    ("AH64-dll/OpenEdit", "Agent 无界面编辑内核", "MCP stdio / CLI / Review Studio", "可逆编辑图、转录、28 类 IR 编辑操作、代理/最终渲染", "MLT/melt + FFmpeg，动效叠加用 HyperFrames", "服务支持原生 Windows；普通视频渲染还需自行构建 MLT", "MIT", "INSTALL.md 明确 Windows 无一键 melt 安装。用户禁用 WSL，因此只考虑原生构建；不能按开箱即用 Windows 内核推荐。"),
    ("x777/frontstage", "独立 Agent 视频编辑器", "桌面 HTTP MCP / 内置 Agent", "多轨、关键帧、GPU 特效、Whisper、生成素材、互操作导出", "WebGPU/WebCodecs/FFmpeg 的应用管线", "提供 Windows 桌面路线；应用需运行", "GPL-3.0", "MCP server.mjs 与 Agent 工具目录均存在。生成依赖 fal.ai；低 Star，跨长片/重特效稳定性未实测。"),
    ("Mas-inx/lumen-ai-video-editor", "独立 Agent 视频编辑器", "桌面 HTTP MCP / 内置 Copilot", "运镜预设、关键帧、音乐卡点、物体跟踪、遮罩跟随、特效", "应用自己的合成/导出管线", "原生 Electron Windows；应用需运行", "MIT", "源码确认 clip_animate、detect_beats、cut_to_beats、track_motion。跟踪采用图像块模板匹配，会丢失目标；7 Star，优先做样片验证。"),
    ("AiPersonacademy/capcut-mcp", "直接编辑 CapCut 草稿的 MCP", "MCP stdio（项目称 24 工具）", "分割、裁切、变换、关键帧、转场、字幕、贴纸", "CapCut 客户端 + FFmpeg 基础代理预览", "Node 原生 Windows/macOS 路径处理", "MIT", "代理预览仅合成基础视频/音频，没有实现完整文字/特效/关键帧渲染。草稿在实际客户端可读性未实测。"),
    ("craftled/openklip", "Agent 原生编辑器", "CLI / MCP（项目称 98 工具）", "图式项目、模板、关键帧、品牌预设、AI 接口", "原生应用渲染", "完整编辑/渲染管线当前 macOS-only", "MIT", "其他平台只能使用部分 CLI 查询能力；不纳入本机优先试用列表。"),
    ("ishan-parihar/openscript", "Agent 视频工作台", "CLI / MCP / Rust + Python", "文档描述 43 工具及 FFmpeg/Remotion 管线", "文档描述 FFmpeg/Remotion 渲染", "原生 Windows 完整链路未核实", "MIT", "只核查公共说明与 GitHub 元数据；未下载大体积源码，不能据此确认全部工具实现。"),
    ("MHughesDev/video-mcp", "无界面 MCP 剪辑内核", "Python MCP stdio", "节拍分析、卡点时间线、速度变化、重构图、LUT、OTIO", "FFmpeg 渲染及 QA", "可按原生 Python + FFmpeg 搭建；Windows 未实测", "MIT", "analyze_beats 确实调用 librosa；MCP 转发到实现模块。0 Star，适合作为小型内核原型，未证明生产稳定性。"),
    ("rdh073/verbreel-engine", "Agent 内核架构原型", "Rust CLI / MCP / HTTP", "确定性项目图、事件、GPU 渲染的架构", "native-render feature 下的 FFmpeg/wgpu", "原生工具链要求较高；Windows 未实测", "README 称 MIT OR Apache-2.0；API 未识别", "README 的当前 v1 floor 主要是 project.list 和按 feature 开启的 render.start，不能把完整架构目录当成全部编辑能力已交付。"),
    ("PlbKin190/video-editor-mcp", "最小 FFmpeg MCP 内核", "Node MCP stdio（9 工具）", "探测、裁切、拼接、缩放、叠加、混音、JSON 顺序镜头渲染", "FFmpeg / ffprobe", "默认说明使用 Docker；原生 Node 路线需另行适配", "Apache-2.0", "本项目禁止 Docker。源码有 npm build/start，可研究原生运行，但不采用 README 的容器部署命令。"),
    ("PlbKin190/video-atelier-mcp", "可查看源码的编辑工作台", "MCP / UI", "文档描述时间线、字幕、SAM2 屏幕替换", "FFmpeg 等", "本机链路未核实", "PolyForm Noncommercial（非 OSI 开源）", "属于 source-available，不能混入可直接做商业广告用途的开源清单。"),
]

EVIDENCE_SPECS = [
    ("jub0t/concat", "src/crates/concat-cli/src/main.rs", "JSON-RPC|Api \\{|Serve \\{"),
    ("jub0t/concat", "src/crates/concat-project/src/commands/properties.rs", "SetClipCutout|SetClipKey|clip.set_key"),
    ("jub0t/concat", "src/crates/concat-api/src/message.rs", 'template.instantiate|export.run|cutout.progress'),
    ("GuanYixuan/pyJianYingDraft", "README.md", '10.8 ❌|fallback_loader|剪映7及以上'),
    ("sun-guannan/VectCutAPI", "mcp_server.py", 'add_effect_impl|add_video_keyframe_impl|def add_effect|def add_video_keyframe'),
    ("sun-guannan/VectCutAPI", "README.md", 'not been open-sourced yet|python mcp_server.py'),
    ("Hommy-master/capcut-mate", "src/service/add_keyframes.py", 'def add_keyframes|segment.add_keyframe'),
    ("Hommy-master/capcut-mate", "src/service/add_effects.py", 'script.add_track_ordered|add_effect_to_draft'),
    ("Hommy-master/capcut-mate", "src/utils/video_task_manager.py", 'ctrl.export_draft|export_video_lock ='),
    ("renezander030/capcut-cli", "docs/quickstart.zh-CN.md", '5.9.x|6.0|harvest-enums|make-preset|save-template'),
    ("renezander030/capcut-cli", "src/render.ts", 'video effects are not rendered|keyframed animation is not applied|fidelityCensus'),
    ("renezander030/capcut-cli", "src/command-specs.ts", 'Read JSONL keyframes|Interpolation easing|capcut keyframe'),
    ("renezander030/capcut-cli", "src/preset.ts", 'Text style presets|animations are excluded'),
    ("Mas-inx/lumen-ai-video-editor", "electron/integrations/server.ts", '47910|ListToolsRequestSchema|StreamableHTTPServerTransport'),
    ("Mas-inx/lumen-ai-video-editor", "src/editor/commands.ts", "'clip.animate'|presetKeyframes|mergeKeyframes"),
    ("Mas-inx/lumen-ai-video-editor", "src/integrations/tools/beats.ts", "name: 'detect_beats'|name: 'cut_to_beats'|await cutToBeats|await analyzeBeats"),
    ("Mas-inx/lumen-ai-video-editor", "src/integrations/tools/footage.ts", "name: 'track_motion'|await trackMotion|Lost sight"),
    ("Mas-inx/lumen-ai-video-editor", "src/engine/tracker.ts", 'template matching|normalized cross-correlation|export async function trackBox'),
    ("x777/frontstage", "apps/desktop/src/main/mcp/server.mjs", 'StreamableHTTPServerTransport|ListToolsRequestSchema|CallToolRequestSchema'),
    ("AH64-dll/OpenEdit", "open_edit/mcp/server.py", 'server.list_tools|server.call_tool|dispatch_mcp_tool'),
    ("AH64-dll/OpenEdit", "INSTALL.md", 'no one-command melt|build MLT yourself|no packaged install'),
    ("MHughesDev/video-mcp", "src/mcp_editor/beat_sync.py", 'def analyze_beats|librosa.beat.beat_track|def plan_beat_synced_edit'),
    ("MHughesDev/video-mcp", "src/mcp_editor/server.py", 'def analyze_beats|analyze_beats_impl|apply_speed_ramp_impl'),
    ("AiPersonacademy/capcut-mcp", "src/capcut/preview-renderer.ts", 'videoTracks|audioTracks|ffmpeg|overlay|amix'),
    ("Monet-AI-Editor/Monet", "README.md", 'macOS-first|editorctl CLI|MCP server'),
    ("rdh073/verbreel-engine", "README.md", 'Current v1 floor|project.list|native-render'),
    ("PlbKin190/video-editor-mcp", "package.json", '"start"|"node"'),
]


def source_info(repository):
    directory = ROOT / "sources" / repository.replace("/", "__")
    for name in ["source-snapshot.json", "selected-source-snapshot.json"]:
        path = directory / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def build_evidence():
    evidence = []
    for repository, file, pattern in EVIDENCE_SPECS:
        info = source_info(repository)
        path = ROOT / "sources" / repository.replace("/", "__") / "code" / file
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        hits = [{"line": index + 1, "text": text.strip()} for index, text in enumerate(lines) if re.search(pattern, text)][:8]
        if not hits:
            raise ValueError(f"Missing source evidence: {repository}/{file}: {pattern}")
        evidence.append({"repository": repository, "file": file, "local_path": str(path),
            "source_commit": info["source_commit"], "pattern": pattern, "matches": hits,
            "source_url": f"https://github.com/{repository}/blob/{info['source_commit']}/{file}#L{hits[0]['line']}"})
    evidence.append({"repository": "jub0t/concat", "source_url": "https://concatenate.pages.dev/docs/transports/mcp/",
        "observation": "Official developer documentation: MCP prototype PR #69 was closed, not merged; JSON-RPC/gRPC are shipped. Source snapshot has no MCP server transport."})
    return evidence


def main():
    findings = []
    for repository, category, interface, capabilities, rendering, windows, license_name, limits in PROFILES:
        meta = META[repository]
        source = source_info(repository)
        findings.append({"repository": repository, "url": meta["url"], "stars": meta["stars"],
            "category": category, "agent_interface": interface, "capabilities": capabilities,
            "rendering": rendering, "windows": windows, "license_assessment": license_name,
            "limits": limits, "source_commit": source["source_commit"] if source else None,
            "source_inspected": bool(source), "runtime_tested": False, "checked_at_utc": meta["checked_at_utc"]})
    findings.sort(key=lambda item: item["stars"], reverse=True)
    evidence = build_evidence()
    (ROOT / "findings.json").write_text(json.dumps({"date": DATE, "scope": "18 selected public repositories, not a global exhaustive ranking", "findings": findings, "evidence": evidence}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = PROJECT / f"面向Agent的视频编辑内核_候选清单_{DATE}.csv"
    keys = ["repository", "stars", "category", "agent_interface", "capabilities", "rendering", "windows", "license_assessment", "limits", "url", "source_commit", "runtime_tested"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(findings)
    by_repo = {item["repository"]: item for item in findings}
    report = INTRO + "\n\n" + TABLE_INTRO + "\n\n"
    report += "| 项目 | Star | 定位 / Agent 接口 | 关键能力 | 渲染与 Windows 边界 |\n|---|---:|---|---|---|\n"
    for item in findings:
        report += f"| [{item['repository']}]({item['url']}) | {item['stars']:,} | {item['category']}；{item['agent_interface']} | {item['capabilities']} | {item['rendering']}；{item['windows']} |\n"
    report += DETAILS
    report += "\n\n## 逐项限制与许可\n\n"
    for item in findings:
        report += f"- **{item['repository']}**（{item['license_assessment']}）：{item['limits']}\n"
    report += "\n\n## 源码核验索引\n\n以下链接固定到本次检查的 commit，便于复查。代码存在与实机验证是两个阶段，本次仅完成前者。\n\n"
    for item in evidence:
        label = f"{item['repository']} · {item.get('file', '官方 MCP 状态文档')}"
        report += f"- [{label}]({item['source_url']})\n"
    report += "\n\n## 本地产物与验证范围\n\n"
    report += "- `research/agent-video-kernels/repository-metadata.json`：18 个仓库的 GitHub API 元数据与查询时间。\n"
    report += "- `research/agent-video-kernels/findings.json`：能力判断、边界、commit 和源码行号。\n"
    report += "- `research/agent-video-kernels/sources/`：16 个仓库的文本/代码快照，其中 OpenEdit 与 Monet 为选择性下载；不包含完整媒体资源、运行依赖和编译产物。\n"
    report += f"- `面向Agent的视频编辑内核_候选清单_{DATE}.csv`：按 Star 排序的筛选清单。\n"
    report += "\n本次执行公开网页/仓库读取与本地文档生成，没有安装或启动候选编辑器，也没有执行仓库脚本、渲染样片、调用 Docker/WSL 或打开浏览器标签页。未核验本机剪映版本、GPU 编译环境及候选程序的实际输出一致性。\n"
    report_path = PROJECT / f"面向Agent的视频编辑内核调研_{DATE}.md"
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps({"report": str(report_path), "csv": str(csv_path), "candidates": len(findings),
        "source_snapshots": sum(item["source_inspected"] for item in findings), "source_evidence_entries": len(evidence),
        "runtime_tested": False}, ensure_ascii=False, indent=2))


INTRO = """# 面向 Agent 的视频剪辑、编辑与自动化内核调研

核查日期：2026-10-11。工作目录：`E:/dev/sandbox/AI广告剪辑/`。

**结论：存在，而且已经有独立编辑器、无界面渲染内核和剪映草稿自动化三类实际程序。** 对“Agent 能剪、能套效果、能批量套运动”的需求已有实现；剪映全部专有 AI 特效的开放、稳定调用接口，则没有在本次筛选中得到证实。

本次按“公开代码是否实现编辑操作、Agent 如何调用、是否能最终渲染、Windows 如何运行”筛选。检索关键词包括 agent-native video editor、video editing MCP、CapCut/Jianying API、headless editing kernel、keyframes、beat sync、motion tracking。检索覆盖 GitHub 项目及项目自己的文档，选出 18 个候选，并读取其中 16 个仓库的源码文件。Star 是仓库当前总数，不能作为效果质量或稳定性的证明。

用户已确认“快速锚点应用”指 **关键帧与运镜预设**，本报告以此为重点；音乐卡点、物体跟踪作为补充。以下能力结论来自代码和文档，未进行本机安装或渲染测试。"""

TABLE_INTRO = """## 候选列表，按 GitHub Star 排序

这是本次相关候选的排序，不代表开源社区全量榜单。`video-use` 是工作流与脚本集合；最后一项为非商业许可的可查看源码项目，单独注明，不视为 OSI 开源。"""

DETAILS = """

## 最接近“面向 Agent 的剪映”的独立程序

**Concat：当前最值得优先评估的独立编辑内核。** 它有真实多轨编辑模型、GPU 效果包、关键帧、模板和最终导出，并提供 Windows 发行路线。源码中的 `concat-cli api/serve`、`edit.apply`、`template.instantiate`、`export.run` 构成可由 Agent 编程调用的完整链路；`SetClipKey` 和 `SetClipCutout` 是真实编辑命令。应用还包含本地自动字幕、TTS、背景移除能力；各能力经 API 暴露的范围应分别核对，不能推断 GUI 的每个 AI 按钮均有同名工具。

需要修正其 README 的接口宣传：**MCP 尚未正式合入主仓库**。官方文档说明旧 MCP 原型 PR #69 已关闭、未合并；当前应走 CLI/JSON-RPC，gRPC 需相应构建 feature。文档提供 Python MCP 桥接示意，但示意代码不等同于随软件发布的 MCP 服务。[官方接口状态](https://concatenate.pages.dev/docs/)、[官方 MCP 状态](https://concatenate.pages.dev/docs/transports/mcp/)、[编辑命令](https://concatenate.pages.dev/docs/api/edits/)

**Lumen：本次在锚点、卡点和跟踪方面最贴合需求的候选。** 原生 Electron 编辑器提供 HTTP MCP（默认端口 47910），Agent 工具与界面共用可撤销的命令系统。源码确认：`clip_animate` 将推拉、平移、Ken Burns、弹入、节拍 punch 等预设写成可编辑关键帧；`detect_beats/cut_to_beats` 分析音乐并重排镜头；`track_motion` 让标题、贴纸或蒙版跟随画面区域。跟踪实现是灰度图块模板匹配，存在丢失目标的返回状态，不能把它称作强鲁棒语义跟踪。生成图片/视频功能还需要对应外部服务。只有 7 Star，适合样片验证。[项目与源码](https://github.com/Mas-inx/lumen-ai-video-editor)

**Frontstage：另一条 Windows 桌面 + 外部 Agent MCP 路线。** 有独立 `packages/core` 时间线命令/撤销域、GPU 编辑/播放引擎、真实 MCP 服务实现；覆盖关键帧、调色、字幕、转场和素材生成。文档描述本地 Whisper/SigLIP，以及 fal.ai 生成素材服务；生成服务需要配置密钥。桌面应用需运行，13 Star，先验证素材兼容与输出一致性。[项目](https://github.com/x777/frontstage)

**Monet / OpenKlip：定位非常接近，但当前完整工作流主要面向 macOS。** Monet 明确围绕 Claude Code/Codex、CLI、MCP 和可读项目状态构建。对于本机 Windows，先保留为产品/架构参考。[Monet](https://github.com/Monet-AI-Editor/Monet)、[OpenKlip](https://github.com/craftled/openklip)

## 继续使用剪映时，哪些接口更合适

**pyJianYingDraft 是基础 SDK。** 适合由 Agent 通过 Python 生成多轨草稿、替换广告模板素材、加字幕、添加原生特效/转场和关键帧。你已经安装的 `$video-cut-jianying-editor` 包含 JyWrapper 与相关剪映草稿接口，可沿用为工作入口。它的 Skill 名称完成了本地注册；注册本身不证明剪映渲染链路已经运行通过。

兼容性要按模块看：上游 README 自报剪映 10.8 支持草稿关键帧、特效等多项功能，但蒙版尚不支持，模板读取可能需 `fallback_loader`；其**自动导出控制器只验证旧版 5.9/6.8，对剪映 7+ 的矩阵为不支持**。因此不能把“可生成新版草稿”当作“可无干预导出新版成片”。[上游兼容矩阵与导出说明](https://github.com/GuanYixuan/pyJianYingDraft/blob/main/README.md)

**VectCutAPI 适合 MCP 接入。** 公开 `mcp_server.py` 实现了素材、字幕、效果、关键帧和保存草稿等调用。Agent 可以直接编排这些操作；但 README 明确完整 Agent 应用、Web 编辑客户端及云渲染模块未开源，公开接口的终点主要是草稿。[项目](https://github.com/sun-guannan/VectCutAPI)

**capcut-mate 适合 HTTP/Coze 批量工作流。** 已实现特效列表/参数、添加效果、批量关键帧、关键帧数据生成与蒙版关键帧；比较适合把一个广告效果配方套用到多组素材。代码中的导出流程实际使用 Windows UI 自动化控制剪映，且有全局导出锁；它不是独立无界面渲染器。其控制器经过修改，不能直接照搬 pyJianYingDraft 的兼容矩阵，需针对目标客户端另做验证。[项目](https://github.com/Hommy-master/capcut-mate)、[关键帧参数 API](https://github.com/Hommy-master/capcut-mate/blob/main/docs/keyframes_infos.md)

**capcut-cli 适合 CLI/JSON 和模板快速复用。** 关键帧支持 `--batch` 读取 JSONL，以及 `linear/ease-in/ease-out/ease-in-out/hold` 缓动。需要区分：`make-preset` 保存的是文字样式，源码明确排除动画，因此不能当作现成运镜预设库。对剪映的现有草稿编辑，项目推荐 5.9.x，并对 6.0+ 有写入保护；加密检测没有解密能力。其 FFmpeg 预览可帮助检查时间安排，但特效、转场、关键帧等不能完整还原，源码会输出 `fidelity` 差异。以上是该 CLI 的支持范围，不能概括为所有新版剪映草稿 SDK 都不可用。[中文快速开始](https://github.com/renezander030/capcut-cli/blob/master/docs/quickstart.zh-CN.md)

## 无界面编辑与自动化内核

**OpenEdit 的 Agent 定位最明确。** 外部 Agent 通过 MCP 操作可逆编辑图，内核负责转录、媒体导入、代理预览、最终渲染与质量检查。服务源码和 Windows 配置均存在。实际限制是普通视频时间线渲染依赖 MLT/melt；安装文档说明 Windows 没有一键 melt 安装，需要自行构建 MLT。按照本项目禁止 WSL 的约束，原生构建成本必须计入选型。HyperFrames 动效叠加/纯动效渲染另有路径。[项目](https://github.com/AH64-dll/OpenEdit)、[Windows 运行要求](https://github.com/AH64-dll/OpenEdit/blob/main/INSTALL.md)

**video-mcp 提供较小的 Python + FFmpeg 内核。** 核心节拍分析调用 librosa，并将节拍规划、速度变化、重构图、调色和渲染操作暴露给 MCP；适合研究混剪/卡点流水线。0 Star，代码核查足以确认它有实际实现，尚不足以证明生产成熟度。[项目](https://github.com/MHughesDev/video-mcp)

**video-editor-mcp 是最小 Node/FFmpeg 工具层。** 有 9 个工具，适合简单拼接、叠加和混音。默认部署文档使用 Docker，不符合本项目约束；原生 Node/FFmpeg 需另行适配。Verbreel 的架构设计值得阅读，但当前公开最低交付能力有限，不作为现成全功能内核优先推荐。

## AI 特效与三类锚点能力

| 需求 | 已发现的实现 | 使用边界 |
|---|---|---|
| 原生剪映特效、花字、转场 | pyJianYingDraft、VectCutAPI、capcut-mate、capcut-cli | 通常把已知资源 ID、参数和时间范围写入草稿；成片由客户端渲染，资源缓存/版本/权限会影响结果 |
| AI 自动字幕、背景移除、视觉检索 | Concat 的本地 AI 能力；Frontstage 的 Whisper/SigLIP | 部分能力需模型文件；Agent 接口暴露范围应逐项核对 |
| 生成式 AI 画面/特效素材 | Lumen、Frontstage 等接外部生成服务后导入时间线 | 是服务/API 集成；没有证实开源项目能直接开放调用剪映全部专有 AI 生成按钮 |
| 关键帧、推拉摇移、预设快速套用 | Lumen 的 clip_animate；剪映 SDK 的 add_keyframe；capcut-cli 的 keyframe --batch；Concat 的 SetClipKey | Lumen 有现成运镜库；其他方案主要提供可编程关键帧，需建立自己的运镜配方 |
| 音乐卡点与时间标记 | Lumen 的 detect_beats/cut_to_beats；video-mcp 的 librosa 节拍计划 | 非稳定节拍素材可能需手工指定 BPM/切点；检测结果需听感检查 |
| 标题/贴纸锚定物体、蒙版跟随 | Lumen 的 track_motion | 真实模板匹配实现，遮挡/快速运动可能丢失；普通 position 关键帧本身不具备识别/跟踪能力 |

## 关键帧与运镜预设专项比较

| 候选 | 可以快速套用什么 | Agent 调用方式 | 配方复用成熟度 |
|---|---|---|---|
| Lumen | Ken Burns、推近/拉远、水平/垂直平移、漂移、滑入、弹入、punch 等 | `clip_animate`；可指定时段、强度和缓动 | 已有命名预设，转换为可编辑关键帧；本次最贴合该需求 |
| capcut-cli | 批量位置、缩放等关键帧及缓动 | `keyframe --batch` / JSONL | 可复用参数配方；`make-preset` 是文字样式，不是运镜库 |
| capcut-mate | 批量关键帧、按时段生成关键帧参数 | `keyframes_infos` + `add_keyframes` HTTP API | 适合把统一广告运镜配方套到多个片段，需自行定义配方 |
| Concat | 位置、缩放、旋转、透明度等关键帧 | `edit.apply` 的 `setClipKey`，以及模板实例化 | 可编程内核；现成“推近/平移”命名预设接口未得到同等确认 |
| pyJianYingDraft / JyWrapper | 素材上的位置、缩放、旋转等关键帧 | Python segment 的 `add_keyframe` | 沿用已有 Skill 即可组织配方；时间偏移、单位与 SDK 版本需核对 |

因此，“立即有命名运镜预设可调用”优先看 Lumen；“继续剪映、批量套自己的运动配方”优先看现有 JyWrapper / capcut-mate / capcut-cli。三者的草稿兼容性与最终导出仍需单独核验。

## 针对当前项目的选型建议

1. **要继续用剪映完成广告：沿用 `$video-cut-jianying-editor`，以 pyJianYingDraft 为基础。** 需要直接 MCP 时优先评估 VectCutAPI；需要批量参数/Coze/HTTP 时优先评估 capcut-mate。先核对目标剪映版本，再确定最终导出路线。
2. **要独立的 Agent 编辑与渲染内核：优先做 Concat 的 CLI/JSON-RPC 小样验证。** 关键验证点为多轨素材、效果包、模板实例化、关键帧和最终 MP4；MCP 接入作为单独桥接工作。
3. **最重视快速套运镜、音乐卡点、物体锚定：优先做 Lumen 功能验证，Frontstage 作第二个桌面候选。** 两者低 Star，先用短广告样片验证接口、撤销、效果与导出一致性。
4. **只要批量混剪与无界面自动化：评估 video-mcp + FFmpeg 的小型流水线。** OpenEdit 的编辑图/MCP 架构也合适，但本机先解决原生 MLT 构建成本。

建议样片验收内容：3 段本地素材、9:16 多轨时间线、字幕/Logo、一个特效、一组运镜关键帧、一个音乐卡点方案，以及最终 MP4 与编辑项目保存。若目标是物体锚定，再加“贴纸跟随 + 遮挡后恢复”样片。这只是后续验证标准，本次未执行安装或制作。
"""

if __name__ == "__main__":
    main()
