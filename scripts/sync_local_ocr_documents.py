"""Publish V62 facts only after terminal frozen regression and native evidence."""
from __future__ import annotations
import json
from pathlib import Path
from run_frozen_regression import frozen
from sync_color_automation_documents import marked, line

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/ocr-20261019-v62'
MEDIA=ROOT/'docs/validation/evidence/ocr-media-20261019-v62-r3'
INSTALL=ROOT/'docs/validation/evidence/ocr-install-20261019-v62-r1'
EN='ocr-english-20261019-v62-r6'
ZH='ocr-chinese-20261019-v62-r4'
OFFLINE='ocr-offline-20261019-v62-r1'
REPORT='离线OCR与文字锚点真实成片实测_2026-10-19.md'
CONTRACT='离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md'
DOCS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
      'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
      'docs/specs/AgentCLI契约_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
      'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def read(path):return json.loads(path.read_bytes())


def run():
    current=frozen();full=read(BASE/'full-r2.json');unit=read(BASE/'unit-r6.json')
    media=read(MEDIA/'verification.json');install=read(INSTALL/'verification.json');skills=read(BASE/'skills-r1.json')
    for v in (full,unit,media,install):
        if v.get('frozen_before')!=current or v.get('frozen_after')!=current or not v.get('frozen_equal'):raise ValueError('completed current frozen evidence required')
    if not full.get('terminal_ok') or full['exit_code'] or full['skipped'] or unit['methods']!=27:raise ValueError('completed full and OCR unit suite required')
    if media['status']!='passed_independent_controlled_ocr_media_checks' or install['status']!='passed_native_isolated_install_ocr_and_encoded_camera':raise ValueError('native OCR/camera acceptance missing')
    en=read(ROOT/'docs/assets'/EN/'verification.json');zh=read(ROOT/'docs/assets'/ZH/'verification.json')
    cli=sum(c['kind']=='cli' for v in (en,zh) for c in v['calls'])
    edge=max(x['edge_max_error_px'] for c in media['camera_checks'] for x in c['active_frames'])
    coverage=min(x['glyph_coverage'] for x in media['chinese_targets'])
    lines=media['english_all_frame_zero_lines']
    summary=(f'2026-10-19 **V62（产品）**：新增本地 PP-OCRv4 CPU `ocr adapter/scan/anchors`，'
        '源帧/PTS、原文字/多边形、唯一精确查询生成可编辑位置/缩放和回全景。'
        f'完整 **{full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过、{len(current)} 文件冻结**；27 OCR 专项为全量子集。'
        f'开发版 **{cli} CLI /192 最终帧 /1,152,000 立体声采样帧**；32 聚焦帧边缘最大差 {edge:.6f} px，160 全景帧 RGB 最大差 2，PCM 0。'
        '英文四个选定目标/中文四个目标通过，原生前向分别 6 det+60 rec /1 det+4 rec；'
        f'**英文首帧全十行仅 {lines["exact_lines"]}/10 完全一致，{lines["character_edits"]}/{lines["expected_characters"]} 字符编辑**，保留空格错误，非盲测。'
        f'**{install["installed_package_files"]} 包内文件 /44 隔离 CLI /192 安装帧**，同源预测/解码音画一致；'
        f'**17 Skills /{skills["local_links_checked"]} 引用**。冒号文本误判、静音夹具/字体缺字、标点阈值参考与旧回归中断保留。'
        '静帧已看，未连续播放/听审；文字框不代表点击区域，全隐私、自然 OCR/语义、VACE 修订版完整交付与完整剪映等价仍未验收。')
    report=f'''# 离线 OCR 与文字锚点真实成片实测

{summary}

按[先行契约](../specs/{CONTRACT})实施，补齐 OpenFilm 录屏流程适配中曾缺少的文字识别内核。复用 PaddleOCR/RapidOCR 公开 DB/CTC 模型及算法，现有原生 ORT/OpenCV/NumPy 执行；没有引入 OpenFilm GUI、在线供应商、剪映运行时或虚拟环境。[模型与许可来源](../third-party/PP-OCRv4离线模型与许可来源_2026-10-19.md)独立记录。

## 编号功能与实测

| 编号 | 已实现 | 本轮实际核验 | 边界 |
|---|---|---|---|
| V62-01 | `ocr adapter register/list/inspect` | 显式本地 detector/recognizer ONNX、原生 Python、来源文件、实现及策略文件 SHA；登记默认 internal/unverified | 不自动下载/安装；默认不授予商业发布权利 |
| V62-02 | `ocr scan` | 英文 6 个源帧、中文 1 图，实际 DB+CTC 前向；原分数/多边形/源帧/PTS/模型信息随报告保存 | 抽样最多 120 帧，不代表漏字、隐私或变化全覆盖；没有方向分类器 |
| V62-03 | 字幕以外的画面文字 | 英文选定 4 个目标精确且文字像素覆盖 100%，中心最大差 1.5 px；中文 4 个目标精确，最低覆盖 {coverage:.6f}、中心最大差 1 px | 英文目标在开发扫描后选定；其他行仍有空格错误，不是留出盲测 |
| V62-04 | `ocr anchors` | 显式源帧/区分大小写/唯一精确文字，输出 3 个可编辑作者通道；dry-run 不变项目、apply 保留源范围和音频，补源/模型权利依赖 | 同尺寸直接正向 1x、无已有变换/裁切/效果；不暗选最高置信度；锁定轨道拒绝 |
| V62-05 | 真实聚焦和回全景 | 四条 6 秒@8 fps 输出，32 个聚焦帧独立投影最大差 {edge:.6f} px，160 个全景帧最大 RGB 差 2；192 个 PTS 全对 | 文字框不是按钮边界，不自动识别点击或操作目的；聚焦时画布其它区域会裁切 |
| V62-06 | 音频保持 | 原创页面录屏与同夹具的原创测试音显式封装为本轮原片；四组共 1,152,000 立体声采样帧逐值差 0 | 初版输入静音已发现并保留；纯测试音不代表自然声音听感 |
| V62-07 | 报告/类型/事务 | 报告登记文件 SHA、内封摘要、当前 source/model/implementation 校验；只有明确 OCR 观测文本可包含冒号/可见 URL | URI 文字只作查询数据；source/model/program/extra 远程路径仍拒绝，伪造标签不能豁免执行引用 |
| V62-08 | 原生取消/超时 | 真 CLI timeout 退出 6，预置 cancel 退出 8；项目/lock/rights 字节不变、不留报告；成功 worker 的自身 Job 全回收 | 只操作本轮自建进程；Python 网络 guard 不是 OS 网络沙箱 |
| V62-09 | 完整回归/发行 | {full['methods']} 个方法、0 跳过、{len(current)} 输入冻结；131 包文件与源码/wheel 一致，安装版 44 隔离 CLI、真实 OCR/四个最终输出和相同门槛通过 | 依赖现有 Windows CPython/FFmpeg 及独立 native OCR Python；不是另一台干净机器验收 |
| V62-10 | Agent 调用 | 6 个现有 Skill 更新，累计 17；{skills['local_links_checked']} 本地引用、验证器及 C→E junction 通过 | 不以 Skill 数、测试数或成功返回宣称完整剪映等价 |

开发 CLI：英文 37、中文 5，共 {cli}；另 9 个封装/预览原生命令。安装 CLI：同一组 42，加 capabilities/schema 2，共 44。开发与安装视频分别计数，不合为来源场景数。当前开发 7 detector+64 recognizer 前向，安装版另同量；超时/取消尝试不计为成功模型前向。此前各开发版本在自己的原收据中单列。

## 原片、成片与 GIF

[本轮含原创测试音的原片](../assets/{EN}/original-screen.mkv)、[原测试页捕获来源](../assets/openfilm-workflow-screen-20261019-v61-r3/capture.stdout.json)、[原始 OCR 输出](../assets/{EN}/ocr-report.json)。OCR worker 只收到已登记媒体与模型，不读取页面 DOM、动作表或答案。

| 编号 | 精确文字/源帧 | 实际输出 | 可编辑工程 |
|---|---|---|---|
| D62-01 | Select local campaign /0 | [MP4](../assets/{EN}/select.mp4)、[原 MKV](../assets/{EN}/select.mkv) | [package](../assets/{EN}/select.aevpkg.zip) |
| D62-02 | Preview headline /8 | [MP4](../assets/{EN}/preview.mp4)、[GIF](../assets/{EN}/preview.gif) | [package](../assets/{EN}/preview.aevpkg.zip) |
| D62-03 | Save plan in this page /0 | [MP4](../assets/{EN}/save.mp4)、[GIF](../assets/{EN}/save.gif) | [package](../assets/{EN}/save.aevpkg.zip) |
| D62-04 | Plan saved locally in page state. /32 | [MP4](../assets/{EN}/result.mp4)、[GIF](../assets/{EN}/result.gif) | [package](../assets/{EN}/result.aevpkg.zip) |

![实际识别框生成可编辑运镜并回全景，受控原页面](../assets/{EN}/select.gif)

预览 MP4/GIF 无音；MKV 保留明确封装的测试音。原页面是原创受控测试页，不是项目 GUI 或自然商业软件。精确文字和源帧由作者明确指定，非自动点击恢复。[源/聚焦/返回共 12 个静帧](evidence/ocr-media-20261019-v62-r3/source-focus-return-contact.png)已用 `view_image` 检查；[静帧观察记录](evidence/ocr-media-20261019-v62-r3/static-review.json)。未连续播放、未听审。

![原创中文输入，三个短语及混排数字价格](../assets/{ZH}/original-chinese.png)

[中文原始结果](../assets/{ZH}/ocr-report.json)、[独立创作真值](../assets/{ZH}/expected-chinese.json)。中文没有附加相机成片，其 4 目标只验识别/几何；不把 PNG 算作新的视频帧。

## 保留全部识别误差

英文首帧十行有 **{lines['exact_lines']} 行完全一致、{lines['character_edits']} 字符编辑/{lines['expected_characters']} 真值字符**，按原码点计入空格；不能用四个成功目标声称全英文通过。示例原文 `LOCAL CAMPAIGN PLANNER` 被识别为 `LOCALCAMPAIGNPLANNER`，`DRAFT` 被识别为前置空格加 DRAFT；配置/结果标题和 downloaded 的空格也有错误。没有事后补空格、更改原文或改成模型输出作答案。完整逐行表见[独立核验 JSON](evidence/ocr-media-20261019-v62-r3/verification.json)的 `english_all_frame_zero_lines`。

| 编号 | 原始问题 | 处理/证据 |
|---|---|---|
| DEV62-01 | 首轮 Python Job 方法名错误，模型未运行；单元几何边界用空字典绕过拒绝 | [unit-r1](evidence/ocr-20261019-v62/unit-r1.json)、[english-r1](../assets/ocr-english-20261019-v62-r1/verification.json)；改用现有 Job.start 和显式字段存在检查 |
| DEV62-02 | 实际 apply 发现 rights dependencies 需对象，磁盘失败未结构化 | [unit-r3](evidence/ocr-20261019-v62/unit-r3.json)和原源码快照；修复依赖引用及 OCR 局部 IO 错误事务 |
| DEV62-03 | 源 smoke 使用 `-I`，隐藏用户现有 jsonschema，compose 拒绝 | [english-r3](../assets/ocr-english-20261019-v62-r3/verification.json)；源端 `-E`，发行端仍 `-I -S` 使用随包依赖，门禁不变 |
| DEV62-04 | 冒号识别文字及 FFmpeg pipe:1 被全树审计当作远程引用 | [english-r4](../assets/ocr-english-20261019-v62-r4/verification.json)；仅明确文本字段按观测类型处理，执行资源不豁免，命令保留摘要 |
| DEV62-05 | CJK 子集字体没有数字，价格源图缺字；另一次误写字体文件名 | [中文 r1](../assets/ocr-chinese-20261019-v62-r1/verification.json)、[r2](../assets/ocr-chinese-20261019-v62-r2/verification.json)；显式本地 DejaVu 数字后备字体，最终价格原样识别 |
| DEV62-06 | 旧原始录屏静音，无法证明音频保持 | [media-r1](evidence/ocr-media-20261019-v62-r1/verification.json)和 [english-r5](../assets/ocr-english-20261019-v62-r5/verification.json)；显式封装同夹具原测试音，重跑全部 4 输出，不以静音通过冒充保留 |
| DEV62-07 | 独立像素阈值 180 漏掉源小句号抗锯齿，放大后句号显现，产生 7 px 假边缘差 | [media-r2](evidence/ocr-media-20261019-v62-r2/verification.json)、[逐列像素诊断](evidence/ocr-media-20261019-v62-r2/threshold-diagnosis.json)；源与输出统一阈值 100，原几何 5 px/覆盖 .8/中心 12 px 门槛不变，保留原失败 |
| DEV62-08 | full-r1 在政策修正前启动，输入冻结已变化 | [原中断收据](evidence/ocr-20261019-v62/full-r1.json)、[精确自建 PID 记录](evidence/ocr-20261019-v62/development-full-r1-interruption.json)；只结束本轮旧 unittest 子树，最终 full-r2 从固定输入重跑 |

## 复现、发行与剩余工作

[完整回归](evidence/ocr-20261019-v62/full-r2.json)、[OCR 专项](evidence/ocr-20261019-v62/unit-r6.json)、[开发媒体独立核验](evidence/ocr-media-20261019-v62-r3/verification.json)、[原生安装/模型](evidence/ocr-install-20261019-v62-r1/verification.json)、[安装媒体独立核验](evidence/ocr-install-20261019-v62-r1/installed-media/verification.json)、[解码同一性](evidence/ocr-20261019-v62/installed-decoded-comparison.json)、[Skills](evidence/ocr-20261019-v62/skills-r1.json)。每个原生样例保存执行脚本、逐命令 stdout/stderr、摘要与产品前后冻结；大 stdout 用 gzip 原样压缩，非降低模型输入质量。

[七轮依赖离线包](../assets/{OFFLINE}/agent-video-kit-cp313-win_amd64.zip)、[manifest](../assets/{OFFLINE}/release-manifest.json)、[本机安装收据](../assets/{OFFLINE}/install-receipt.json)。没有重新打包 OCR 权重、ORT/OpenCV、原生 Python 或 FFmpeg；已有模型目录/依赖需独立提供。源码 Apache notices 随产品包保存；[权利/模型来源](../third-party/PP-OCRv4离线模型与许可来源_2026-10-19.md)不能替代具体使用许可审核。本轮实际商业广告检查退出 7，默认 internal 渲染可用。

```powershell
C:/Python313/python.exe -B -X utf8 scripts/smoke_local_ocr.py --kind english --work product/.runtime/<新工作目录> --output docs/assets/<新英文例>
C:/Python313/python.exe -B -X utf8 scripts/smoke_local_ocr.py --kind chinese --work product/.runtime/<新工作目录> --output docs/assets/<新中文例>
C:/Python313/python.exe -B -X utf8 scripts/audit_local_ocr_media.py --english docs/assets/<新英文例> --chinese docs/assets/<新中文例> --output docs/validation/evidence/<新核验目录>
```

当前只有 1 个原创受控页面视频和 1 张原创中文图；重跑/安装不扩充来源数。自然小字/透视/竖排、多语方向分类、长片/移动端素材、多机平台、复杂裁切/嵌套/变速锚点、自动动作理解、任意隐私全覆盖、自然美学/听感、内容库规模及完整剪映功能/效果仍开放。VACE 修订版真实模型完整交付也仍待验。没有用 OCR 或 Skill 数量替代这些任务。
'''
    (ROOT/'docs/validation'/REPORT).write_text(report,encoding='utf-8',newline='\n')
    for name in DOCS:
        path=ROOT/name;text=path.read_text(encoding='utf-8')
        text=text.replace('\n2026-10-19 **V61（Agent 工作流适配）**','\n历史工作流 2026-10-19 **V61（Agent 工作流适配）**')
        prefix='docs/validation/' if name=='README.md' else ('../validation/' if name.startswith('docs/specs/') else './' if name.startswith('docs/validation/') else 'validation/')
        text=marked(text,'V62-CURRENT',summary+f' [原片/GIF/识别错误/安装与范围]({prefix}{REPORT})。')
        if name=='README.md':
            row=f'| V62 | 离线 OCR 与文字锚点 | {full["methods"]}/{full["methods"]}；{cli} CLI/192 帧/1,152,000 采样帧；131 包内文件/44 安装 CLI；17 Skills | 英文首帧 5/10 行完全一致；受控目标通过，点击/隐私/自然质量和完整等价未验收 | [原片/GIF/原错误/发行]({prefix}{REPORT}) |'
            if '| V62 |' in text:text=line(text,'| V62 |',row)
            else:
                rows=text.splitlines();i=next(i for i,x in enumerate(rows) if x.startswith('| V61 |'));rows.insert(i+1,row);text='\n'.join(rows)+'\n'
            demo=(f'**V62 离线 OCR 文字运镜**：[原片、四组输出、中文输入、完整错误与安装]({prefix}{REPORT})；'
                  '实际模型识别框生成可编辑相机，精确查询由作者指定，非自动点击理解。\n\n'
                  f'![识别文字后聚焦并回全景，原创受控页面](docs/assets/{EN}/select.gif)')
            text=marked(text,'V62-DEMO',demo)
        if name=='docs/构建进度总表_2026-10-16.md':
            text=line(text,'| 24 |','| 24 | Agent Skills | 已实现，持续扩展 | V62 仍为 17 个 video-cut- Skill；6 个入口补 OCR/精确文字锚点，228 本地引用通过 | 抽样 OCR 不等于点击/语义/隐私覆盖；完整等价继续开放 |')
        if name=='docs/specs/AgentCLI契约_v0.1_2026-10-13.md':
            usage=f'''## V62 OCR 命令契约

执行细节和预先门槛见[离线 OCR 契约]({CONTRACT})。以下 `<root>`、模型/Python/证据都是显式已有本地路径；不提供安装或下载开关。

| 命令 | 必须参数与行为 |
|---|---|
| `ocr adapter register` | `--project --adapter-id --model-path --python-executable --evidence`；可选 `--threads 1..16`、许可/用途/核验字段，默认 internal/unverified；模型目录必须含固定 det/rec 文件名；重复 ID 拒绝 |
| `ocr adapter list/inspect` | 都需 `--project`，inspect 另需 `--adapter-id`；只读并检查登记，不自动改摘要 |
| `ocr scan` | `--project --asset-id --adapter-id --output validation/<new>.json`；源帧 `--start-frame` 包含、`--end-frame` 排他，默认 step=8/max=120；dry-run 不推理或写报告 |
| `ocr scan` 执行控制 | `--timeout .1..3600` 秒；`--cancel-file <local-flag>`；预置取消退出 8，超时/worker 失败退出 6，来源/模型变化退出 10；失败不提交报告登记 |
| `ocr anchors` | `--project --report --clip-id --query --frame-index`；可选 sequence/zoom/hold/return；默认只返回计划，`--apply` 提交，支持 `--dry-run`；未识别/重复精确文字退出 2 |

```powershell
python -X utf8 -m ai_ad_editor ocr adapter register --project <root> --adapter-id ocr_local --model-path <local-model-dir> --python-executable <native-python.exe> --evidence <local-evidence.json>
python -X utf8 -m ai_ad_editor ocr adapter inspect --project <root> --adapter-id ocr_local
python -X utf8 -m ai_ad_editor ocr scan --project <root> --asset-id <video> --adapter-id ocr_local --output validation/text.json --start-frame 0 --end-frame 48 --step-frames 8 --dry-run
python -X utf8 -m ai_ad_editor ocr anchors --project <root> --report validation/text.json --clip-id <clip> --query 'Select local campaign' --frame-index 0 --zoom 1.5 --hold-seconds .5 --return-seconds .5 --apply --dry-run
```

省略 dry-run 才实际执行对应动作。`scan` 报告和 `anchors` 只消费登记本地媒体；识别出的 URL 是原样文本，不会被访问。锚点应用前校验报告登记/内封摘要/当前来源及实现，任何执行资源的远程路径都继续拒绝。查询区分大小写和空格，不自动使用最高置信度消除歧义。输出是普通 `transform.position.x/y`、`transform.scale` 作者关键帧及源/模型依赖，工程包保留报告；文字框不代表点击区域。
'''
            text=marked(text,'V62-CLI',usage)
        if name.endswith('能力覆盖与验收矩阵_v0.1_2026-10-13.md'):
            row=f'| 离线 OCR/文字锚点（V62） | 登记/源帧识别/唯一精确查询、可编辑聚焦及全景返回 | [{full["methods"]} 全量/192 开发帧与独立几何]({REPORT})；安装版同源解码一致 | 英文首帧 5/10 行全一致；自然 OCR、自动点击、全隐私和复杂变换未验收 |'
            if '| 离线 OCR/文字锚点（V62） |' in text:text=line(text,'| 离线 OCR/文字锚点（V62） |',row)
            else:text=text.replace('| 三套本地创作工作流（V61） |',row+'\n| 三套本地创作工作流（V61） |',1)
        path.write_text(text,encoding='utf-8',newline='\n')
    design=ROOT/'docs/OpenFilm创作流程本地适配设计_2026-10-19.md'
    text=design.read_text(encoding='utf-8');text=marked(text,'V62-OCR',
        f'V62 后续产品增量：已接入独立开源 PP-OCRv4 CPU 内核，支持源帧文字框及精确查询生成可编辑运镜/回全景。见[真实原片、错误和安装](validation/{REPORT})；不是 OpenFilm 内置 OCR 的拆取。原 R05/V61 的“未做 OCR”是当轮范围，仍保留；自动点击、自然文字质量和完整等价继续开放。')
    design.write_text(text,encoding='utf-8',newline='\n')
    reuse=ROOT/'docs/OpenFilm复用复核与开发成本更新_2026-10-19.md'
    text=reuse.read_text(encoding='utf-8');text=marked(text,'V62-FOLLOWUP',
        f'后续产品状态：V61 已将 REUSE-05 的三套流程适配为本地 Skill，累计 17 个；V62 另接入 PP-OCRv4 离线识别与可编辑文字运镜。见[当前实测/失败/安装](validation/{REPORT})。下方工期、未安装说明和社区量保留 **R05 查询时点**，不是当前状态；本轮未重新计算实际节省人日或更新上游 stars，也未将 OCR 称为 OpenFilm 已有内核。')
    reuse.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'documents':len(DOCS)+3,'cli_calls':cli,'full_methods':full['methods'],'frozen_files':len(current),'skills':17}))


if __name__=='__main__':run()
