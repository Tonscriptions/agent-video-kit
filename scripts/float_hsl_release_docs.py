"""Numbered HSL documents generated from actual frozen execution receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-balance-lab-20261022'
REL='docs/validation/evidence/float-hsl-20261022-lab'
ASSETS='docs/assets/float-hsl-20261022-r2'
REPORT='docs/validation/连续浮点八色HSL与显式色域策略实测_2026-10-22.md'
CONTRACT='docs/specs/连续浮点八色HSL与显式色域策略契约_v0.1_2026-10-22.md'
MARKER='V105-CONTINUOUS-FLOAT-EIGHT-BAND-HSL'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')

def read(path):return json.loads(path.read_bytes())

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')

def current():
    inputs=frozen();assert len(inputs)==318
    native=read(ROOT/REL/'native-r2/verification.json');media=read(ROOT/REL/'media-r2/verification.json')
    assert native['status']=='passed' and native['methods']==328 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-selective-HSL-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle=media['hsl_oracle']
    assert oracle['scenarios']==['warm','cool','mixed','input_clip','residual']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=2e-6
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/hsl_media_oracle.py')
    assert sha(ROOT/REL/'media-r2/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path=ROOT/REL/'installed-r1/verification.json'
    installed=read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-190-resources-real-previews-and-528-methods'
        assert installed['isolated_methods']['methods']==528 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay=read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed

def section(full=None,published=False):
    inputs,native,media,installed=current();o=media['hsl_oracle']
    title='V105 连续浮点八色HSL与显式色域策略' if published else 'V105 候选：连续浮点八色HSL与显式色域策略（未发布）'
    if installed['status'].startswith('passed-'):
        itext=f"**528项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；190份source/wheel/site资源、8个固定离线wheel、NumPy931文件及许可一致；安装版CLI音画、Float32和PNG16与源码版一致。"
    else:itext=f"**{installed['status']}，不计通过**；目标528项、190资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2623 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext=f"**2623项 /{full['suite_seconds']}秒 /0跳过**；318产品输入、8外部夹具和9依赖不变。"
    else:ftext='**尚未通过，不计通过**；目标2623项，仅在V104实际完整2579项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式`float32-native-v1`工程的正式render和预览共用连续浮点八色HSL、24通道及强度关键帧、原始色相分带和明确输入/输出信号。既有8位HSL后端保持原接口；默认后端迁移、其余浮点算子、自然素材/离线AI质量与完整剪映目标继续开发。

| 编号 | 功能性核验 | 实际内容与边界 | 证据 |
|---|---|---|---|
| FH105-01 | 共用内核 | 父色轮316→318产品输入，5条路径改变；44新增方法；正式render、区间预览和PNG16使用既有有序效果链 | [接口契约]({CONTRACT}) |
| FH105-02 | 八色24通道 | red/orange/yellow/green/cyan/blue/purple/magenta×hue/saturation/lightness；原始色相同时决定全部权重，保留橙/紫不等宽扇区与红色环绕 | [源码及328项相关回归]({REL}/native-r2/verification.json) |
| FH105-03 | 连续精度 | 不经过整数表面或LUT；131073个连续值检查，近黑色不用epsilon地板抹除色度；HSL使用binary64临时量，持久表面Float32；alpha逐位保留 | [实际断言]({REL}/native-r2/unittest.log) |
| FH105-04 | 真实后端对照 | 24通道分别对照真实8位FFmpeg geq；混合八色对照随包frei0r插件；预先门槛1码，直接RGBA8输入/输出，未宣称旧后端支持连续浮点 | [真实命令/原始I/O]({REL}/native-r2/verification.json) |
| FH105-05 | 显式色域 | 默认reject越界；clip明确裁切算子输入；preserve_residual把原始RGB减去bounded RGB的残差加回HSL结果。输出clip另设，均报告实际分量计数 | [契约与边界]({CONTRACT}) |
| FH105-06 | 信号与强度 | 明确input/output primaries和transfer，不猜测视频标签；强度在线性工作RGB中混合；灰阶和未选色像素在相同信号下保留原RGB | [独立colorsys参考]({REL}/native-r2/unittest.log) |
| FH105-07 | 作者关键帧 | 25个数值通道可动；6种插值、4控制Bezier时间根、大整数/有理tick、保持左极限、作者窗口和嵌套倒放 | [实际断言]({REL}/native-r2/unittest.log) |
| FH105-08 | 顺序与事务 | 曝光/LUT/曲线/色阶/色轮/HSL按作者顺序；只读输入、跨分块一致、晚块非法值、预算/取消/转换溢出保留输入 | [冻结与执行日志]({REL}/native-r2/verification.json) |
| FH105-09 | 真实公开CLI | {len(media['calls'])}调用/{len(media['checks'])}检查；2次正式render、3次preview；原创320×180、10fps、2秒各20帧；暖色/冷色/八色混合/输入clip/残差五场景 | [真实命令与媒体]({REL}/media-r2/verification.json) |
| FH105-10 | 全像素独立参考 | 作者帧3..16共2,419,200线性RGB，最终交付clip后最大绝对误差{o['maximum_linear_absolute_error']:.12g}，执行前门槛2e-6；裁切前峰值{o['unclipped_linear_max']:.9g}，越界分量{o['unclipped_outside_RGB_components']}；96000/选区67200双声道PCM采样帧一致，PNG16≤1码 | [独立邻点权重/colorsys]({REL}/media-r2/executed-oracle.py.txt) |
| FH105-11 | 原片/GIF | CC0原创图形、移动帧标记、透明度和正弦音频；GIF左原片右实际CLI预览，14×100ms；静看3/10/16共6幅，未做连续播放/听审 | [原片]({ASSETS}/original-range.mp4) · [实际输出]({ASSETS}/range.mp4) · [Float32]({ASSETS}/range.master.nut) · [查看记录]({REL}/static-review-r1.json) |
| FH105-12 | 离线安装 | {itext} | [安装收据]({REL}/installed-r1/verification.json) · [工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [CC0]({ASSETS}/LICENSE.txt) |
| FH105-13 | 完整回归 | {ftext} 源码328、安装528与完整套件分别记录，不相加作为功能完成率 | [本轮报告]({REPORT}) |
| FH105-14 | 保留失败与边界 | 首轮44项有1个测试环境错误；首次演示曝光终点3.5超出既有上限，CLI拒绝。仅修正测试子进程环境和演示参数；未改产品算法/保护或放宽容差。residual是明确创意延伸，不代表HDR感知模型、自然素材质量、长片RSS或完整剪映等价 | [原失败与修正]({REL}/failure-analysis-r1.json) |

![原片与真实CLI八色HSL预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''

def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)

def report(full=None,published=False):
    _,native,_,_=current()
    return f'''# 连续浮点八色HSL与显式色域策略实测

实际源码关联回归 **{native['methods']}项 /{native['seconds']:.6f}秒 /0跳过**，其中44项新增；离线安装和完整回归分别执行，不累计为剪映功能完成度。

既有selective_hsl/hsl_bands/eight_band_hsl在8位geq或随包frei0r中执行。本轮在明确float32-native-v1工程中实现连续Float32路径，不加载8位插件处理浮点表面，不生成整数LUT，不新增在线请求或闭源服务。HSL分析和重建使用binary64临时量，持久表面为Float32。标准YUV hue效果没有被悄悄替换为RGB HSL。

24个分色通道逐项与真实geq比较，混合八色与真实随包frei0r插件比较；输入明确为RGBA8，比较最终8位码，执行前门槛1码。另用标准库colorsys和原始色相左右邻点插值作独立连续参考，覆盖不等宽扇区、红色环绕、灰阶、极暗色度、输入/输出传递和线性强度。整数后端对照不代表整数后端支持高位深或任意自然画质。

首轮native-r1实际44项/83.0629272秒，0失败/1错误/0跳过。测试把compile_native放在patch.dict中，却在退出环境作用域后启动FFmpeg，导致FREI0R_PATH先被还原、插件无法定位。首次追加复现误把目录标为odd-size，该目录原样保留；实际stderr与corrected-native-test-environment收据明确证明原因是环境作用域，原43×17尺寸在修正子进程环境后成功，最大1码。仅修改测试文件，未改运行时算法和误差门槛；native-r2重跑全部328项关联范围。验证器补存CalledProcessError的原始I/O以便未来失败定位，不改写旧收据。

首轮media-r1的原创正式render成功，edited render在验证时拒绝：演示残差场景曝光终点3.5超出既有上限3。r2仅把该演示/独立参考的曝光改为2.7..3，不改任何产品输入、曝光保护或容差；实际仍产生超白并到达最终交付clip边缘。两个失败及其执行源、日志和命令均保留。

五段公开CLI覆盖暖色、冷色、全部八色、曝光后输入clip和曝光后残差保留。独立参考自行解四控制Bezier时间根、按原始色相左右邻点给权重、用colorsys重建HSL、解析源alpha并按线性背景合成；未导入产品数学模块。最终整数视频、PNG16与当前Float32预览参考明确使用交付range_policy=clip，不把裁切后参考称为无界HDR母版。静态联系表查看与连续播放/声音听审分别登记。

'''+relink(section(full,published),REPORT)

def contract():
    return '''# 连续浮点八色HSL与显式色域策略契约 v0.1

选择settings.pixel_pipeline.engine=float32-native-v1，公共render、preview range/frame共用原作者时间线和有序效果链。原有8位geq/frei0r工程保持原语义。默认后端迁移、其他浮点算子、自然素材和离线AI质量以及完整剪映功能仍需继续实现与验收。

## 参数与作者时间

类型selective_hsl/hsl_bands/eight_band_hsl。八色中心依次red=0、orange=30、yellow=60、green=120、cyan=180、blue=240、purple=270、magenta=300度。每色具有_hue[-180,180]、_saturation[-1,1]、_lightness[-1,1]，默认0；intensity[0,1]默认1。全部25通道可用同名keyframes编辑。参数均为有限JSON数值，布尔、字符串、非有限、越界、未知字段拒绝。

parameters.input_signal和output_signal须明确primaries/transfer，使用已有D65相对RGB信号集合；线性工作表面先转换到input_signal，HSL结果按output_signal解释再转回工作表面。颜色标签不能隐式选择transfer；无物理白点匹配、绝对nits、ICC、PQ/HLG或HDR感知承诺。

每轨1..1024键，总16384键、序列化4MiB；作者tick严格递增非负整数，采样支持非负有限实数、大整数和Fraction；关键帧不得超过原作者时长。支持linear/hold/ease_in/ease_out/ease_in_out/bezier；二控制Bezier直接取值，四控制Bezier先解时间根。父/子/倒放与presentation_window继续使用既有原作者时钟，不重置到预览起点。轨道可位于effect.keyframes或parameters.keyframes之一。

```json
{
  "type": "selective_hsl",
  "parameters": {
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "red_hue": 20, "orange_saturation": -0.2, "blue_lightness": 0.1,
    "intensity": 0.7, "input_gamut": "reject", "output_gamut": "preserve"
  },
  "keyframes": [{"property": "red_hue", "keyframes": [
    {"at_tick": 0, "value": -20, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 20, "interpolation": "linear"}
  ]}]
}
```

## HSL与分色

bounded RGB的max/min决定L=(max+min)/2，delta=max-min；非灰阶S=delta/(max+min)或delta/(2-max-min)，按L<=.5分支，灰阶S=0。H为标准RGB HSL色相。每色在相邻中心之间线性下降至0，左右宽度不同；原始色相同时决定全部权重，灰阶全部权重0，不对前一色调节后的色相重新选带。三个加权delta分别汇总。H按360度环绕；S和L在delta>=0时v+(1-v)delta，否则v(1+delta)，最后限制0..1并重建RGB。极暗色度不用1e-12地板；chroma=2min(L,1-L)S避免1-|2L-1|的消去。

## 显式色域与混合

input_gamut默认reject：算子输入信号的RGB超出0..1时拒绝，不加容差或偷偷量化。clip：先明确裁切到bounded RGB再调HSL。preserve_residual：B=clip(RGB,0,1)，在HSL(B)结果上加回RGB-B；这是可复现的创意扩展，不能称为HDR感知模型或专业色域映射。output_gamut默认preserve，明确clip时在算子输出域裁切。实际越界、裁切和残差分量计数写入效果收据。

最终强度混合在线性工作RGB执行source*(1-intensity)+graded*intensity。intensity=0在验证源表面后逐字节恒等，明确跳过HSL色域策略。相同输入/输出信号下未选色像素和灰阶保留原始RGB；显式输入或输出clip确实改变的像素仍按策略处理。alpha不参与HSL或强度运算，源alpha位级保留，包括signed-zero与有效次正规数。渲染合成和最终编码边缘沿用各自已有策略。

## 资源、取消与边界

连续H×W×4 Float32、边长1..16384、总像素<=16777216。请求tile_pixels为1..262144，实际每块<=16384。工作区估算=3×表面字节+保留LUT字节+每块像素×2048+4×轨道JSON字节+524288，不超过768MiB；这不是整个进程峰值RSS保证。先检查预算和整张表面的有限RGB/alpha范围，再分块处理；输入保持只读，晚块错误、取消及转换溢出不修改调用者数据或发布半成品。取消回调返回True或抛异常均会传播。

原始8位对照、新连续参考、公开CLI媒体、8-wheel隔离安装和完整2623项是独立门槛。未执行/运行中不记通过，不累计测试数作为剪映完成率。未验收自然画质、HDR、全套AI效果、长片RSS、连续播放/听审或完整剪映等价。
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
    target=ROOT/'product/.runtime/float-hsl-20261022'/('readme-preview-'+args.revision)
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
