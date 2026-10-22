"""Project a cumulative native Float32 delivery without inventing intermediate passes."""
import json
from pathlib import Path
import re
from urllib.parse import unquote

import float_delivery_bundle as bundle
import float_preview_release_docs as preview

ROOT, MAIN, REL = bundle.ROOT, bundle.MAIN, bundle.REL
REPORT, CONTRACT = bundle.REPORT, bundle.CONTRACT
LATEST_DOCS = preview.LATEST_DOCS
MARKER = 'V97-CUMULATIVE-NATIVE-FLOAT-DELIVERY'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip()+'\n', encoding='utf8', newline='\n')


def section(full=None, published=False):
    data = bundle.audit()
    text = preview.section(full, published)
    text = text.replace(preview.MARKER, MARKER).replace('| V97-', '| FD97-')
    title = ('V94–V97 原片 Float32 渲染、预览与缓存合并交付' if published else
        'V94–V97 候选：原片 Float32 渲染、预览与缓存合并验收')
    text = re.sub(r'^### .+$', '### '+title, text, count=1, flags=re.M)
    text = text.replace('预计2355方法，等待实际V96父提交发布后串行执行。',
        '预计2355方法；等待正在执行的292输入回归结束，再对最终300输入执行一次完整回归。')
    text = text.replace('[当前实测报告]('+preview.REPORT+')', '[合并实测报告]('+REPORT+')')
    row = next(v for v in text.splitlines() if v.startswith('| FD97-13 |'))
    extra = f'''| FD97-14 | 逐级源码与安装 | 292→296→298→300 输入衔接一致；安装182/203/220/260方法分别有终态，分别绑定176/178/179/180资源；不相加为当前通过数 | [四份原门禁核验]({REL}/prepared-r1.json) |
| FD97-15 | 正式render、队列与恢复 | 显式`settings.pixel_pipeline.engine=float32-native-v1`进入共享render/queue/resume；原片窗口、视频与原生音频共用作者时钟；默认后端及未接算子继续实施 | [CLI契约]({bundle.COMPONENTS[2][9]}) · [CLI原片/输出]({bundle.COMPONENTS[2][8]}) |
| FD97-16 | 合并验收范围 | 最终快照相对已发布V93/R16改变{len(data['changed_product_paths'])}产品路径，其中{len(data['added_product_paths'])}新增；V95/V96早期快照各自的2320/2337项完整回归未执行，不登记通过 | [交付契约]({CONTRACT}) |
| FD97-17 | 历史等待失败 | 原四个等待进程因前序发布字节断言停止，均在测试启动前；原状态保留，使用新的拥有进程和完整证据目录 | [保留状态与准备记录]({REL}/prepared-r1.json) |'''
    text = text.replace(row, row+'\n'+extra, 1)
    return text


def documents(target, full=None, published=False):
    block = section(full, published)
    for name in LATEST_DOCS:
        source = (MAIN/name).read_text('utf8')
        source = re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?', '\n', source, flags=re.S)
        first, _, rest = source.partition('\n')
        write(target/name, first+'\n\n'+preview.relink(block, name)+'\n'+rest.lstrip('\n'))
    result = list(LATEST_DOCS)
    status = (f"最终300输入已实际通过完整 **2355方法 /{full['suite_seconds']:.3f}秒 /0跳过**。" if full else
        '最终300输入的完整2355项尚未取得通过终态。')
    for component in bundle.COMPONENTS:
        _, lab, _, _, _, _, _, _, report, contract, _ = component
        root = ROOT.parent/lab
        for name in (report, contract):
            text = (root/name).read_text('utf8')
            marker = 'FLOAT-CUMULATIVE-DELIVERY-NOTE'
            text = re.sub(r'\n?<!-- '+marker+r' -->.*?<!-- /'+marker+r' -->\n?', '\n', text, flags=re.S)
            first, _, rest = text.partition('\n')
            relative = '../'*(len(Path(name).parts)-1)+'docs/validation/原片浮点渲染与预览合并交付实测_2026-10-22.md'
            note = ('\n\n<!-- '+marker+' -->\n> 合并交付说明：'+status+
                ' 以下保留该候选当时的分项、安装和失败记录；296/298输入早期快照未各自执行2320/2337项完整回归。'
                '当前验收以[合并实测]('+relative+')及其实际收据为准。\n<!-- /'+marker+' -->\n')
            write(target/name, first+note+rest)
            result.append(name)
    write(target/REPORT, report_text(full))
    write(target/CONTRACT, contract_text())
    result.extend((REPORT, CONTRACT))
    return result


