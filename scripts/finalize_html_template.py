"""Publish terminal checks and current documentation, preserving earlier failures."""
from __future__ import annotations
import argparse,json,os,re,shutil
from pathlib import Path
from smoke_fragments import frozen,save,sha

ROOT=Path(__file__).resolve().parents[1]
CORE=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
      'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
      'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
REPORT='docs/validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md'
CONTRACT='docs/specs/离线HTML模板控件与覆盖恢复契约_v0.1_2026-10-18.md'


def relative(file,target):return Path(os.path.relpath(ROOT/target,(ROOT/file).parent)).as_posix()


def run(full_path,wheel_root):
    full=json.loads(full_path.read_text(encoding='utf-8'))
    assert full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0 and full['frozen_equal']
    assert full['methods']==1025 and full['frozen_after']==frozen() and len(frozen())==146
    evidence=ROOT/'docs/validation/evidence/html-template-20261018';fixture=json.loads((evidence/'verification.json').read_text(encoding='utf-8'))
    assert fixture['status']=='passed' and fixture['frozen_after']==frozen() and fixture['actual_cli_calls']==26
    wheel=json.loads((wheel_root/'verification.json').read_text(encoding='utf-8'))
    assert wheel['status']=='passed' and wheel['frozen_after']==frozen() and wheel['package_file_count']==100
    tests=ROOT/'docs/validation/evidence/html-template-tests-20261018';tests.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(full_path,tests/'full.json');shutil.copyfile(full_path.with_suffix('.log'),tests/'full.log')
    for number in range(1,7):
        path=ROOT/f'product/.runtime/html-template-tests-20261018-dev{number}.json'
        for suffix in ('.json','.log'):shutil.copyfile(path.with_suffix(suffix),tests/(f'dev{number}'+suffix))
    for source,name in [('html-template-full-20261018-final.json','full-initial-start.json'),
        ('html-template-full-20261018-final.log','full-initial.log'),('html-template-full-aborted-20261018.json','full-aborted.json'),
        ('html-template-full-aborted-owned-processes-20261018.json','full-aborted-owned-processes.json'),
        ('html-template-bg-policy-repro-20261018.json','background-policy-reproduction.json')]:
        shutil.copyfile(ROOT/'product/.runtime'/source,tests/name)
    release=ROOT/'docs/validation/evidence/html-template-wheel-20261018';release.mkdir(parents=True,exist_ok=False)
    for path in wheel_root.iterdir():
        if path.is_file() and (path.name.endswith(('.json','.log'))):shutil.copyfile(path,release/path.name)
    summary=(f'2026-10-18 **V45（产品）**：复用 OpenFilm MIT 模板字段与原字节覆盖/恢复函数，新增 `motion html-controls` 和 '
        '`html-render --overrides`；CSS 单位、原文/换行、已登记图片、逐帧恢复、配方继承/单项 null 撤销及跨工程重建可用。'
        f'完整 **1025/1025，{full["suite_seconds"]:.3f} 秒**，0 跳过；**146 文件（含测试）**冻结，20 新增专项为全量子集。'
        '原创样例 **26 CLI / 72 编码帧**，144 次额外乱序重绘、2 次单帧检查；17,280 品牌像素及 84,924 不透明图片像素与独立参考一致，'
        '继承/撤销/工程包/片段组重建 RGBA 一致，浏览器 Job 全部回收。**100 包内文件 / 11 独立进程 CLI** 的离线 wheel、'
        '**14 Skills / 150 引用**通过。三时刻静帧目检，未连续播放；原创样例无音频、0 新模型推理。缺字/越界、自然广告美学、'
        '长片/HDR、Schema 随包/干净机器及完整剪映等价仍未验收；FGT 继续为 V44 研究候选，自然画质和来源链未关闭。')
    for file in CORE:
        path=ROOT/file;text=path.read_text(encoding='utf-8-sig');assert 'V45（产品）' not in text,file
        text=re.sub(r'(?m)^2026-10-18 \*\*V44',r'历史研究 2026-10-18 **V44',text)
        text=re.sub(r'(?m)^2026-10-18 \*\*V43',r'历史产品 2026-10-18 **V43',text)
        block=summary+f' [契约]({relative(file,CONTRACT)})、[原片/GIF/完整实测]({relative(file,REPORT)})。\n\n'
        if file=='README.md':position=text.index('历史研究 2026-10-18 **V44')
        else:position=text.index('\n')+1
        text=text[:position]+'\n'+block+text[position:]
        path.write_text(text,encoding='utf-8',newline='\n')
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    row=('| V45 | OpenFilm HTML 模板控件与覆盖恢复 | 实际 CSS/文字/图片控件；26 CLI、72 HTML 帧，继承/撤销与工程包/片段组 RGBA 一致；'
        '完整 1025/1025，146 文件冻结；100 文件 wheel/11 新进程 CLI；14 Skills/150 引用 | 20 新增专项是全量子集；'
        '三时刻静帧，无连续播放；缺字/布局/自然广告美学、HDR/长片/干净机器及剪映等价未验收 | '
        f'[原片/GIF/实测]({REPORT})、[独立像素/迁移]({evidence.relative_to(ROOT).as_posix()}/verification.json)、'
        '[全量](docs/validation/evidence/html-template-tests-20261018/full.json) |')
    text=re.sub(r'(?m)^(\| V44 \|.*)$',lambda m:m[0]+'\n'+row,text)
    gallery=('\n**V45 离线模板控件**：左为原模板，中为换品牌色/图片/文案，右为 null 撤销后重建。'
        '三列为实际同帧输出；原片 384×216、12 帧/6 fps/2 秒；GIF 768×144、12 帧/2 秒，无音频。\n\n'
        '![V45 原模板、覆盖与恢复](docs/assets/html-template-20261018/comparison.gif)\n\n'
        '[原模板视频](docs/assets/html-template-20261018/original.mp4) · [修改后视频](docs/assets/html-template-20261018/changed.mp4) · '
        '[恢复视频](docs/assets/html-template-20261018/restored.mp4) · [实际联系表](docs/assets/html-template-20261018/contact.png) · '
        f'[来源/逐帧证据]({REPORT})\n')
    text=text.replace('## 实测演示素材\n','## 实测演示素材\n'+gallery,1)
    update=('\nV45 已进一步采用 O14：MIT 原字节 `overrides.mjs` 和四个模板字段函数，现有离线 host 可发现 CSS/文字/图片控件、'
        '保存覆盖并单项恢复；工程包及片段组实际重建通过。新的 Git 引用检查确认 main 仍为 `eefd6a8d`，'
        '星数仅沿用下方 08:38 的 API 快照，不把缓存页面或失败的新 API 请求当成最新计数。'
        '[最新采用与剩余范围](docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md#v45-html-模板控件受控接入)、'
        '[来源引用检查](docs/validation/evidence/openfilm-template-current-20261018/verification.json)。'
        'O15 三种创作流程、完整页面/媒体范围、布局/字体诊断仍可继续复用；没有实测人时，不能据此宣称节省某个工期比例。\n')
    text=text.replace('## 开源复用核查\n','## 开源复用核查\n'+update,1)
    text=text.replace('2026-10-18 08:38（Asia/Taipei）最新 API：OpenFilm',
        '2026-10-18 08:38（Asia/Taipei）API 历史快照：OpenFilm')
    text=text.replace('下一个可复用范围是离线模板变量/诊断和官方 Skill 工作流。',
        'V45 已采用离线模板字段与覆盖恢复；剩余可复用范围包括布局/字体诊断和官方 Skill 工作流。')
    old_status='最近产品 V43 完整 **1005/1005**、0 跳过；V44 FGT 研究受控门槛通过，141 生产文件不变，未接入产品。'
    assert old_status in text
    text=text.replace(old_status,'最近产品 V45 完整 **1025/1025**、0 跳过，146 文件（含测试）冻结；模板控件、覆盖/撤销与跨工程实际重建通过。V44 FGT 仍未接入产品。')
    readme.write_text(text,encoding='utf-8',newline='\n')
    progress=ROOT/'docs/构建进度总表_2026-10-16.md';text=progress.read_text(encoding='utf-8')
    text=text.replace('V41 HTML/CSS/SVG/Canvas 源闭包、强类型参数及新版本重建','V41 源闭包/参数；V45 CSS 单位/文字/图片控件、覆盖/撤销和可迁移配方')
    text=text.replace('条件/复杂槽位图、自动 CSS 控件/缺字越界诊断、展开多轨/跨执行上下文','条件/复杂槽位图、Canvas 语义控件/缺字越界诊断、展开多轨/跨执行上下文')
    text=text.replace('完整 975/975、137 文件冻结；HTML 五组与独立 alpha/RGB 合成核验；wheel 94 文件/11 独立 CLI；历史源编辑证据保留',
        f'V45 完整 1025/1025、146 文件（含测试）冻结；26 CLI/72 HTML 帧和独立像素；wheel 100 文件/11 独立 CLI；历史失败保留')
    text=text.replace('六静帧目检、无连续播放/听审；Schema 随包','当前三时刻联系表、无连续播放、样例无音频；Schema 随包')
    progress.write_text(text,encoding='utf-8',newline='\n')
    matrix=ROOT/CORE[-1];text=matrix.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^\| HTML 动效（V41）.*$',
        '| HTML 动效/模板（V41/V45） | 固定本地工具链、源闭包、透明 NUT、CSS/文字/图片控件、覆盖继承/null 撤销、全帧多顺序核验和 Job 回收 | '
        '[26 CLI/72 帧、工程包/片段组与独立像素](./离线HTML模板控件与覆盖恢复实测_2026-10-18.md)；20 新增专项为完整 1025 子集 | '
        '全 film.html/嵌入媒体/WebGL/Canvas 语义控件/字体布局诊断/中文复杂排版/自然画质/HDR/长片/干净机器未验 |',text)
    matrix.write_text(text,encoding='utf-8',newline='\n')
    report=ROOT/REPORT;text=report.read_text(encoding='utf-8')
    text=text.replace('当前正在完成全量回归与发行检查；最终数值以本文件后续写入的终态证据为准。',
        '完整回归、实际公开样例、原生发行和技能检查已取得下方终态证据；功能与效果边界分别保留。')
    text=text.replace('原始原创输入、实际三列成片与 GIF 将以最终批次发布；',
        '原始原创输入、实际三列成片与 GIF 随下方最终批次发布；')
    text+='\n## 本轮终态证据\n\n'+summary+'\n\n'
    text+='''| 编号 | 实际执行 | 结果与证据 |
|---|---|---|
| T01 | MIT 来源与采用字节 | 原 overrides 4117 字节；字段函数去 TS 后 2032 字节；原 MIT 与固定 ZIP 对照通过 |
| T02 | 实际控件检查 | 第 3 帧在两个新上下文绘制一致，CSS 数值单位、品牌色、字体族识别与有效替换返回；不修改工程/台账 |
| T03 | 实际成片 | 6 次成功 HTML 渲染共 72 帧；额外 144 次乱序重绘是同一输出的验证，不算新素材场景；精确 PTS |
| T04 | 独立像素参考 | 17,280 品牌条像素和 84,924 PNG 不透明内部像素完全一致；不是以同一渲染器另做参考 |
| T05 | 继承与撤销 | 未提供新覆盖时实际 RGBA 与已有修改一致；null 撤销全部指定项后与原模板全帧一致 |
| T06 | 工程包/片段组 | 各重建 12 帧，已包含在 T03；新图片与源码 ID/权利闭包保留，片段组图片 ID 实际重映射 |
| T07 | 实际拒绝 | 缺失 selector 运行失败且工程/台账不变、无新编码资产；网络 CSS 值与变化图片摘要在 dry-run 拒绝；Job 全回收 |
| T08 | 发行 | 100 包内文件逐字节一致，11 次 fresh-process CLI，Python host 阻断 NumPy/Pillow/Torch 与网络连接后仍可重建；明确依赖已有原生工具链 |
| T09 | 技能与注册 | 14 个 video-cut Skills，150 本地引用；三份正文更新，历史哈希/审计保留；没有自动安装上游十份在线流程 |
| T10 | 完整产品回归 | 1025/1025、0 skip；20 新增专项是子集，不能再加 56 预检、26 CLI、11 发行进程或历史通过数 |

机器证据：[实际样例](evidence/html-template-20261018/verification.json)、[完整回归与冻结](evidence/html-template-tests-20261018/full.json)、[原始日志](evidence/html-template-tests-20261018/full.log)、[wheel](evidence/html-template-wheel-20261018/verification.json)、[Skills](evidence/html-template-skills-20261018.json)。dev1–dev6 的 JSON/日志保留在同一个 tests 目录；dev3 冻结失败不算通过。第一次完整回归出现背景图片场景策略失败后明确中止，保留[中止/冻结/所属进程](evidence/html-template-tests-20261018/full-aborted.json)、[原始未完日志](evidence/html-template-tests-20261018/full-initial.log)、[独立复现](evidence/html-template-tests-20261018/background-policy-reproduction.json)，没有完整通过数；修复并添加普通文字/CSS 与真实网络地址的区分检查后重跑本节全量。中间通过批次另存为 [interim](evidence/html-template-interim-20261018/verification.json) 和[策略修复前批次](evidence/html-template-pre-policy-20261018/verification.json)，其原媒体仅保留本地 ignored runtime，不作为当前图库；最终批次及发布版媒体以本节证据为准。

## 原片和实际预览

三列依次为原模板、覆盖、null 恢复；三行静帧为 0/5/11。仅静态目检，不声称连续播放或自然广告审美验收。

![实际模板变化](../assets/html-template-20261018/comparison.gif)

[原模板](../assets/html-template-20261018/original.mp4) · [修改](../assets/html-template-20261018/changed.mp4) · [恢复](../assets/html-template-20261018/restored.mp4) · [对比 MP4](../assets/html-template-20261018/comparison.mp4) · [联系表](../assets/html-template-20261018/contact.png)

四份 MP4 预览为 H.264/YUV420p CRF18；同名 `*-lossless.mp4` 保留 RGB CRF0，三份 `*-alpha.nut` 保留原始 FFV1/BGRA。像素门槛在实际无损输出核对，不以压缩 GIF/MP4 判定精确颜色。GIF 768×144、12 帧、[170,160,170] ms 循环四次恰为 2 秒，无音频。[媒体发布与探测](evidence/html-template-20261018/media-publication.json)保留原生成媒体摘要和之后的预览转码，不重跑页面或模型。[原创源码/图像/字体](../assets/html-template-20261018/template/manifest.json)、[覆盖](../assets/html-template-20261018/overrides.json)、[撤销](../assets/html-template-20261018/reset.json)、[来源](../assets/html-template-20261018/provenance.json)。

## 使用

```powershell
ai-ad-editor motion html-controls --project E:\\work\\ad --source-asset-id title --frame-index 0
ai-ad-editor motion html-render --project E:\\work\\ad --source-asset-id title --asset-id title_v2 --overrides E:\\work\\changes.json --dry-run
ai-ad-editor motion html-render --project E:\\work\\ad --from-asset-id title_v2 --asset-id title_v3 --overrides E:\\work\\reset.json
```

执行前登记已有本地 Node/Playwright/Chromium；`dry-run` 只规划，不能检查 CSS selector 是否在实际 DOM 存在。正式输出使用新 ID，源包和旧输出不覆盖；成功后检查报告的实际目标、精确时钟、全帧顺序与浏览器关闭/原生 Job 回收。CSS 根变量只覆盖声明值，保留单位；字体族可以识别，但新增字体文件须另建已登记资源的源码版本，系统字体/缺字与排版效果未验收。
'''
    report.write_text(text,encoding='utf-8',newline='\n')
    openfilm=ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md'
    text=openfilm.read_text(encoding='utf-8')
    current_reuse='''
**当前结论（V45）**：OpenFilm 可以降低局部模块的二次开发成本，适合接入现有 Agent Project + Python/FFmpeg 主链。已采用的原码、借鉴的业务规则和仍待适配的能力分开记录：

| 优先级 | 模块 | 当前采用方式 | 能减少的工作 / 剩余成本 |
|---|---|---|---|
| 1 | O14 模板字段、覆盖与恢复 | 本轮采用原 MIT overrides 字节和四个纯字段函数；本地 CLI/资源闭包自行集成 | 复用字段分类、直接文字/图片覆盖和恢复规则；字体布局诊断、Canvas 内部语义仍需实现 |
| 2 | O01 字幕分句 | 既有固定原码 worker | 可复用分句、数字单位与双语规则；本地 ASR、逐字对齐和声音质量继续独立建设 |
| 3 | O02/O03/O13 时间线与片段组 | 既有部分规则/流程借鉴，本项目作者时钟与资源/权利事务实现 | 可复用操作规划和可编辑组工作流；不重复移植已实现主链，剩余源范围/展开多轨另验 |
| 4 | O04–O06 帧时钟、HTML 动效与诊断 | 既有原码时钟和本地最小 host | HTML 动效与乱序重绘已经可用；下一步重点字体/布局诊断，完整媒体/WebGL/HDR 未验 |
| 5 | O15 官方创作 Skills | 尚未安装或宣称产品接入；优先参考片、录屏、长转短 | 可复用任务步骤和对照片段标准；需绑定现有本地工具、模型、素材和实际验收 |

本轮功能验证、公开原片/GIF、失败记录及发行检查见[产品实测](validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)。代码许可不能替代素材/字体/模型权利；在线 provider、Studio/Electron 不在采用范围。下文人日均为历史同范围估算，没有实测总人时或项目节省比例，不能加总为剪映全量工期。当前源码引用检查见[固定 main/新 API 失败记录](validation/evidence/openfilm-template-current-20261018/verification.json)，不将旧星数写成新计数。

'''
    position=text.index('**最新落地状态（V41）**')
    text=text[:position]+current_reuse+text[position:]
    text=text.replace('**最新落地状态（V41）**：','**V41 落地状态（历史；V45 见末节）**：',1)
    text=text.replace('本项目 JSON 模板变量已有；这是将来 HTML 模板桥，不能当新增全套模板系统；需资源/字体权利与离线闭包',
        '**V45 已接入受控子集**：实际 CSS/文字/图片控件、逐帧覆盖与恢复、配方继承/null 撤销及迁移；Canvas 语义控件、字体/布局诊断仍未验收')
    text=text.replace('**随 HTML 后端，1–3 人日增量**；同范围从头约 3–5；不含 HTML 渲染',
        '历史估算：增量 1–3 人日、从头约 3–5；已接入范围见末节，没有采集实测人时')
    text=text.replace('HTML 动效仍独立设为可选后端里程碑。',
        '后续 V41 已交付可选的最小 HTML 后端，V45 补齐模板控件；剩余页面/媒体范围仍独立验收。')
    openfilm.write_text(text,encoding='utf-8',newline='\n')
    with openfilm.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write('\n## V45 HTML 模板控件受控接入\n\n'+summary+'\n\n')
        stream.write('''| 原编号 | 本轮采用 / 结果 | 剩余范围 |
|---|---|---|
| O14 | 原字节 overrides.mjs + 四个模板字段函数；CSS/单位、文字/换行、img/bg 图片控件、逐帧恢复、配方继承/null 撤销；工程包和片段组实际重建 | Canvas 内部语义控件、完整页面编辑、字体选择器/缺字/布局诊断；不得把最小控件当成所有网页可编辑 |
| O01/O02/O13/O04–O06 | 继续保留既有字幕、关联、片段组、时钟和离线 host，未重复计收益 | 全 film.html、媒体/WebGL 与自然质量仍独立验收 |
| O15 | 十份官方 Skill 仍为流程候选，优先 reference/replicate、screen-demo、long-to-short 的本地绑定 | 原文 npx/get/provider 不能原样执行；文档不提供 ASR、跟踪、视觉理解或修复算法 |

下一批诊断优先提取 DOM 检查，不整套引入上游 host。固定源码的 [look.mjs 第 45 行](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/src/look.mjs#L45) 仅检查 FontFace 加载 error，不能证明所用字体覆盖全部中文字形。实际裁切函数位于 [shared.mjs 的 cutText](https://github.com/openfilm/openfilm/blob/eefd6a8d379289102141359a4718dbab12170526/packages/openfilm/src/shared.mjs#L361)，扫描 DOM 文字 Range：2 CSS 像素容差、最多 50 条、只报告仍与画面/容器有交集的部分裁切，完全在画面外的文字可能漏检；不提供 Canvas/SVG 语义文字或字形覆盖检查。look 在至少两个采样帧发现后给警告，不代表整段布局通过。共享模块间接耦合 host/Playwright，上游 host 还有可选网络放行，接入时继续使用本项目断网和 Job 回收边界。[本次三文件静态复核](validation/evidence/openfilm-template-current-20261018/diagnostics-source-review.json)没有新增运行检查或生产采用，也不增加上游 20 测试计数。

本轮只重新确认 main 引用仍为固定提交，API 新请求遇到本机 DNS 失败，星数沿用 V44 的 08:38 快照；没有再核验全部 702 文件或上游 20 测试。[引用与失败](validation/evidence/openfilm-template-current-20261018/verification.json)、[实际采用字节](validation/evidence/openfilm-template-adoption-20261018-e2/verification.json)、[产品终态与原片](validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)。原 1–3/3–5 人日是同范围历史估算；本轮没有采集真实人时，不能宣称整个差额或项目百分比已经节省。FGT 权利与自然画质未通过，不把它混入 OpenFilm 的 MIT 采用清单。
''')
    notice=ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md'
    with notice.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write('''\n## V45：模板字段与 DOM 覆盖原码

固定 `eefd6a8d379289102141359a4718dbab12170526` 的 `packages/openfilm/src/overrides.mjs` 按原 4117 字节写入 [openfilm_overrides.mjs](../../product/src/ai_ad_editor/openfilm_overrides.mjs)。`studio/ui/src/lib/template-controls.ts` 中 COLOR/NUMBER/QUOTED、fieldOf/isFontVar/valueOf/labelOf 提取到 [openfilm_template_fields.mjs](../../product/src/ai_ad_editor/openfilm_template_fields.mjs)，仅移除 TypeScript 标注/非空断言，2032 字节；文件头保留原作者、固定来源与 MIT 指向。两份原文和根 LICENSE、ZIP/SHA、适配记录见[采用证据](../validation/evidence/openfilm-template-adoption-20261018-e2/verification.json)。

新 [html_template.py](../../product/src/ai_ad_editor/html_template.py)、[DOM 桥](../../product/src/ai_ad_editor/html_template_dom.mjs) 和原生 CLI/配方/权利闭包为本项目验证与集成实现，不导入 React/Studio/Electron/供应商或上游 host。每帧先恢复原状态，再执行页面 frame，最后应用覆盖；不得把原 MIT 改写为素材、字体或新内容许可。100 包内文件逐字节核对，原 MIT/7 份 MJS 随 wheel 保留，[发行证据](../validation/evidence/html-template-wheel-20261018/verification.json)。外部 Node/Playwright/Chromium 仍显式登记，不随包下载；Schema 随包和干净机器仍未验收。
''')
    cli_contract=ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md'
    with cli_contract.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write('''\n## V45 HTML 模板增量

`motion html-controls --project --source-asset-id|--from-asset-id [--params] [--overrides] [--frame-index 0] [--timeout-seconds 120] [--cancel-file]`：单个 CFR 帧/两个新上下文的实际控件检查，不编码或登记资产，返回 controls/effective_controls/采样摘要和回收报告；dry-run 不启动浏览器。`motion html-render` 新增 `--overrides <本地 JSON>`，保存到新输出的 html_motion.template_overrides；省略项继承，null 删除已有覆盖。图片使用 asset_id、独立摘要及权利依赖，可随工程包/片段组重映射。CSS 数值单位必须明确，无效/缺失目标和错图片类型运行时拒绝；dry-run 不冒充 DOM 验收。

字段与预算、逐帧恢复/动画时钟和实际发布边界见[契约](./离线HTML模板控件与覆盖恢复契约_v0.1_2026-10-18.md)、[原片/终态/失败](../validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)。这两个命令继续执行原生 Windows/离线工具链、超时取消和 Job 回收约束。
''')
    contract=ROOT/CONTRACT;text=contract.read_text(encoding='utf-8')
    text=text.replace('状态：V45 开发预声明；测试和成片证据另行记录。',
        '状态：V45 已实现的受控范围；以下约束于开发前声明，[测试和成片终态证据](../validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)另行记录。')
    contract.write_text(text,encoding='utf-8',newline='\n')
    save(evidence/'terminal-publication.json',{'status':'passed','full_methods':full['methods'],'full_seconds':full['suite_seconds'],
        'frozen_file_count':146,'new_methods_subset':20,'wheel_package_files':100,'fresh_wheel_clis':11,
        'fixture_cli_calls':26,'fixture_encoded_frames':72,'skills':14,'skill_links':150,'finalizer_sha256':sha(Path(__file__))})
    print(json.dumps({'documents_updated':12,'methods':full['methods'],'seconds':full['suite_seconds']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',type=Path,required=True);parser.add_argument('--wheel',type=Path,required=True)
    args=parser.parse_args();run(args.full.resolve(),args.wheel.resolve())
