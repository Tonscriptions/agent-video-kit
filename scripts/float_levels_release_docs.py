"""Numbered levels/exposure documentation from actual immutable receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen,sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
PARENT = ROOT.parent/'float-curves-lab-20261022'
REL = 'docs/validation/evidence/float-levels-20261022-lab'
ASSETS = 'docs/assets/float-levels-20261022-r1'
REPORT = 'docs/validation/浮点RGBA色阶与动态曝光实测_2026-10-22.md'
CONTRACT = 'docs/specs/浮点RGBA色阶与动态曝光契约_v0.1_2026-10-22.md'
MARKER = 'V103-FLOAT-RGBA-LEVELS-AND-ANIMATED-EXPOSURE'
LATEST_DOCS = ('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):return json.loads(path.read_bytes())


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs = frozen();assert len(inputs)==314
    native = read(ROOT/REL/'native-r2/verification.json')
    media = read(ROOT/REL/'media-r1/verification.json')
    assert native['status']=='passed' and native['methods']==242 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-levels-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle = media['levels_oracle']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=5e-7
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/levels_media_oracle.py')
    assert sha(ROOT/REL/'media-r1/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path = ROOT/REL/'installed-r1/verification.json'
    installed = read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-188-resources-real-previews-and-442-methods'
        assert installed['isolated_methods']['methods']==442 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay = read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):
            assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed = current()
    title = 'V103 浮点RGBA色阶与动态曝光' if published else 'V103 候选：浮点RGBA色阶与动态曝光（未发布）'
    if installed['status'].startswith('passed-'):
        itext = f"**442项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；188份source/wheel/site资源、8个固定离线wheel、NumPy931文件及原许可一致；安装版实际CLI音画、Float32及PNG16与源码版一致。"
    else:itext = f"**{installed['status']}，不计通过**；目标442项、188资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2537 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext = f"**2537项 /{full['suite_seconds']}秒 /0跳过**；314产品输入、8外部夹具和9依赖不变。"
    else:ftext = '**尚未通过，不计通过**；实际发现2537项，仅在V102完整2495项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式 `float32-native-v1` 工程的正式render和预览共用RGBA色阶、曝光关键帧及原作者时钟；局部调色保留浮点负值和超白值。默认后端迁移、其余浮点算子、离线AI质量及完整剪映功能仍未完成。

| 编号 | 功能性核验 | 实际内容与范围 | 证据 |
|---|---|---|---|
| FL103-01 | 共用内核 | 父曲线候选311→314输入、6条产品路径改变；42新增方法；RGBA色阶/动态曝光接入正式render、区间预览和PNG16的共用有序效果链 | [接口契约]({CONTRACT}) |
| FL103-02 | 端点与信号 | 共享RGB和独立RGBA各四端点；输入/输出信号明确，强度在线性工作域混合；反向范围、RGB负值/超白保留，alpha默认逐位保留 | [实际242项相关回归]({REL}/native-r2/verification.json) |
| FL103-03 | 七种保留模式 | none/lum/max/avg/sum/nrm/pwr，与真实GBRAPF32明确端点及独立标量方程对照；lum为max+min，avg含+1，不宣称Rec.709加权亮度 | [原生命令/I/O]({REL}/native-r2/verification.json) |
| FL103-04 | 自动黑白点 | 按每个自身通道的完整输入表面统计，含隐藏RGB；最小值以1、最大值以0初始化；负端点表示自动检测；零跨度默认拒绝或显式output_black | [端点与分块断言]({REL}/native-r2/unittest.log) |
| FL103-05 | 原生已知差异 | 本机FFmpeg8.1在GBRAPF32自动端点中出现跨通道依赖：红输入不变，改绿范围使原生红范围由.25..75变为.166667..833333；产品红结果不变。不把原生自动检测差异列为等价通过 | [三次隔离复现/原字节]({REL}/native-analysis-r1/verification.json) |
| FL103-06 | 作者关键帧 | 色阶共享/独立端点/强度、曝光amount/black的六种时间插值；直接Bezier及超2^53有理tick、作者窗口、嵌套倒放左极限 | [实际断言]({REL}/native-r2/unittest.log) |
| FL103-07 | 顺序与事务 | 曝光/色阶/曲线/LUT有序执行；只读输入、跨分块逐位一致；晚块非法值、取消和预算拒绝保留输入。预算含保留LUT，是工作区估算，不是进程总RSS | [源码冻结及日志]({REL}/native-r2/verification.json) |
| FL103-08 | 公开CLI | {len(media['calls'])}脚本调用/{len(media['checks'])}检查；2次正式render、3次preview；原创320×180、10fps、2秒各20帧，五段覆盖共享/RGBA/自动/保留/Bezier和动态曝光顺序 | [真实命令及输出]({REL}/media-r1/verification.json) |
| FL103-09 | 独立全选区参考 | 作者帧3..16共2,419,200个线性RGB值，最大绝对误差{media['levels_oracle']['maximum_linear_absolute_error']:.12g}，预先门槛5e-7；正式96000及选区67200双声道PCM采样帧一致；PNG16与对应作者帧误差≤1码 | [无产品数学导入的参考]({REL}/media-r1/executed-oracle.py.txt) |
| FL103-10 | 原片与GIF | CC0原创图形、alpha和正弦音频；GIF左原片、右真实CLI预览，14×100ms；静看3/10/16共6幅画面，不代替连续播放或试听 | [原片]({ASSETS}/original-range.mp4) · [实际预览]({ASSETS}/range.mp4) · [Float32]({ASSETS}/range.master.nut) · [PNG16]({ASSETS}/frame.png) · [查看记录]({REL}/static-review-r1.json) |
| FL103-11 | 离线安装 | {itext} | [安装收据]({REL}/installed-r1/verification.json) · [作者工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [CC0]({ASSETS}/LICENSE.txt) |
| FL103-12 | 完整回归 | {ftext} 源码242、安装442和完整套件分别记录，不累加为功能完成率 | [本轮报告]({REPORT}) |
| FL103-13 | 保留失败及未验收 | r1实际38项有2失败/1错误：两个原生自动端点参考与分通道契约不符、NumPy时钟被拒绝；原日志保留。没有新模型、自然/HDR、实时/长片RSS、连续播放/听审或完整剪映等价验收 | [失败与修正]({REL}/failure-analysis-r1.json) |

![原片与真实CLI浮点RGBA色阶及动态曝光预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix = '../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_ = current()
    return '''# 浮点RGBA色阶与动态曝光实测

从未改动的曲线311候选复制331个输入：311产品、9依赖、8外部夹具与3份基础运行器。复制时父完整2495项尚未运行/发布。本候选314产品输入、6条产品路径改变。242项相关源码=42新增+200既有；442项隔离安装与完整目标2537项分别执行，不能相加为剪映完成度。完整回归须等待实际V102完整2495项通过并普通发布。

运行内核是本项目的NumPy浮点实现，不调用FFmpeg colorlevels/exposure，不构造整数查表或在线请求。端点/保留度量的数学语义对照[官方colorlevels源码](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_colorlevels.c)、[保留度量](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/preserve_color.h)及[曝光参数](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_exposure.c)；未复制C代码。原生比较实际启动本机FFmpeg8.1，并保留原GBRAPF32输入输出；明确端点、保留模式与自动检测差异分别登记。

首轮r1实际38项/64.4595804秒，2失败/1错误，0跳过。两个测试把原生平面自动端点当成分通道参考，结果不符。隔离三次复现表明：红输入始终.3..7，绿范围.1..9→.2..8→.1..9，使原生红输出.25..75→.166667..833333→.25..75；输出重复字节相同。本项目按自身通道统计，红输出不受绿色变化影响。r2保留原生差异诊断，自动端点另对照独立整平面统计，不扩大原生等价容差，也不模拟跨通道行为。静态明确端点和七模式的原生对照继续保留。NumPy浮点时钟错误改为接受有限Real/Integral并保留有理/大整数路径；另补顶层动态曝光参数和布尔取消返回值处理。

公开CLI仍要求每个关键帧写明interpolation；库编译器省略时默认linear，属于两个接口边界。强度混合在线性工作RGB及显式alpha完成；默认alpha原位型保留，显式映射若最终覆盖率超出0..1则拒绝，绝不静默裁切。零输入跨度会拒绝或按显式output_black策略处理，不输出NaN。

真实样例是原创图形/移动标记/透明度与自制立体声正弦音频，五段共享色阶、独立RGBA、自动端点、lum保留、Bezier强度，均带动态曝光顺序。媒体参考独立推导端点/整平面极值、传递、曝光、强度和alpha合成；没有导入产品数学。静态联系表检查与连续播放/听审区分记录。原生Windows运行，不使用Docker、WSL、容器、虚拟环境、云服务或交互浏览器tab。

'''+relink(section(full,published),REPORT)


def contract():
    return '''# 浮点RGBA色阶与动态曝光契约 v0.1

选择`settings.pixel_pipeline.engine=float32-native-v1`；公共`render`、`preview frame/range`共用原作者时间线。正式输出仍执行工程交付范围策略。默认后端尚未迁移，其他算子、离线AI质量与完整剪映功能继续开发。

## 作者数据

色阶type为color_levels/levels/colorlevels；parameters须明确input_signal/output_signal的primaries/transfer，转换使用现有相对D65模型，共同工作信号须为linear。共享RGB端点input_black/input_white范围[-1,1]，output_black/output_white范围[0,1]，默认0/1/0/1。独立red_/green_/blue_/alpha_加上述端点名覆盖各自通道，允许反向输入或输出范围。共享RGB不会改变alpha。

旧rimin/rimax/romin/romax作者别名继续广播RGB；独立红色使用red_input_black等规范名。gimin/gimax/gomin/gomax、bimin/bimax/bomin/bomax、aimin/aimax/aomin/aomax分别为对应独立通道别名。重复别名数值不同拒绝；重复关键帧别名即使值相同也拒绝。

```json
{
  "type": "color_levels",
  "parameters": {
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "input_black": 0,
    "input_white": 1,
    "output_black": 0.03125,
    "output_white": 0.9375,
    "red_output_white": 0.875,
    "alpha_output_white": 0.9,
    "preserve": "lum",
    "intensity": 0.75,
    "zero_span": "reject"
  },
  "keyframes": [{"property": "red_output_white", "keyframes": [
    {"at_tick": 0, "value": 0.75, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 0.9375, "interpolation": "linear"}
  ]}]
}
```

## 自动端点、计算与保留模式

任何负输入端点表示按该通道完整输入表面自动检测，含透明像素隐藏RGB。最小值从1、最大值从0开始；统计基于输入信号转换后的Float32，是共享时钟采样时刻该层完整表面，不是片段全时长、整条最终序列或当前分块。RGB/alpha分别统计，跨分块结果逐位相同。未声明的独立通道实时继承共享RGB值；显式alpha独立于共享值。

端点转Float32；系数使用Float32端点差后binary64相除并写回Float32，RGB执行独立减/乘/加，无整数中间量、不裁切负值/超白。输入跨度为0默认报FLOAT_LEVELS_ZERO_SPAN；显式zero_span=output_black将该通道映射到其输出黑点。极小跨度/输出溢出拒绝。零强度验证输入后逐位复制，不为平坦自动端点制造NaN。

preserve/preserve_color支持none/lum/max/avg/sum/nrm/pwr。lum=max+min，max=最大值，avg=(R+G+B+1)/3，sum=和，nrm=平方和开根，pwr=立方和的实立方根；都在当前输入/输出信号的RGB数值上比较。输出度量>0才用输入/输出比缩放，否则保持映射结果。这些是公开模式的精确定义，不宣称加权亮度、感知色恒定或HDR。bool/0/1/off别名按旧契约映射none或lum。

本机FFmpeg8.1的GBRAPF32自动端点已实测出现跨通道依赖，产品按各自通道完整表面计算。明确端点/保留模式的原生对照与自动模式的独立数学对照分别留证；不能宣称所有输入逐位复制FFmpeg或剪映。

## 动态曝光与作者时间

曝光type=exposure，amount/exposure范围[-3,3]，black范围[-1,1]；曝光在共同线性RGB上工作。动态amount/black可在effect.keyframes或parameters.keyframes之一声明。原静态协议/系数不变，动态协议为author-clock-native-coefficient-float32-exposure-v1。白点=Float32(exp2(-Float32(amount)))，差为绝对Float32白点减黑点；零差增益1024，否则取倒数Float32。每像素两次Float32减/乘，alpha原位型保留。

所有色阶端点、intensity与曝光两通道支持linear/hold/ease_in/ease_out/ease_in_out/bezier；前缀effect./parameters./当前类型.可用。Bezier两控制值直接计算，四控制值按x求根；超范围时间插值结果按通道范围限制后采样。固定不可变规范JSON轨道，每轨1..1024关键帧、总16384、最多通道数、序列化4MiB，严格递增非负整数at_tick。超2^53整数/有理偏移保留；窗口及嵌套倒放用原作者时钟和左极限。未知字段/通道、重复、非法数字、控制点或超作者时长拒绝。

## 表面、alpha、预算与失败

输入连续H×W×4 Float32，RGB有限，alpha在0..1；单边≤16384、总像素≤16777216。独立alpha端点仅在显式声明/轨道时启用，强度与原覆盖率在线性覆盖域混合；最终越界拒绝，默认alpha逐位保留。RGB转回共同线性工作域后以binary64混强度再写Float32。

请求分块1..262144，实际≤16384。工作区估算=3倍表面字节+保留LUT+实际块像素×2048+4倍轨道JSON字节+524288，最大768MiB；不含整个Python对象图、解析器、音频、缓存、并发或总RSS。只读输入可用；取消回调抛异常或返回true均中止新动态运算，失败不改输入。效果链按作者顺序执行，禁用效果跳过；色阶自动检测可能需要额外整帧遍历，不声称实时。

尚未验收绝对nits、ICC/PQ/HLG、广泛自然素材与模型质量、长片/RSS、连续播放/听审或完整剪映功能等价。
'''


def documents(target,full=None,published=False):
    names = [*LATEST_DOCS,REPORT,CONTRACT];block = section(full,published)
    for name in LATEST_DOCS:
        text = (MAIN/name).read_text('utf8')
        text = re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?','\n',text,flags=re.S)
        position = text.find('\n')+1
        write(target/name,text[:position]+'\n'+relink(block,name)+'\n'+text[position:])
    write(target/REPORT,report(full,published));write(target/CONTRACT,contract())
    return names


def links(target,names):
    found = []
    for name in names:
        for value in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)',(target/name).read_text('utf8')):
            path = unquote(value.strip('<>').split('#')[0])
            if not path or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',path):continue
            assert any((base/name).parent.joinpath(path).resolve().exists() for base in (target,ROOT,MAIN,PARENT)),(name,path)
            found.append([name,path])
    return found


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--revision',required=True);args = parser.parse_args()
    assert re.fullmatch(r'r\d+',args.revision)
    target = ROOT/'product/.runtime/float-levels-20261022'/('readme-preview-'+args.revision)
    assert not target.exists();target.mkdir(parents=True)
    names = documents(target);checked = links(target,names)
    write(ROOT/REPORT,report());write(ROOT/CONTRACT,contract())
    inputs,_,_,installed = current()
    receipt = ROOT/REL/('readme-preview-'+args.revision+'.json');assert not receipt.exists()
    write(receipt,json.dumps({'status':'passed-local-document-links','documents':{name:sha(target/name) for name in names},
        'document_count':len(names),'links':len(checked),'installed_status':installed['status'],
        'frozen_input_count':len(inputs),'main_mutated':False,'full_suite_claimed_passed':False,
        'preview_root':str(target),'generator_sha256':sha(Path(__file__))},ensure_ascii=False,indent=2))
    print(json.dumps({'documents':len(names),'links':len(checked),'installed_status':installed['status'],'full_suite_claimed_passed':False}))


if __name__=='__main__':main()