def report_text(full=None):
    data = bundle.audit()
    native = bundle.read(ROOT/'docs/validation/evidence/float-preview-20261022-lab/native-r2/verification.json')
    log = (ROOT/'docs/validation/evidence/float-preview-20261022-lab/native-r2/unittest.log').read_text('utf8')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', log)
    assert match and int(match[1]) == native['methods'] == 57
    native_suite_seconds = float(match[2])
    installed = bundle.read(ROOT/'docs/validation/evidence/float-preview-20261022-lab/installed-r1/verification.json')
    status = ('尚未合入或推送；完整回归尚未取得终态。' if full is None else
        f"最终完整回归已实际通过 **{full['methods']}方法 /{full['suite_seconds']:.3f}秒 /0跳过**；Git发布以拥有进程终态为准。")
    return f'''# 原片浮点渲染与预览合并交付实测

{status} 本次合并原生音视频、原片窗口、正式CLI渲染和预览缓存四个连续候选，保留完整产品目标。默认后端迁移、未接效果、自然素材AI质量、HDR、长片和完整剪映等价仍需继续实现。

## 1. 实际源码与安装

| 编号 | 原候选输入 | 原安装方法 | 原安装资源 | 当前证据 |
|---|---|---|---|---|
| FD97-I01 | 292（音频/编码库） | 182 /0跳过 | 176 | [V94原门禁](evidence/float-delivery-20261022/component-gates-r1/V94.json) |
| FD97-I02 | 296（原片窗口） | 203 /0跳过 | 178 | [V95原门禁](evidence/float-delivery-20261022/component-gates-r1/V95.json) |
| FD97-I03 | 298（正式CLI） | 220 /0跳过 | 179 | [V96原门禁](evidence/float-delivery-20261022/component-gates-r1/V96.json) |
| FD97-I04 | 300（预览/缓存） | 260 /0跳过，{installed['isolated_methods']['suite_seconds']:.3f}秒 | 180 | [V97原门禁](evidence/float-delivery-20261022/component-gates-r1/V97.json) |

以上属于各自原始字节快照，不累计为当前通过数。最终源码相关回归实际为{native['methods']}方法 /{native_suite_seconds:.3f}秒 /0跳过，包含18项新预览、22项既有预览与17项正式浮点渲染。新安装媒体以-I -S进程重做2次render、3次preview，Float32/PCM/PNG16解码SHA相同，248个实际测试模块均来自新安装目录。

## 2. 合并完整回归

从已发布V93/R16的288输入到最终300输入，共{len(data['changed_product_paths'])}产品路径变更、{len(data['added_product_paths'])}新增。保留已经启动的292输入2299项回归；其终态之后对最终300输入实际运行一次完整2355项。早期296/298快照未各自执行完整2320/2337项；其全部测试文件纳入最终快照，原安装和分项证据保留。

原四份等待拥有进程均因前序发布字节断言停止，`suite_launched=false`。这些状态保存在[准备收据](evidence/float-delivery-20261022/prepared-r1.json)引用的文件中，新的完整记录使用独立路径。本轮重新检查原门禁没有重新执行测试，也没有新增测试通过数。完整启动、2355实际终态、8外部夹具、9依赖、验证脚本SHA与发布父提交必须分别核验。

首次独立暂存预检误纳入仍在写入的V94完整日志，在采集与复制间出现内容SHA变化；预检失败，main未改写。[原失败、执行代码及复制片段](evidence/float-delivery-20261022/preflight-failure-r1/review.json)已保留。新的私有预检只复制稳定证据；实际发布须等待该日志终态，将完整日志一并纳入SHA及暂存blob核验。

## 3. 功能、媒体与边界

'''+preview.relink(section(full), REPORT)+f'''

## 4. 发布

发布前需核验完整2355、全新安装260、四候选连续性、真实CLI媒体和失败记录；在独立原生Git暂存库逐字节比对，随后复制到main，检查17份Skill、文档链接和暂存blob，普通提交和推送。所有运行使用原生Windows现有本地工具，不使用Docker、WSL、容器、虚拟环境或云provider。

主参考为linear GBRAP Float32，PNG为独立RGBA16；观看MP4路径已有去alpha精度损失的原生实测，不能作为理想量化参考。只做过原始/输出抽帧及GIF时钟检查，未连续播放、试听，也未验收自然广告、HDR或完整剪映效果。
'''


