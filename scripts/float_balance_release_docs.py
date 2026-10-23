"""Numbered balance documents generated from actual frozen execution receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-levels-lab-20261022'
REL='docs/validation/evidence/float-balance-20261022-lab'
ASSETS='docs/assets/float-balance-20261022-r2'
REPORT='docs/validation/浮点三向色轮与色温实测_2026-10-22.md'
CONTRACT='docs/specs/浮点三向色轮与色温契约_v0.1_2026-10-22.md'
MARKER='V104-FLOAT-THREE-WAY-BALANCE-AND-CREATIVE-KELVIN'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')

def read(path):return json.loads(path.read_bytes())

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')

def current():
    inputs=frozen();assert len(inputs)==316
    native=read(ROOT/REL/'native-r2/verification.json');media=read(ROOT/REL/'media-r2/verification.json')
    assert native['status']=='passed' and native['methods']==284 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-levels-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle=media['balance_oracle']
    assert oracle['scenarios']==['balance','wheel','midrange','native_hsl','temperature']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=2e-6
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/balance_media_oracle.py')
    assert sha(ROOT/REL/'media-r2/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path=ROOT/REL/'installed-r1/verification.json'
    installed=read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-189-resources-real-previews-and-484-methods'
        assert installed['isolated_methods']['methods']==484 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay=read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed

def section(full=None,published=False):
    inputs,native,media,installed=current()
    title='V104 浮点三向色轮与创意色温' if published else 'V104 候选：浮点三向色轮与创意色温（未发布）'
    if installed['status'].startswith('passed-'):
        itext=f"**484项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；189份source/wheel/site资源、8个固定离线wheel、NumPy931文件及许可一致；安装版CLI音画、Float32和PNG16与源码版一致。"
    else:itext=f"**{installed['status']}，不计通过**；目标484项、189资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2579 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext=f"**2579项 /{full['suite_seconds']}秒 /0跳过**；316产品输入、8外部夹具和9依赖不变。"
    else:ftext='**尚未通过，不计通过**；目标2579项，仅在V103实际完整2537项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式`float32-native-v1`工程的正式render和预览共用连续浮点色彩平衡、九通道色轮、创意Kelvin映射及原作者关键帧。默认后端迁移、其余浮点算子、自然素材/离线AI质量及完整剪映功能继续开发。

| 编号 | 功能性核验 | 实际内容与边界 | 证据 |
|---|---|---|---|
| FB104-01 | 共用内核 | 父色阶314→316产品输入，5条路径改变；42新增方法；接入正式render、区间预览和PNG16的既有有序效果链 | [接口契约]({CONTRACT}) |
| FB104-02 | 三类调色 | shadow-only RGB平衡、9个shadows/midtones/highlights×RGB通道、1000..40000 K创意映射；Kelvin不是物理白平衡或色适应 | [源码及284项相关回归]({REL}/native-r2/verification.json) |
| FB104-03 | 连续浮点 | 无整数LUT或中间量化；131073个连续值检查；明确输入/输出信号，强度在线性工作域混合；默认保留负值/超白，alpha逐位保留 | [实际断言]({REL}/native-r2/unittest.log) |
| FB104-04 | 原生对照 | 本机FFmpeg colorbalance不接受GBRAPF32，关闭自动转换后实际拒绝；直接RGBA64和GBRAP16输入输出对照，预先门槛2码。最大实际码差见收据；不把整数对照称为原生浮点支持 | [真实命令/原始I/O]({REL}/native-r2/verification.json) |
| FB104-05 | 亮度与色域 | none/native_hsl/midrange；native_hsl只接受算子域0..1 RGB并保留原生边界规则；midrange支持负值/超白；clip是明确算子域策略 | [契约和边界]({CONTRACT}) |
| FB104-06 | 已知原生差异 | 已复现原生pl=1在限定调色下把纯白输出为黑；本实现明确保留纯黑/纯白，防止零分母产生非有限值。不将该差异宣称原生等价 | [保留样例与原始I/O]({REL}/native-r2/verification.json) |
| FB104-07 | 作者关键帧 | 6种插值、直接4控制Bezier时间根、超2^53有理tick、保持左极限、作者窗口和嵌套倒放；所有九通道及强度可动，Kelvin可动 | [实际断言]({REL}/native-r2/unittest.log) |
| FB104-08 | 事务与顺序 | 曝光/色阶/曲线/LUT/色轮按作者顺序；alpha映射按实际效果报告；只读输入、跨分块一致、晚块非法值/预算/取消保留输入 | [冻结及执行日志]({REL}/native-r2/verification.json) |
| FB104-09 | 真实公开CLI | {len(media['calls'])}调用/{len(media['checks'])}检查；2次正式render、3次preview；原创320×180、10fps、2秒各20帧，五段平衡/色轮/超白midrange/HSL/色温及动态曝光 | [真实命令和媒体]({REL}/media-r2/verification.json) |
| FB104-10 | 独立参考 | 作者帧3..16共2,419,200线性RGB值，最终交付clip后最大绝对误差{media['balance_oracle']['maximum_linear_absolute_error']:.12g}，执行前门槛2e-6；参考裁切前峰值{media['balance_oracle']['unclipped_linear_max']:.9g}，越界分量{media['balance_oracle']['unclipped_outside_RGB_components']}；96000/选区67200双声道PCM采样帧一致；PNG16≤1码 | [独立binary64/colorsys参考]({REL}/media-r2/executed-oracle.py.txt) |
| FB104-11 | 原片/GIF | CC0原创图形/移动标记/透明度及正弦音频；GIF左原片右实际CLI预览，14×100ms；静看3/10/16共6幅画面，不代表连续播放/听审 | [原片]({ASSETS}/original-range.mp4) · [实际输出]({ASSETS}/range.mp4) · [Float32]({ASSETS}/range.master.nut) · [查看记录]({REL}/static-review-r1.json) |
| FB104-12 | 离线安装 | {itext} | [实际安装收据]({REL}/installed-r1/verification.json) · [作者工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [CC0]({ASSETS}/LICENSE.txt) |
| FB104-13 | 完整回归 | {ftext} 源码284、安装484和完整套件分别记录，不相加为功能完成率 | [本轮报告]({REPORT}) |
| FB104-14 | 失败与未验收 | 首轮42项有1个二次ease_in_out测试预期错误；首轮媒体漏写最终范围策略，真实CLI以FLOAT_STREAM_RANGE拒绝。原日志及字节保留，仅修正测试参考/演示工程，未修改运行时曲线、范围保护或放宽容差。无新模型/自然/HDR/长片RSS/连续播放/听审或完整剪映等价验收 | [失败与修正]({REL}/failure-analysis-r1.json) |

![原片与真实CLI三向色轮及色温预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''

def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)

def report(full=None,published=False):
    _,native,_,_=current()
    return f'''# 浮点三向色轮与创意色温实测

实际源码关联回归 **{native['methods']}项 /{native['seconds']:.6f}秒 /0跳过**，其中42项为新增；与离线安装及完整回归分别执行，不累计为剪映完成度。

当前实现为独立NumPy Float32算子，不在运行时调用FFmpeg colorbalance，不使用整数中间层或云请求。参考[FFmpeg n8.1官方源码](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavfilter/vf_colorbalance.c)的参数及权重语义，使用本机实际整数原生输出和独立binary64方程验证；未复制C代码。首次源码HTTP连接重置保留在reference-r1；reference-r2通过官方Contents API成功取得n8.1正文、blob SHA与完整响应，原始源码SHA256为75e4e9ba06a29ce6d16218fcbb2134c2472ce11d2396e33e982954fb3484f34b。它仅作为研究证据，不参与产品编译或运行。

原生只接受整数RGB。对照从明确uint16 RGB/alpha出发，GBRAP16平面及RGBA64交错两条路径，比较最终16位码，预先容差2码；产品自身始终连续Float32。权重使用max(R,G,B)+min(R,G,B)，既不是平均灰度，也不是Rec.709亮度。原生HSL零分母可使纯白变黑，本实现对纯黑/纯白定义明确有限结果并保留原生差异。

首轮native-r1实际42项/113.2833461秒，1失败、0错误、0跳过。测试把二次ease_in_out在p=.25的值误写为smoothstep的.15625，正确值为2×.25²=.125。只修改测试参考，保留runtime、原失败、原输入输出与原代码；没有放宽容差。native-r2重新运行完整关联范围。两个控制值的Bezier仍为smoothstep，四控制Bezier按时间坐标求根，分别检查。

首轮media-r1执行4调用/3检查，正式edited CLI以FLOAT_STREAM_RANGE拒绝，因为超白示例没有明确最终交付策略。r2仅为演示工程加入既有range_policy=clip，不改变任何产品输入或范围保护。最终正式整数视频、PNG16和Float32预览参考按各自既有交付边缘明确裁切；内核自身仍保留headroom。独立参考保存裁切前峰值/越界分量，并检查实际正式渲染和预览均报告非零裁切数，不把最终裁切后的参考称为无界HDR母版。

已接受媒体执行的status沿用旧验证器的floating-levels标签；它不是本轮操作类型。实际balance_oracle五场景、执行代码、原始命令、316个源码输入与全像素参考共同约束本轮范围，不改写已执行收据。离线重播沿用同一真实执行脚本和标签。

五段真实公开CLI分别覆盖shadow平衡、九通道、曝光后超白midrange、bounded HSL和动态Kelvin；源像素、alpha、曝光、binary64权重和Python colorsys重建形成独立参考，未导入产品数学模块。原片、输出、GIF、Float32参考、PNG16、作者工程与权利账一并保存。静态联系表与连续播放/听审分别登记。

'''+relink(section(full,published),REPORT)

def contract():
    return '''# 浮点三向色轮与创意色温契约 v0.1

选择settings.pixel_pipeline.engine=float32-native-v1。公共render、preview frame/range共用原作者时间线和有序效果链；作者IR、交付范围及最后编码边缘继续使用既有契约。默认后端尚未迁移，完整剪映目标尚未完成。

## 作者参数与时间

color_balance/colorbalance仅有red/green/blue，原生别名rs/gs/bs；映射到shadows，默认0。color_wheel/three_way_color/three_way_wheel具有shadows/midtones/highlights×red/green/blue九通道，原生别名rs/gs/bs/rm/gm/bm/rh/gh/bh。所有调节值有限JSON数字且在[-1,1]。color_temperature/temperature/warmth只有kelvin[1000,40000]，默认6500；delta=clamp((kelvin-6500)/6500,-1,1)，shadows RGB=(-.30delta,-.05delta,.30delta)。这是沿用的创意调色映射，不是黑体、物理白平衡或色适应，13000以上饱和。

三类均要求parameters.input_signal/output_signal明确提供支持的D65 RGB primaries和relative transfer，禁止猜测bt709标签含义。工作信号必须linear。intensity范围[0,1]，默认1；keyframes支持全部本类通道及强度。每轨1..1024键，总16384，序列化4MiB；重复别名、两层keyframes、未知字段、非有限数、越界和非法时钟拒绝。关键帧tick为原作者非负严格递增整数；采样接受非负有限实数、有理数及不经浮点转换的大整数。linear/hold/ease_in/ease_out/ease_in_out/bezier；4控制Bezier先解x，2控制Bezier用固定时间。公共CLI每键仍须明确interpolation。关键帧不得超过原作者时长。

可放入clip.effects的作者声明示例（90000 ticks对应的秒数由工程timebase决定）：

```json
{
  "type": "color_wheel",
  "parameters": {
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "shadows_red": 0.15,
    "midtones_green": 0.08,
    "highlights_blue": -0.05,
    "intensity": 0.7,
    "output_gamut": "preserve",
    "preserve_lightness": "none"
  },
  "keyframes": [{"property": "midtones_green", "keyframes": [
    {"at_tick": 0, "value": 0, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 0.2, "interpolation": "linear"}
  ]}]
}
```

## 连续算子

输入线性工作RGB→明确input_signal→连续色轮→明确output_signal→线性工作RGB→intensity混合。设L=max(R,G,B)+min(R,G,B)，U(x)=clamp(x,0,1)：

- shadows权重=.7 U(4(.333-L)+.5)
- midtones权重=.7 U(4(L-.333)+.5) U(4(1-L-.333)+.5)
- highlights权重=.7 U(4(L+.333-1)+.5)
- 各RGB通道依次加本通道三个权重×调节值，使用Float32运算，不经整数LUT。

output_gamut默认preserve，保留有限负RGB和超白；clip明确把算子域映射限制0..1，不保证线性工作域的局部强度混合也被clip。alpha始终逐位保留，包括符号零与微小覆盖率。intensity=0在全输入有限/alpha检查之后逐位返回原输入。

preserve_lightness默认none，可选native_hsl、midrange；preserve_luma/pl布尔或lum等既有明确别名映射native_hsl，冲突拒绝。native_hsl要求转换后的算子输入RGB在0..1，先限制调整后RGB，再用原始minmax亮度重建HSL，保留原生max=1/min=0时零饱和规则；原始纯黑/纯白直接定义为纯黑/纯白，避免原生零分母。超范围输入明确拒绝，不静默裁切。midrange在调整后各通道加(max(input)+min(input)-max(adjusted)-min(adjusted))/2的共同偏移，保持minmax中点，支持负值/超白；若同时clip，最终再clip，因此亮度保留有边界限制。两种方法语义不同，Agent须明确选择。

## 资源、所有权与验证

连续H×W×4 Float32、单边≤16384、像素≤16777216；alpha 0..1，所有输入有限。tile请求1..262144，实际≤16384。工作区预算≤768MiB，估算3×surface bytes + retained LUT bytes + tile pixels×2048 + 4×tracks JSON bytes +524288；不是整个进程RSS，未包含所有解析对象、音频/缓存或多任务并发。所有算子对只读输入成立；晚块非法值、取消、预算和非有限结果保留调用者输入。true取消返回值及异常均向上传递。

实际native-r2、真实公开CLI、独立源像素参考、离线8-wheel安装和完整2579项是不同门槛；未执行/运行中不得登记通过。原始失败保留，不按通过数宣称完整剪映等价。未验收物理白平衡、绝对nits、ICC/PQ/HLG、自然素材/模型质量、长片RSS或连续播放/听审。
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
    target=ROOT/'product/.runtime/float-balance-20261022'/('readme-preview-'+args.revision)
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
