"""Numbered RGB-curve documentation from actual frozen-source and media receipts."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen,sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
PARENT = ROOT.parent/'float-lut-lab-20261022'
REL = 'docs/validation/evidence/float-curves-20261022-lab'
ASSETS = 'docs/assets/float-curves-20261022-r2'
REPORT = 'docs/validation/连续浮点RGB曲线与作者控制点实测_2026-10-22.md'
CONTRACT = 'docs/specs/连续浮点RGB曲线与后置总曲线契约_v0.1_2026-10-22.md'
MARKER = 'V102-CONTINUOUS-FLOAT-RGB-CURVES'
LATEST_DOCS = ('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):return json.loads(path.read_bytes())


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def current():
    inputs = frozen();assert len(inputs)==311
    native = read(ROOT/REL/'native-r3/verification.json')
    media = read(ROOT/REL/'media-r2/verification.json')
    assert native['status']=='passed' and native['methods']==200 and native['skipped']==0
    assert native['frozen_before']==native['frozen_after']==inputs
    assert media['status']=='passed-public-CLI-floating-curves-and-native-float-previews'
    assert media['frozen_before']==media['frozen_after']==inputs
    assert media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in media['checks'])
    oracle = media['curves_oracle']
    assert oracle['RGB_values']==2419200 and oracle['maximum_linear_absolute_error']<=3e-7
    assert oracle['oracle_sha256']==sha(ROOT/'scripts/curves_media_oracle.py')
    assert sha(ROOT/REL/'media-r2/executed-oracle.py.txt')==oracle['oracle_sha256']
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    path = ROOT/REL/'installed-r1/verification.json'
    installed = read(path) if path.exists() else {'status':'not-executed'}
    if installed['status'].startswith('passed-'):
        assert installed['status']=='passed-fresh-eight-wheel-186-resources-real-previews-and-400-methods'
        assert installed['isolated_methods']['methods']==400 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==inputs
        replay = read(ROOT/REL/'media-installed-r1/verification.json')
        assert replay['status']==media['status'] and replay['isolated']
        for key in ('Float32_sha256','PCM_sha256','PNG16_sha256'):
            assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    return inputs,native,media,installed


def section(full=None,published=False):
    inputs,native,media,installed = current()
    title = 'V102 连续浮点RGB曲线与作者控制点' if published else 'V102 候选：连续浮点RGB曲线与作者控制点（未发布）'
    if installed['status'].startswith('passed-'):
        itext = f"**400项 /{installed['isolated_methods']['suite_seconds']}秒 /0跳过**；186份source/wheel/site资源、8个固定离线wheel、NumPy931文件及原许可一致；安装版实际CLI音画、Float32及PNG16与源码版一致。"
    else:itext = f"**{installed['status']}，不计通过**；目标400项、186资源。"
    if full:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2495 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==inputs
        ftext = f"**2495项 /{full['suite_seconds']}秒 /0跳过**；311产品输入、8外部夹具和9依赖不变。"
    else:ftext = '**尚未通过，不计通过**；实际发现2495项，仅在V101完整2455项通过并普通发布后执行。'
    return f'''<!-- {MARKER} -->
### {title}

显式 `float32-native-v1` 工程的正式render和预览共用连续RGB曲线。空间natural/PCHIP、独立通道、后置总曲线与作者控制点关键帧直接浮点求值，无整数曲线表。默认后端迁移、其余浮点算子及完整剪映功能仍未完成。

| 编号 | 功能性核验 | 实际内容与范围 | 证据 |
|---|---|---|---|
| FC102-01 | 共同内核 | 新增float_curves及40项测试，父LUT候选309→311输入、5条产品路径改变；正式render、区间预览与PNG16共用有序效果链 | [接口契约]({CONTRACT}) |
| FC102-02 | 连续曲线 | natural三对角求解、PCHIP保形插值；独立稠密矩阵与Hermite基函数对照。1..256固定点、常量端点延伸、曲线输出夹0..1；不是8/16位网格 | [实际200项相关回归]({REL}/native-r3/verification.json) |
| FC102-03 | RGB与总曲线 | all仅给未独立声明通道提供默认；旧master别名指all；post_master为独立后置总曲线；动态通道从静态all分叉后独立 | [控制点与顺序断言]({REL}/native-r3/unittest.log) |
| FC102-04 | 作者时钟 | all/R/G/B/post_master的点x/y和强度，六种时间插值；Bezier直接求值，四控制值用48次求根；保留超2^53有理tick偏移、作者窗口和嵌套倒放左极限 | [实际执行源码]({REL}/native-r3/verification.json) |
| FC102-05 | 浮点与信号 | 65536级灰阶与相邻Float32保留；明确输入/输出信号，转回线性工作RGB后混强度；alpha位型与隐藏RGB单独核验；强度0逐位复制 | [精度/信号断言]({REL}/native-r3/unittest.log) |
| FC102-06 | 原生对照边界 | natural/PCHIP的真实RGB16单阶段及后置总曲线；分别建模原生格起点、截断和两次量化，每阶段独立误差≤1码；合并原生结果与真实两阶段逐字节相同。连续结果另对照数学基准 | [原生命令/I/O/4组记录]({REL}/native-r3/verification.json) |
| FC102-07 | 有序效果与预算 | 曝光/曲线、LUT/曲线顺序、禁用项、只读输入、分块逐位相同；晚块非法值、取消和工作区拒绝保留输入；预算含保留LUT，不是进程总RSS | [实际断言]({REL}/native-r3/unittest.log) |
| FC102-08 | 公开CLI | {len(media['calls'])}脚本调用/{len(media['checks'])}检查；2次正式render、3次preview；原创320×180、10fps、2秒各20帧，5段覆盖空间插值、点x/y、后置总曲线、Bezier强度及效果顺序 | [原始命令与输出]({REL}/media-r2/verification.json) |
| FC102-09 | 独立全选区参考 | 作者帧3..16共2,419,200个线性RGB值，最大绝对误差{media['curves_oracle']['maximum_linear_absolute_error']:.12g}；正式96000及选区67200双声道PCM采样帧相同；PNG16与选区对应作者帧误差≤1码 | [独立执行参考]({REL}/media-r2/executed-oracle.py.txt) |
| FC102-10 | 原视频/GIF | 原创RGB16图形、alpha与正弦音频，CC0；GIF左原片、右真实CLI预览，14×100ms；静看3/10/16共6幅画面，不代替连续播放或试听 | [原片]({ASSETS}/original-range.mp4) · [实际预览]({ASSETS}/range.mp4) · [Float32]({ASSETS}/range.master.nut) · [PNG16]({ASSETS}/frame.png) · [查看记录]({REL}/static-review-r1.json) |
| FC102-11 | 离线安装 | {itext} | [安装收据]({REL}/installed-r1/verification.json) · [作者工程]({ASSETS}/author-project.json) · [权利账]({ASSETS}/rights-ledger.json) · [CC0]({ASSETS}/LICENSE.txt) |
| FC102-12 | 完整回归 | {ftext} 200源码、400安装与完整套件分别记录，覆盖重叠不累计成完成率 | [本轮报告]({REPORT}) |
| FC102-13 | 保留失败与未验收 | 源码r1实际40项3失败、r2实际200项1失败；真实样例r1因末关键帧缺少公开入口必填插值被拒绝。自然素材、动态增删点、HDR/ICC、实时/长片RSS和完整剪映等价尚未验收 | [失败与精度边界]({REL}/failure-analysis-r1.json) |

![原片与真实CLI连续RGB曲线预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text,name):
    prefix = '../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)


def report(full=None,published=False):
    _,native,_,_ = current()
    return '''# 连续浮点RGB曲线与作者控制点实测

从未改动的LUT309候选复制329个输入：309产品、9依赖、8外部夹具与3份基础运行器；复制时父完整2455项尚未运行/发布。本候选311产品输入、5条产品路径改变。200项相关源码=40新增+160既有；400项安装与完整目标2495项单独执行，不相加为剪映完成度。完整套件必须等待实际V101父候选完整2455项通过并普通发布。

本实现直接解自然三次样条导数和PCHIP斜率，不构造整数查表，也不把正式渲染交给FFmpeg curves。独立自然曲线基准解稠密全局二阶导矩阵，PCHIP基准使用Hermite基函数；媒体基准独立计算作者关键点、传递函数、强度和alpha合成。空间数学定义及原生量化规则参考[FFmpeg官方文档](https://ffmpeg.org/ffmpeg-filters.html#curves)和[官方曲线源码](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_curves.c)，未复制其C实现。

源码r1实际40项/44.009秒有3失败：沿旧32段时间采样使对称Bezier不是精确0.5；错误地用统一2码比较连续曲线与原生整数表；倒放夹具把应保留的nextafter左极限误写成精确160。产品改为直接Bezier求值；时间端点夹具检查明确左极限。r2实际200项/513.699秒有1失败：单阶段整数误差经后置曲线放大后不是单阶段1码预算。没有通过加宽总容差掩盖差异；r3逐阶段核验，合并原生与真实两阶段输出完全相同，再分别对照各阶段独立整数参考。原生I/O、各次执行源码及失败日志均保留。

本机原生PCHIP仅两点时在域外按直线延长，而本产品的所有显示曲线均明确采用常量端点延伸；复杂蓝通道夹具中连续产品与原生差异可达7378.648个RGB16码，该值是声明的语义诊断，绝非误差验收通过。自然曲线的格起点与后置整数截断也与连续浮点数学不同。不能用上述原生核验声称逐像素复制FFmpeg或剪映的所有曲线结果。

真实CLI样例r1为原创作者工程漏写末关键帧插值，公开校验正确拒绝；r2创作生成器显式填写linear，未修改产品以绕过校验。公开CLI仍要求每个关键帧有interpolation；库级编译器的省略默认linear是单独接口边界。真实20帧媒体分5段，独立参考涵盖all点y、红通道点x、后置总曲线点y、natural/PCHIP、直接Bezier和曝光前后顺序。原片、工程、权利账、PCM、Float32、PNG16、MP4/GIF与SHA完整保留。

''' + f"实际相关源码套件200项/{native['seconds']:.6f}秒/0跳过。\n\n" + relink(section(full,published),REPORT)


def contract():
    return '''# 连续浮点RGB曲线与后置总曲线契约 v0.1

显式settings.pixel_pipeline.engine=float32-native-v1。effects数组类型curves/curve或rgb_curves/rgb_curve/channel_curves，参数必须在parameters中；明确input_signal/output_signal，各含primaries/transfer。共同工作域必须是明确线性ColorSignal。旧整数effects catalog的曲线网格限制不覆盖这个显式能力；默认后端未迁移。

以下为片段effects数组的一项；示例作者时基90000 tick/秒、原作者时长至少1秒。工程还需按既有契约声明原片信号与本地素材，不修改素材本身：

```json
{
  "type": "rgb_curves",
  "parameters": {
    "all": "0/0 0.5/0.4 1/1",
    "red": "0/0 0.4/0.45 1/1",
    "post_master": "0/0 0.5/0.55 1/1",
    "interpolation": "natural",
    "intensity": 0.8,
    "input_signal": {"primaries": "bt709", "transfer": "bt709-oetf"},
    "output_signal": {"primaries": "bt709", "transfer": "bt709-oetf"}
  },
  "keyframes": [{"property": "all.1.y", "keyframes": [
    {"at_tick": 0, "value": 0.4, "interpolation": "ease_in_out"},
    {"at_tick": 90000, "value": 0.6, "interpolation": "linear"}
  ]}]
}
```

all为未独立声明通道的默认曲线；curves/curve拒绝独立RGB，使用rgb_curves声明red/green/blue。master是all的旧别名，二者冲突拒绝；真正后置总曲线用post_master，在独立RGB映射后执行一次。每条曲线为1..256个0..1有限x/y字符串点；x以binary64严格递增，不受8位格限制。1点为常量，2点为直线；所有曲线在首末点外作常量延伸，输出夹0..1。natural为自然三次样条，pchip为保形分段三次Hermite。极近点造成非有限系数时明确拒绝，不静默替换成整数表。

关键帧属性all/red/green/blue/post_master.<index>.x或.y，以及intensity。master.<index>归一化为all别名；支持effect./parameters./本类型名前缀。动画独立通道没有静态点时，从静态all完整分叉；后置总曲线没有静态点时从0/0 1/1分叉。固定拓扑，不动态增删点；重复轨道、未知点、每轨超1024关键帧、总数超65536或超2561轨道拒绝。关键帧tick为递增非负整数，值0..1；每个实际作者采样时刻再次校验x顺序，交叉/重合中止事务。

六种时间插值hold/linear/ease_in/ease_out/ease_in_out/bezier。本浮点曲线直接计算Bezier，不沿旧32段/8位小数查表；两值控制为固定横向1/3、2/3的三次式，四值横向控制0..1并用48次二分求根，纵向控制有限。overshoot后的点和强度夹0..1，再检查几何。完整作者tick和有理偏移传入，presentation_window、子序列速度/倒放与父容器分别求值，倒放端点保留左极限。库级省略interpolation默认linear；公开CLI验证仍要求关键帧显式填写interpolation。

每块从共同线性工作信号转入声明input_signal，独立通道和可选post_master以Float64坐标/系数计算，映射后写Float32，再按output_signal转回工作域。intensity为有限0..1，可动画，混合在工作线性straight RGB中用Float64累加后写Float32。强度0逐位复制原RGB，包括域外值；强度1直接取结果。alpha是覆盖率，不参与曲线或传递函数，其原始Float32位型保留，包括负零、透明像素隐藏RGB。

曝光、LUT与曲线按作者effects顺序运行，片段几何和混合前求值；嵌套容器效果在子画布合成后求值。启用的未知效果明确拒绝；未承诺序列区间调节层、所有其他算子或蒙版空间已全部迁入此路径。源与作者工程只读，缓存由作者字段、信号、实际输入和实现SHA绑定。

表面必须连续H×W×4 Float32，有限RGB、alpha0..1，单边≤16384，总像素≤16777216。请求块1..262144、内部最多16384像素。工作数组估算含三份表面、保留LUT、分块数组、序列化作者轨道和固定余量，最多768MiB；估算不是实测总RSS，不包括全部Python对象、JSON解析、音频、源缓存和并发总额。只读输入允许，预算拒绝、非法晚块、取消和数值溢出都不修改源或返回部分结果。

原生FFmpeg RGB16是独立交叉观察：自然曲线的整数格起点/输出截断、后置曲线第二次量化单独建模；PCHIP两点域外直线延伸与本契约的常量端点存在明确差异。连续浮点曲线的通过依据是独立数学参考，不能声称与原生整数后端所有像素相同。自然广告素材、ICC/PQ/HLG/绝对nits、色域映射、HDR质量、实时预览、长片总RSS及完整剪映等价均未验收。
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
    target = ROOT/'product/.runtime/float-curves-20261022'/('readme-preview-'+args.revision)
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
