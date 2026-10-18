"""Publish V46 terminal evidence and documentation without changing frozen code."""
from __future__ import annotations
import argparse,json,os,re,shutil
from pathlib import Path
from smoke_fragments import frozen,save,sha

ROOT=Path(__file__).resolve().parents[1]
CORE=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
      'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
      'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
REPORT='docs/validation/HTML文字布局与字体覆盖实测_2026-10-18.md'
CONTRACT='docs/specs/HTML文字布局与字体覆盖核验契约_v0.1_2026-10-18.md'


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def relative(file,target):return Path(os.path.relpath(ROOT/target,(ROOT/file).parent)).as_posix()


def run(full_path,wheel_root):
    full=load(full_path);current=frozen()
    assert full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0 and full['frozen_equal']
    assert full['methods']==1051 and full['frozen_after']==current and len(current)==152
    evidence=ROOT/'docs/validation/evidence/html-quality-20261018';fixture=load(evidence/'verification.json')
    assert fixture['status']=='passed' and fixture['frozen_after']==current and fixture['cli_calls']==26
    assert fixture['html_renders']==5 and fixture['quality_jobs']==9 and fixture['manual_static_review']['status']=='reviewed'
    wheel=load(wheel_root/'verification.json')
    assert wheel['status']=='passed' and wheel['frozen_after']==current and wheel['package_file_count']==104 and wheel['fresh_process_cli_calls']==14
    tests=ROOT/'docs/validation/evidence/html-quality-tests-20261018';tests.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(full_path,tests/'full.json');shutil.copyfile(full_path.with_suffix('.log'),tests/'full.log')
    for prefix,count,label in [('html-font-coverage-tests',4,'font'),('html-quality-tests',5,'quality')]:
        for number in range(1,count+1):
            path=ROOT/f'product/.runtime/{prefix}-20261018-dev{number}.json'
            for suffix in ('.json','.log'):shutil.copyfile(path.with_suffix(suffix),tests/(f'{label}-dev{number}'+suffix))
    release=ROOT/'docs/validation/evidence/html-quality-wheel-20261018';release.mkdir(parents=True,exist_ok=False)
    for path in wheel_root.iterdir():
        if path.is_file() and path.name.endswith(('.json','.log')):shutil.copyfile(path,release/path.name)
    summary=(f'2026-10-18 **V46（产品）**：采用 OpenFilm MIT `cutText` 原函数作同帧诊断对照，新增 `motion html-quality` 和 '
        '`html-render --layout-check strict`；逐帧检查部分/完全出框、容器独立轴裁切、实际平台字体及本地 Unicode→glyph 映射。'
        '严格门禁随配方继承并重新执行，失败报告/PNG 保留，工程/台账/新编码资产不变。'
        f'完整 **1051/1051，{full["suite_seconds"]:.3f} 秒**，0 跳过；**152 文件（含测试）**冻结，26 新增专项为全量子集。'
        '原创样例 **26 CLI / 60 编码帧**，120 次额外渲染重绘；9 次质量检查共 108 帧及 108 次独立反序重绘，'
        'FontTools 独立核对 120 个字符，33 页面全关闭/Job 回收，继承及工程包重建 RGBA 一致。'
        '**104 包内文件 / 14 独立进程 CLI** 的离线 wheel、**14 Skills / 156 引用**通过。'
        'V45 缺 O 字体负例及两轮开发实测失败保留；公开出框/裁切/修复使用新原创完整字体，不发布系统 fallback 像素。'
        '三时刻静帧，未连续播放；无音频、0 新模型推理。复杂字形/变换、WOFF2、自然质量、长片/HDR、Schema 随包/干净机器、'
        'FGT 自然画质与来源链及完整剪映等价仍未验收。')
    for file in CORE:
        path=ROOT/file;text=path.read_text(encoding='utf-8-sig');assert 'V46（产品）' not in text,file
        text=re.sub(r'(?m)^2026-10-18 \*\*V45',r'历史产品 2026-10-18 **V45',text)
        block=summary+f' [契约]({relative(file,CONTRACT)})、[原片/GIF/实测]({relative(file,REPORT)})。\n\n'
        position=text.index('历史产品 2026-10-18 **V45') if file=='README.md' else text.index('\n')+1
        text=text[:position]+'\n'+block+text[position:];path.write_text(text,encoding='utf-8',newline='\n')
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    row=('| V46 | HTML 全帧文字布局与本地字体覆盖门禁 | 部分/完全出框、独立轴裁切与实际字体映射；26 CLI/60 编码帧，'
        '9 次质量/108 帧、独立 FontTools 120 字符；继承/工程包 RGBA 一致；完整 1051/1051、152 文件冻结；104 文件 wheel/14 新进程；14 Skills/156 引用 | '
        '26 新增专项属全量子集；旧字体缺 O/开发失败保留；系统 fallback 不公开像素，复杂布局/塑形/自然质量/完整剪映等价未验 | '
        f'[原片/GIF/实测]({REPORT})、[机器证据]({evidence.relative_to(ROOT).as_posix()}/verification.json)、'
        '[全量](docs/validation/evidence/html-quality-tests-20261018/full.json) |')
    text=re.sub(r'(?m)^(\| V45 \|.*)$',lambda m:m[0]+'\n'+row,text)
    text=re.sub(r'(?m)^\| V13 \|.*$',
        '| V13 | 产品自动回归 | 最近 V46 完整 **1051/1051**、0 跳过；152 文件（含测试）冻结，26 新增专项为完整子集 | '
        '26 实测 CLI、14 wheel 新进程和历史研究分计；自然质量与完整剪映未验 | [完整日志](docs/validation/evidence/html-quality-tests-20261018/full.log)、'
        '[冻结与终态](docs/validation/evidence/html-quality-tests-20261018/full.json) |',text)
    gallery=('\n**V46 布局诊断与修复**：左为后段标题完全出框，中为 CTA 容器裁切，右为修复。'
        '实际三列输出使用新原创完整字体；旧字体的系统 fallback 仅发布诊断元数据。每列 384×216、12 帧/6 fps/2 秒；GIF 768×144、12 帧/2 秒，无音频。\n\n'
        '![V46 完全出框、容器裁切与修复](docs/assets/html-quality-20261018/comparison.gif)\n\n'
        '[出框视频](docs/assets/html-quality-20261018/outside.mp4) · [裁切视频](docs/assets/html-quality-20261018/clip.mp4) · '
        '[修复视频](docs/assets/html-quality-20261018/fixed.mp4) · [联系表](docs/assets/html-quality-20261018/contact.png) · '
        f'[诊断/失败/来源]({REPORT})\n')
    text=text.replace('## 实测演示素材\n','## 实测演示素材\n'+gallery,1)
    update=('\nV46 继续提取固定 `eefd6a8d` 的 MIT `cutText` 原函数（38 行，带来源头 2262 字节）作实际帧对照，'
        '本项目补充完全出框、独立轴裁切、body overflow 传播、标准库字体映射及严格门禁。'
        '原算法会漏掉本轮后 3 帧完全出框标题，新检查实际检出；字体加载成功不等于覆盖。'
        f'[采用与效果]({REPORT})、[固定 ZIP/原函数摘要](docs/validation/evidence/openfilm-layout-adoption-20261018/verification.json)。'
        '本轮未重新获取 GitHub 星数、核验整树或重跑上游测试；既有快照按各自时间保留。剩余重点是复杂字形/Canvas 语义、完整媒体范围与官方创作流程的本地绑定。\n')
    text=text.replace('## 开源复用核查\n','## 开源复用核查\n'+update,1)
    text=text.replace('最近产品 V45 完整 **1025/1025**、0 跳过，146 文件（含测试）冻结；模板控件、覆盖/撤销与跨工程实际重建通过。',
        '最近产品 V46 完整 **1051/1051**、0 跳过，152 文件（含测试）冻结；逐帧布局/字体门禁、继承及工程包重建通过。')
    text=text.replace('O15 三种创作流程、完整页面/媒体范围、布局/字体诊断仍可继续复用；','V45 当时剩余的 O15 创作流程、完整页面/媒体范围和布局/字体诊断仍需适配；布局/字体受控子集随后见 V46；')
    text=text.replace('剩余可复用范围包括布局/字体诊断和官方 Skill 工作流。','V46 已补充受控布局/字体诊断，剩余包括复杂布局语义和官方 Skill 工作流。')
    readme.write_text(text,encoding='utf-8',newline='\n')
    progress=ROOT/'docs/构建进度总表_2026-10-16.md';text=progress.read_text(encoding='utf-8')
    text=text.replace('V45 CSS 单位/文字/图片控件、覆盖/撤销和可迁移配方','V45 控件/覆盖/撤销；V46 全帧 DOM 出框/裁切、本地字体映射及可继承严格门禁')
    text=text.replace('条件/复杂槽位图、Canvas 语义控件/缺字越界诊断、展开多轨/跨执行上下文','条件/复杂槽位图、Canvas 语义/复杂字形与变换、WOFF2、展开多轨/跨执行上下文')
    text=text.replace('V45 完整 1025/1025、146 文件（含测试）冻结；26 CLI/72 HTML 帧和独立像素；wheel 100 文件/11 独立 CLI；历史失败保留',
        'V46 完整 1051/1051、152 文件（含测试）冻结；26 CLI/60 编码帧、108 质量帧；wheel 104 文件/14 独立 CLI；历史失败保留')
    progress.write_text(text,encoding='utf-8',newline='\n')
    matrix=ROOT/CORE[-1];text=matrix.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^\| HTML 动效/模板.*$',
        '| HTML 动效/模板/诊断（V41/V45/V46） | 固定本地工具链、源闭包、透明 NUT、控件/覆盖恢复、全帧出框/独立轴裁切与字体映射；严格模式继承/重建重新门禁，Job 回收 | '
        '[26 CLI/60 编码帧、108 质量帧与 FontTools 独立核对](./HTML文字布局与字体覆盖实测_2026-10-18.md)；26 新增专项为完整 1051 子集 | '
        '全 film.html/嵌入媒体/WebGL/Canvas 语义/复杂字形塑形/WOFF2/自然画质/HDR/长片/干净机器未验 |',text)
    matrix.write_text(text,encoding='utf-8',newline='\n')
    report=ROOT/REPORT;text=report.read_text(encoding='utf-8')
    text=text.replace('当前正在执行完整验证，终态数值另行补录；本文件不提前宣称完整回归通过。','完整回归、公开样例、离线 wheel 和技能检查均取得下方终态证据，功能与质量边界分别保留。')
    text+='''
第二轮实测完成 20 次 CLI 后，复现脚本误将工程包导入的必填 `--output` 写为 `--project`，在参数解析阶段退出 2；这是脚本错误，未产生完整通过结果。[原参数/错误/已有调用](evidence/html-quality-argument-failure-20261018/terminal.json)保留，修正后另建新目录完整重跑，没有覆盖失败记录。

## 终态与可复现证据

'''+summary+'''

| 编号 | 核验 | 实际结果 |
|---|---|---|
| T01 | 固定原码与本地扩展 | 原 `cutText` 38 行不改，用作同帧诊断对照；新的门禁不等于原算法完整兼容 |
| T02 | 原创缺字负例 | 旧字体 `O` 未映射；实际前 6 帧报告 U+004F 缺失及系统字体来源未核验，不发布 fallback 像素 |
| T03 | 独立字体参考 | 新增原创 O 后，FontTools 对全部 12 帧的 120 个非空白字符独立检查；生产解析不依赖 FontTools/NumPy/Pillow |
| T04 | 动态完全出框 | 第 9/10/11 帧标题完全出框；原 cutText 未报该标题，本项目全帧检查实际检出 |
| T05 | 独立 X 轴裁切 | CTA 容器 overflow-x:clip、overflow-y:visible，12 帧均只报告 X 轴 |
| T06 | 严格失败 | 缺字及完全出框两次编码前拒绝；实际报告/PNG 可读取，工程、台账和新编码资产未变 |
| T07 | 继承与可移植 | 正常 strict、继承重建、工程包导入重建均新执行门禁，36 帧 RGBA 相等；这 3 次已计入 5 渲染/60 帧 |
| T08 | 帧序与生命周期 | 9 次质量检查共 108 主帧及 108 独立反序重绘；5 次渲染另有 120 验证重绘；33 页开关相等且原生 Job 全回收 |
| T09 | 离线 wheel | 104 文件原字节、14 fresh-process CLI；阻断 Python NumPy/Pillow/Torch 和 socket 仍可核验/重建；另 24 编码帧与公开无损参考完全相同 |
| T10 | 全量和技能 | 1051/1051、0 跳过，152 文件冻结；26 新增方法是全量子集。14 Skills/156 本地引用和注册目录联接通过 |

[实际样例/媒体 SHA](evidence/html-quality-20261018/verification.json) · [全量终态](evidence/html-quality-tests-20261018/full.json) · [原日志](evidence/html-quality-tests-20261018/full.log) · [离线 wheel](evidence/html-quality-wheel-20261018/verification.json) · [Skills](evidence/html-quality-skills-20261018.json)。字体 dev1–dev4、质量 dev1–dev5 的原 JSON/日志均在 tests 目录，保留失败和不同冻结版本，不能累计为新的产品通过数。轮次来自 2026-10-18，本轮未重新运行历史上游整树/20 测试、FGT 或其他模型。

样例 `rights check` 按预期退出 7：新增源码/派生资产的商业发布权利仍未核验；布局/字体通过不提升 Rights Ledger 状态。公开生成的原创输入/几何演示具备单独 CC0 来源记录，不等于替所有工程资产关闭发布门禁。

## 原输入和实际输出

三列依次为后段完全出框、容器裁切、修复；联系表三行是第 0/8/11 帧，仅做静帧目检。原始模板为 [V45 原创输入](../assets/html-template-20261018/template/manifest.json)，V46 四份源码及字体都在 [本轮目录](../assets/html-quality-20261018/provenance.json)，旧字体版本保持原字节，不覆盖历史证据。

![实际出框、裁切与修复](../assets/html-quality-20261018/comparison.gif)

[出框 MP4](../assets/html-quality-20261018/outside.mp4) · [裁切 MP4](../assets/html-quality-20261018/clip.mp4) · [修复 MP4](../assets/html-quality-20261018/fixed.mp4) · [三列 MP4](../assets/html-quality-20261018/comparison.mp4) · [联系表](../assets/html-quality-20261018/contact.png) · [修复源码](../assets/html-quality-20261018/fixed/manifest.json)

每列实际成片 384×216、12 帧/6 fps/2 秒；三列 MP4 1152×216；H.264/YUV420p 仅供预览，`*-alpha.nut` 为无损 FFV1/BGRA 核验源。GIF 768×144、12 帧，[170,160,170] ms 循环四次共 2 秒，无音频。全帧解码/PTS 和命令质量自动检查不等于连续观看、听审或自然广告美学；0 新模型推理。

## CLI

```powershell
ai-ad-editor motion html-quality --project E:\\work\\ad --source-asset-id title --dry-run
ai-ad-editor motion html-quality --project E:\\work\\ad --source-asset-id title
ai-ad-editor motion html-render --project E:\\work\\ad --source-asset-id title --asset-id title_v2 --layout-check strict
ai-ad-editor motion html-render --project E:\\work\\ad --from-asset-id title_v2 --asset-id title_v3
```

最后一条继承 strict，重新核验后编码。源码模式未明确配置默认为 off，旧配方亦为 off；显式改为 off 是配置变更，不可把该输出称为严格验收。`html-quality` 失败退出 2，运行/超时错误 6，取消 8；失败报告位于 validation，预览位于 cache/html-quality，最多 8 帧。命令只写诊断，不登记资产；strict 全帧预检和正式渲染共享总期限。实际使用的 WOFF2/未知字体、变体序列、旋转/3D、复杂裁切/滤镜和 Canvas/SVG 文字等返回未核验，严格模式不能绕成通过。
'''
    report.write_text(text,encoding='utf-8',newline='\n')
    spec=ROOT/CONTRACT;text=spec.read_text(encoding='utf-8').replace('状态：V46 开发前声明。','状态：有效（V46 受控范围；初始条款于开发前声明）。')
    spec.write_text(text+'\n终态、原片与失败记录见[本轮实测](../validation/HTML文字布局与字体覆盖实测_2026-10-18.md)。\n',encoding='utf-8',newline='\n')
    reuse=ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md';text=reuse.read_text(encoding='utf-8')
    text=text.replace('**当前结论（V45）**','**当前结论（V46）**')
    text=text.replace('本轮采用原 MIT overrides 字节和四个纯字段函数','V45 采用原 MIT overrides 字节和四个纯字段函数')
    text=text.replace('字体布局诊断、Canvas 内部语义仍需实现','V46 已补受控字体映射/布局门禁；Canvas 内部语义和复杂塑形仍需实现')
    text=text.replace('既有原码时钟和本地最小 host | HTML 动效与乱序重绘已经可用；下一步重点字体/布局诊断，完整媒体/WebGL/HDR 未验',
        '原帧时钟、本地最小 host；V46 原 cutText 对照和扩展质量门禁 | 全帧出框/独立轴裁切/本地字体映射可用；复杂塑形/变换、完整媒体/WebGL/HDR 未验')
    text=text.replace('本轮功能验证、公开原片/GIF、失败记录及发行检查见[产品实测](validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)。',
        '当前 V46 功能/原片/GIF/失败/发行见[布局字体实测](validation/HTML文字布局与字体覆盖实测_2026-10-18.md)，V45 模板控件保留[当轮实测](validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)。')
    text=text.replace('下一批诊断优先提取 DOM 检查，不整套引入上游 host。','V45 当时的下一批诊断建议为提取 DOM 检查；随后 V46 受控接入见末节。')
    text+='''
## V46 全帧布局与字体映射受控接入

O04/O06 的 `shared.mjs:cutText` 原函数 38 行已提取为带来源头的 2262 字节 MIT 模块，同帧实际执行作对照。其 2 px/最多 50 条/只查部分相交限制按原样保留；产品新的 DOM 文字检查覆盖完全出框、overflow 独立轴和 body 传播，另通过 CDP 实际字体、标准库 SFNT/WOFF1 映射与明确预算实现 `html-quality`/strict 门禁。这些扩展不是上游原功能，未引入完整 host、Studio、在线服务或云模型。

本轮真实输出发现旧原创字体缺 O，前 6 帧实际 fallback/映射未核验；动态标题最后 3 帧完全出框由新检查检出，原函数未报。修复后严格门禁继承、工程包重建通过，26 CLI/60 编码帧与 108 质量帧分计，33 页全关闭。完整 1051/1051、104 包内文件/14 新进程和 14 Skills/156 引用见[实测/原片/失败](validation/HTML文字布局与字体覆盖实测_2026-10-18.md)；[固定 ZIP/原函数字节](validation/evidence/openfilm-layout-adoption-20261018/verification.json)可复核。没有本轮新星数/整树/上游测试计数，也没有真实节省人时测量。

剩余 O15 优先参考片复刻、录屏示范、长转短流程的本地绑定；其 Skill 不提供本地 ASR/视觉理解/生成式修复算法。复杂塑形/变换、WOFF2、完整媒体/WebGL/film.html 语义、自然广告与 AI 质量仍独立验收。原 MIT 代码不能替代字体、素材、模型和内容模板权利；FGT 继续是独立研究，未作为 OpenFilm 功能引入。
'''
    reuse.write_text(text,encoding='utf-8',newline='\n')
    third=ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md'
    with third.open('a',encoding='utf-8',newline='\n') as stream:stream.write('''
## V46：原裁切诊断函数与本地扩展

固定 `eefd6a8d379289102141359a4718dbab12170526` 的 `packages/openfilm/src/shared.mjs:cutText` 原 38 行提取到 [openfilm_text_bounds.mjs](../../product/src/ai_ad_editor/openfilm_text_bounds.mjs)，带固定来源/作者/MIT 文件头共 2262 字节。原函数不改，实际同帧调用作诊断对照；[ZIP/原文/采用 SHA](../validation/evidence/openfilm-layout-adoption-20261018/verification.json)保留。

[html_quality_dom.mjs](../../product/src/ai_ad_editor/html_quality_dom.mjs)、[html_quality.py](../../product/src/ai_ad_editor/html_quality.py) 和 [font_coverage.py](../../product/src/ai_ad_editor/font_coverage.py) 的完全出框/独立轴/body 传播、实际字体源与标准库 cmap/预算、原生 CLI/事务/门禁为本项目新增实现。原函数不提供这些完整能力。原 MIT、9 份 MJS 与 Python 共 104 份包内文件按原字节核对；[14 fresh-process CLI](../validation/evidence/html-quality-wheel-20261018/verification.json)另计，不重算上游测试。外部 Node/Chromium 不随包下载，闭源系统字体 fallback 只保存元数据，公开演示使用新增原创字体。代码/字体映射检查不提升内容发布权利。
''')
    cli_contract=ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md'
    with cli_contract.open('a',encoding='utf-8',newline='\n') as stream:stream.write('''
## V46 HTML 全帧布局与字体质量

`motion html-quality --project --source-asset-id|--from-asset-id [--params] [--overrides] [--timeout-seconds 600] [--cancel-file] [--dry-run]`：逐个有理 CFR 帧绘制，并在独立上下文反序重绘、核对 PNG/布局。只写 validation 报告和 cache/html-quality 预览，最多 8 帧，不修改工程/资产/权利；dry-run 不运行浏览器。实际字体来源、Unicode cmap 与 DOM 行矩形分别记录，未知来源/复杂布局/序列不冒充通过。

`html-render --layout-check off|strict`：省略继承既有配方，未配置/旧配方 off。strict 在编码之前重新执行同计划的全帧门禁，与编码共享总期限；失败/未核验返回 `HTML_QUALITY_FAILED` 退出 2，实际报告和 PNG 在事务回滚后仍保留，工程/台账/新编码资产不变。运行/超时错误 6、取消 8。成功输出保存 layout_check 和绑定摘要的 layout_evidence；不把系统字体 fallback 自动登记为有商业权利。

[范围/预算契约](./HTML文字布局与字体覆盖核验契约_v0.1_2026-10-18.md)、[实际缺字/裁切/继承/发行](../validation/HTML文字布局与字体覆盖实测_2026-10-18.md)。
''')
    print(json.dumps({'status':'published','full_methods':full['methods'],'frozen_files':len(current),'suite_seconds':full['suite_seconds']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',type=Path,required=True);parser.add_argument('--wheel',type=Path,required=True)
    args=parser.parse_args();run(args.full.resolve(),args.wheel.resolve())
