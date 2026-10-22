"""Generate numbered crop documents only from actual source/installed receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-mask-lab-20261022'
REL='docs/validation/evidence/float-crop-20261022-lab'
ASSETS='docs/assets/float-crop-20261022-r1'
REPORT='docs/validation/浮点作者裁剪与单次运镜投影实测_2026-10-22.md'
CONTRACT='docs/specs/浮点作者裁剪与运镜投影契约_v0.1_2026-10-22.md'
MARKER='V100-FLOAT-CROP-PROJECTION'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):return json.loads(path.read_bytes())


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs=frozen();assert len(inputs)==306
    native=read(ROOT/REL/'native-r2/verification.json')
    media=read(ROOT/REL/'media-r1/verification.json')
    assert native['status']=='passed' and native['methods']==123 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-crops-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(c['ok'] for c in media['checks'])
    oracle=media['crop_oracle']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=3e-7
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/crop_media_oracle.py')
    assert sha(ROOT/REL/'media-r1/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path=ROOT/REL/'installed-r1/verification.json'
    installed=read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-183-resources-real-previews-and-323-methods'
        assert installed['isolated_methods']['methods']==323 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay=read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):
            assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed=current()
    title='V100 浮点作者裁剪与单次运镜投影' if published else 'V100 候选：浮点作者裁剪与单次运镜投影（未发布）'
    if installed['status'].startswith('passed-'):
        itext=f"**323项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；8个固定离线wheel、183份source/wheel/site资源、NumPy931文件一致；安装版实际CLI视频/PCM/Float32/PNG16与源码版一致。"
    else:
        itext=f"**{installed['status']}，不计通过**；目标323项、183资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2418 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext=f"**2418项 /{full['suite_seconds']}秒 /0跳过**；306产品输入、8外部夹具和9依赖不变。"
    else:
        ftext='**尚未通过，不计通过**；目标2418项；仅在实际V99完整2390项通过且普通发布后才执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式 `float32-native-v1` 工程的正式render和预览共用作者裁剪投影。支持裁剪位置/宽高关键帧和fit/fill/stretch，并把裁剪、适配与位移/缩放/旋转合并为一次浮点采样。默认后端迁移与全剪映功能仍未完成。

| 编号 | 功能性核验 | 实际结果与范围 | 证据 |
|---|---|---|---|
| FC100-01 | 共同内核 | NumPy独立实现；源像素单位、归一化单位及width/w、height/h别名；正式render、区间和PNG16预览共用 | [契约]({CONTRACT}) |
| FC100-02 | 三种适配 | fit透明留边、fill保留原始裁剪纹理、stretch独立宽高缩放；半像素中心映射和半开窗口 | [28项新增方法]({REL}/native-r2/unittest.log) |
| FC100-03 | 原生坐标舍入 | 叶片段固定尺寸及仅移动窗口采用ties-to-even舍入；实际FFmpeg planar-float裁剪对照，并单独诊断10个边界值 | [原生边界诊断]({REL}/native-rounding-analysis-r1/receipt.json) |
| FC100-04 | 作者动画 | clip与crop本地轨、6种插值、局部同名覆盖、尺寸overshoot夹限；预览选区不重启原作者tick，嵌套反向时钟分层 | [123项相关回归]({REL}/native-r2/verification.json) |
| FC100-05 | 运镜/透明 | 单次crop-fit-TRS；fill旋转可露出静止视窗外纹理；双线性在预乘RGB/alpha内计算，极小alpha和扩展RGB保留 | [独立逐像素与原生I/O]({REL}/native-r2/verification.json) |
| FC100-06 | 数值/资源错误 | 65536级RGB、分块逐位一致、只读输入；晚块NaN/Inf/非法alpha、预算和中途取消均拒绝并保留输入 | [执行源码]({REL}/native-r2/verification.json) |
| FC100-07 | 真实公开CLI | {len(media['calls'])}脚本调用/{len(media['checks'])}检查，2次render+3次preview；原片/结果各320×180、10fps、20帧；96000双声道采样帧一致 | [命令与检查]({REL}/media-r1/verification.json) |
| FC100-08 | 独立像素参考 | 作者帧3..16的2,419,200个线性RGB值，独立正向齐次矩阵求解与预乘插值参考最大绝对误差{media['crop_oracle']['maximum_linear_absolute_error']:.12g}；选区67200双声道采样帧一致 | [实际执行参考]({REL}/media-r1/executed-oracle.py.txt) |
| FC100-09 | 原视频/GIF | 左原片、右实际CLI预览；GIF14×100ms；静态看过作者帧3/10/16的6个画面，未连续播放/试听或接受自然素材质量 | [原片MP4]({ASSETS}/original-range.mp4) · [结果MP4]({ASSETS}/range.mp4) · [Float32母参考]({ASSETS}/range.master.nut) · [PNG16]({ASSETS}/frame.png) · [查看记录]({REL}/static-review-r1.json) |
| FC100-10 | 权利与安装 | {itext} 原输入图形/alpha/正弦音频为本次CC0生成，标签用Pillow默认字体 | [原生输入]({ASSETS}/original.native.mkv) · [作者工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [声明]({ASSETS}/LICENSE.txt) |
| FC100-11 | 完整回归 | {ftext} | [本轮报告]({REPORT}) |
| FC100-12 | 失败与限制 | r1实际28项有1失败：误把原生仅移动窗口舍入当截断；已修内核并保留原始失败。双线性不等于area/Lanczos或旧整数滤镜逐位一致；自然素材、HDR、实时性、长片总RSS和全剪映均未验收 | [失败与修正]({REL}/failure-analysis-r1.json) |

![原片与真实CLI裁剪运镜预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_=current()
    return '''# 浮点作者裁剪与单次运镜投影实测

新增float_crop.py和28项测试，在浮点蒙版候选上连接FloatTimeline、能力发现及未支持操作夹具。父候选304产品输入，本候选306输入，5条产品路径改变。相关123项含28项新增与95项既有测试；离线安装323项及完整目标2418项分别记录，不累计为功能完成度。

首轮实际28项、32.223秒、1失败、0错误、0跳过。失败是新内核把仅移动的原生裁剪窗口坐标错误截断。随后独立执行10个真实FFmpeg边界值，确认0.5→0、1.5→2、2.5→2、3.5→4的ties-to-even规则；修正产品与预期，再完整运行相关123项，不通过放宽误差消除失败。原失败的执行源码、命令和原生I/O保留。

新的真实媒体来自本轮生成RGB16/alpha梯度/移动色块/帧标记和双声道正弦音频。前半固定尺寸窗口平移，后半宽高变化及运镜；独立参考通过正向齐次矩阵的线性方程求解获得源坐标，以另一种可分离预乘插值计算比较。FFmpeg仍负责编解码、最终RGB16交付与音频；投影不复制原生滤镜实现、不进行整数中间计算。

''' + f"相关123项实际用时{native['seconds']:.6f}秒，0跳过。\n\n" + relink(section(full,published),REPORT)


def contract():
    return '''# 浮点作者裁剪与运镜投影契约 v0.1

显式选择settings.pixel_pipeline.engine=float32-native-v1。输入仍为Agent Project的crop、transform和关键帧，作者工程、源窗口与时间基不重写。支持pixel/pixels、relative/normalized单位；x/y、width/w、height/h和fit/mode别名。fit/fill/stretch三种模式。未知或冲突字段和非法关键帧直接拒绝，不回落旧8位图。未声明crop的旧浮点分支继续沿用自身契约；显式空crop对象选择新投影。

clip.keyframes的crop.*与crop.keyframes均可控制位置/宽高；本地短名规范加crop前缀，本地同一完整名字覆盖clip名字，width优先于w、height优先于h。每层最多128轨，每轨1..1024递增非负整数时钟；关键值有限、非负，normalized不超过1，动画尺寸大于零。六种作者插值使用既有公共32段/8位小数Bezier查表。几何取原始作者tick，包括presentation_window偏移、嵌套速度/反向左极限；不会按预览起点重新计时。

叶片段无尺寸轨时，静态宽高和静态原点按Python ties-to-even舍入；仅位置轨也按真实FFmpeg验证的ties-to-even规则舍入。无动画原点时先把静态原点夹到源内，再缩小窗口避免越界；有位置轨时保留固定尺寸并逐帧夹原点。存在宽高轨时，四字段连续求值，先把宽高夹到min(2,源维度)..源维度，再把原点夹到0..源维度减窗口尺寸。嵌套容器始终保留连续子画布坐标与同样夹限，不把归一化坐标误用为父画布像素。单像素源维度是声明的退化边界，使用1像素窗口。

投影在一遍采样中合成crop、fit/fill/stretch及位移/缩放/旋转/锚点。像素中心为整数，像素格边缘位于中心±0.5；裁剪外覆盖为透明黑，窗口格边界半开；窗口内坐标夹到首末中心，双线性邻点在物理源边缘重复。fit透明留边可见下层；fill的源裁剪纹理在最终父画布采样前保留，旋转可露出静止父视窗外内容。anchor以裁剪窗口为参照，position以父画布为参照。新crop路径的mask在投影后的父画布处理；曝光仍在源线性工作RGB中先处理，opacity和blend在层合成时应用。未声明crop的既有mask空间未在本轮统一迁移，此差异需在后续组合验收中处理。

公共表面为连续HxWx4 straight Float32；RGB有限，alpha在0..1。采样以Float64预乘RGB和alpha累计、非零alpha除回straight，最终Float32一次舍入；零覆盖输出规范透明黑。nearest为库级显式选项，正式Agent渲染当前只接入其公开bilinear设置；area配置由正式浮点路径明确拒绝。本轮不承诺严重缩小抗锯齿、Lanczos等价或旧整数滤镜逐位相同。

单边最多16384、总像素最多16777216；分块1..262144、默认65536。768MiB是输入/输出/保守分块工作数组估算限，不是进程峰值RSS。取消、无效输入和预算拒绝均保留输入，不返回部分结果；源缓存、音频、嵌套及并发的预算继续独立适用。输入可只读，输出独立拥有。逆映射系数有限且绝对值不超过1e9，过小缩放等不生成非有限坐标。

本轮接受合成媒体的声明几何、作者时钟、像素及PCM一致性。默认后端迁移、其他浮点滤镜/字幕/转场、自然素材质量、实时预览、长片总RSS、HDR/ICC/PQ/HLG和完整剪映等价仍未验收。MP4/GIF是观看副本；Float32母参考与PNG16另行核验。静态抽帧不代表连续播放或听感。
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
    target=ROOT/'product/.runtime/float-crop-20261022'/('readme-preview-'+args.revision)
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
