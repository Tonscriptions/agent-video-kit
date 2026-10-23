"""Numbered spatial documents bind source/media/4K/installed actual receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
PARENT = ROOT.parent/'float-gaussian-lab-20261022'
REL = 'docs/validation/evidence/float-spatial-20261022-lab'
ASSETS = 'docs/assets/float-spatial-20261022-r1'
ASSETS_4K = 'docs/assets/float-spatial-4k-20261022-r2'
REPORT = 'docs/validation/连续浮点均值方框模糊与4K分块实测_2026-10-22.md'
CONTRACT = 'docs/specs/连续浮点均值方框模糊与空间预算契约_v0.1_2026-10-22.md'
MARKER = 'V108-CONTINUOUS-FLOAT-SPATIAL-MEANS-4K'
LATEST_DOCS = ('README.md', 'docs/README.md', 'docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md', 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md', 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path): return json.loads(path.read_bytes())


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip()+'\n', encoding='utf8', newline='\n')


def fourk(inputs):
    d = read(ROOT/REL/'4k-r2/verification.json')
    assert d['status'] == 'passed-actual-default-budget-4K-formal-preview-and-independent-pixels'
    assert d['frozen_before'] == d['frozen_after'] == inputs
    assert len(d['cases']) == 3 and d['public_CLI_processes'] == 8
    assert all(row['ok'] for row in d['checks'])
    assert d['script_sha256'] == sha(ROOT/'scripts/smoke_float_spatial_4k.py')
    for row in d['cases']:
        assert row['actual_resolution'] == [3840, 2160] and row['compared_components'] == 33177600
        assert row['maximum_absolute_error'] <= 2e-6 and row['default_workspace_bytes'] == 768*1024*1024
    for name, row in d['assets'].items(): assert sha(ROOT/name) == row['sha256']
    return d


def current():
    inputs = frozen(); assert len(inputs) == 326
    native = read(ROOT/REL/'native-r2/verification.json'); media = read(ROOT/REL/'media-r1/verification.json')
    assert native['status'] == 'passed' and native['methods'] == 479 and native['skipped'] == 0
    assert native['frozen_before'] == native['frozen_after'] == inputs
    assert media['status'] == 'passed-public-CLI-floating-spatial-means-and-native-float-previews'
    assert media['frozen_before'] == media['frozen_after'] == inputs
    assert media['actual_public_render_CLI_processes'] == 2 and media['actual_public_preview_CLI_processes'] == 3
    assert all(row['ok'] for row in media['checks'])
    oracle = media['spatial_oracle']
    assert oracle['scenarios'] == ['average', 'box', 'horizontal', 'RGB_only', 'premult_headroom']
    assert oracle['RGB_values'] == 2419200 and oracle['maximum_linear_absolute_error'] <= 2e-6
    assert oracle['oracle_sha256'] == sha(ROOT/'scripts/spatial_media_oracle.py')
    assert sha(ROOT/REL/'media-r1/executed-oracle.py.txt') == oracle['oracle_sha256']
    for name, row in media['assets'].items(): assert sha(ROOT/name) == row['sha256']
    fourk(inputs)
    path = ROOT/REL/'installed-r1/verification.json'
    installed = read(path) if path.exists() else {'status': 'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status'] == 'passed-fresh-eight-wheel-195-resources-real-previews-and-679-methods'
        assert installed['isolated_methods']['methods'] == 679 and installed['isolated_methods']['skipped'] == 0
        assert installed['frozen_before'] == installed['frozen_after'] == inputs
        replay = read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status'] == media['status'] and replay['isolated']
        for key in ('Float32_sha256', 'PCM_sha256', 'PNG16_sha256'):
            assert replay['preview_decoded'][key] == media['preview_decoded'][key]
    return inputs, native, media, installed


def section(full=None, published=False):
    inputs, native, media, installed = current(); o = media['spatial_oracle']; k = fourk(inputs)
    records = native['native_spatial_records']
    avg = max(r['maximum_fractional_code_error'] for r in records if r['kind'] == 'average_blur')
    box = max(r['maximum_fractional_code_error'] for r in records if r['kind'] == 'box_blur')
    title = 'V108 连续浮点均值／方框模糊与4K分块' if published else 'V108 候选：连续浮点均值／方框模糊与4K分块（未发布）'
    if installed['status'].startswith('passed-'):
        itext = f"**679项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**，195份source/wheel/site资源一致；8固定离线wheel、NumPy931文件和许可一致；安装版真实编码音画、Float32和PNG16与源码版一致。"
    else: itext = f"**{installed['status']}，不计通过**；目标679项、195资源。"
    if full:
        assert full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 2774 and full['skipped'] == 0
        assert full['frozen_before'] == full['frozen_after'] == inputs
        ftext = f"**2774项 /{full['suite_seconds']}秒 /0跳过**；326产品输入、8外部夹具、9固定依赖保持一致。"
    else: ftext = '**尚未通过，不计通过**；目标2774项，仅在V107实际完整2715项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式`float32-native-v1`的正式render和preview新增均值／方框模糊，支持连续半径、作者关键帧和透明边缘。高斯及均值内核按剩余预算自动缩小转换分块，保留完整空间工作区准入和768MiB估算上限。

| 编号 | 功能性核验 | 实际内容与边界 | 证据 |
|---|---|---|---|
| FS108-01 | 共用内核 | 高斯父323→326产品输入、10路径改变、59新增方法；3个未支持操作样例从avgblur换成unsharp，拒绝码／清理／禁回退断言保留 | [契约]({CONTRACT}) |
| FS108-02 | 均值模糊 | avgblur/average_blur；半径0..1024、默认2；复制边缘、有效XY半径分别限制至轴长度整除2；单次归一化有限窗 | [源码479项]({REL}/native-r2/verification.json) |
| FS108-03 | 方框模糊 | boxblur/box_blur；半径0..128、默认4；半采样点对称边界，power为0..4静态整数；先全部水平遍数再全部垂直遍数 | [实测日志]({REL}/native-r2/unittest.log) |
| FS108-04 | 连续半径／时钟 | 整数内层tap为1，两个外层tap权重为半径小数，除以2r+1；6种插值、Bezier时间根、Fraction、原作者窗口和嵌套倒放；不是四舍五入到整数窗口 | [契约]({CONTRACT}) |
| FS108-05 | 实际原生对照 | {len(records)}组整数平面FFmpeg；均值8/10/12/16位与16种GBRA掩码，方框8/16位与4种power、默认CPU／纯C；均值最大误差{avg:.9g}码，门槛1.02；方框最大{box:.9g}码，分别受执行前固定倒数／逐遍量化解析界限约束 | [命令与原始I/O]({REL}/native-r2/verification.json) |
| FS108-06 | 独立数学 | 显式tap／边界索引矩阵与矩阵幂，不调用产品求和；不同边界、单像素／行列、最大半径、分数半径、方向与多遍均执行 | [日志]({REL}/native-r2/unittest.log) |
| FS108-07 | 透明与动态范围 | straight／premultiplied；GBRA位保持G1/B2/R4/A8；RGB-only保留alpha位，alpha-only同信号绕过RGB转换；零密度清RGB，正1e-30密度无epsilon阈值 | [契约]({CONTRACT}) |
| FS108-08 | 防止低覆盖率丢失 | 有界逐行分层求和，不做大前缀相减；真实检查不相邻不透明像素之后的1e-30覆盖率，以及1e30高亮之后的局部正常RGB；不是加epsilon掩盖误差 | [实际断言]({REL}/native-r2/unittest.log) |
| FS108-09 | 信号／强度／安全 | 明确输入输出信号；返回线性工作RGB后混合intensity，coverage独立线性混合；只读输入、取消／回调异常、完整表面非法值和保留表预算检查 | [日志]({REL}/native-r2/unittest.log) |
| FS108-10 | 预算修复 | 原高斯4K默认tile估算830865416>805306368，曾明确拒绝；现保留6×完整表面等固定估算，按余量缩tile，4K默认3903像素。71×65／2MiB新旧预算输出逐位一致 | [旧拒绝]({REL}/admission-probe-r1.json) · [新实际4K]({REL}/4k-r2/verification.json) |
| FS108-11 | 真正4K公开入口 | 3种模糊各1帧3840×2160；{k['public_CLI_processes']}次公开CLI，含正式render、原尺寸range、Gaussian PNG16及独立进程缓存复用；无提高768MiB算子预算 | [4K记录]({REL}/4k-r2/verification.json) |
| FS108-12 | 4K全部像素 | 每种33,177,600个RGBA分量逐项检查，总99,532,800；独立几何卷积边界项／显式tap行数学，图像竖直恒定；最大误差{max(c['maximum_absolute_error'] for c in k['cases']):.12g}，门槛2e-6；正式16位输入与实预览一致，4800帧双声道静音一致 | [4K复现代码]({REL}/4k-r2/executed-script.py.txt) |
| FS108-13 | 五场景公开视频 | {len(media['calls'])}调用/{len(media['checks'])}检查、2正式render／3preview；320×180、10fps、2秒20帧；均值、方框、水平、RGB-only、预乘超白各4帧 | [视频实测]({REL}/media-r1/verification.json) |
| FS108-14 | 全选区／声音 | 2,419,200线性RGB最大误差{o['maximum_linear_absolute_error']:.12g}，门槛2e-6；96000／选区67200双声道PCM帧一致，PNG16≤1码；clip前线性峰值{o['unclipped_linear_max']:.9g}、越界{o['unclipped_outside_RGB_components']}分量 | [独立参考]({REL}/media-r1/executed-oracle.py.txt) |
| FS108-15 | 可查看媒体 | CC0原创输入／实际输出／工程／权利账；视频GIF14×100ms，静看作者3/10/16共6幅；4K GIF仅切换3张实际单帧，不作为连续运动证明 | [原片]({ASSETS}/original-range.mp4) · [输出]({ASSETS}/range.mp4) · [工程]({ASSETS}/author-project.json) · [4K]({ASSETS_4K}/contact.png) · [目检]({REL}/static-review-r1.json) |
| FS108-16 | 离线安装 | {itext} | [安装收据]({REL}/installed-r1/verification.json) |
| FS108-17 | 完整回归 | {ftext} 源码479、安装679和完整套件分别登记，不相加作为完成率 | [本轮报告]({REPORT}) |
| FS108-18 | 失败／许可／边界 | 首次4K测试输出目录位于工程外而被拒绝；修复测试路径后重跑。私有编排首跑沿用上一轮媒体结果常量，在安装启动前拒绝；仅修正编排器并重新绑定18脚本。产品数值／门槛不变。均值数学独立实现，原高斯NOTICE继续核对；长片RSS／自然素材／HDR／完整剪映目标继续开发 | [4K原失败]({REL}/4k-r1/verification.json) · [编排修复]({REL}/continuation-recovery-r2.json) · [契约]({CONTRACT}) |

![原创输入与真实CLI空间模糊预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text, name):
    prefix = '../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/', lambda m: m[1]+prefix+'docs/', text)


def report(full=None, published=False):
    _, native, _, _ = current()
    return f'''# 连续浮点均值／方框模糊与4K分块实测

实际源码关联回归 **{native['methods']}项 /{native['seconds']:.6f}秒 /0跳过**，其中59项新增。每阶段结果分别列示，未执行／仍运行不计通过，完整剪映目标继续开发。

本轮新增有限窗口均值和重复方框模糊，同时修复高斯4K的转换分块准入。原空间工作区与768MiB估算上限保持，适配可用余量确定检查／信号转换块。不是把整图卷积切成没有重叠的独立小块；全空间依赖仍整体准入，逐行求和临时空间另行预留。该估算不是整个进程的峰值RSS保证。

均值使用复制边缘、有效半径限制至轴长度整除2。方框使用半采样点对称边界、多次水平后多次垂直。两者对整数半径实现理想归一化有限窗；原FFmpeg均值输出有整数floor，方框有固定倒数及逐轴逐遍量化，因此不保证位相同。32组实际整数格式对照保留原始输入／输出；均值1.02码门槛、方框按位深／半径／power预先计算解析量化界限，未按观察结果调整。

分数半径是明确的连续扩展：内层tap为1、外层tap权重为小数部分，除以2r+1。局部求和不做大前缀相减，避免远处不透明／高亮样本吞掉局部低密度或正常颜色。覆盖率1e-30、高亮1e30的实际测试与普通随机数据／矩阵参考分开保留。产品数学使用独立的逐行分层窗口求和，没有复制FFmpeg C循环。

真实4K由竖直恒定的原创条纹／矩形和透明度梯度组成，每种模糊1帧。高斯参考以有限几何卷积和边界项求解，不运行产品递推；均值参考显式逐tap和边界索引，不调用产品求和。逐项检查每个4K RGBA值，正式render输入、Float32预览、PNG16、静音样本及缓存另验。4K GIF只切换三种单帧输出；较小五场景视频另提供20帧原片与成片。二者均不能证明长视频性能、自然素材画质、连续播放或听感。

首个4K脚本误将正式render输出指向工程外的docs/assets，现有路径约束拒绝；原错误与执行代码保留。修复只把测试输出改为工程内，再复制已完成结果；没有修改数值算法、误差门槛或产品路径保护。私有continuation-r1还因保留上一轮Gaussian媒体状态常量而拒绝新空间滤镜的有效媒体状态，发生在安装或finisher启动前；保留该失败，以新私有continuation-r2修正结果名称并重绑18脚本，产品326输入不变。R107之前独立记录的NOTICE打包故障保持历史，本轮继承修复后的父输入，并继续核对193旧资源加2个新Python模块。

研究对照为官方[FFmpeg n8.1 vf_avgblur.c](https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_avgblur.c)和[vf_boxblur.c](https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_boxblur.c)。前者带MIT、后者GPL2+声明；本轮观察其边界与量化行为，不把GPL C源码纳入Python模块。FFmpeg程序本身及原高斯BSD参考保留既有许可归属。研究文本读取与运行网络策略分开；产品运行及测试无线上请求，无Docker／WSL／虚拟环境或浏览器tab。

'''+relink(section(full, published), REPORT)


def contract():
    return '''# 连续浮点均值／方框模糊与空间预算契约 v0.1

## 入口与参数

settings.pixel_pipeline.engine=float32-native-v1明确启用。render、preview range/frame共用有序EffectCompiler。avgblur/average_blur为均值，boxblur/box_blur为方框。parameters必须声明input_signal和output_signal={primaries,transfer}，工作信号须linear。旧默认后端不自动迁移。

均值radius/radius_x/radius_y为有限数字0..1024，默认链接radius=2；方框为0..128、默认4。轴静态值或关键帧出现时独立覆盖该轴；其余轴跟随radius。均值有效半径分别min(请求值,宽整除2)和min(请求值,高整除2)，不得重写作者值；metadata报告effective_radii。方框小表面的较大半径是明确的周期对称延拓扩展，不声称原FFmpeg在原来尺寸限制外可执行。

均值兼容size_x/sizeX/sizex和size_y/sizeY/sizey别名。由旧size_y别名声明的0继承已解析X半径，包含动画采样到0；canonical radius_y=0明确关闭垂直轴，两个语义不可混淆。同静态通道重复别名或重复轨道拒绝。未指定size_y时，沿用本项目旧默认Y=2；不是把FFmpeg本身的sizeY默认0冒称本项目旧默认。

intensity默认1、0..1。planes默认15、整数0..15；G=1/B=2/R=4/A=8。box的power默认1、静态整数0..4；均值固定一次并拒绝power字段。power=0为不做空间模糊；不同输入输出信号仍可造成明确的解释变化。planes/power/alpha_mode/output_gamut不动画。alpha_mode为straight默认或premultiplied，后者必须planes=15；output_gamut为preserve默认或clip。顶层仅id/type/enabled/parameters/keyframes，未知字段／类型／非有限值拒绝。

```json
{"type":"boxblur","parameters":{"input_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"output_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"radius_x":5.5,"radius_y":2.25,"power":3,"planes":15,"alpha_mode":"premultiplied","intensity":0.8}}
```

## 数学、边界与精度

令n=floor(r)、f=r-n，偏移-n..n的权重为1，偏移±(n+1)的权重为f，归一化除数2r+1。r=0跳过该轴。这是明确的连续有限窗扩展；不量化半径、不建立整数图像或LUT。均值越界索引夹到端点。方框索引按周期2L映射，再把第二半段映射到2L-1-index，即双端点重复的半采样点对称；与不重复端点的reflect不同。先做power遍水平，再power遍垂直。

持久RGBA为Float32，空间临时为Float64。窗口求和以互不重叠的二进制长度区间组合，没有相减大前缀；逐行有界临时，不建立整图前缀表或r×整图tap副本。它保护窗口外高亮／不透明样本之后的局部值；并不承诺任意极端有符号浮点求和精确到实数。

与原FFmpeg的整数输出不同：均值有最后floor；方框每轴每遍按16位固定倒数缩放并舍入。native_bit_equivalence=false。原生对照在受支持的gbrap8/10/12/16格式执行；不得把boxblur通用format列表中的浮点声明当作其8/16位C实现已正确处理Float32。方框每遍理想量化界由0.5码加最大码值×固定倒数增益误差递推，在执行前计算；不按实际结果放宽门槛。

## 信号、透明度与时钟

先从线性工作信号转换到input_signal，在该信号内滤波，再按output_signal解释回线性工作RGB。intensity混合线性RGB和独立coverage。straight对选中平面独立处理，隐藏RGB可能渗边；premultiplied先将RGB乘coverage，对四平面同算子处理，再除正Float64密度，精确零密度RGB置0，不用epsilon阈值。正密度转Float32可能下溢为0，该情况不等同Float64精确零。未处理alpha保留原位模式；alpha-only、同信号、preserve绕过RGB转换保留RGB位。output_gamut只裁算子RGB，与最终交付范围策略分开。intensity0在整图验证后逐位恒等。

radius/radius_x/radius_y/intensity可动画，6插值为linear/hold/ease_in/ease_out/ease_in_out/bezier；Bezier2或4控制值，4控制先解时间根。键tick严格递增非负整数；采样支持有限实数、大整数与Fraction；每轨1..1024键，总16384、规范JSON≤4MiB、最多4数值轨。越过原作者时长拒绝，采样过冲按通道边界限幅。呈现窗口和嵌套倒放保持原作者时钟，编译计划不可变。

## 完整空间预算与失败

输入为连续H×W×4 Float32、有限RGB、alpha0..1，边长1..16384，像素≤16777216。共享空间准入先保留fixed=6×完整表面字节+保留表字节+4×轨道JSON字节+max(1MiB,逐行临时估算)。逐行估算为(max(H,W)+2ceil(max(rX,rY))+1)×选中通道数×8×4。高斯保留原1MiB固定开销。

转换分块请求tile_pixels为1..262144，实际先限至16384及像素数，再限至floor((预算-fixed)/2048)。不足一个像素块拒绝；最终估算fixed+实际tile×2048不得超过768MiB或调用者更低预算。4K、无关键帧、无保留表、1MiB行开销下，实际默认tile3903；不提高空间预算，不减少整图空间依赖。估算不是进程峰值RSS或并发总内存保证。

整图预算、有限值和alpha验证先于结果。只读调用者可用；转换／块写入／逐行和分层求和均检查取消。取消True报RENDER_CANCELLED，回调异常原样传播；非有限或Float32溢出明确拒绝。失败、取消、晚块非法值不修改调用者。公开CLI输出仍限制在工程内，展示目录仅复制已完成产物。

## 验收与边界

59新增／479关联源码、真实整数原生对照、20调用31检查视频、实际4K8次CLI、195资源679项离线安装与2774项完整套件分别登记。运行中或未执行不计通过。4K证据为三种滤镜各一帧、竖直恒定图形，不能替代完整自然视频、长片延迟、峰值RSS、HDR、听感、连续播放或完整剪映等价验收。3个旧未支持样例改用unsharp，保留拒绝／清理／禁回退断言。

Python均值数学独立实现，未复制FFmpeg的GPL方框C源码；FFmpeg二进制、原高斯NOTICE、NumPy及其他依赖许可分别保留。无产品在线请求、云provider或虚拟化环境。后续继续锐化／时间滤镜、完整浮点迁移及其余剪映差异。
'''


def documents(target, full=None, published=False):
    names = [*LATEST_DOCS, REPORT, CONTRACT]; block = section(full, published)
    for name in LATEST_DOCS:
        text = (MAIN/name).read_text('utf8')
        text = re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?', '\n', text, flags=re.S)
        position = text.find('\n')+1
        write(target/name, text[:position]+'\n'+relink(block, name)+'\n'+text[position:])
    write(target/REPORT, report(full, published)); write(target/CONTRACT, contract())
    return names


def links(target, names):
    found = []
    for name in names:
        for value in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', (target/name).read_text('utf8')):
            path = unquote(value.strip('<>').split('#')[0])
            if not path or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', path): continue
            assert any((base/name).parent.joinpath(path).resolve().exists() for base in (target, ROOT, MAIN, PARENT)), (name, path)
            found.append([name, path])
    return found


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--revision', required=True); args = parser.parse_args()
    assert re.fullmatch(r'r\d+', args.revision)
    target = ROOT/'product/.runtime/float-spatial-20261022'/('readme-preview-'+args.revision)
    assert not target.exists(); target.mkdir(parents=True)
    names = documents(target); checked = links(target, names)
    write(ROOT/REPORT, report()); write(ROOT/CONTRACT, contract())
    inputs, _, _, installed = current()
    receipt = ROOT/REL/('readme-preview-'+args.revision+'.json'); assert not receipt.exists()
    write(receipt, json.dumps({'status': 'passed-local-document-links', 'documents': {name: sha(target/name) for name in names},
        'document_count': len(names), 'links': len(checked), 'installed_status': installed['status'], 'frozen_input_count': len(inputs),
        'main_mutated': False, 'full_suite_claimed_passed': False, 'preview_root': str(target), 'generator_sha256': sha(Path(__file__))}, ensure_ascii=False, indent=2))
    print(json.dumps({'documents': len(names), 'links': len(checked), 'installed_status': installed['status'], 'full_suite_claimed_passed': False}))


if __name__ == '__main__': main()
