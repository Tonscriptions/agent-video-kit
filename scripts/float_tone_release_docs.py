"""Numbered basic-tone documents generated from actual execution receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-hsl-lab-20261022'
REL='docs/validation/evidence/float-tone-20261022-lab'
ASSETS='docs/assets/float-tone-20261022-r1'
REPORT='docs/validation/连续浮点基础调色与YCbCr语义实测_2026-10-22.md'
CONTRACT='docs/specs/连续浮点基础调色与YCbCr语义契约_v0.1_2026-10-22.md'
MARKER='V106-CONTINUOUS-FLOAT-BASIC-YCBCR-TONE'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):return json.loads(path.read_bytes())


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs=frozen();assert len(inputs)==320
    native=read(ROOT/REL/'native-r2/verification.json');media=read(ROOT/REL/'media-r1/verification.json')
    assert native['status']=='passed' and native['methods']==372 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-basic-tone-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle=media['tone_oracle']
    assert oracle['scenarios']==['color','gamma','hsl','gray','native_clip']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=2e-6
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/tone_media_oracle.py')
    assert sha(ROOT/REL/'media-r1/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path=ROOT/REL/'installed-r1/verification.json'
    installed=read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-191-resources-real-previews-and-572-methods'
        assert installed['isolated_methods']['methods']==572 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay=read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed=current();o=media['tone_oracle']
    records=native['native_tone_records'];maximum=max(r['maximum_fractional_code_error'] for r in records)
    title='V106 连续浮点基础调色与YCbCr语义' if published else 'V106 候选：连续浮点基础调色与YCbCr语义（未发布）'
    if installed['status'].startswith('passed-'):
        itext=f"**572项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；191份source/wheel/site资源、8个固定离线wheel、NumPy931文件及许可一致；安装版公开CLI的编码音画、Float32和PNG16与源码版一致。"
    else:itext=f"**{installed['status']}，不计通过**；目标572项、191资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2667 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext=f"**2667项 /{full['suite_seconds']}秒 /0跳过**；320产品输入、8外部夹具和9依赖不变。"
    else:ftext='**尚未通过，不计通过**；目标2667项，仅在V105实际完整2623项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式`float32-native-v1`工程的正式render和预览共用亮度、对比度、饱和度、组合color、Gamma、色相、全局HSL和灰度。矩阵/量程/信号明确，像素连续；全局HSL保留YCbCr旋转模型，与八色RGB HSL分开。默认后端迁移、其余浮点算子、自然素材/离线AI质量与完整剪映目标继续开发。

| 编号 | 功能性核验 | 实际内容与边界 | 证据 |
|---|---|---|---|
| FT106-01 | 共用内核 | 父HSL318→320产品输入，5条路径改变；44新增方法；原生Windows，无容器/网络运行时 | [接口契约]({CONTRACT}) |
| FT106-02 | 基础调色 | 8类语义及14个类型名；亮度/对比度/Gamma作用于Y码值，eq饱和度作用于Cb/Cr，全局HSL使用色度旋转和旧hue亮度幅度 | [372项相关回归]({REL}/native-r2/verification.json) |
| FT106-03 | 显式信号 | 明确input/output primaries与transfer、四种受支持矩阵、full/limited量程及8/10位分数码值轴；矩阵独立于transfer，不猜测标签 | [独立矩阵求逆参考]({REL}/native-r2/unittest.log) |
| FT106-04 | 实际原生对照 | {len(records)}次真实FFmpeg YUVA444 eq/hue对照，包括8位与10位hue、默认CPU与纯C亮度路径；最大分数码误差{maximum:.9g}，执行前门槛1.01码；alpha不变。整数后端对照不代表任意浮点输入等价 | [原始命令/I/O]({REL}/native-r2/verification.json) |
| FT106-05 | 两种算术 | continuous使用连续公式；native_coefficients只量化旧内核标量系数，不量化像素。原生输出还会取整，未承诺逐位相同 | [实际差异断言]({REL}/native-r2/unittest.log) |
| FT106-06 | 旧语义边界 | eq饱和度作者范围0..4但有效上限3，显式报告；eq零饱和度中心为半最大码，与中性色度灰度不同；HSL亮度±1是8位±25.5码，10位±102.4码 | [契约]({CONTRACT}) |
| FT106-07 | 连续精度 | 131072个不同浮点输入保持超过130000个不同输出；无整数表面/LUT；持久RGBA Float32、临时数学binary64、alpha逐位保留 | [实际断言]({REL}/native-r2/unittest.log) |
| FT106-08 | 码值裁切 | 仅发生改变的YCbCr平面裁切至参考码值轴，报告分量数；未改变平面保留headroom；RGB output_gamut=clip单独声明，最终交付clip另设 | [契约]({CONTRACT}) |
| FT106-09 | 作者与顺序 | 6种插值、4控制Bezier时间根、大整数/有理tick、原作者预览窗口与嵌套倒放；效果顺序保留；只读、预算、取消/异常与溢出保护调用者输入 | [执行日志]({REL}/native-r2/unittest.log) |
| FT106-10 | 真实公开CLI | {len(media['calls'])}调用/{len(media['checks'])}检查；2次正式render、3次preview；原创320×180、10fps、2秒各20帧；color/Gamma/HSL/灰度/曝光后原生系数五场景 | [实测记录]({REL}/media-r1/verification.json) |
| FT106-11 | 全像素参考 | 作者帧3..16共2,419,200线性RGB，交付clip后最大绝对误差{o['maximum_linear_absolute_error']:.12g}，执行前门槛2e-6；裁切前峰值{o['unclipped_linear_max']:.9g}、越界RGB分量{o['unclipped_outside_RGB_components']}；96000/选区67200双声道PCM采样帧一致、PNG16≤1码 | [独立矩阵求逆/标量参考]({REL}/media-r1/executed-oracle.py.txt) |
| FT106-12 | 原片/GIF | CC0原创图形、移动帧标记、透明度和正弦音频；左原片右实际预览，GIF14×100ms；静看3/10/16共6幅，未做连续播放/听审 | [原片]({ASSETS}/original-range.mp4) · [输出]({ASSETS}/range.mp4) · [Float32]({ASSETS}/range.master.nut) · [目检]({REL}/static-review-r1.json) |
| FT106-13 | 离线安装 | {itext} | [安装收据]({REL}/installed-r1/verification.json) · [可编辑工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [CC0]({ASSETS}/LICENSE.txt) |
| FT106-14 | 完整回归 | {ftext} 源码372、安装572与完整套件独立登记，不相加当作功能完成率 | [本轮报告]({REPORT}) |
| FT106-15 | 原失败 | native-r1实际44项/81.670621秒，0失败/1错误/0跳过；测试遗漏必需Bezier控制点，仅补测试夹具；保留执行源/日志，未改算法/保护或放宽门槛 | [失败分析]({REL}/failure-analysis-r1.json) |
| FT106-16 | 未验收边界 | 10位eq为显式连续扩展，没有原生eq10兼容承诺；无HDR感知模型、自然素材质量、长片RSS、持续播放/听审或完整剪映等价验收 | [契约与边界]({CONTRACT}) |

![原片与真实CLI基础调色预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_=current()
    return f'''# 连续浮点基础调色与YCbCr语义实测

源码关联回归实际 **{native['methods']}项 /{native['seconds']:.6f}秒 /0跳过**，44项新增。源码、隔离安装、公开CLI媒体与完整回归分别记录，不将通过数解释为剪映等价。

本轮将8类旧基础调色连接到显式float32-native-v1时间线，保留Y码值亮度/对比度/Gamma、CbCr饱和度以及全局HSL的色度旋转语义。未用RGB HSL替换全局hsl。八色selective_hsl仍使用独立RGB HSL模型。matrix/range与输入输出RGB信号必须声明；工作表面保持线性RGBA Float32，算子在声明信号的分数YCbCr码值中处理，强度在线性RGB混合。

真实原生测试直接输入/输出YUVA444平面，不通过RGB转码来掩盖误差。eq比较原生8位亮度、对比度、饱和度、组合color和Gamma；hue比较8位色相、8/10位灰度与10位HSL。默认CPU和禁用CPU特性的亮度调用均执行。预先门槛为1.01分数码，允许原生像素取整与Float32投影误差，不承诺逐位相同。continuous模式还用独立矩阵求逆/标量参考核验；native_coefficients模式只舍入系数，持续像素不量化。

原生eq的快速对比度/亮度与Gamma LUT使用不同数值路径。continuous明确使用连续归一化公式；native_coefficients在Gamma为1时保留标量固定点系数，在Gamma不为1时保留连续幂函数并对参数使用原生单精度。eq饱和度实际限制3，作者4在元数据报告有效3；hue饱和度仍按其接口处理。eq零饱和度围绕最大码的一半，灰度围绕中性色度码，两者不假装相同。

首轮44项中1项测试构造遗漏Bezier控制点，保护按要求拒绝。仅补测试夹具，运行时未变；完整保留native-r1失败、执行源和原始I/O，随后native-r2运行372项相关回归。没有调整算法、功能约束或误差门槛。

实片五场景的独立参考只使用NumPy、标准数学和单独的矩阵求逆，不导入产品颜色/矩阵/关键帧/效果函数。检查整个选区的全部RGB和PCM、实际PNG16、分进程缓存复用与作者数据不变。最终交付策略明确为clip；裁切前超白单独统计，不把交付裁切参考称作无界HDR母版。CC0媒体保留原片、实际输出、GIF、工程、权利账、SHA和执行脚本。静态目检与连续播放/声音听审分别登记。

来源研究参考：[FFmpeg n8.1 eq实现](https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_eq.c)。本机原生执行二进制为已配置FFmpeg 8.1。研究目录的旧FFmpeg源码标记8.0.git，不能冒称n8.1；本轮网络抓取n8.1的eq.h/hue失败，失败保留在私有研究收据，不作为已取得版本源码的证明。产品运行和媒体验证没有在线请求；没有复制旧源码充作新版本证据。

'''+relink(section(full,published),REPORT)


def contract():
    return '''# 连续浮点基础调色与YCbCr语义契约 v0.1

## 选择与参数

显式settings.pixel_pipeline.engine=float32-native-v1，正式render、preview range/frame共用有序内核。类型：brightness/lightness、contrast、saturation、color、gamma/gamma_adjust、hue/hue_rotate、hsl/hsl_adjust、grayscale/black_white/blackandwhite。默认8位后端及其现有工程保持原实现；本接口不自动迁移旧工程。

所有类型parameters均须input_signal/output_signal={primaries,transfer}、matrix、range。RGB基色/transfer使用既有明确D65相对信号集合；matrix可bt709/smpte170m/bt470bg/bt2020nc，range为full/limited。矩阵不能替代RGB基色/transfer声明，两者允许创意组合且不隐式猜测。reference_bits默认8、可10；表示分数码值轴，不代表中间像素量化。

brightness[-1,1]默认0；contrast[0,4]默认1；saturation[0,4]默认1；gamma[.1,10]默认1；hue[-360,360]默认0；hsl.lightness[-1,1]默认0；各类型intensity[0,1]默认1。color只包含brightness/contrast/saturation。单独brightness/contrast/saturation/gamma支持amount/value别名；hue支持degrees/angle/value；hsl支持degrees/angle→hue和brightness→lightness。静态或轨道重复声明同一通道别名拒绝。灰度只有intensity。未知字段、布尔/非有限/字符串数字/越界拒绝。

arithmetic为continuous（默认）或native_coefficients。output_gamut为preserve（默认）或clip。effect顶层仅id/type/enabled/parameters/keyframes；轨道可放effect.keyframes或parameters.keyframes一个层级。enabled=false由效果宿主跳过。

```json
{"type":"color","parameters":{"input_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"output_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"matrix":"bt709","range":"limited","brightness":0.03,"contrast":1.1,"saturation":0.8,"arithmetic":"continuous","intensity":0.7}}
```

## 码值与算子

令M=2^bits-1、S=2^(bits-8)。full的Y=亮度×M、Cb/Cr中点=128S、幅度=M；limited的Y=16S+亮度×219S、Cb/Cr中点128S、幅度224S。RGB先按声明input_signal解释；Y使用所选矩阵的Kr/Kb，Cb=(B-Y)/(2(1-Kb))、Cr=(R-Y)/(2(1-Kr))。连续码值没有取整、色度抽样或整数LUT。

continuous eq在Y归一化码值上计算contrast×(x-.5)+.5+brightness，然后改变的平面clip到0..1并使用幂1/gamma。饱和度是Cb/Cr平面的contrast。未改变的平面直接保留，不隐式裁掉其headroom。eq饱和度实际按旧原生路径夹到3，sampled_values保留作者值并以effective_eq_saturation另报有效值。

native_coefficients对原生eq参数使用单精度；Gamma为1时采用标量固定点contrast系数与brightness偏置，保留连续像素，不执行原生每像素整数floor。Gamma非1时保留连续幂函数；原生8位LUT的输出取整不能逐位相同。10位eq只允许continuous，明确为独立连续扩展；FFmpeg eq没有原生10位后端可作为兼容依据。

hue/hsl围绕中性色度128S旋转Cb/Cr并乘饱和度；grayscale把色度置中点、Y保持。hsl.lightness通过旧hue亮度幅度改变Y：8位每单位25.5码，10位102.4码；与eq brightness不是同一幅度。native_coefficients使用单精度角度及16位标量三角系数。全局HSL不是RGB HSL；八色selective_hsl使用另外的模型。

改变后的平面裁切至0..M，计入changed_plane_clipped_components。逆矩阵恢复RGB后可负值或超白；output_gamut=clip显式裁切算子RGB并报告，preserve保留。算子RGB按output_signal解释，再转换回线性工作信号，最后按intensity与原始工作RGB混合。算子输出clip不等于最终交付clip。intensity=0在完整有限值/alpha/预算检查后逐位返回输入；同信号、无效果及无实际裁切的identity也保留原RGB位模式。alpha从输入逐位复制，不参与码值和信号转换。

## 作者时间与资源

各类型现有数值及intensity可动画，6种插值linear/hold/ease_in/ease_out/ease_in_out/bezier。每轨1..1024键，总16384键、规范JSON最多4MiB；轨道数不超过当前类型通道数。tick严格递增非负整数，采样允许非负有限实数、大整数与Fraction；Bezier须2或4控制值，4控制先解时间根；插值越界按通道边界限幅。超过原作者时长拒绝。预览窗口、父子嵌套与倒放均沿用原作者时钟，编译计划不保留可变作者字典。

输入为连续H×W×4 Float32，边长1..16384、像素<=16777216。请求tile_pixels为1..262144、实际<=16384。工作区估算=3×表面字节+保留表字节+每块像素×2048+4×轨道JSON字节+524288，最多768MiB；它不是整个进程峰值RSS保证。预算与整张有限RGB/alpha0..1检查完成后再构造输出；只读输入可用，取消返回True或异常、晚块非法值、传递溢出均不修改调用者输入。

## 验收边界

真实YUVA444 eq/hue原生对照、独立连续数学、公开CLI全像素/PCM/PNG16、8-wheel隔离安装和完整2667项分别验收；未执行/运行中不记通过，不累加作为剪映功能完成率。未完成默认后端迁移、所有其他浮点效果、自然素材/离线AI质量、HDR感知/绝对nits、ICC/白点适配、长片RSS和完整剪映等价。媒体记录的静态抽帧查看不能替代连续播放或声音听审。
'''


def documents(target,full=None,published=False):
    names=[*LATEST_DOCS,REPORT,CONTRACT];block=section(full,published)
    for name in LATEST_DOCS:
        text=(MAIN/name).read_text('utf8')
        text=re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?','\n',text,flags=re.S)
        position=text.find('\n')+1
        write(target/name,text[:position]+'\n'+relink(block,name)+'\n'+text[position:])
    write(target/REPORT,report(full,published));write(target/CONTRACT,contract())
    return names


def links(target,names):
    found=[]
    for name in names:
        for value in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)',(target/name).read_text('utf8')):
            path=unquote(value.strip('<>').split('#')[0])
            if not path or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',path):continue
            assert any((base/name).parent.joinpath(path).resolve().exists() for base in (target,ROOT,MAIN,PARENT)),(name,path)
            found.append([name,path])
    return found


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--revision',required=True);args=parser.parse_args()
    assert re.fullmatch(r'r\d+',args.revision)
    target=ROOT/'product/.runtime/float-tone-20261022'/('readme-preview-'+args.revision)
    assert not target.exists();target.mkdir(parents=True)
    names=documents(target);checked=links(target,names)
    write(ROOT/REPORT,report());write(ROOT/CONTRACT,contract())
    inputs,_,_,installed=current()
    receipt=ROOT/REL/('readme-preview-'+args.revision+'.json');assert not receipt.exists()
    write(receipt,json.dumps({'status':'passed-local-document-links','documents':{name:sha(target/name) for name in names},
        'document_count':len(names),'links':len(checked),'installed_status':installed['status'],'frozen_input_count':len(inputs),
        'main_mutated':False,'full_suite_claimed_passed':False,'preview_root':str(target),'generator_sha256':sha(Path(__file__))},ensure_ascii=False,indent=2))
    print(json.dumps({'documents':len(names),'links':len(checked),'installed_status':installed['status'],'full_suite_claimed_passed':False}))


if __name__=='__main__':main()
