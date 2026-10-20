"""Generate V80 docs from actual native, isolated and regression receipts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from sync_html_components_documents import block, link

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/curve-points-20261021-v80'
BASE=ROOT/REL
NATIVE='docs/assets/curve-points-20261021-v80-native-r2'
INSTALLED='docs/assets/curve-points-20261021-v80-installed-r1'
CONTRACT=ROOT/'docs/specs/RGB曲线控制点动画契约_v0.1_2026-10-21.md'
REPORT=ROOT/'docs/validation/RGB曲线控制点动画离线实测_2026-10-21.md'
DOCUMENTS=('README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')
FOLLOWUPS=('docs/specs/本地效果目录与参数契约_v0.1_2026-10-14.md',
    'docs/specs/逐帧调色参数自动化契约_v0.1_2026-10-19.md','docs/Concat与剪映功能差异矩阵_2026-10-12.md')
SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-quality','video-cut-template-library')
SCRIPTS=('smoke_curve_automation','verify_curve_automation_install','probe_curve_automation_clocks','sync_curve_automation_documents',
         'audit_curve_automation_release','publish_curve_automation')


def read(path):return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true');args=parser.parse_args()
    focus=read(BASE/'targeted-r3.json');dev=read(BASE/'native-r2/verification.json')
    install=read(BASE/'installed-r1/verification.json');media=read(BASE/'installed-r1/media/verification.json')
    current=focus['frozen_after']
    assert focus['terminal_ok'] and focus['methods']==110 and focus['skipped']==0 and len(current)==239
    for value in (focus,dev,install,media):assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media):assert value['status']=='passed' and all(row['ok'] for row in value['checks'])
    clocks=read(BASE/'clocks-native-r2/verification.json');isolated_clocks=read(BASE/'clocks-installed-r2/verification.json')
    for v in (clocks,isolated_clocks):
        assert v['status']=='completed-with-known-CFR-01-gap' and v['accepted_cases']==2 and v['unaccepted_cases']==1
        assert v['frozen_equal'] and v['frozen_before']==v['frozen_after']==current
    full_text='全量离线回归仍在运行；候选尚未完成 main 发布验收'
    skill_text='4 份相关 Skill 已更新；17 份发现联接待 main 核对'
    if not args.candidate:
        full=read(BASE/'full-r1.json');skills=read(BASE/'skills-r1.json')
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==1819 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==current and full['frozen_equal'] and full['external_fixtures_equal']
        full_text=f'完整原生回归 **{full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过，239 冻结输入＋8 外部夹具前后相同**'
        skill_text=f'{skills["skill_count"]} Skills／{skills["local_links_checked"]} 本地引用与发现联接已核对'
    summary=('2026-10-21 **V80（RGB 曲线控制点动画限定验收）**：补齐差异 #60 的固定拓扑曲线控制点时间动画。'
        '`curves/rgb_curves` 支持 `all/red/green/blue.<点号>.x/y`，六种时间插值、完整作者时钟、剪入剪出、倒放嵌套和区间调节层。'
        '逐通道整曲线命令保留独立 RGB，拒绝六位小数后交叉／重合的 8-bit x 采样格；共享递归预算与内容寻址缓存。'
        f'效果目录 **0.9.0／46 项**；原数值引擎仍为 10 家族／34 通道，分色 HSL 25 通道另计。{full_text}；'
        f'相关专项 **110/110、{focus["suite_seconds"]:.3f} 秒、0 跳过**，属于全量子集。'
        f'开发 **{dev["cli_calls"]} CLI／{len(dev["checks"])} 检查**，5 组×24 帧独立静态参考、原始透明度、PCM 与 PTS、包／片段重建；'
        f'离线 **156 资源／7 wheels／{install["isolated_cli_calls"]} 隔离 CLI＋1 来源探针**，开发和安装解码一致；{skill_text}。'
        '附加非线性变速／祖先倒放探针 2 组通过；分数帧率与非整帧起点探针暴露 **CFR-01：静态路径也缺末帧覆盖**，该场景未验收。'
        '未验收动态增删控制点、HDR／线性光、自然广告质量、连续播放审片、实时性能或完整剪映效果等价。')
    for name in DOCUMENTS:
        path=ROOT/name
        body=summary+'\n\n'+link(path,'曲线动画契约',CONTRACT)+' · '+link(path,'实测、原素材与失败记录',REPORT)
        if name=='README.md':
            rows=[('V80-01 / #60','控制点动画','固定拓扑 1–256 点；all 与独立 RGB 的 x/y；master 继续是 curves 的 all 别名','targeted-r3.json'),
                ('V80-02','原生执行与拒绝','整通道更新、运行时门禁、交叉／同格拒绝、四项共享配额、缓存篡改拒绝','targeted-r3.json'),
                ('V80-03','真实 CLI 与时钟',f'{dev["cli_calls"]} CLI／{len(dev["checks"])} 检查；5×24 帧、独立参考、剪窗口／倒放嵌套／区间层、PCM／PTS','native-r2/verification.json'),
                ('V80-04','离线安装',f'156 资源逐字节一致／7 wheels；{install["isolated_cli_calls"]} 隔离 CLI＋1 来源探针；5组解码一致','installed-r1/verification.json'),
                ('V80-05','完整回归',full_text,'full-r1.json'),
                ('V80-06','失败留证','targeted-r1 的4夹具错误、r2 的窗口元数据预期错误、native-r1 的嵌套夹具缺序列名均保留','targeted-r1.json')]
            rows.append(('V80-07 / CFR-01','额外时钟诊断',f'{clocks["cli_calls"]} 额外 CLI；2组变速通过，1组45帧场景未通过：显示帧33缺图层覆盖，移除曲线仍复现','clocks-native-r2/verification.json'))
            body+='\n\n| 编号 | 核验内容 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
            body+='\n'.join(f'| {a} | {b} | {c} | {link(path,"收据",BASE/d)} |' for a,b,c,d in rows)
            body+='\n\n'+link(path,'原创输入 MP4',ROOT/NATIVE/'source-preview.mp4')+' · '+link(path,'透明原 PNG',ROOT/NATIVE/'foreground-original.png')+' · '+link(path,'原音频',ROOT/NATIVE/'audio-original.wav')+'\n\n'
            body+='![RGB曲线动画：左原图，右实际输出]('+str(Path(NATIVE)/'all-with-red.gif').replace('\\','/')+')\n\n'
            body+=link(path,'独立 RGB 实际 MP4',ROOT/NATIVE/'independent-rgb.mp4')+' · '+link(path,'5组静态对照',ROOT/NATIVE/'comparison.png')
        block(path,'V80-CURRENT',body)
    for name in FOLLOWUPS:
        path=ROOT/name;block(path,'V80-FOLLOWUP',summary+'\n\n'+link(path,'当前契约',CONTRACT)+' · '+link(path,'实测证据',REPORT))
    matrix=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md'
    rows=matrix.read_text(encoding='utf8').splitlines()
    for i,row in enumerate(rows):
        if row.startswith('| 本地效果目录 |'):
            rows[i]='| 本地效果目录 | `effects.py` 0.9.0/46 项；34 原生命令数值通道、25 八色 HSL 通道、2 类曲线坐标路径分别发现 | [V80 真实 CLI、离线安装和边界](RGB曲线控制点动画离线实测_2026-10-21.md)、[目录契约](../specs/本地效果目录与参数契约_v0.1_2026-10-14.md) | 未列通道仍静态；GPU/HDR/自然质量另验 |'
        elif row.startswith('| 效果参数关键帧 |'):
            rows[i]='| 效果参数关键帧 | 原七项表达式、10 类/34 数值通道、25 HSL 通道；新增曲线 all/R/G/B 固定控制点 x/y，整通道 native 命令、完整作者时钟和共享预算 | [V80 像素/PCM/PTS、包/片段/安装](RGB曲线控制点动画离线实测_2026-10-21.md) | 动态增删点、布尔/枚举/颜色 token、其它插件、HDR/自然抠像/厂商等效未验；CFR-01 非整帧末尾覆盖缺口未验收 |'
    matrix.write_text('\n'.join(rows)+'\n',encoding='utf8',newline='\n')
    catalog=ROOT/FOLLOWUPS[0];text=catalog.read_text(encoding='utf8')
    text=text.replace('曲线保持静态，逐帧参数会进入近似警告。','静态点字符串决定固定拓扑；V80 允许 `<通道>.<点号>.x/y` 数值关键帧，按曲线动画契约执行。')
    text=text.replace('`rgb_curves` 生成一个静态 `curves` filter，并为 `all`/`red`/`green`/`blue` 分别执行字符白名单与 `0..1` 坐标校验。','`rgb_curves` 无控制点动画时保持静态 `curves` filter；有动画时生成有界的整通道命令，执行固定拓扑、六位小数 x 采样格和共享预算校验；不向 Agent 开放任意原生命令。')
    catalog.write_text(text,encoding='utf8',newline='\n')
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    if not REPORT.exists():REPORT.write_text('# RGB 曲线控制点动画离线实测\n',encoding='utf8')
    body=summary+'\n\n'
    body+='|编号|已执行核验|结果|\n|---|---|---|\n'
    for row in dev['checks']:body+=f'| C{dev["checks"].index(row)+1:02} | `{row["name"]}` | '+('通过' if row['ok'] else '失败')+' |\n'
    body+='\n5 组均为 320×180、12 fps、2 秒、24 帧；无损 FFV1/BGRA 用于像素与 PCM，MP4/GIF 用于预览。GIF 会合并相同的连续帧，实际为14/19/24帧但均保持2000毫秒，不能将 GIF 帧数当作导出帧数。左右栏标示原输入和实际输出，原输入为原创几何静帧视频，并非自然拍摄素材。\n\n'
    for value in dev['cases']:
        body+=f'- `{value["name"]}`：最大 RGB 误差 {value["max_rgb_error"]}/255；alpha 与 PCM 逐字节一致。'+link(REPORT,'MP4',ROOT/NATIVE/(value['name']+'.mp4'))+' · '+link(REPORT,'GIF',ROOT/NATIVE/(value['name']+'.gif'))+'\n'
    body+='\n'+link(REPORT,'执行脚本',ROOT/'scripts/smoke_curve_automation.py')+' · '+link(REPORT,'开发完整收据',BASE/'native-r2/verification.json')+' · '+link(REPORT,'隔离安装收据',BASE/'installed-r1/verification.json')+' · '+link(REPORT,'相关110项专项',BASE/'targeted-r3.json')+' · '+link(REPORT,'完整回归',BASE/'full-r1.json')+'\n\n'
    body+=(f'额外时钟探针开发 {clocks["cli_calls"]} CLI、隔离安装 {isolated_clocks["cli_calls"]} CLI，分别记录，不并入主实测或回归计数。'
        '解析反函数独立核验线性源速曲线 0.5→1.5 的指数映射（22 帧）及外层倒放／2倍速（11 帧），最大误差≤1/255。'
        '**CFR-01 未验收**：30000/1001 fps、起点0.11秒、时长1秒、根序列1.5秒的45帧输出中，显示帧33（1.1011秒）应有图层但为空；'
        '移除 sendcmd 和 curves 的静态基线同样缺失。其余可见帧曲线误差≤1/255；这不能抵消整场景失败。下一步需修复媒体 PTS/EOF 与实际 CFR 边界的映射，覆盖静态、视频、嵌套、窗口和音频，重新全量验证；不得静默吸附作者时间。\n\n'
        +link(REPORT,'首次失败探针',BASE/'clocks-native-r1/verification.json')+' · '+link(REPORT,'无曲线静态基线',BASE/'clocks-native-r1/static-coverage-baseline.json')+' · '
        +link(REPORT,'开发诊断',BASE/'clocks-native-r2/verification.json')+' · '+link(REPORT,'隔离诊断',BASE/'clocks-installed-r2/verification.json')+'\n\n')
    body+='失败记录保留：'+link(REPORT,'首轮23项/4错误',BASE/'targeted-r1.json')+'；'+link(REPORT,'第二轮23项/1错误',BASE/'targeted-r2.json')+'；'+link(REPORT,'首轮真实样例',BASE/'native-r1/verification.json')+'。首轮初始化用了不存在的 width/height/fps 参数；第二轮误把作者窗口内嵌的完整曲线元数据当成顶层可见帧元数据；真实样例缺少嵌套序列 name。修正夹具与断言后重跑，未放宽产品门禁。\n\n'
    body+='发行审计首次误要求 GIF 必须24帧，遇到相同画面被合并而失败；已改为核验实际帧数与总时长2000毫秒，MP4/FFV1仍要求24帧。'+link(REPORT,'保留审计源码与失败说明',BASE/'audit-format-r1/verification.json')+'。\n\n'
    body+='仅检查静态对照 PNG，未进行连续播放或听音审查；自动 PCM 一致不等同主观音质验收。使用 Windows 原生 FFmpeg，无 Docker/WSL/虚拟化、无云请求、无新模型推理；本轮媒体流程无需浏览器。全量回归中 HTML 子进程由现有 Job 清理。\n\n'
    body+=link(REPORT,'原创 CC0 说明',ROOT/NATIVE/'LICENSE.txt')+' · '+link(REPORT,'输入和输出逐文件摘要',BASE/'native-r2/verification.json')
    block(REPORT,'V80-DETAIL',body)
    status='状态：候选实现，专项与真实样例已验证；完整回归与 main 发布待完成。' if args.candidate else '状态：限定实现已验收；完整回归、独立安装与 main 发布前字节审计已通过。'
    text=CONTRACT.read_text(encoding='utf8');text=text.replace('状态：开发契约；实施与实测通过后更新验收证据。对应细化差异 #60，效果自动化 #33。',status+'对应细化差异 #60，效果自动化 #33。')
    import re
    text=re.sub(r'状态：候选实现，专项与真实样例已验证；完整回归与 main 发布待完成。',lambda _:status,text)
    CONTRACT.write_text(text,encoding='utf8',newline='\n')
    for skill in SKILLS:
        path=ROOT/'skills'/skill/'SKILL.md'
        common=('RGB curves now accept fixed-topology point animation: `all.1.y`, `red.1.x`, '
            '`green.1.y`, `blue.1.y` using normal numeric effect keyframes. Inspect the 0.9.0 local catalog first. '
            'Keep the original point strings and author keyframes in the project; never persist or edit generated sendcmd files. '
            '`curves.master` remains an alias for all, not a post-master curve. Explicit RGB or an animated RGB channel forks the static all curve; '
            'other channels inherit animated all. Six-decimal x positions must occupy strictly increasing 8-bit bins; do not sort or drop points to force rendering. '
            'Point count is fixed (1–256); temporal easing is separate from native natural-cubic color interpolation. '
            'Known CFR-01: fractional FPS with non-frame-aligned clip boundaries can lose trailing coverage even without curves; '
            'verify actual visibility and do not claim that scenario accepted or silently snap author time. '
            'Use complete author clocks for trims, reverse/nesting and interval layers; respect shared command/sample/byte/target quotas. '
            'Check actual frame RGB/alpha, PCM/PTS and package/fragment rebuilds. Do not claim HDR, natural quality, real-time preview or CapCut algorithm equivalence.\n\n'
            +link(path,'RGB point contract',CONTRACT)+' · '+link(path,'native/isolated validation and failures',REPORT))
        block(path,'V80-CURVES',common)
    print(json.dumps({'status':'candidate' if args.candidate else 'synchronized','documents':len(DOCUMENTS)+len(FOLLOWUPS)+2,'skills_updated':len(SKILLS)}))


if __name__=='__main__':main()
