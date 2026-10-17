"""Synchronize current product documents only after final frozen evidence passes."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]


def update():
    evidence=json.loads((ROOT/'docs/validation/evidence/html-motion-20261018.json').read_text(encoding='utf-8'))
    full=evidence['full'];assert evidence['status']=='passed' and full['frozen_equal'] and full['skipped']==0
    methods=full['methods'];seconds=f"{full['suite_seconds']:.3f}";count=len(full['frozen_after'])
    report='离线HTML动效源码与透明合成实测_2026-10-18.md';contract='离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md'
    summary=(f'本轮 V41：提取 OpenFilm 原帧时钟，新增完全本地 `motion html-register/html-source/html-inspect/html-render`；'
        f'保留 HTML/CSS/SVG/Canvas 源码、固定资源/工具链、强类型参数、新版本重建和普通时间线透明叠加。'
        f'完整 **{methods}/{methods}，{seconds} 秒**，0 跳过；{count} 文件冻结，37 新增专项为完整子集。'
        '五组成功内容/三项页面拒绝共 30 CLI 入口调用，96 HTML 编码输入帧、192 全帧乱序重绘、24 原生时间线主帧分计；'
        '独立 RGB 合成最大差 3、均值 0.476496，工程包/片段组重建 RGBA 一致，所有实际浏览器 Job 回收。'
        '94 文件离线 wheel/11 独立进程 CLI、14 Skills/133 本地引用通过；六张静帧目检，未连续播放/听审。'
        '初始 MKV 帧时钟错位、源长和回收/工具链诊断失败原证据保留；正式采用逐帧精确 PTS 的 FFV1/BGRA NUT。'
        '完整 OpenFilm HTML 时间线/媒体/WebGL、自动模板控件/缺字越界诊断、HDR/自然广告美学、长片资源、Schema 随包/干净机器及完整剪映等价仍未验收。')
    def read(name):return (ROOT/name).read_text(encoding='utf-8-sig')
    def write(name,text):(ROOT/name).write_text(text,encoding='utf-8',newline='\n')
    def row(text,prefix,new):
        lines=[line for line in text.splitlines() if line.startswith(prefix)];assert len(lines)==1,(prefix,len(lines))
        return text.replace(lines[0],new,1)
    name='README.md';text=read(name);assert '| V41 |' not in text
    text=text.replace('Python 和本地 FFmpeg，通过 CLI','Python 和本地 FFmpeg，并提供显式登记的本地 Node/Chromium 动效后端，通过 CLI',1)
    a=text.index('本表随功能和验证结果同步更新。');b=text.index('\n\n',a)
    text=text[:a]+'本表随功能和验证结果同步更新。**功能执行、实际内容、自动质量与听感分别验收，失败记录保留。** '+summary+text[b:]
    text=row(text,'| V13 |',f'| V13 | 产品自动回归 | 完整 **{methods}/{methods}，{seconds} 秒**，0 跳过；{count} 文件冻结，37 HTML 专项为完整子集 | 30 内容 CLI 入口、11 wheel 独立进程 CLI 和历史研究分计；完整剪映未验 | [完整日志](docs/validation/evidence/html-motion-final-full-20261018.log)、[机器证据](docs/validation/evidence/html-motion-20261018.json) |')
    previous=next(line for line in text.splitlines() if line.startswith('| V40 |'))
    text=text.replace(previous,previous+'\n'+f'| V41 | 离线 HTML/SVG/Canvas 动效与可编辑源码 | 30 CLI、全帧正序/反序/乱序与真实 PTS；透明叠加独立最大 RGB 差 3；包/片段组可重建，失败/取消 Job 回收 | 五组为原创几何/英文字体；自然广告、中文复杂排版、全 film.html/媒体/WebGL/HDR/长片未验 | [原输入与实际 GIF/MP4](#实测演示素材)、[实测](docs/validation/{report})、[证据](docs/validation/evidence/html-motion-20261018.json) |',1)
    needle='## 实测演示素材\n';assert needle in text
    gallery=f'''
**正式产品 CLI V41：保留动效源码，生成透明标题并叠入时间线。** 左列为原创底图输入，右列为真实产品时间线成片；SVG 商品、文字、CSS 动画与 Canvas 标记均由本地 Chromium 逐帧生成。

![原始输入与实际原生时间线成片](docs/assets/html-motion-20261018/native-comparison.gif)

[原输入 PNG](docs/assets/html-motion-20261018/source.png) · [原输入 MP4](docs/assets/html-motion-20261018/source.mp4) · [HTML/清单](docs/assets/html-motion-20261018/template/index.html) · [SVG 原素材](docs/assets/html-motion-20261018/template/bottle.svg) · [透明原文件 NUT](docs/assets/html-motion-20261018/S01-alpha.nut) · [实际产品 MP4](docs/assets/html-motion-20261018/S03-timeline.mp4) · [实际产品 MKV](docs/assets/html-motion-20261018/S03-timeline.mkv) · [改参预览](docs/assets/html-motion-20261018/S02-preview.mp4) · [可重建工程包](docs/assets/html-motion-20261018/editable-project.zip) · [五组/失败/复现](docs/validation/{report})。

自制 CC0 背景、几何商品和原创像素字体；原片/主输出 640×360、12 fps、24 帧、2 秒。双列 GIF **960×270、12 帧/2000 ms**，无声；主 MKV 另有自动生成的精确静音流。96 成功 HTML 输入帧、192 乱序重绘与 24 原生时间线主帧分计，S03 与独立 alpha/RGB 合成最大差 3、均值 0.476496。78 文件/6,332,822 字节、10 视频/1 静音音频流复解码；两组三时刻静态目检，未连续播放/听审。绿色块为几何核验标记；未验中文长标题、照片广告或自然美学。[来源/30 原始 CLI](docs/assets/html-motion-20261018/verification.json)、[媒体审计](docs/validation/evidence/html-motion-media-final-20261018.json)、[原 MKV 错位成片](docs/assets/html-motion-clock-failure-20261018/S03-timeline.mkv)、[失败与原冻结源码](docs/validation/evidence/html-motion-development-20261018/verification.json)。MIT 只授权复用代码，源码/字体/图片权利继续分别登记。
'''
    text=text.replace(needle,needle+gallery+'\n',1);write(name,text)
    core=['docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
          'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/validation/回归验证记录_2026-10-13.md']
    for name in core:
        text=read(name);assert '本轮 V41：' not in text
        position=text.index('本轮 V40：');prefix='./' if '/validation/' in name else './validation/'
        text=text[:position]+summary+f' 见[原片/GIF/实测]({prefix}{report})和[机器证据]({prefix}evidence/html-motion-20261018.json)。\n\n'+text[position:].replace('本轮 V40：','历史 V40：',1)
        if name=='docs/README.md':
            text=row(text,'| 审计日期 |',f'| 审计日期 | 2026-10-18（V41；{methods} 完整、离线 HTML/源码重建受控通过；完整剪映未验） |')
            needle='| [真实源范围外扩契约]';assert needle in text
            text=text.replace(needle,f'| [离线 HTML 动效契约](./specs/{contract}) | 工具链、可编辑源码/资源、参数、精确帧时钟与进程回收 | 有效 |\n| [HTML 动效实测](./validation/{report}) | 五组内容/30 CLI/37 专项、完整回归、wheel/Skill/原失败 | 有效 |\n'+needle,1)
        if name=='docs/构建进度总表_2026-10-16.md':
            text=row(text,'| 本次状态快照 |',f'| 本次状态快照 | 2026-10-18，README V41；完整 {methods}/{methods}、0 跳过；本地 HTML 动效受控通过，完整剪映未验 |')
            text=row(text,'| 核对范围 |',f'| 核对范围 | {methods} 完整、37 新增子集、{count} 冻结文件；五组/30 CLI、96 HTML 输入帧/192 验证重绘/24 原生时间线帧分计；11 独立发行 CLI；历史开发/研究分计 |')
            text=text.replace('当前 V40 为 938/938、132 文件冻结',f'当前 V41 为 {methods}/{methods}、{count} 文件冻结',1)
            text=row(text,'| 16 |','| 16 | 广告规划与模板引擎 | 部分实现 | 本地 ad plan/apply、类型变量/槽位/批量变体；可编辑片段组；V41 HTML/CSS/SVG/Canvas 源闭包、强类型参数及新版本重建 | 条件/复杂槽位图、自动 CSS 控件/缺字越界诊断、展开多轨/跨执行上下文、模板内容量与真实投放样片 |')
            text=row(text,'| 19 |','| 19 | 渲染与输出 | 已实现，有边界 | FFmpeg 画幅/透明输出/队列/独立子画布/显式 area 与投影配额；V41 显式本地 Chromium 动效到精确 CFR 透明 NUT，再入普通时间线 | HTML 限受信任本地模板，无嵌入媒体/WebGL/全 film.html；GPU、HDR/线性光、全进程 RSS、4K/长片/并发及跨构建一致性 |')
            text=row(text,'| 20 |','| 20 | 可移植项目包 | 已实现，有边界 | .aevpkg.zip、项目/台账/引用素材/模型登记元数据、URI 重写、逐文件 SHA-256 和篡改拒绝；V41 实测保留 HTML 源/字体/图片并重建 | 外部模型/Python/Node/浏览器不随包分发，须显式本地重新登记；干净机器/超大包压力测试未验 |')
            text=row(text,'| 25 |',f'| 25 | 质量、性能与发行 | 工具已实现，产品验收未完成 | 完整 {methods}/{methods}、{count} 文件冻结；HTML 五组与独立 alpha/RGB 合成核验；wheel 94 文件/11 独立 CLI；历史源编辑证据保留 | 六静帧目检、无连续播放/听审；Schema 随包、干净机器、长片资源、自然 AI/完整剪映等价待验 |')
            text=row(text,'| 当前生产代码 |',f'| 当前生产代码 | 130 Python+4 MJS+Schema+pyproject+MIT 共 {count} 文件，完整/专项/公开媒体/wheel 前后字节一致 | 开发失败与原 MKV 冻结源码另列 |')
            text=row(text,'| 最近完整产品回归 |',f'| 最近完整产品回归 | V41 **{methods}/{methods}，{seconds} 秒**，0 跳过 | [完整日志](./validation/evidence/html-motion-final-full-20261018.log)；耗时不是性能基准 |')
            text=row(text,'| 本轮新增子集 |',f'| 本轮新增子集 | 37 新增 HTML 方法，均为 {methods} 完整子集；另一次 37 项专项不累加 | 源码/参数/资源闭包、真实透明像素/逐帧 PTS、重建/拒绝/超时/取消和 Job 回收 |')
            text=row(text,'| 本轮实际功能核验 |',f'| 本轮实际功能核验 | 五组/30 CLI、96 HTML 输入帧/192 全帧验证重绘/24 时间线帧；94 文件 wheel/11 独立发行 CLI | [原片/结果/失败](./validation/{report})；六静帧目检，未连续播放/听审 |')
            text=row(text,'| Skill 审计 |','| Skill 审计 | 14 Skills、133 引用，目录联接/格式/SHA 通过 | 引用检查不等于自然质量 |')
            text=row(text,'| 运行时与策略 |','| 运行时与策略 | 原生 Windows/Python/FFmpeg；可选显式本地 Node/Playwright/Chromium，无服务器端口；上游 API 调研单独记录 | 无依赖下载/线上产品 API/剪映/Docker/WSL；浏览器由原生 Job 回收 |')
            text=row(text,'| 文档 |','| 文档 | README/模块/契约/矩阵/基线/原片 GIF 同步；[当前审计](./validation/evidence/docs-audit-html-motion-20261018.json) | 不证明外链、锚点、自然质量或许可 |')
        if name=='docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md':
            needle='| 能力 | 当前实现 | 证据 | 仍未关闭的边界 |\n|---|---|---|---|\n';assert needle in text
            text=text.replace(needle,needle+f'| HTML 动效（V41） | 固定本地工具链、HTML/SVG/Canvas/参数、可编辑源闭包、透明 NUT、全帧多顺序核验与 Job 回收 | [五组/30 CLI/37 专项及完整](./{report})；独立合成最大 RGB 差 3 | 全 film.html/嵌入媒体/WebGL/自动控件/中文复杂排版/自然画质/HDR/长片/干净机器未验 |\n',1)
        write(name,text)
    name='docs/validation/'+report;text=read(name)
    text=text.replace('完整回归进行中；本记录将按最终冻结日志补充发行与通过数。',f'状态：受控功能通过；完整 **{methods}/{methods}、{seconds} 秒、0 跳过、{count} 文件冻结**。完整剪映等价未验收。',1)
    text=text.replace('完整回归最终数量、日志与字节冻结结果待最终进程退出后写入本节，不以专项通过替代全套。',f'最终完整 **{methods}/{methods}，{seconds} 秒**、0 跳过；{count} 文件运行前后冻结一致。[原始完整日志](evidence/html-motion-final-full-20261018.log)、[摘要/全部冻结字节](evidence/html-motion-final-full-20261018.json)、[总证据](evidence/html-motion-20261018.json)。37 专项已包含在完整数量中；历史失败、上游研究及 30 内容 CLI/11 wheel CLI 分开统计。',1)
    text=text.replace('开发轮日志：','[开发源字节/原日志/原失败媒体](evidence/html-motion-development-20261018/verification.json)和[原 MKV 时间线成片](../assets/html-motion-clock-failure-20261018/S03-timeline.mkv)保留；用于 D04 复现的 137 份源码均按当时冻结摘要重建核对。\n\n开发轮日志：',1);write(name,text)
    name='docs/specs/'+contract;text=read(name)
    text=text.replace('状态：实现与验收进行中，不能作为已通过的功能声明。',f'状态：受控实现通过，37 专项与完整 {methods} 项均通过；[正式实测](../validation/{report})保留全部失败和未验收边界。',1)
    text=text.replace('限制帧数、像素工作量、文件数','限制帧数、单次正序像素工作量（两次验证重绘另计）、文件数',1)
    text=text.replace('该工作量门限不等同于浏览器进程 RSS 的数学上界。',
        '当前限制为 1800 帧、单次正序 20 亿像素、256 个文件及 64 MiB 素材闭包；编码过程中检查 512 MiB 输出门限。两次全帧验证的重绘工作另计。worker Job 超时可设 1–1800 秒，探测/逐帧时钟核验另有局部超时；不承诺整个命令严格在同一墙钟期限结束。该工作量门限不等同于浏览器进程 RSS 的数学上界。',1)
    text=text.replace('路径、版本、包和浏览器目录内的文件摘要均登记','路径、版本、包和浏览器目录内的发行文件摘要均登记（仅排除根目录可变诊断 debug.log，新日志指向 E 盘临时目录）',1)
    write(name,text)
    name='docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md';text=read(name);assert '## 产品增量 V41' not in text
    text=row(text,'| GitHub 当次快照 |','| GitHub 当次快照 | R02 为 809 stars / 89 forks；V41 复核为 **832 stars / 90 forks**（2026-10-18 06:27，Asia/Taipei），均为时点值 |')
    text=text.replace('后续复核：',
        f'**最新落地状态（V41）**：固定上游提交未变；新增本地 HTML/SVG/Canvas 最小后端，原帧时钟按字节采用，其余资源封装、事务、精确 PTS 和进程回收为本项目实现。下列 R02/R03 估算和失败记录按历史保留，当前采用范围见[本页 V41](#产品增量-v41离线动效与可重建源码)与[实际视频/失败记录](validation/{report})，不能把历史待办当成全部仍未实现。\n\n后续复核：',1)
    text=text.replace('## 当前复用落地决策（R03）','## 历史复用落地决策（R03）',1)
    text=text.replace('## 2. 面向当前项目的复用顺序','## 2. 面向项目的复用顺序（R02 研究时估算）',1)
    text+='''
## 产品增量 V41：离线动效与可重建源码

再次读取公开 API：**832 stars / 90 forks**，main 仍为 `eefd6a8d379289102141359a4718dbab12170526`；702 上游文件与 ZIP 一致。[本轮原 API 与提取摘要](validation/evidence/openfilm-html-adoption-20261018/verification.json)记录实际获取时刻。网页缓存星标与 API 可能不同，不把历史 829 或本次 832 当作永久排名。

| 编号 | 当前采用 | 实际边界 / 成本含义 |
|---|---|---|
| O05 | 新增 `motion html-*`，把本地 HTML/CSS/SVG/Canvas 生成为普通透明视频资产，保留源码、资源和参数 | 没有搬入默认联网 host/render、Studio 或独立 HTML 时间线。NUT 精确帧时钟、权利与工程事务是本项目新实现；全 film.html/媒体/WebGL 仍未完成 |
| O04/O06 | 原 FILM_CLOCK 导出行 1066 字节完全一致；所有帧在两种全新页面顺序下重绘核对，报告保留 Job 回收和页面失败 | 联系表、缺字/越界自动诊断、跨版本确定性仍候选；静态复核脚本不冒称完整 look CLI |
| O14 | 复用已有模板变量校验，title/color 等强类型参数进入 frame(t,params)，保留配方并重建新版本 | 不是原 CSS 自动控件提取或整个 overrides.mjs 移植；换图片/字体须登记新资源/源码版本 |
| O01/O02/O03/O13 | 继续沿用既有字幕算法、部分关联规则、转场工作流和 Saved 片段组工作流；本轮实际验证 HTML 源码在工程包和片段组中的闭包/ID 重映射 | 旧轮通过数保留；新增动效不能代替原自然分割/修复质量、完整磁吸或完整剪映验收 |

'''+summary+f' 见[契约](specs/{contract})、[实际原片/GIF与全部失败](validation/{report})。\n\n原 O05 的 5–10 / 12–20 人日、随行 O04/O06/O14 为包含共享工作的历史估算。本轮未记录人时，不能宣称已节省全部差额、整个项目百分比或从单行复用量推算收益；已实现最小后端不再作为全额待办。剩余优先项是完整帧/媒体格式范围、诊断、自动控件和三种官方 Skill 流程的离线绑定；NLE xmeml 按实际交换需求另行接入。\n'
    write(name,text)
    name='docs/third-party/OpenFilm复用声明_2026-10-17.md';text=read(name);assert '## V41' not in text
    text+=f'''
## V41：原帧时钟与离线 host

从固定 `eefd6a8d379289102141359a4718dbab12170526` 的 `packages/openfilm/src/host.mjs` 提取 `FILM_CLOCK` 到 [openfilm_frame_clock.mjs](../../product/src/ai_ad_editor/openfilm_frame_clock.mjs)，原 1066 字节导出行完全一致；保留 Copyright (c) 2026 OpenFilm contributors 和原 MIT。其余 host 的 frame/ready、两次栅格等待和时间绘制契约用作工作流参考；[新 worker](../../product/src/ai_ad_editor/html_motion_worker.mjs)、Python 资源/参数封装、精确 PTS 与原生 Windows Job 生命周期为本项目适配/新实现，不是整个上游执行器兼容移植。原字幕算法保持原字节。

原 MIT、四份 MJS 与 Python 模块随 wheel 分发，94 包内文件原字节核对，11 个产品隔离 fresh-process CLI 通过。[来源/原 ZIP/702 文件/时钟对照](../validation/evidence/openfilm-html-adoption-20261018/verification.json)、[wheel](../validation/evidence/html-motion-wheel-20261018/verification.json)、[实测](../validation/{report})。本轮显式使用已安装的 Node、Apache-2.0 Playwright 与 Chromium headless shell，工具链许可文件摘要登记但不随本项目 wheel 分发；不下载浏览器、引入 Studio/GUI、服务商或自动安装入口。代码许可不升级模板、字体、图片和模型权利，实际产品新源码/派生输出仍默认未核验。没有实际人时数据或完整剪映等价结论。
'''
    write(name,text)
    print(json.dumps({'methods':methods,'seconds':seconds,'core_documents':len(core),'readme':'V41'},ensure_ascii=False))


if __name__=='__main__':update()
