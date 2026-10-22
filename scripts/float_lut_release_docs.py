"""Numbered LUT documentation generated from actual immutable receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
PARENT = ROOT.parent/'float-crop-lab-20261022'
REL = 'docs/validation/evidence/float-lut-20261022-lab'
ASSETS = 'docs/assets/float-lut-20261022-r1'
REPORT = 'docs/validation/浮点LUT五种插值与有序调色链实测_2026-10-22.md'
CONTRACT = 'docs/specs/浮点LUT色彩信号与作者强度契约_v0.1_2026-10-22.md'
MARKER = 'V101-FLOAT-LOCAL-LUT'
LATEST_DOCS = ('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):return json.loads(path.read_bytes())


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs = frozen();assert len(inputs)==309
    native = read(ROOT/REL/'native-r3/verification.json')
    media = read(ROOT/REL/'media-r1/verification.json')
    assert native['status']=='passed' and native['methods']==160 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-LUTs-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle = media['lut_oracle']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=3e-7
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/lut_media_oracle.py')
    assert sha(ROOT/REL/'media-r1/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path = ROOT/REL/'installed-r1/verification.json'
    installed = read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-185-resources-real-previews-and-360-methods'
        assert installed['isolated_methods']['methods']==360 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay = read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):
            assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed = current()
    title = 'V101 浮点本地LUT与有序调色链' if published else 'V101 候选：浮点本地LUT与有序调色链（未发布）'
    if installed['status'].startswith('passed-'):
        itext = f"**360项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；8个固定离线wheel、185份source/wheel/site资源、NumPy931文件一致；安装版实际CLI视频/PCM/Float32/PNG16与源码版一致。"
    else:
        itext = f"**{installed['status']}，不计通过**；目标360项、185资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2455 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext = f"**2455项 /{full['suite_seconds']}秒 /0跳过**；309产品输入、8外部夹具和9依赖不变。"
    else:
        ftext = '**尚未通过，不计通过**；目标2455项；仅在实际V100完整2418项通过且普通发布后才执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式 `float32-native-v1` 工程的正式render和预览共用本地LUT。完整3D CUBE支持五种插值、明确输入/输出色彩信号与作者关键帧强度；曝光和LUT按作者顺序执行。默认后端迁移、其余浮点效果及完整剪映功能仍未完成。

| 编号 | 功能性核验 | 实际结果与范围 | 证据 |
|---|---|---|---|
| FL101-01 | 共同内核 | 新增float_lut、float_effect_chain及37项测试；父候选306输入→309输入，6条产品路径改变；正式render、区间及PNG16共用 | [契约]({CONTRACT}) |
| FL101-02 | 本地CUBE | red-fastest不可变Float32表；2..256边长、DOMAIN_MIN/MAX、标题/注释；项目内路径或登记ID/SHA，资源变化拒绝；1D shaper及3dl/csp/dat尚未迁入浮点路径 | [37项新增方法]({REL}/native-r3/unittest.log) |
| FL101-03 | 五种插值 | nearest/trilinear/tetrahedral/pyramid/prism；独立多项式与重心线性方程参考；实际原生29宽标量与32宽默认CPU各核验全部五种，含边界/同坐标 | [原生I/O与结果]({REL}/native-r3/verification.json) |
| FL101-04 | 色彩与混合 | 共同线性工作RGB→明确LUT输入信号→查表→明确输出信号→线性工作RGB后混合；alpha独立。DOMAIN先归一化再夹边，不裁剪表输出 | [信号与范围测试]({REL}/native-r3/unittest.log) |
| FL101-05 | 作者强度 | 静态0..1、6种关键帧插值、Bezier overshoot显式夹0..1；作者窗口和嵌套反向保留各自时钟，预览选区不重启动画 | [160项相关回归]({REL}/native-r3/verification.json) |
| FL101-06 | 有序效果 | exposure→LUT与LUT→exposure结果区分，多LUT按序，禁用项跳过；相同本地表共享；未接入效果明确拒绝 | [顺序与作者IR测试]({REL}/native-r3/unittest.log) |
| FL101-07 | 精度与拒绝 | 65536级中性色、负值/超1表输出、极小alpha、强度0逐位保留；分块逐位一致、只读输入、晚块非法值、预算和中途取消均核验 | [实际执行源码]({REL}/native-r3/verification.json) |
| FL101-08 | 真实公开CLI | {len(media['calls'])}脚本调用/{len(media['checks'])}检查，2次render+3次preview；原片/结果各320×180、10fps、20帧；5段各4帧覆盖五种插值、动态强度和两种效果顺序 | [命令与检查]({REL}/media-r1/verification.json) |
| FL101-09 | 独立像素与声音 | 作者帧3..16的2,419,200个线性RGB值，最大绝对误差{media['lut_oracle']['maximum_linear_absolute_error']:.12g}；正式96000、选区67200双声道采样帧逐一一致；PNG16与对应帧误差≤1码 | [独立执行参考]({REL}/media-r1/executed-oracle.py.txt) |
| FL101-10 | 原视频/GIF | 左原片、右实际CLI预览；GIF14×100ms；静态看过作者帧3/10/16的6个画面。五种均做数值核验，未据此声称五种均完成视觉、连续播放或试听验收 | [原片MP4]({ASSETS}/original-range.mp4) · [结果MP4]({ASSETS}/range.mp4) · [Float32母参考]({ASSETS}/range.master.nut) · [PNG16]({ASSETS}/frame.png) · [查看记录]({REL}/static-review-r1.json) |
| FL101-11 | 权利与安装 | {itext} 原CUBE、图形/alpha及正弦音频为本次CC0生成，标签用Pillow默认字体；23份源码演示资产单独校验SHA | [原CUBE]({ASSETS}/original-look.cube) · [作者工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [声明]({ASSETS}/LICENSE.txt) |
| FL101-12 | 完整回归 | {ftext} 160项源码、360项安装及完整套件覆盖重叠，分别记录 | [本轮报告]({REPORT}) |
| FL101-13 | 失败与限制 | r1实际159项有2失败：更宽坐标改变pyramid分面、夹具误比较修改时间；r2实际160项有1夹具字段错误，均保留。另观察到本机原生29宽tetrahedral加速差异；已分开核验标量及对齐默认路径。自然质量/HDR/实时性/长片总RSS/完整剪映均未验收 | [失败与修正]({REL}/failure-analysis-r1.json) |

![原片与真实CLI本地LUT预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix = '../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_ = current()
    return '''# 浮点LUT五种插值与有序调色链实测

本轮新增两份产品模块和37项测试，连接既有共同FloatTimeline和FloatRenderContext。父裁剪候选306产品输入复制后只读保留；本候选309输入、6条产品路径改变。160项源码相关回归=37项新增+123项既有；360项离线安装核验和完整目标2455项分别执行，不相加为功能完成度。复制时父2418项尚未执行/发布，完整套件必须等父候选实际2418项通过并普通发布后启动。

插值由独立NumPy加权顶点表达式实现，独立参考用多项式或重心线性方程求解。实际原生FFmpeg只作为对照及编解码器；产品运行时不启动lut3d滤镜。五种插值的公开定义与原生pyramid严格分支参考[FFmpeg官方文档源码](https://ffmpeg.org/doxygen/7.0/vf__lut3d_8c_source.html)，产品未复制其C实现。输入归一化坐标按Float32网格舍入，顶点权重Float64累计，输出Float32；这与CUBE表本身的Float32存储及最终整数交付是不同边界。

初次相关套件实际159项、377.286秒、2失败：更宽的网格临时数使pyramid在整数平面处选择不同分面；夹具把save_project预期更新的modified时间误当作者编辑。产品修正坐标，夹具按settings/sequences/assets逐项精确比较。随后160项、441.065秒有1错误，来自测试误用缓存字段key；改为公开cache_key。未通过增加像素容差掩盖失败。各轮执行源码、原生命令和原始I/O完整保留。

另做20次本机原生诊断，覆盖29/32宽、5插值及默认/关闭CPU优化。在这个固定二进制及夹具上，默认29宽tetrahedral出现颜色和alpha变化（最大颜色误差1.4314032793、alpha误差0.4847784042）；标量路径保留alpha，对齐32宽默认路径也保留。本轮正式接受的原生对照分别核验任意29宽标量与32宽默认路径全部五种。此观察不推广为其他版本/平台的结论；诊断后的工具摘要与原始文件另存，未虚构执行前工具摘要绑定。

真实媒体使用本轮原创5³ CUBE、RGB16图形、alpha梯度、移动标记及双声道正弦音频。五段各4帧，作者强度.15→.9、ease_in_out，分别执行曝光→LUT或LUT→曝光。独立参考根据原输入量化码、作者时间和明确传递函数计算全部选区像素；未调用产品色彩/LUT/时钟函数。正式原片与结果、区间MP4、Float32母参考、PNG16、工程、CUBE登记、权利账、GIF和逐项SHA均保留。

''' + f"实际160项相关源码套件用时{native['seconds']:.6f}秒，0跳过。\n\n" + relink(section(full,published),REPORT)


def contract():
    return '''# 浮点LUT色彩信号与作者强度契约 v0.1

显式选择settings.pixel_pipeline.engine=float32-native-v1。Agent仍用effects数组，参数置于parameters；类型lut3d/lut/cube/look，path/file/lut同值别名或lut_id二选一。每个LUT必须明确input_signal与output_signal，两者均含primaries/transfer；原有effects list中的整数后端说明不替代此显式浮点契约。未知字段或未接入效果拒绝。默认渲染后端未迁移。

支持完整3D .cube，边长2..256、red-fastest、TITLE、DOMAIN_MIN/MAX、空行、注释和UTF-8 BOM。数据必须恰为size³组三个有限Float32，DOMAIN各轴有限、最大值严格大于最小值；头不重复、不得出现在样本之后；1D shaper及未知扩展拒绝。3dl/csp/dat仍属于既有整数后端范围，未自动转换或宣称本轮支持。TITLE使用带引号的单行字符串；严格安全解析不猜测厂商方言。

路径解析后必须在现有本地项目根内，不允许URL、UNC、项目外路径或file协议字符串。登记ID必须有匹配SHA，登记JSON与LUT文件一并绑定；固定表为不可改bytes上的Float32视图，编译计划不会跟随作者对象或文件变动。正式render/preview在事务核验时重查文件身份，文件变化不能以旧计划发布；持久预览键包含原文件依赖。强度0仍编译并验证本地资源，不能绕过缺失或损坏登记。库级FloatTimeline调用必须给resource_root；正式共同上下文自动提供项目根。

共同工作域须为明确线性光ColorSignal。每块先从工作域转到LUT声明输入，归一化坐标=(输入-DOMAIN_MIN)/(DOMAIN_MAX-DOMAIN_MIN)，夹到[0,1]后以Float32乘(size-1)，再按所选插值求值。nearest以floor(coord+.5)取点；trilinear八顶点；tetrahedral按分数的有序四顶点；prism为R/B平面的三角形沿G插值；pyramid为原生严格分支选择的零轴双线性面加对角校正，同分数时保留其第三轴分支约定。权重Float64、表输出Float32，保留有限负值及超1输出，无整数中间量。

查表输出按声明output_signal转回共同线性工作域，然后执行source*(1-intensity)+graded*intensity，Float64混合、Float32结果；强度1直接取变换结果，强度0逐位复制原表面。混合在工作线性RGB内，不用编码域整数blend，也不以重写CUBE近似动态强度。alpha为独立straight覆盖率，位模式保持，不参与色彩转换或LUT；后续几何/合成仍遵守自己的alpha契约。

静态intensity有限且在0..1；顶层或parameters内可有单条intensity关键帧，二者不能同时声明。支持effect./parameters./类型名前缀，1..1024递增非负整数tick，六种既有作者插值：hold、linear、ease_in、ease_out、ease_in_out、bezier。Bezier沿既有32段/8小数公共查表；控制值有限，四值时横向控制在0..1，overshoot后的实际强度夹到0..1。FloatTimeline在源作者动画tick求值，presentation_window偏移、子序列速度/反向和父序列时钟保持区分。

曝光与LUT按作者数组顺序逐项运行；曝光继续使用既有原生系数契约，所有效果在该片段几何与层混合之前处理；嵌套容器效果在子画布合成之后处理。未声明crop的mask空间与显式crop分支的父画布mask差异沿前轮契约保留，本轮不宣称完成所有组合统一验收。禁用效果跳过；未知的启用效果拒绝，不静态近似或退回整数路径。

表面为连续H×W×4 Float32，RGB有限、alpha在0..1，输入可只读。单边≤16384、总像素≤16777216。文件≤512MiB、单行≤4096字节；表解析按二份表与有界I/O估算入场，拒绝超预算后才分配。像素请求分块1..262144、默认65536，内部单块最多16384以符合共同色彩转换尺寸；估算包括三份全帧、已保留表和保守分块工作数组，上限768MiB。相同路径表共享，跨片段所有保留表合计入场。此配额不等于进程总RSS，也不覆盖项目/登记JSON、Python对象、音频、源缓存和并发总额。取消、晚块无效值、溢出和预算拒绝均保留输入，不返回部分结果。

支持既有明确D65 bt709/display-p3/bt2020与linear/srgb/bt709-oetf/gamma22/gamma24相对信号；未增加ICC、PQ/HLG、绝对nits、色域映射、色适应或HDR验收。合成像素一致不代表自然广告素材质量、实时预览、长片内存或完整剪映等价。MP4/GIF是观看副本，Float32/PCM/PNG16另核验；静态抽帧不代替连续播放与听感。
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
    target = ROOT/'product/.runtime/float-lut-20261022'/('readme-preview-'+args.revision)
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
