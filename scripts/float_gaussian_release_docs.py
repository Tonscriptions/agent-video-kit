"""Numbered Gaussian documents bound to actual source, media and install receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-tone-lab-20261022'
REL='docs/validation/evidence/float-gaussian-20261022-lab'
ASSETS='docs/assets/float-gaussian-20261022-r2'
REPORT='docs/validation/连续浮点高斯模糊与透明边缘实测_2026-10-22.md'
CONTRACT='docs/specs/连续浮点高斯模糊与透明边缘契约_v0.1_2026-10-22.md'
MARKER='V107-CONTINUOUS-FLOAT-GAUSSIAN-COVERAGE'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):return json.loads(path.read_bytes())


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs=frozen();assert len(inputs)==323
    native=read(ROOT/REL/'native-r3/verification.json');media=read(ROOT/REL/'media-r2/verification.json')
    assert native['status']=='passed' and native['methods']==420 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-Gaussian-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle=media['gaussian_oracle']
    assert oracle['scenarios']==['linked','horizontal','vertical','RGB_only','premult_headroom']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=2e-6
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/gaussian_media_oracle.py')
    assert sha(ROOT/REL/'media-r2/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path=ROOT/REL/'installed-r2/verification.json'
    installed=read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-193-resources-real-previews-and-620-methods'
        assert installed['isolated_methods']['methods']==620 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay=read(ROOT/REL/'media-installed-r2/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed=current();o=media['gaussian_oracle'];records=native['native_gaussian_records']
    maximum=max(r['maximum_absolute_error'] for r in records)
    title='V107 连续浮点高斯模糊与透明边缘' if published else 'V107 候选：连续浮点高斯模糊与透明边缘（未发布）'
    if installed['status'].startswith('passed-'):
        itext=f"**620项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；193份source/wheel/site资源、8个固定离线wheel、NumPy931文件及许可一致；安装版公开CLI编码音画、Float32和PNG16与源码版一致。"
    else:itext=f"**{installed['status']}，不计通过**；目标620项、193资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2715 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext=f"**2715项 /{full['suite_seconds']}秒 /0跳过**；323产品输入、8外部夹具和9依赖不变。"
    else:ftext='**尚未通过，不计通过**；目标2715项，仅在V106实际完整2667项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式`float32-native-v1`工程的正式render和preview共用连续高斯模糊，支持链接／独立XY半径、作者关键帧、GBRA平面选择及straight／premultiplied透明度。沿用旧gblur递归近似与端点边界模型，使用归一化binary64临时递推维持稳定，持久RGBA Float32；未承诺原生Float32逐位相同。

| 编号 | 功能性核验 | 实际内容与边界 | 证据 |
|---|---|---|---|
| FG107-01 | 共用内核 | 基础调色父320→323产品输入、10路径改变、48新增方法；3个旧拒绝样例从blur换成仍未支持的avgblur，原拒绝／清理／禁回退断言保留 | [接口契约]({CONTRACT}) |
| FG107-02 | XY半径 | blur/gaussian_blur/gblur；链接radius默认4、范围0..128；radius_x/y可静态或动画独立覆盖；steps为1..6 | [420项关联回归]({REL}/native-r3/verification.json) |
| FG107-03 | 实际原生对照 | {len(records)}组真实FFmpeg gbrapf32le；单双方向、奇偶尺寸、6种steps、16种GBRA位掩码、默认CPU／纯C及预乘密度；最大绝对误差{maximum:.12g}，执行前门槛8e-5 | [原始命令与Float32 I/O]({REL}/native-r3/verification.json) |
| FG107-04 | 独立数学 | 两个边界线性系统求解及矩阵幂参考，无产品递推调用；脉冲、端点、单像素／单行列、近零半径与最大128／6步常量DC | [实际断言]({REL}/native-r3/unittest.log) |
| FG107-05 | 透明边缘 | 默认straight逐选中平面模糊；premultiplied同时处理RGBA，先乘coverage、模糊再除正coverage，精确零密度RGB置0；隐藏红色渗边和1e-30正coverage实际核验 | [透明度契约]({CONTRACT}) |
| FG107-06 | 平面语义 | 位掩码保持FFmpeg的G=1/B=2/R=4/A=8；planes=7保留alpha位，planes=8同信号／preserve下保留RGB位并绕过往返信号转换 | [全部16种实际对照]({REL}/native-r3/unittest.log) |
| FG107-07 | 信号与强度 | 明确输入／输出RGB信号；在声明信号中模糊，返回线性工作RGB后按intensity混合，coverage独立线性混合；算子RGB clip与交付clip分开 | [契约]({CONTRACT}) |
| FG107-08 | 连续精度 | 140000个浮点坡度保持超过130000种输出，无整数表面／LUT／每帧子进程；高半径归一化避免未归一递推的中间放大 | [执行日志]({REL}/native-r3/unittest.log) |
| FG107-09 | 作者与安全 | 6种插值、Bezier时间根、大整数／有理tick、原作者预览窗口和嵌套倒放、有序调色／曝光／模糊；只读、完整预算、晚块非法值、取消及回调异常保护输入 | [执行日志]({REL}/native-r3/unittest.log) |
| FG107-10 | 真实公开CLI | {len(media['calls'])}调用/{len(media['checks'])}检查、2次正式render和3次preview；原创320×180、10fps、2秒20帧，5场景各4帧 | [实测记录]({REL}/media-r2/verification.json) |
| FG107-11 | 全像素与PCM | 作者帧3..16共2,419,200线性RGB，包含模糊后的coverage合成；最大绝对误差{o['maximum_linear_absolute_error']:.12g}，执行前门槛2e-6；96000／选区67200双声道PCM采样帧一致，PNG16≤1码 | [独立矩阵参考]({REL}/media-r2/executed-oracle.py.txt) |
| FG107-12 | 显式超白交付 | 最终clip前线性峰值{o['unclipped_linear_max']:.9g}、越界RGB分量{o['unclipped_outside_RGB_components']}；实际正式／预览交付均报告裁切；并非无界HDR母版验收 | [实测记录]({REL}/media-r2/verification.json) |
| FG107-13 | 原片与GIF | CC0原创图形／帧码／透明度／正弦音频；GIF14×100ms；已静看作者3/10/16共6幅，未做连续播放／听审 | [原片]({ASSETS}/original-range.mp4) · [输出]({ASSETS}/range.mp4) · [Float32]({ASSETS}/range.master.nut) · [目检]({REL}/static-review-r2.json) |
| FG107-14 | 离线安装 | {itext} | [安装收据]({REL}/installed-r2/verification.json) · [可编辑工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [CC0]({ASSETS}/LICENSE.txt) |
| FG107-15 | 完整回归 | {ftext} 源码420、安装620与完整套件独立登记，不相加作为功能完成率 | [本轮报告]({REPORT}) |
| FG107-16 | 许可与边界 | 原数值参考的BSD许可及作者声明随源代码／wheel／安装站点保留；平均／方框模糊、锐化、时间降噪继续接入；默认后端迁移、自然素材／HDR／实时质量与完整剪映目标未完成 | [接口与边界]({CONTRACT}) |
| FG107-17 | 打包故障与修复 | 首次source193／wheel192／site192，唯一缺失NOTICE；显式补入package-data，保留首次420项和安装失败，随后以新source／media／install证据重跑；数值算法与门槛未改变 | [诊断与修复]({REL}/failure-analysis-r1.json) |

![原片与真实CLI高斯预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_=current()
    return f'''# 连续浮点高斯模糊与透明边缘实测

源码关联回归实际 **{native['methods']}项 /{native['seconds']:.6f}秒 /0跳过**，其中48项新增。源码、原生数值对照、公开CLI媒体、离线安装及完整套件分别登记；全剪映目标继续开发。

首次相关源码420项通过，但离线安装资源一致性检查拒绝：source193、wheel192、site192，唯一缺少float_gaussian_NOTICE.txt。package-data采用显式清单，本轮遗漏新增NOTICE。修复仅将该文件加入product/pyproject.toml；数值代码、关键帧、预算和误差门槛不变。原source-r2、media-r1、安装／finisher／continuation-r1与旧ROOT脚本完整保留；新source-r3、media-r2和installed-r2重新绑定最终323输入，不能用旧源码通过结果替代新输入验收。

本轮为显式float32-native-v1接入blur/gaussian_blur/gblur。旧8位工程继续走既有后端；新内核与旧gblur采用相同递归近似和端点边界模型，默认半径4、默认处理RGBA。增加独立XY半径、steps、平面选择和明确预乘模式。原测试中3个“未支持操作拒绝”样例改用仍未接入的avgblur，保留拒绝码、资源清理及不回退旧后端的断言。

数值实现使用归一化凸组合前后扫，临时binary64、输出Float32，避免大半径及多次迭代未归一中间值的放大。它在理想实数运算下与原递归近似同一边界算子；归一化、操作顺序和临时精度不同，不能宣称原生Float32逐位等价，也不能宣称精确无限支撑高斯卷积。37组实际原生测试直接输入／输出gbrapf32le，保留命令、原始字节与SHA；独立参考使用边界线性系统与矩阵幂，覆盖脉冲、端点、近零半径、单像素及最大半径常量DC。8e-5原生门槛在执行前声明，没有调整。

straight对选中平面独立模糊，因此透明区域隐藏RGB可渗入可见边缘。premultiplied显式将RGB乘coverage、同算子模糊RGB密度和coverage，再除正密度；没有任意epsilon下限，精确零密度RGB置0。后者仅允许全部RGBA平面。1e-30正coverage、全透明、隐藏红色渗边及原生预乘密度均执行。GBRA位掩码保持G1/B2/R4/A8，没有错套RGBA位顺序。默认行为没有静默换成预乘。

公开CLI实片含链接、水平、垂直、仅RGB和预乘超白五场景。独立参考单独求解边界系统，不导入产品数学／信号／作者函数，包含变更后的coverage及背景合成，验证整个选区RGB、实际PNG16、PCM、独立进程缓存复用和作者数据不变。最终交付使用明确clip，超白计数在交付前另报。保留21项CC0媒体／工程／权利文件；静态六幅对照与GIF时钟检查不能替代连续播放和声音听审。

研究参考为官方[FFmpeg n8.1 vf_gblur.c](https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_gblur.c)与[vf_gblur_init.h](https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_gblur_init.h)。本机实际执行FFmpeg8.1；研究目录旧源码标记8.0.git，未冒称n8.1下载件。独立Python实现附原数值参考作者及BSD二条款许可，安装资源验收包含NOTICE。运行／验证均原生Windows、无虚拟化环境、无产品在线请求。

'''+relink(section(full,published),REPORT)


def contract():
    return '''# 连续浮点高斯模糊与透明边缘契约 v0.1

## 入口与作者参数

显式settings.pixel_pipeline.engine=float32-native-v1；正式render、preview range/frame共用有序内核。type为blur、gaussian_blur或gblur。parameters必须明确input_signal/output_signal={primaries,transfer}；工作信号须linear。旧默认后端和既有工程不在此轮自动迁移。

radius默认4、范围0..128，未覆盖时同时控制水平和垂直。radius_x/radius_y为独立覆盖；静态或关键帧出现任一轴即覆盖该轴。sigma别名radius，sigma_x别名radius_x，sigma_y/sigmaV/sigmav别名radius_y；同一通道重复静态别名或重复轨道拒绝。intensity默认1、0..1。steps默认1、整数1..6；planes默认15、整数0..15。steps/planes/alpha_mode为静态配置，不能动画。未知字段、布尔／字符串／非有限数值与越界拒绝。

planes沿用FFmpeg平面位：G=1、B=2、R=4、A=8。7为RGB，8为alpha，15为全部。alpha_mode为straight默认或premultiplied；预乘仅允许planes=15。output_gamut为preserve默认或clip。effect顶层只允许id/type/enabled/parameters/keyframes。轨道放effect.keyframes或parameters.keyframes其中一层；disabled由效果宿主跳过。

```json
{"type":"blur","parameters":{"input_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"output_signal":{"primaries":"bt709","transfer":"bt709-oetf"},"radius_x":8,"radius_y":2,"steps":3,"planes":15,"alpha_mode":"premultiplied","intensity":0.8}}
```

## 连续递推、边界与透明度

该算子保留旧gblur递归高斯近似；steps增大时重复前后递推，不是固定窗口平均，也不承诺精确无限支撑高斯核。令lambda=sigma²/(2steps)，q=2lambda/(1+2lambda+sqrt(1+4lambda))、a=1-q。每步前扫首值保持，内部为a×当前+q×前值；后扫末值保持，内部为a×当前+q×后值。先水平全部steps，再垂直全部steps。零半径跳过该轴。端点扩展为递归状态边界；不能替换成循环或镜像填充。实现采用代数有理化q，近零半径不以相减丢失有效小系数。

递推临时binary64，持久RGBA Float32；不存在整数表面、量化LUT或每帧外部进程。归一化凸扫与原未归一递推在理想实数下等价，临时精度、归一化和运算顺序不同，因此native_bit_equivalence=false。实际原生普通半径／steps对照和最大128／6步稳定性是不同验收项，未宣称所有极端条件逐位匹配原生Float32。

先从线性工作信号转换到明确input_signal。straight只对选中通道分别递推，默认RGBA均模糊，隐藏RGB可能影响透明边缘。premultiplied将RGB乘alpha，模糊四通道后以正的binary64模糊alpha相除；精确零密度的RGB置0，不使用epsilon阈值。极小正binary64密度转Float32可能下溢为零，此时保持该正密度对应的隐藏RGB；零密度计数指binary64精确零。模糊后的alpha只修正数值边界至0..1，RGB不隐式裁切。

模糊结果按output_signal解释，转换回线性工作RGB，再与原工作RGB按intensity线性混合；coverage也独立线性混合。未处理alpha时保留输入alpha位模式。alpha-only、input/output同信号且preserve时完全绕过RGB往返转换，保留RGB位模式。output_gamut=clip只裁算子RGB，另报分量数；与最终交付clip分开。intensity=0在完整验证后保持输入字节；零半径／planes=0且同信号、preserve也字节恒等。不同输入输出信号是显式解释变化，不能自动当作恒等。

## 时钟、资源与失败

radius/radius_x/radius_y/intensity支持linear/hold/ease_in/ease_out/ease_in_out/bezier六插值；Bezier须2或4控制值，4控制先解时间根，越界采样按通道边界限幅。每轨1..1024键、总16384键、规范JSON最多4MiB、最多4数值轨。键tick严格递增非负整数，采样可非负有限实数、大整数与Fraction；超过原作者时长拒绝。预览窗口、嵌套倒放保持原作者时钟，编译计划不引用可变作者数据。

输入为连续H×W×4 Float32，有限RGB与alpha0..1；边长1..16384、像素<=16777216。请求tile_pixels为1..262144，转换／检查块实际<=16384；递归空间依赖整张选中表面，不可按无重叠小块独立模糊。估算=6×表面字节+保留表字节+min(实际tile,像素)×2048+4×轨道JSON字节+1048576，上限768MiB。它包含整张递推工作区的保守准入，但不是整个进程峰值RSS保证。

完整预算与整张有限值／alpha验证先于输出；只读输入可用。取消回调返回True产生RENDER_CANCELLED，回调异常向上传递；检查、转换、递推按步和每32索引检查取消。晚块非法值、信号溢出、预算、取消或异常均不修改调用者输入。数学产生Float32溢出明确拒绝，不以clip掩盖非有限中间值。

## 验收与许可

48项新增／420项相关源码回归、真实Float32 gblur、独立边界矩阵、20调用31检查公开CLI、8-wheel193资源隔离安装及2715项完整套件分别登记。没有执行或仍运行不计通过；新安装目标620项。三个旧拒绝样例改为仍未支持的avgblur，禁回退／清理断言保留。原参考BSD作者声明与许可随float_gaussian_NOTICE.txt发布并逐字节安装核对。

平均模糊、方框模糊、锐化、时间降噪及默认后端迁移继续开发；未验收长片RSS、实时性能、自然素材感知质量、完整HDR／绝对nits、ICC／白点适配、连续播放／听审或完整剪映等价。
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
    target=ROOT/'product/.runtime/float-gaussian-20261022'/('readme-preview-'+args.revision)
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