def contract_text():
    return '''# 原片浮点渲染与预览合并交付契约

## 1. 作者与执行

沿用Agent Project、现有CLI、Rights Ledger和本地运行策略。显式`settings.pixel_pipeline.engine="float32-native-v1"`选择本地原片窗口与FloatTimeline；源的基色、传递、像素族、矩阵、范围、alpha及扫描方式按支持格式完整声明。原始作者IR、源SHA和原生PTS保持绑定；未接入效果与格式明确拒绝。

标准render、队列和恢复沿用共同音频、编码器、质量与操作记录；预览区间使用完整作者帧号和独立音频样本端点。持久缓存绑定作者、素材、信号、实际代码及NumPy运行时SHA，损坏缓存必须拒绝。dry-run保持只读，取消与失败回收自有线程、进程和临时目录，保护既有导出。

## 2. 精度与输出

预览master.nut为straight BT.709 linear GBRAP Float32与48kHz stereo PCM_f32；单帧为独立RGBA16 PNG。完整合成后在线性预乘域按像素中心双线性缩放。正式整数交付与观看MP4分别标记，观看副本的原生去alpha精度损失保留失败证据。此处不承诺HDR、ICC、色适应或理想量化。

## 3. 验收修订

V94至V97连续候选采用一次最终快照合并交付。已运行的292输入2299项完整回归保留，不停止或重复启动；随后针对最终300输入运行完整2355项。296/298输入早期快照各自的2320/2337项完整回归不执行、不登记通过。独立分项和新安装结果仍绑定各自源SHA，不能累加成最终通过数；最终全量必须实际包含所有连续候选测试。

新完整拥有进程须绑定已发布V93产品和R16文档提交、四份原安装/媒体门禁、8份外部夹具、9份离线依赖及启动脚本，验证运行前后300输入相同。发布还需实际260项新安装终态、真实CLI样例、17份Skill和文档链接、暂存字节与源字节一致；随后普通commit/push并核对远端和干净状态。每个新执行使用独立证据目录，保留所有历史失败。

## 4. 剩余产品目标

默认Float32迁移、所有调整/滤镜/转场/字幕/跟踪算子、抗混叠、SAR/方向/隔行、自然素材本地AI质量、HDR与长片并发RSS、开放素材及模板库、剪映全部功能和效果等价继续保留为开发与验收要求。合并交付通过不等于这些要求全部完成。
'''


def links(target, names):
    roots = [target, ROOT, *(ROOT.parent/c[1] for c in bundle.COMPONENTS), MAIN]
    result = []
    for name in names:
        if not name.endswith('.md'):
            continue
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', (target/name).read_text('utf8')):
            value = value.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', value) or value.startswith('#'):
                continue
            part = unquote(value.split('#', 1)[0])
            assert any((base/Path(name).parent/part).resolve().exists() for base in roots), (name, value)
            result.append({'document': name, 'target': value})
    return result
