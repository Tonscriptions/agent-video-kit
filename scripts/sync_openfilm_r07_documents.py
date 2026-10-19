"""Publish the fixed 0.2.1 source review separately from product acceptance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from sync_color_automation_documents import marked

ROOT = Path(__file__).resolve().parents[1]
REPORT = "OpenFilm_0.2.1复用清单与成本复核_2026-10-19.md"
EVIDENCE = "validation/evidence/openfilm-reuse-20261019-r07-r3"
ACQUIRE = "validation/evidence/openfilm-refresh-20261019-r07"


def run():
    r = json.loads((ROOT / "docs" / ACQUIRE / "verification.json").read_bytes())
    v = json.loads((ROOT / "docs" / EVIDENCE / "verification.json").read_bytes())
    full = json.loads((ROOT / "docs/validation/evidence/audio-source-context-20261019-v64/full-r1.json").read_bytes())
    if (v["status"] != "completed_scoped_r07_review_with_cache_limitation"
            or v["totals"] != {"tests": 76, "pass": 75, "fail": 0, "skipped": 1}
            or not v["frozen_equal"] or not v["source_equal"]
            or full["frozen_after"] != v["frozen_after"] or not full["terminal_ok"]):
        raise ValueError("Completed fixed source checks and unchanged V64 product inputs required")
    at = datetime.fromisoformat(r["checked_at_utc"]).astimezone(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    head = r["head"]
    upstream = f"https://github.com/openfilm/openfilm/blob/{head}/"
    link = lambda label, path: f"[{label}]({upstream}{path})"
    summary = (f"2026-10-19 **R07（OpenFilm 0.2.1 源码研究）**：固定 `{head[:8]}`，API "
               f"**{r['stars']} stars /{r['forks']} forks** 为 {at} Asia/Taipei 时点；"
               "731→749 文件，37 新增/179 修改/19 changeset 删除。选定原测试 **75 通过/1 可选 DTD 跳过**，"
               "另 13 纯数据夹具通过；**同大小、还原 mtime 的内容修改未改变预览缓存键，直接复用门槛不通过**。"
               "优先候选为硬件编解码探测/显式回退、受控诊断；预览缓存需重写内容指纹，FCPXML 为可选交换。"
               "10 份创作 Skill 所在 31 文件、provider 目录 29 文件均与 R06 相同；"
               "既有 3 套本地工作流保留，不新增本地 AI 特效内核。196 产品输入与 V64 完整回归相同；"
               "本轮为研究，无新产品接入/成片/完整回归。")
    body = f"""# OpenFilm 0.2.1 复用清单与成本复核

**有可复用内容。继续保留 Agent Project＋Python/FFmpeg 主链，拆取独立模块与业务规则，能降低重复实现的成本。** 对当前项目，下一步价值最高的是硬件编解码能力探测与失败回退；字幕、HTML 动效、模板参数和三套创作流程已有采用记录。OpenFilm 的 HTML 页面动画与在线生成路由，不能单独补齐剪映的本地 AI 特效、人物处理、专业调色或完整模板素材库。

{summary}

## R07 固定来源与本轮实际检查

