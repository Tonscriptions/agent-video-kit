"""Generate numbered documents only from actual mask receipts and media."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-exposure-lab-20261022'
REL='docs/validation/evidence/float-mask-20261022-lab'
ASSETS='docs/assets/float-mask-20261022-r4'
REPORT='docs/validation/浮点蒙版曲线羽化与真实CLI实测_2026-10-22.md'
CONTRACT='docs/specs/浮点作者蒙版与羽化契约_v0.1_2026-10-22.md'
MARKER='V99-FLOAT-ALPHA-MASKS'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(p):return json.loads(p.read_bytes())


def write(p,text):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs=frozen();assert len(inputs)==304
    native=read(ROOT/REL/'native-r3/verification.json')
    media=read(ROOT/REL/'media-r4/verification.json')
    assert native['status']=='passed' and native['methods']==95 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-masks-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(c['ok'] for c in media['checks'])
    assert media['mask_oracle']['RGB_values']==2419200 and media['mask_oracle']['maximum_linear_absolute_error']==0
    assert media['mask_oracle']['oracle_sha256']==sha(ROOT/'scripts/mask_media_oracle.py')
    for n,row in media['assets'].items():assert sha(ROOT/n)==row['sha256']
    path=ROOT/REL/'installed-r2/verification.json'
    installed=read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-182-resources-real-previews-and-295-methods'
        assert installed['isolated_methods']['methods']==295 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay=read(ROOT/REL/'media-installed-r2/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):
            assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed=current()
    title='V99 浮点蒙版、曲线路径与羽化' if published else 'V99 候选：浮点蒙版、曲线路径与羽化（未发布）'
    if installed['status'].startswith('passed-'):
        itext=f"**295项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；8个固定离线wheel、182份source/wheel/site资源及NumPy931文件一致；安装版实际CLI音画/Float32/PNG16与源码版相同。"
    else:
        itext=f"**{installed['status']}，不计通过**；目标为295项和182资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2390 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext=f"**2390项 /{full['suite_seconds']}秒 /0跳过**，304产品输入、8外部夹具和9依赖不变。"
    else:
        ftext='**尚未通过，不计通过**；目标2390项，等待实际V98完整2369项通过且发布后才执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式 `float32-native-v1` 工程的正式render与预览现在共用蒙版核。支持矩形、圆、椭圆、多边形、采样三次曲线路径，以及蒙版本地关键帧、反选、静态和动画羽化；默认后端迁移及全剪映功能仍未完成。

| 编号 | 功能性核验 | 实际结果与范围 | 证据 |
|---|---|---|---|
| FM99-01 | 共同宿主 | 解码/曝光后、仿射前处理alpha；嵌套组在子序列合成后处理；正式render、区间和PNG16预览共用 | [契约]({CONTRACT}) |
| FM99-02 | 多边形/曲线 | 凹多边形、自相交偶奇填充、逐点动画、线段与三次Bezier控制点动画；最多32候选点/8段，不静默截断 | [21个新增方法]({REL}/native-r3/unittest.log) |
| FM99-03 | 作者关键帧 | clip与mask本地轨道、别名与局部覆盖；六种插值、原作者tick、裁切窗口与嵌套加速均实际核验 | [95项相关回归]({REL}/native-r3/verification.json) |
| FM99-04 | 羽化与透明 | 静态为源alpha乘蒙版后进行alpha-only对称边界盒模糊H/H/V/V；动画为形内距离线性覆盖；反选在乘alpha前 | [独立逐项平均/线段距离与原生alpha16对照]({REL}/native-r3/unittest.log) |
| FM99-05 | 浮点精度与错误 | 65536个alpha值、微小alpha、隐藏RGB/负零/扩展RGB、分块一致；晚块NaN/Inf/越界alpha、预算与中途取消拒绝且输入不变 | [执行源码与原生I/O]({REL}/native-r3/verification.json) |
| FM99-06 | 真实公开CLI | {len(media['calls'])}个脚本级调用/{len(media['checks'])}项检查；2次render和3次preview；原片/结果各320×180、10fps、20帧；各96000双声道采样帧相同 | [原始命令/检查]({REL}/media-r4/verification.json) |
| FM99-07 | 独立像素基准 | 作者帧3..16共14帧、2,419,200个实际线性RGB值与独立多边形/曲线/羽化/源alpha/sRGB背景合成计算一致，最大误差0；选区67200双声道采样帧一致 | [独立基准]({REL}/media-r4/executed-mask-media-oracle.py.txt) |
| FM99-08 | 原视频/GIF | 下图左原片、右真实CLI预览；14×100ms。静态看过作者帧3/10/16的6个画面；未连续播放、试听或接受自然素材质量 | [原片MP4]({ASSETS}/original-range.mp4) · [结果MP4]({ASSETS}/range.mp4) · [浮点母参考]({ASSETS}/range.master.nut) · [PNG16]({ASSETS}/frame.png) · [查看记录]({REL}/static-review-r1.json) |
| FM99-09 | 素材/权利 | 本次生成RGB16图形、alpha梯度与正弦波，原输入CC0；工程和权利账保留。标签使用Pillow附带默认字体，不分发字体文件 | [原生输入]({ASSETS}/original.native.mkv) · [作者工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [声明]({ASSETS}/LICENSE.txt) |
| FM99-10 | 实际离线安装 | {itext} | [本轮报告]({REPORT}) |
| FM99-11 | 完整回归 | {ftext} | [完整回归状态与范围]({REPORT}) |
| FM99-12 | 原失败/限制 | 原r1关键帧边界/透明输出夹具、r2理想Y亮度断言、媒体r1缺插值/r2背景信号误设均保留；未据合成图案接受全剪映、HDR、实时性或长片总RSS | [失败与修正]({REL}/failure-analysis-r1.json) |

![原片与真实CLI蒙版曲线羽化预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda m:m[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_=current()
    return '''# 浮点蒙版曲线羽化与真实CLI实测

新增独立NumPy蒙版核和21项蒙版测试，在已有曝光候选上连接FloatTimeline、能力发现及旧未支持夹具。父候选302输入，本候选304输入，5个产品路径改变。相关95项包含21项新增和74项既有回归，不与安装295项、完整目标2390项累计。父发布、全套回归和本轮发布各有独立门槛。

蒙版采用作者工程现有定义，不复制FFmpeg的GPL实现。盒模糊边界和整数输出交叉对照参照[FFmpeg官方boxblur源码说明](https://ffmpeg.org/doxygen/trunk/vf__boxblur_8c_source.html)；产品独立实现归一化浮点平均，原生整数定点倒数/舍入仅用于声明误差内的对照，不能当作逐位浮点基准。

原失败没有改写：首轮21项有1失败/1错误；r2实际95项有1失败（理想Y标量公式在空间边缘与实际10位编码差2.12397码值）。后续改为独立RGB16交付字节SHA和独立原生编码后的全部YUV字节对照，不放宽该断言。公开CLI媒体r1被合法schema门槛拒绝，因为夹具未写必需的interpolation；r2的独立基准误把sRGB背景当作BT709相机曲线，修正基准信号后r3通过。最终r4重新在当前完整源码/测试输入执行，未将旧源码媒体收据复标为当前通过。

''' + f"本次相关套件实际95项、{native['seconds']:.6f}秒、0跳过。\n\n" + relink(section(full,published),REPORT)


def contract():
    return '''# 浮点作者蒙版与羽化契约 v0.1

显式选择`settings.pixel_pipeline.engine=float32-native-v1`。不改变作者mask字段、源路径或源时间。支持rectangle、circle、ellipse、polygon、path及关闭标记；未接类型明确拒绝，不能回落旧8位图。mask位于源工作信号/曝光之后、局部仿射之前；嵌套mask位于子序列合成之后。只操作straight alpha，RGB位型在本操作内保持；后续仿射/合成会按自身透明像素契约规范隐藏RGB。

几何为整数像素中心，归一化坐标分别乘原栅格W/H。矩形边界含等号；圆半径乘min(W,H)；椭圆静态默认半径至少.001、运行归一化半径至少1e-6。多边形使用偶奇填充和明确半开交点规则。路径可为3..32点，或1..8个line/cubic/bezier/cubic_bezier段；三次段每段2..16等参数采样，全部候选点不超过32。控制点动画先求值再计算Bernstein多项式；闭合边连接末点与首点。它是采样折线，不宣称解析曲线、亚像素面积抗锯齿或任意剪映形状。

clip.keyframes与mask.keyframes均可控制几何/feather。局部短属性规范为mask前缀；局部同名轨道覆盖clip同名轨道，多个别名按声明顺序取首个。每层最多128轨，每轨1..1024关键点，时钟递增非负整数。支持linear/hold/ease_in/ease_out/ease_in_out/bezier；Bezier继续用公共作者时钟的32段八位小数查表，非任意精度解析曲线。几何关键值0..1，feather0..0.5，插值后夹到声明范围。裁切窗口与祖先反向左极限继承原作者动画tick，不能从预览局部零点重启。

两种已有羽化语义不能混淆。无feather动画轨时，先做硬几何及反选，再乘素材已有alpha；静态半径floor(min(W,H)*feather)，在alpha上执行归一化盒平均H/H/V/V，边界对称延拓且重复边缘像素。运算用Float64累计，公共alpha最终Float32一次舍入，不经过整数码值。radius0不模糊RGB或alpha。存在feather轨时，即使轨值恒定，也采用形内边缘距离除以min(W,H)*feather的线性覆盖；值0采用硬几何。圆距离为半径减欧氏距离，矩形为四边最小距离，多边形为内部点到最近有限线段距离，椭圆为归一化径向差乘最小半径的近似距离。动画覆盖反选后乘源alpha，不再盒模糊。

输入连续H×W×4 Float32，RGB有限、alpha0..1。最多16,777,216像素、单边16,384；块1..262,144，默认65,536。工作区估算限768MiB，包含输入/输出、alpha和保守块/行前缀缓冲；此估算不等于进程峰值RSS，其他源缓存/投影预算继续适用。取消和错误不修改输入、不交付部分表面。未知字段、冲突别名、非法点/轨道/样本数明确拒绝，不跳过坏段或静默截断。

本轮仅接受合成媒体中的声明几何与数值契约。未迁移默认后端，裁剪/全部滤镜/转场/字幕组合仍需接入；自然素材观感、剪映相同效果、实时预览、长片并发总RSS、ICC/PQ/HLG/HDR和完整产品等价仍未验收。MP4/GIF为观看副本，原生Float32和PNG16分别核验；静态抽帧不代表连续播放或听感。
'''


def documents(target,full=None,published=False):
    names=[*LATEST_DOCS,REPORT,CONTRACT];block=section(full,published)
    for name in LATEST_DOCS:
        text=(MAIN/name).read_text('utf8')
        text=re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?','\n',text,flags=re.S)
        pos=text.find('\n')+1
        write(target/name,text[:pos]+'\n'+relink(block,name)+'\n'+text[pos:])
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
    target=ROOT/'product/.runtime/float-mask-20261022'/('readme-preview-'+args.revision)
    assert not target.exists();target.mkdir(parents=True)
    names=documents(target);checked=links(target,names)
    write(ROOT/REPORT,report());write(ROOT/CONTRACT,contract())
    inputs,_,_,installed=current()
    receipt=ROOT/REL/('readme-preview-'+args.revision+'.json');assert not receipt.exists()
    write(receipt,json.dumps({'status':'passed-local-document-links','documents':{n:sha(target/n) for n in names},
        'document_count':len(names),'links':len(checked),'installed_status':installed['status'],
        'frozen_input_count':len(inputs),'main_mutated':False,'full_suite_claimed_passed':False,
        'preview_root':str(target),'generator_sha256':sha(Path(__file__))},ensure_ascii=False,indent=2))
    print(json.dumps({'documents':len(names),'links':len(checked),'installed_status':installed['status'],'full_suite_claimed_passed':False}))


if __name__=='__main__':main()