| 编号 | 检查 | 结果与证据 |
|---|---|---|
| R07-C01 | 版本 | [固定提交 `{head[:8]}`](https://github.com/openfilm/openfilm/commit/{head})，提交时间 {r['commit_at_utc']}；`packages/openfilm` 为 **0.2.1**。这是请求时点快照，不代表未来 main |
| R07-C02 | 社区量 | API **{r['stars']} stars /{r['forks']} forks**；获取完成 {r['checked_at_utc']} /{at} Asia/Taipei。[原响应与请求 SHA]({ACQUIRE}/requests.json)。属于仓库时点值，不能分别赋给十份 Skill |
| R07-C03 | 整树字节比较 | R06 `91b4e90c` 的 731→749 文件：**533 不变、37 新增、179 修改、19 删除**；19 个删除均为已消费的 `.changeset/*.md`。逐文件 SHA 与差异补丁见[获取收据]({ACQUIRE}/verification.json)。字节比较不等于逐行验收全部代码 |
| R07-C04 | 固定源码与许可 | [源码 ZIP](../sources/upstream/openfilm-refresh-20261019-r07/repo.zip)，{r['source_archive_bytes']:,} 字节，`{r['source_archive_sha256']}`；根 MIT 与现有随包许可原字节一致。{link('上游许可', 'LICENSE')}、{link('品牌规则', 'TRADEMARK.md')} |
| R07-C05 | 选定原始测试 | 8 个文件，**76 项：75 通过、0 失败、1 跳过**。涉及 film 文档、FCPXML、字幕、覆盖/模板字段、问题日志和诊断包；[stdout]({EVIDENCE}/upstream-selected.stdout.log)、[stderr]({EVIDENCE}/upstream-selected.stderr.log)。非完整上游套件 |
| R07-C06 | 独立夹具 | **13 项通过**：轨道标签/种类/1 ms 容差、编解码参数、色彩标签、诊断辅助函数、封面文件头、缓存正常变化。[执行脚本]({EVIDENCE}/pure-fixtures.mjs)、[机器结果]({EVIDENCE}/fixtures.json)。参数检查没有执行 GPU 或实际视频编码；PNG 文件头检查不是完整图像解码 |
| R07-C07 | 直接复用负例 | `a.html` 从 `AAAA` 改为 `BBBB`、保持大小并还原 mtime，SHA-256 不同而缓存键相同。**不接受直接用作本项目内容寻址缓存**；该项单列失败，不混入 13 通过数。见[前后 hash/key]({EVIDENCE}/fixtures.json) |
| R07-C08 | 本地环境与跳过 | Node **22.14.0** 运行选定子集；monorepo/doctor 要求 ≥22.18，package 声明仍为 ≥22.2。这不是完整环境兼容验收。可选 Final Cut Pro 1.10 DTD 不存在，保留 1 跳过；没有在目标 NLE 打开工程 |
| R07-C09 | 执行范围 | 测试 preload 拒绝网络/本地服务器/子进程，未触发拒绝；未运行上游 CLI、GUI、完整 doctor、硬件探测或模型。[限制器]({EVIDENCE}/no-runtime-io.mjs)。没有启动浏览器 tab、Docker/WSL/虚拟环境 |
| R07-C10 | 产品状态 | 全部 **749 上游文件**前后相同，**196 产品/测试/Schema/发行输入**与 V64 最近完成的 1410/1410 冻结相同。此处仅验证源码未变，没有重跑产品回归，也不把上游 75 项或 13 个夹具加到产品测试总数 |
| R07-C11 | 保留的开发失败 | [首轮]({EVIDENCE.replace('-r3', '')}/verification.json)：Windows `--import` 传入盘符路径、原测试未执行；修正为 file URL。[第二轮]({EVIDENCE.replace('-r3', '-r2')}/verification.json)：上游 75 通过/1 跳过，但独立 PNG 夹具误用仅 8 字节，违反上游 >8 字节条件；修正夹具，未改上游。最终 r3 通过；不累加重复运行数 |

## 编号复用清单

“已采用”按既有固定版本计；“候选”表示尚未接入产品。源码链接均固定本轮 SHA，便于复核。所谓节约是避免重复研究/实现相同规则，没有实际总人时基线，不给出项目节省百分比。

| 编号 | 可拆内容 | 能减少的工作 | 当前决定 /边界 |
|---|---|---|---|
| OFR07-01 | {link('subtitle-segments.mjs', 'packages/openfilm/studio/server/subtitle-segments.mjs')} | 中英文分句、数字单位保护、双语分段和局部回写 | **已采用，维护**。这是文本规则；ASR、翻译和声学词级定位仍由本地独立链路负责 |
| OFR07-02 | {link('timeline-edit.ts', 'packages/openfilm/studio/ui/src/lib/timeline-edit.ts')}、{link('transitions.ts', 'packages/openfilm/studio/ui/src/lib/transitions.ts')} | 关联、同步锁、主轨联动、添加/调长/移除转场的业务规划 | **部分规则已借鉴**。现有 Python 事务、整数 tick、作者窗和源句柄继续保留；上游毫秒模型和 UI 状态不能整体复制 |
| OFR07-03 | {link('saved.mjs', 'packages/openfilm/studio/server/saved.mjs')} / `saved-insert.ts` | 剪好的片头、CTA、字幕包装与素材组复用 | **工作流已适配**。本项目已有跨工程不可变片段组与权利闭包，重复建设第二套存储没有收益 |
| OFR07-04 | {link('host.mjs / frame 时钟', 'packages/openfilm/src/host.mjs')} | 通过 `frame(t)` 随机访问动画时刻，减少 HTML 动效执行约定设计 | **部分原码已采用**，继续用受控离线 HTML 后端。完整视频浏览器宿主、WebGL 和长片性能另验 |
| OFR07-05 | {link('overrides.mjs', 'packages/openfilm/src/overrides.mjs')}、{link('template-controls.ts', 'packages/openfilm/studio/ui/src/lib/template-controls.ts')} | CSS 参数、文字/图片替换、覆盖与恢复、字体/单位规则 | **已采用**。适合广告字卡和模板变量；美术模板数量、内容版权与自然审美不由控件代码提供 |
| OFR07-06 | {link('look.mjs / shared.mjs', 'packages/openfilm/src/shared.mjs')} | 接触表、同时间点审片和文字裁切诊断方法 | **部分诊断已采用并补强**。原 `cutText` 漏过的完全出框已在本项目历史门禁检出；抽帧不替代全片审片 |
| OFR07-07 | {link('十份官方创作 Skill', 'packages/openfilm/skills')} | 参考片重建、长转短、录屏演示、动效及风格工作的任务步骤 | **3 套已适配为本地 Skill**：`$video-cut-reference-remake`、`$video-cut-long-to-short`、`$video-cut-screen-demo`。其余七套可作为内容层候选；31 个目录文件相对 R06 原字节未变。没有新 Skill 自动提供缺失模型 |
| OFR07-08 | **新增** {link('encoders.mjs', 'packages/openfilm/src/encoders.mjs')} | 枚举 FFmpeg 编码器、短样本试用、逐平台参数、解码输出对照和失败回退策略 | **P1，优先原型**。拆纯参数/策略或改写 Python，适配现有任务、取消、资源和 manifest；本轮只验证参数/策略，不承诺本机硬件有效或提速倍数 |
| OFR07-09 | 更新的 {link('seekable.mjs', 'packages/openfilm/src/seekable.mjs')} | 浏览器不支持素材的本地中间副本、短 GOP、透明度与色彩标签保留策略 | **P2，随 HTML 媒体需求验证**。FFmpeg 主链本就能直接处理多种素材；只为真正遇到的浏览器解码瓶颈引入代理，原素材仍为音频/权利来源 |
| OFR07-10 | **新增** {link('preview-cache.mjs', 'packages/openfilm/studio/server/preview-cache.mjs')} | 区间预渲染、串行后台任务、陈旧任务取消、临时文件发布的流程 | **P2，借鉴状态机，重写缓存键**。本轮同大小/mtime 负例失败；还需完整资产闭包、内容 SHA、渲染器配置/版本、字幕及字体指纹。当前 CLI 不需要照搬 GUI 连续播放预览 |
| OFR07-11 | {link('render.mjs', 'packages/openfilm/src/render.mjs')} | 按空闲内存和核心限制浏览器并发、短任务单 worker、低优先级、异常清理 | **P1/P2，资源调度规则候选**。适配 Windows Job 和当前显存/任务策略；本轮没有真实浏览器、压力测试或提速测量 |
| OFR07-12 | {link('exports.mjs', 'packages/openfilm/studio/server/exports.mjs')} | 同画面尺寸/参数的多平台输出复用一次绘制，减少重复工作 | **P2，先做 CLI 批量导出规划器**。须比较完整渲染签名，分别确认音频、字幕、编码和权利；不能只按尺寸相同就视为相同输出 |
| OFR07-13 | **新增** {link('problems.mjs', 'packages/openfilm/src/problems.mjs')}、{link('doctor.mjs', 'packages/openfilm/src/doctor.mjs')}、{link('diagnostics.mjs', 'packages/openfilm/studio/server/diagnostics.mjs')} | 结构化故障摘要、有限历史、脱敏、诊断包与可修复提示 | **P1/P2，拆辅助函数**。沿用本项目 JSON 错误/任务日志，去掉默认 npm 检查和 Studio/Agent 聊天宿主收集；整体 doctor 默认联网/启动浏览器，不能作为本地 CLI 默认链。脱敏规则不是所有隐私场景的完备证明 |
| OFR07-14 | {link('fcpxml.mjs', 'packages/openfilm/studio/server/fcpxml.mjs')} / {link('nle.mjs', 'packages/openfilm/studio/server/nle.mjs')} | 有理帧率、轨道/音画关联、源范围、角色和音量等 XML 表达 | **P2，明确交换需求再接**。已有原测试子集；仍需 Agent Project 映射、逐项损失报告及目标 NLE 真实导入。HTML 等复杂效果会涉及烘焙，不能保留所有可编辑语义 |
| OFR07-15 | {link('jianying.mjs', 'packages/openfilm/studio/server/jianying.mjs')} | 作为明文草稿 JSON 字段和工程导出映射的研究参考 | **独立候选**。可研究数据序列化而不运行剪映；上游这部分是有限导出器，不是任意版本、加密草稿、完整效果的双向转换器。不会接入自动寻找剪映目录/打开剪映的运行路径 |
| OFR07-16 | {link('track-layout.mjs', 'packages/openfilm/studio/server/track-layout.mjs')} | 轨道类型、P/V/A 编号、重叠分层三个纯函数 | **P2，可直接拆小工具或改写 Python**。本轮再验 1 ms 容差，不能默认为本项目精确帧格规则；已有完整时间线时收益小 |
| OFR07-17 | {link('provider 目录', 'packages/openfilm/studio/server/providers')} / `get` | 服务商接口划分、失败表达、任务种类可参考 | **不接入本地生成运行链**。29 文件相对 R06 未变；外部服务路由不提供本地分割/修复/人物美容/运镜恢复的模型权重与推理实现 |
| OFR07-18 | Studio React / Electron /桌面 Agent 聊天 | 交互、附件、会话和窗口管理 | **当前不移植 GUI**。其中纯业务函数可另拆；`timeline-keys.ts` 处理键盘快捷键，不能误认为视频关键帧内核 |

配套 `openfilm/examples` 的两个描线函数已在历史 V48 独立核验并采用，来源是另一仓库，不计为本轮新模块或新媒体；见[原输入/实际成片/GIF](validation/离线逐笔描线动效实测_2026-10-18.md)。

## 重点功能能否直接补足

| 编号 | 目标 | OpenFilm 能提供 | 对当前项目仍需什么 |
|---|---|---|---|
| GAP07-01 | 关键帧与运镜预设 | `frame(t)` 页面动画、CSS 变换与创作说明；可编写平移、缩放、视差等效果 | 本项目已有可编辑时间线关键帧/运镜；新预设可基于现有能力编写并验收。相机运动恢复、自动语义锚点、任意动画代码转结构化曲线不能直接获得 |
| GAP07-02 | AI 特效与人物处理 | 页面合成、效果编排、在线服务请求路由 | 本地模型、权重、推理内核与自然质量；抠像、跟踪、修复、美颜/美体、复杂重光照等逐项建设和验收 |
| GAP07-03 | 完整模板与可商用素材库 | 模板参数和十套创作/风格说明；另有配套示例 | 可编辑模板资产、权利台账、字体/音效/音乐/媒体授权、版本和检索。MIT 代码不自动许可所有媒体或商标 |
| GAP07-04 | 对标剪映全部功能内核 | Agent CLI、HTML 文档协议、局部剪辑和工程导出组件 | 仍需本地专业音画处理、模型质量、长片/HDR/多设备稳定性及完整功能矩阵验收；不能从上游功能介绍推导全面等价 |

## 后续接入成本与顺序

估算假设：一名熟悉当前 Python/Node/FFmpeg 代码的工程师，每人日约六小时有效开发；使用既有依赖和明确输入。以下是**剩余适配投入的规划值**，不是实测节约人日，各项共享工具和核验不能机械相加。

| 优先级 | 任务 | 剩余适配估计 | 包含与不包含 |
|---|---|---|---|
| 1 | OFR07-08 硬件编解码探测与显式回退 | **Windows 受控原型 1–2 人日；生产接入总计 3–6 人日，含原型** | 参数/探测、错误与取消、设备及回退记录、编码前后画面/色彩/时长核验；不包含所有 GPU/驱动/操作系统认证，不承诺固定提速 |
| 2 | OFR07-13 本地故障摘要与诊断包 | **1–2 人日**，限纯本地辅助逻辑 | 基于既有日志结构、错误原因、有限历史、测试脱敏和 JSON 交付；不引入桌面 Agent 宿主或全量聊天日志收集 |
| 3 | OFR07-11 /12 并发预算与批量绘制去重 | **2–4 人日，共享规划器范围** | 当前 CLI/HTML 后端中的小范围适配和定向核验；多平台长片压力/性能基准另做，不据源码注释宣称速度 |
| 4 | OFR07-10 预览区间缓存 | **2–4 人日**，只在出现重复渲染需求时 | 内容 SHA、字体/字幕/资产闭包、版本指纹、取消/失效；不包括 GUI 播放器。原项目已有缓存/队列，先评估整合收益 |
| 5 | OFR07-14 FCPXML/xmeml | **共享映射/序列化 3–6 人日**，沿用既有 R05/R06 估计 | 作者时间图与损失报告；完整目标 NLE/复杂项目兼容另需实际环境验收，不与其它格式重复计费 |
| 6 | OFR07-16 纯轨道函数 | **0.5–1 人日** | 小范围适配及时间边界核验；当前已有时间线，因此优先级低 |
| 维护 | OFR07-01..07 已采用部分 | **本轮不重复估算迁移收益** | 17 个本地 Skills 中的三套流程及字幕/动效/模板继续沿用；其余七套风格说明不等于七个新处理内核 |

建议先推进硬件编解码原型，其次用已有模板/工作流构建真实广告内容；格式交换按交付需要安排。本次范围是核查与决策，候选均尚未接入产品。本项目的开放质量缺口仍按[能力覆盖与验收矩阵](validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md)逐项推进。

## 已有实片、许可与复现

已落地三套流程的[原输入、实际输出、GIF 和失败记录](validation/OpenFilm三套本地创作Skill与实片核验_2026-10-19.md)属于 **V61 历史产品演示**；本轮没有产生新视频。既有 HTML、字幕、模板和描线的采用版本及 MIT 声明见[第三方复用说明](third-party/OpenFilm复用声明_2026-10-17.md)。本次下载的 0.2.1 不替换产品已固定模块。

```powershell
# 使用已经固定的 0.2.1 快照；--output 必须是未使用的新目录。
C:/Python313/python.exe -B -X utf8 scripts/audit_openfilm_r07.py --refresh docs/validation/evidence/openfilm-refresh-20261019-r07/verification.json --output docs/validation/evidence/<新R07目录>
```

检查器只接受本次 SHA。原生 Windows 测试使用 E 盘临时目录，不安装依赖、不会启动上游 CLI/GUI、浏览器或外部服务；测试 I/O 限制器拒绝子进程和网络。开发获取源码所用网络记录在独立 acquisition 收据，不与产品离线执行混同。
"""
    (ROOT / "docs" / REPORT).write_text(body, encoding="utf-8", newline="\n")
    for name in ("README.md", "docs/README.md", "docs/构建进度总表_2026-10-16.md",
                 "docs/OpenFilm当前复用决策_2026-10-18.md", "docs/validation/README功能核验与实测演示_2026-10-16.md"):
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        prefix = "docs/" if name == "README.md" else "../" if name.startswith("docs/validation/") else "./"
        text = marked(text, "R07-RESEARCH", summary + f" [18 项复用/成本/证据]({prefix}{REPORT})。")
        if name == "README.md" and "| R07 |" not in text:
            rows = text.splitlines()
            i = next(i for i, row in enumerate(rows) if row.startswith("| R06 |"))
            rows.insert(i + 1, f"| R07 | OpenFilm 0.2.1 源码与降本复核 | f6a65ae5；749 文件；原测试 75 通过/1 跳过；13 纯数据夹具；196 产品输入不变 | 缓存同大小/mtime 负例失败；候选未接入、无新媒体/GPU/产品回归 | [18 项复用/投入/原证据]({prefix}{REPORT}) |")
            text = "\n".join(rows) + "\n"
        if name == "docs/OpenFilm当前复用决策_2026-10-18.md":
            text = text.replace("**当前复核 R04 /V54：", "**历史复核 R04 /V54（以下保留当轮状态，当前决定见上方 R07）：", 1)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"documents": 6, "research": "R07", "frozen_inputs": len(v["frozen_after"]), "product_inputs_match_v64": True}))


if __name__ == "__main__":
    run()
