"""Publish V58 facts from terminal receipts while retaining historical scopes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'docs/validation/evidence/effect-automation-20261019-v58'
PUBLIC = ROOT/'docs/assets/color-automation-r7-20261019-v58'
NATIVE = ROOT/'docs/validation/evidence/color-native-release-r3-20261019-v58'
CONTRACT = '逐帧调色参数自动化契约_v0.1_2026-10-19.md'
REPORT = '逐帧调色参数自动化实测_2026-10-19.md'
DOCS = ['README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
    'docs/specs/AgentCLI契约_v0.1_2026-10-13.md', 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md']

def read(path): return json.loads(path.read_bytes())
def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(value, encoding='utf-8', newline='\n')
def line(text, prefix, value):
    assert sum(x.startswith(prefix) for x in text.splitlines()) == 1, prefix
    return '\n'.join(value if x.startswith(prefix) else x for x in text.splitlines())+'\n'
def marked(text, name, value):
    a, b = '<!-- '+name+' -->', '<!-- /'+name+' -->'; block = a+'\n'+value+'\n'+b
    if a in text: return text[:text.index(a)]+block+text[text.index(b)+len(b):]
    head, rest = text.split('\n', 1); return head+'\n\n'+block+'\n\n'+rest.lstrip('\n')

def run(final):
    current = frozen(); full = read(EVIDENCE/'full-final.json'); targeted = read(EVIDENCE/'targeted-final.json')
    smoke = read(PUBLIC/'verification.json'); native = read(NATIVE/'verification.json'); skills = read(EVIDENCE/'skills.json')
    assert len(current) == 186 and full['frozen_before'] == current
    for r in (targeted, smoke, native): assert r['frozen_before'] == r['frozen_after'] == current
    assert targeted['methods'] == 28 and targeted['terminal_ok'] and targeted['skipped'] == 0
    assert len(smoke['cases']) == 14 and smoke['cli_calls'] == 64 and smoke['main_frames'] == 262
    assert smoke['stereo_sample_frames'] == 1158528 and smoke['cases'][11]['animated_text_rgb_changes_observed']
    assert native['isolated_cli_calls'] == 65 and native['installed_package_files'] == 124
    assert native['actual_new_frames'] == 282 and native['actual_new_stereo_sample_frames'] == 1254528
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 206
    group = read(ROOT/'docs/validation/evidence/color-group-native-r2-20261019-v58/verification.json')
    assert group['status'] == 'passed' and group['isolated_cli_calls'] == 6 and group['frames'] == 20
    assert group['frozen_before'] == group['frozen_after'] == current
    if final:
        assert full['terminal_ok'] and full['exit_code'] == full['skipped'] == 0
        assert full['methods'] == 1357 and full['frozen_after'] == current
        complete = f"1357/1357、{full['suite_seconds']:.3f} 秒、0 跳过、186 文件冻结"
    else: complete = '完整回归运行中、186 文件冻结；最近完整 V57 1329/1329 为历史结果'
    for name in DOCS:
        path = ROOT/name; text = path.read_text(encoding='utf-8-sig')
        report = ('docs/validation/' if name == 'README.md' else '' if name.startswith('docs/validation/') else '../validation/' if name.startswith('docs/specs/') else 'validation/')+REPORT
        contract = ('docs/specs/' if name == 'README.md' else '../specs/' if name.startswith('docs/validation/') else '' if name.startswith('docs/specs/') else 'specs/')+CONTRACT
        if '<!-- V57-CURRENT -->' in text:
            a, b = text.index('<!-- V57-CURRENT -->'), text.index('<!-- /V57-CURRENT -->')
            old = text[a:b].replace('2026-10-19 **V57（产品）**', '历史 **V57（产品，2026-10-19）**')
            text = text[:a]+old+text[b:]
        text = marked(text, 'V58-CURRENT',
            '2026-10-19 **V58（产品）**：色温、基础色彩平衡、三向色轮、曝光、色阶共 **19 数值通道**逐帧执行，'
            '保留作者时钟和可编辑字段；独立实例、递归配额、运行时能力及缓存摘要门禁。**'+complete+'**；'
            '28 新增专项为全量子集。**64 CLI /14 组 /262 帧 /1,158,528 立体声采样帧**；13 组独立参数参考 RGB 最大差 1，'
            '文字另验实际颜色变化、Alpha 0 与同编码音频一致；全部 PCM 0。'
            '**124 包内文件 /65 隔离 CLI /282 安装帧 /1,254,528 采样帧；14 Skills /206 引用**。'
            '另验复合容器自身效果：6 隔离 CLI/20 帧/96,000 采样帧，RGB/Alpha/PCM 0，重复实例时钟重置。'
            '原曝光参考失配与文字夹具修正保留，未放宽误差门槛。原生静态参考共用 FFmpeg 算法及相同交付边界；'
            'Kelvin/基础平衡仍为阴影映射，物理白平衡、HDR、自然质量、连续播放/听审、另一台机器及完整剪映等价未验收。'
            f'[契约]({contract})、[原输入/MP4/GIF/失败/安装]({report})。')
        if name == 'README.md':
            text = line(text, '| V13 |', f'| V13 | 产品自动回归 | 最近 V58 {complete}；28 新增为全量子集 | 历史、研究、安装和专项不相加；完整剪映仍未验收 | [完整日志](docs/validation/evidence/effect-automation-20261019-v58/full-final.log)、[终态](docs/validation/evidence/effect-automation-20261019-v58/full-final.json) |')
            row = f'| V58 | 逐帧调色参数自动化 | 5 类/19 通道；28 新增；{complete}；64 CLI/262 帧；124 文件/65 隔离 CLI/282 安装帧；另复合容器 6 CLI/20 帧；14 Skills/206 引用 | 独立参数与同 FFmpeg 交付边界分清；文字实际变色/Alpha；曝光与文字失败保留；自然调色及完整等价未验 | [契约]({contract})、[14 组及复合容器原片/GIF/失败/安装]({report}) |'
            if '| V58 |' in text: text = line(text, '| V58 |', row)
            else:
                rows = text.splitlines(); i = next(i for i, x in enumerate(rows) if x.startswith('| V57 |')); rows.insert(i+1, row); text = '\n'.join(rows)+'\n'
            demo = ('**V58 实际逐帧调色**：原创色卡/瓶体图案，2 秒内依次变化；四格为色温、九色轮、曝光、色阶的真实成片。GIF 无声音。'
                '[原图](docs/assets/color-automation-r7-20261019-v58/source.png)、[原 MKV](docs/assets/color-automation-r7-20261019-v58/source.mkv)、'
                '[原 WAV](docs/assets/color-automation-r7-20261019-v58/source.wav)、[原输入 MP4](docs/assets/color-automation-r7-20261019-v58/source-preview.mp4)、'
                '[曝光 MP4](docs/assets/color-automation-r7-20261019-v58/CA04.mp4)、[有色文字 MP4](docs/assets/color-automation-r7-20261019-v58/CA12.mp4)、'
                '[复合容器效果 MP4](docs/assets/color-group-r2-20261019-v58/CA15-group.mp4)、'
                '[可编辑工程](docs/assets/color-automation-r7-20261019-v58/CA04.aevpkg.zip)、[原生离线包](docs/assets/color-automation-r7-20261019-v58/agent-video-kit-cp313-win_amd64.zip)。'
                f'[全部 14 组/失败/范围]({report})。\n\n![V58 真实逐帧调色](docs/assets/color-automation-r7-20261019-v58/color-automation.gif)')
            if '<!-- V58-DEMO -->' in text: text = marked(text, 'V58-DEMO', demo)
            else: text = text.replace('<!-- V57-DEMO -->', '<!-- V58-DEMO -->\n'+demo+'\n<!-- /V58-DEMO -->\n\n<!-- V57-DEMO -->', 1)
            text = line(text, '- 当前模块进度见', f'- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：最近 V58 {complete}；五类调色 19 通道、完整作者输出及主轨磁吸已受控实现。物理白平衡、动态外部混合、全手势、自然质量、CTC 精度、长片/HDR、另一台机器、内容库规模和完整剪映等价继续开放。')
        if name == 'docs/构建进度总表_2026-10-16.md':
            changes = {
                '| 本次状态快照 |': f'| 本次状态快照 | 2026-10-19，README V58；{complete}；28 新增专项为全量子集 |',
                '| 最近产品增量 |': '| 最近产品增量 | V58 五类调色 19 数值通道、真实 CFR 参数命令、完整作者时钟、递归独立实例/配额与缓存摘要门禁 |',
                '| 研究状态与历史快照 |': '| 研究状态与历史快照 | OpenFilm R05 固定 main 7a64d1fe/727 文件；947 stars/99 forks 为 API 时点；148 核心原字节不变，选定上游 63 通过/1 跳过，与 V58 本地实现/产品回归分计 |',
                '| 核对范围 |': f'| 核对范围 | V58 {complete}；64 CLI/262 帧/1,158,528 采样帧；124 包内文件/65 隔离 CLI/282 帧/1,254,528 采样帧 |',
                '| 当前生产代码 |': '| 当前生产代码 | 产品/测试/Schema/发行输入共 186 文件；专项/媒体/安装前后冻结一致，完整终态另列 | 186 不是纯运行时数量；发行包内 124 文件，失败保留 |',
                '| 最近完整产品回归 |': f'| 最近完整产品回归 | V58 {complete} | [完整日志](validation/evidence/effect-automation-20261019-v58/full-final.log)；耗时不是性能基准 |',
                '| 最近产品新增子集 |': '| 最近产品新增子集 | V58 28 方法（20 契约＋5 原生参数/Alpha＋3 CLI/递归图） | 为完整子集；13 独立参数图像与文字 Alpha 控制分计 |',
                '| 最近产品实际核验 |': f'| 最近产品实际核验 | V58 14 组/64 CLI/262 主帧/1,158,528 采样帧；另 65 隔离 CLI/282 帧/1,254,528 采样帧 | [原片/GIF/失败/发行](validation/{REPORT})；21 样本静帧，无连续播放/听审 |',
                '| Skill 审计 |': '| Skill 审计 | 14 Skills/206 引用；格式/目录联接/SHA 通过 | [当前记录](validation/evidence/effect-automation-20261019-v58/skills.json)；不证明自然质量 |',
                '| 文档 |': '| 文档 | README/进度/契约/矩阵/基线/效果目录/原片 GIF 同步，当前行指向 V58 | [当前审计](validation/evidence/effect-automation-20261019-v58/release.json)；不证明外链、锚点、许可或自然质量 |'}
            for prefix, value in changes.items(): text = line(text, prefix, value)
            text = line(text, '“已实现”表示', f'“已实现”表示列出的实现和验证，不表示完整剪映等价。当前 V58 {complete}；28 新增、研究、媒体和安装分别计数。自然调色、阴影映射之外的白平衡、声音、内容库和规模继续开放。')
        if name.startswith('docs/validation/能力覆盖'):
            row = f'| 调色参数自动化（V58） | 五类/19 通道、作者时钟、文字/复合/区间层、唯一实例、递归配额和缓存门禁 | [28 新增/14 组/原生安装]({report})；{complete}，262 帧/1,158,528 采样帧 | 同 FFmpeg 算法；Kelvin/基础平衡仅阴影，物理白平衡/HDR/自然广告调色/完整等价未验 |'
            if '| 调色参数自动化（V58） |' in text: text = line(text, '| 调色参数自动化（V58） |', row)
            else: text = text.replace('| 完整输出变速与磁吸联动（V57） |', row+'\n| 完整输出变速与磁吸联动（V57） |', 1)
            text = line(text, '| 本地效果目录 |', '| 本地效果目录 | `effects.py` 0.5.0/45 项；参数、别名、许可、19 数值通道及共享预算可查询 | `test_effect_catalog_cli_is_local_and_queryable`、[目录契约](../specs/本地效果目录与参数契约_v0.1_2026-10-14.md)、[实际输出]('+REPORT+') | RGB 曲线/未列通道仍静态；GPU/自然质量另验 |')
            text = line(text, '| 效果参数关键帧 |', '| 效果参数关键帧 | 原七项表达式；新增色温、色彩平衡、九色轮、曝光、色阶 19 数值通道，逐 CFR 帧 native 命令，完整作者时钟与递归共享配额 | [专项、14 组、包内重建与安装]('+REPORT+') | 布尔/枚举/曲线字符串/LUT 动态强度、其它插件、物理白平衡/跨渲染器等效仍未实现或未验 |')
        if name == 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md':
            old = '曝光、色阶、RGB 曲线、三向色轮、降噪、时域混合、镜头校正、框线、色彩对比、去闪烁和 DCT 降噪等新增原生滤镜当前以静态参数执行；项目可以保留这些效果的关键帧，但渲染会写入 `RENDER_FEATURE_APPROXIMATE`，不得把静态回退描述成逐帧等效。'
            new = 'V58 的 `color_temperature`、`color_balance`、`color_wheel`、`exposure`、`color_levels` 共 19 数值通道通过有界 `sendcmd`/独立滤镜实例逐帧执行，精确属性由 0.5.0 目录返回；未知动态属性拒绝。RGB 曲线、降噪、时域混合等未列通道仍保持原静态/告警行为。作者时钟、区间局部时钟、Bezier 截断、缓存及配额见[调色参数契约]('+CONTRACT+')。'
            if old in text: text = text.replace(old, new, 1)
            else: assert new in text
        save(path, text)
    build_report(complete, full, smoke, native, skills)
    mapping_path = ROOT/'video-cut-install-manifest.json'; mapping = read(mapping_path)
    audit_path = (EVIDENCE/'skills.json').relative_to(ROOT).as_posix()
    if mapping['current_audit']['record'] != audit_path: mapping.setdefault('audit_history', []).append(mapping['current_audit'])
    mapping['current_audit'] = {'record': audit_path, 'record_sha256': sha(EVIDENCE/'skills.json'),
        'checked_at_utc': skills['checked_at_utc'], 'skills': 14, 'local_links_checked': 206,
        'semantics': 'V58 nineteen bounded numeric color channels; independent parameter clocks on pinned native delivery; full parity unaccepted'}
    for row in mapping['skills']: row['skill_md_sha256'] = next(r['sha256'][7:] for r in skills['results'] if r['skill'] == row['name'])
    save(mapping_path, json.dumps(mapping, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'documents': len(DOCS)+1, 'full_final': final, 'frozen_files': 186, 'skill_links': 206}))


def build_report(complete, full, smoke, native, skills):
    public = '../assets/'+PUBLIC.name+'/'
    evidence = 'evidence/'+EVIDENCE.name+'/'
    installed = 'evidence/'+NATIVE.name+'/'
    labels = {'CA01': 'Kelvin 3000→12000，三个派生阴影分量', 'CA02': '基础 RGB 平衡三个通道',
        'CA03': '阴影/中间调/高光九通道＋静态保亮度', 'CA04': '曝光 amount/black',
        'CA05': '色阶四通道、RGB 同步', 'CA06': '重复子序列＋每层两个同后端效果，独立实例',
        'CA07': '嵌套 1×/2× hold 曲线＋倒放，解析原作者时钟', 'CA08': '完整作者输出窗 0.4..1.6 秒',
        'CA09': '九色轮完整子画面＋0.4 秒复合定格', 'CA10': '0.35..1.55 秒区间调节层，首采样重置局部时钟',
        'CA11': '30000/1001 fps，1.001 秒静态图源', 'CA12': '暗色独立文字＋图层/颜色 Alpha＋实际颜色变化',
        'CA13': '35 ms 非整帧片段起点，原局部偏移', 'CA14': 'hold＋解析 cubic Bezier＋ease_out'}
    rows = []
    for c in smoke['cases']:
        name = c['name']; metric = str(c['max_rgb_error']) if c['rgb_acceptance_applies'] else f"{c['max_rgb_error']}（变色控制，非 RGB 等效门槛）"
        rows.append(f"| {name} | {labels[name]} | {c['fps']} /{c['frames']} /{c['stereo_sample_frames']:,} | {metric} /{c['max_alpha_error']} /{c['max_pcm_error']:g} | [MP4]({public+name}.mp4) /[原主片]({public+c['output']}) /[工程包]({public+name}.aevpkg.zip) /[参考帧]({public+name}-reference.npz) |")
    baseline = read(PUBLIC/'baseline-v57.json')
    old_rows = '\n'.join(f"| {c['name']} | {c['reference_error']} | 超过未改变的 2 级门槛 | [真实 V57 成片]({public+c['name']}-v57.mkv) |" for c in baseline['cases'])
    request = {'operations': [{'op': 'update_clip', 'clip_id': 'color_clip', 'patch': {'effects': [
        {'type': 'exposure', 'parameters': {'black': 0}, 'keyframes': [{'property': 'amount', 'keyframes': [
            {'at_tick': 0, 'value': -.5, 'interpolation': 'linear'},
            {'at_tick': 180000, 'value': .7, 'interpolation': 'linear'}]}]}]}}]}
    checks = f'''| 编号 | 核验 | 实际结果和范围 |
|---|---|---|
| CHECK-01 | 新增专项 | **28/28、{read(EVIDENCE/'targeted-final.json')['suite_seconds']:.3f} 秒、0 跳过**：20 契约、5 原生动态/Alpha、3 CLI/递归图方法；五类数值 native subTest 不另加总。[终态]({evidence}targeted-final.json)、[原日志]({evidence}targeted-final.log) |
| CHECK-02 | 完整产品回归 | **{complete}**。专项是完整子集；修改既有目录版本断言不增加测试数。[终态]({evidence}full-final.json)、[完整日志]({evidence}full-final.log) |
| CHECK-03 | 实际开发样例 | **64 CLI、14 组、262 主帧、1,158,528 立体声采样帧**；另 5 次真实旧版渲染。13 组独立数值/时钟参考 RGB 最大差 1；暗色文字实际变色、Alpha 0；全部 PCM 最大差 0。[总证据]({public}verification.json)、[CLI]({public}calls.json)、[原生命令]({public}native-calls.json) |
| CHECK-04 | 离线原生安装 | **7 个 wheel、124 包内文件、65 次 -I -S 独立 CLI、282 新安装帧、1,254,528 采样帧**；全部 14 工程重建、一次真实参数修改、幂等、未知通道与缓存篡改拒绝。安装源/轮包/当前源码逐字节相等；解码 RGBA/PCM 与开发版完全一致。[证据]({installed}verification.json)、[ZIP]({public}agent-video-kit-cp313-win_amd64.zip)、[清单]({public}release-manifest.json) |
| CHECK-05 | 媒体与时钟 | 14 MP4 的 PTS、fps、帧数、各自音频长度及主片解码 SHA 通过；CA13 视频覆盖 1.1 秒，原作者音频为 1.035 秒，按既有交付契约分别保留。GIF **640×432、20 帧、2000 ms**。[审计]({evidence}media-final.json) |
| CHECK-06 | 实际静帧检查 | 两张实际主片接触表，21 个样本；暗色文字用棋盘展示透明度。[记录]({evidence}static-review-final.json)。未连续播放/未听审，不能据此判断连续运动或自然广告质量 |
| CHECK-07 | Skills | **14 Skills /206 本地引用**，两项主要技能加入精确通道、时钟、门禁和参考范围，目录联接、格式和 SHA 通过。[证据]({evidence}skills.json) |
| CHECK-08 | 精度与失败保留 | 原曝光错误参考仍为 RGB 3；原始图像边界误差 0，相同合成/BT.709 编码参考误差 0；门槛仍为 2。[可复现诊断]({evidence}precision-reproduced/verification.json)、[早期/失败索引]({evidence}development/index.json) |
| CHECK-09 | 源文件与发行绑定 | 186 文件在专项、完整回归、媒体和安装前后绑定；不是纯运行时数量。最终审计将源码、包、实际媒体、技能、失败和文档统一核对。[发行审计]({evidence}release.json) |
| CHECK-10 | 复合容器自身效果 | 另 **6 次 -I -S CLI、20 帧、96,000 采样帧、6 独立 target**；两个重复容器各有动态 red，子层另有 red/blue。独立静态参考 RGB/Alpha/PCM 差均 0；容器与无容器效果控制 RGB 最大差 14，两个实例解码帧完全重复。[证据](evidence/color-group-native-r2-20261019-v58/verification.json)、[MP4](../assets/color-group-r2-20261019-v58/CA15-group.mp4)、[原主片](../assets/color-group-r2-20261019-v58/CA15-group.mkv)、[工程包](../assets/color-group-r2-20261019-v58/CA15-group.aevpkg.zip)、[参考](../assets/color-group-r2-20261019-v58/CA15-group-reference.npz)。复用同一原输入/124 文件安装版，不加入主 14 组或 65 次计数 |
'''
    text = f'''# 逐帧调色参数自动化实测

V58 已为五类现有调色效果接入 **19 个数值通道的逐 CFR 帧命令**，沿用本地 FFmpeg 主渲染链与可编辑工程字段。它补充差异矩阵 #33 效果参数关键帧和 #45 调节层中的具体缺项；完整剪映功能、自然画质和色彩算法等价仍未达到。

先行范围见[契约](../specs/{CONTRACT})。`effects list/inspect` 目录升为 **0.5.0，仍为 45 项效果**；没有把原有效果重新计为新算法。本轮产品变化为 `effect_automation.py`、主渲染接线、严格校验、目录和能力声明，新增 28 方法；项目 Schema 和原静态效果路径保持兼容。

## 数值范围与调用

| 编号 | 效果 | 可动画属性 | 数量 /原生映射 |
|---|---|---|---|
| COLOR-01 | `color_temperature` | `kelvin`，1000..40000 | 1；沿用 Kelvin→`rs/gs/bs` 阴影 RGB 近似 |
| COLOR-02 | `color_balance` | `red/green/blue`，-1..1 | 3；`colorbalance.rs/gs/bs`，按 FFmpeg 阴影权重生效 |
| COLOR-03 | `color_wheel` | `shadows/midtones/highlights` 各 `red/green/blue`，-1..1 | 9；`rs/gs/bs/rm/gm/bm/rh/gh/bh`；`preserve_luma` 仍静态 |
| COLOR-04 | `exposure` | `amount` -3..3；`black` -1..1 | 2；`exposure/black` |
| COLOR-05 | `color_levels` | `input_black/input_white` -1..1；`output_black/output_white` 0..1 | 4；每一属性同步 RGB 原生色阶选项 |

使用原有 compose 更新效果栈，无新增 CLI 入口。以下示例以 90000 tick/秒、2 秒的 `color_clip` 为前提；写入本地 JSON 后调用 `timeline compose --project <工程> --input <变更文件>`。

```json
{json.dumps(request, ensure_ascii=False, indent=2)}
```

`effects[].keyframes` 优先于 `effects[].parameters.keyframes`。支持 hold、linear、ease_in/out/in_out 和两值/四值 Bezier。所有作者 tick、曲线及窗口均保留；整数 tick 严格递增、数值有限且在范围内、规范属性不可重复。未知动态属性明确拒绝。Bezier 求值超调按参数范围截断并计数。原布尔、枚举、RGB 曲线字符串、LUT 动态强度和未列滤镜不由这次实现扩展。

每个动态滤镜具有唯一且确定性的 target。完整递归根图共享 **2,000,000 状态采样 /200,000 数值命令 /16 MiB 文本 /1024 实例**配额；这是计划准入，不是总 RSS 或长片性能验收。参数按实际显示帧采样、命令安排在相邻采样之间，首帧显式初始化；原生值使用与静态映射一致的六位小数。运行时不具备所需 `T` 选项、未知动态属性或缓存同名异字节均拒绝；不静默降为静态。

命令是 `cache/effect-automation/<SHA256>.ffcmd` 派生缓存；manifest 记录二进制、参数、原作者时钟、帧范围、命令文件/数量/字节、截断和根配额。包保留作者字段并在新工程重建缓存，不依赖旧绝对缓存路径。独立文字、复合容器和区间调节层均接入；区间效果时钟从第一张保留的 CFR 帧重置，**不是改为绝对序列时钟**。

## 核验结果

{checks}
## 14 组实际成片

原输入为原创 **160×96 RGBA 色卡/瓶体、FFV1/BGRA 40 帧/4 秒/10 fps**，以及原创 48 kHz、立体声、16-bit、192000 采样帧扫频；图案和音频以 CC0 发布。统一底层 BGM 保持原作者速度，以验证颜色处理未改音频；它不是子序列变速音质验收。文字采用原 DejaVu Sans 与随附 Bitstream Vera notice。

[原 PNG]({public}source.png)、[原 MKV]({public}source.mkv)、[原 WAV]({public}source.wav)、[输入 MP4]({public}source-preview.mp4)、[来源及摘要]({public}source-provenance.json)、[字体现有许可]({public}LICENSE_DEJAVU)。主片 MKV 为 libx264 CRF=0/yuv444p＋pcm_f32le；CA12 主片为 WebM/VP9 yuva420p＋Opus，显式 libvpx 解码 Alpha。MP4 为可看预览，不能据它冒充无损 RGBA。

| 编号 | 核验内容 | fps /主帧 /立体声采样帧 | 最大 RGB /Alpha /PCM 差 | 实际媒体与可编辑数据 |
|---|---|---|---|---|
{chr(10).join(rows)}

13 组的原参数与时间公式独立编写，交给同一固定 FFmpeg 的逐帧**静态**滤镜比较；它独立于产品的动态命令/时钟编译，不独立于 FFmpeg 调色算法。窗口/复合定格参考先完成原作者滤镜图像，再选帧/重复帧和交付编码。CA14 使用独立解析 cubic 公式，没有调用生产 easing 求值。

CA12 与无效果的同版文字绘制基线比较，要求实际颜色变化、相同 Alpha 和相同编码音频；RGB 差在这里表示预期变色，**不作为独立 RGB 画质通过值**。字号、字形和自然字体质量没有独立验收。其余受控 RGB 门槛为 2 级、Alpha 为 0、PCM 为 2e-6；实际 13 组最大 RGB 1、Alpha 0、所有 PCM 0。

![实际 CLI 四类调色成片]({public}color-automation.gif)

上图来自 CA01/CA03/CA04/CA05 的实际编码输出，640×432、20 帧/2 秒，无声。另有[三时刻调色接触表]({public}encoded-static-review.png)、[嵌套/区间/暗色文字接触表]({public}timeline-static-review.png)。21 个静帧已通过 `view_image` 实际查看；曝光末段亮部剪切是当前参数的预期结果，不是自然广告调色建议。未连续播放或听审。

## 旧版实际对照

固定已发布 V57 `{baseline['commit']}`，从 Git archive 提取原产品源码，对 CA01..CA05 同项目真实渲染。以下是同一交付边界下相对新独立参数参考的最大 RGB 差；原 5 次渲染不与新 262 帧、完整回归或安装计数相加。

| 编号 | V57 最大 RGB 差 | 结果 | 证据 |
|---|---|---|---|
{old_rows}

[固定源码归档摘要、真实命令及退出码]({public}baseline-v57.json)。旧版使用静态参数，不能以其正常退出推断动态执行已经存在。

## 曝光参考诊断与保留记录

第二次样例中，较大图案的曝光主片相对直接 `exposure→RGBA` 参考最大差 **3**，超过预设的 **2**；原失败没有删除或放宽。独立复现表明：实际渲染图请求 raw RGBA 与直接静态参考逐帧差 **0**；实际 H264 主片经过不透明底合成、yuv444p 和声明的 BT.709 编码。将独立静态参考也置于相同交付边界后差 **0**。因此修正参考的合成/编码阶段，无需修改产品算法。

[原失败](../assets/color-automation-r2-20261019-v58/failure.json)、[原曝光主片](../assets/color-automation-r2-20261019-v58/CA04.mkv)、[原逐次诊断]({evidence}precision-diagnostic.json)、[可复现诊断]({evidence}precision-reproduced/verification.json)、[实际 raw 图]({evidence}precision-reproduced/CA04-actual-graph-rgba.nut)、[独立参考数组]({evidence}precision-reproduced/references.npz)。相同 FFmpeg 边界相等不证明物理色彩科学或商业产品等价。

| 记录 | 实际问题 /范围 | 保留与处理 |
|---|---|---|
| 首次完整回归 | 原运行句柄失效，系统已无对应进程，日志无终态 | [实际观察]({evidence}full-interruption-observation.json)、[原日志]({evidence}full-interrupted.log)；保留中断，从头在原生隐藏后台进程重跑，不复用局部通过数 |
| 首次专项 | 28 方法中 1 失败＋1 错误：Bezier 二分逼近与测试小数位误差、错误窗口字段 | [原终态]({evidence}targeted-first.json)、[原日志]({evidence}targeted-first.log)、[原测试文件]({evidence}development/targeted-first-test.py)；改为既有求值器 1e-6 标量容差和正确窗口字段，像素门槛未改 |
| 样例 r1 | 全局 clip/asset ID 同名，严格校验拒绝 | [原失败](../assets/color-automation-r1-20261019-v58/failure.json)；修复 clip 测试 ID |
| 样例 r2 | 曝光参考边界不同导致 RGB 3 | 原片、原生成器、参考诊断均保留，见上文 |
| 样例 r3 | 文字轨道/clip ID 同名，严格校验拒绝 | [原失败](../assets/color-automation-r3-20261019-v58/failure.json)；修复文字测试 ID |
| 样例 r4 | 14 组在原声明的 Alpha 控制范围通过，但白字不能证明颜色变化 | [原通过证据](../assets/color-automation-r4-20261019-v58/verification.json)保留，不并入最终计数；扩大文字验证要求 |
| 样例 r5/r6 | 更严格的“实际变色”检查拒绝：两种较亮文字仍在阴影权重之外 | [r5](../assets/color-automation-r5-20261019-v58/failure.json)、[r6](../assets/color-automation-r6-20261019-v58/failure.json)；[九次真实静态范围探针]({evidence}text-shadow-range-diagnostic.json)确认暗色控制会响应，最终以原生权重范围内素材验证 |
| 首次安装 | 检查器把 JSON 层级误写成点分字符串，2 次 CLI 后断言失败 | [原失败](evidence/color-native-release-20261019-v58/failure.json)和原生成器保留；修改检查器后重装；早期 r4 安装通过另存，不并入最终 65 |
| 复合容器补验首次 | 检查器把渲染输出放在工程外，第四次 CLI 按策略拒绝，尚未渲染 | [原失败](evidence/color-group-native-20261019-v58/failure.json)、[原执行生成器](evidence/color-group-native-20261019-v58/executed-generator.py)保留；改为工程内渲染后复制公开，第二次完整 6 调用通过；产品未修改 |

所有早期文件/摘要和执行生成器见[索引]({evidence}development/index.json)。本轮原生效果没有新增模型前向、云服务、Docker、WSL、venv 或 GUI；开发样例无浏览器调用，完整套件内既有 HTML 检查的 headless Job 生命周期另由最终审计检查。

## 安装和复现

从项目根目录原生 PowerShell 执行，输出使用未存在的新目录；Python、FFmpeg、已有 HTML/R3 工具链需按本机实际路径提供，不会在线补装。以下发行包含 7 个固定 wheel 与原 notice，不含 Python、FFmpeg 或 HTML 浏览器工具链；它验证本机隔离安装，不代表另一台干净机器验证。

```powershell
C:/Python313/python.exe -B -X utf8 scripts/smoke_color_automation.py --work product/.runtime/<新工作目录> --public docs/assets/<新公开目录>
C:/Python313/python.exe -B -X utf8 scripts/run_frozen_regression.py --output docs/validation/evidence/<新回归>.json --html-runtime product/.runtime/html-motion-runtime-20261018-e2.json --rubberband product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe
C:/Python313/python.exe -B -X utf8 product/offline/build.py --output product/.runtime/<新发行目录>
C:/Python313/python.exe -B -X utf8 scripts/verify_color_automation_native.py --bundle product/.runtime/<新发行目录> --work product/.runtime/<新安装目录> --public docs/assets/<新公开目录> --evidence docs/validation/evidence/<新安装证据目录>
C:/Python313/python.exe -B -X utf8 scripts/verify_color_automation_group.py --installed product/.runtime/<新安装目录>/installed --source docs/assets/<新公开目录> --work product/.runtime/<新复合容器目录> --public docs/assets/<新复合容器公开目录> --evidence docs/validation/evidence/<新复合容器证据目录>
```

生成脚本：[样例原字节]({public}executed-generator.py)、[安装原字节]({installed}executed-generator.py)、[复合容器原字节](evidence/color-group-native-r2-20261019-v58/executed-generator.py)、[生产实现](../../product/src/ai_ad_editor/effect_automation.py)。[发行清单]({public}release-manifest.json)与[安装清单]({public}install-receipt.json)记录各文件 SHA；不将容器时间戳导致的文件字节变化当作解码差异。

## 尚未验收的完整目标

当前同一 FFmpeg 的数值接线/时钟/编码结果通过，仍不证明剪映的物理白平衡、色彩管理、HDR、专业曲线与动态 LUT、插件生态、自然广告审美、长片资源/性能、所有 GUI 手势或全部功能/效果等价。基础平衡和 Kelvin 的阴影映射不能代替通用白平衡。声音仅验证受控编码样本不受影响，未听审。完整剪映对标需求继续保持开放。

这次产品实现属于本项目 FFmpeg 扩展，没有新增 OpenFilm 算法采用或安装官方 Skill；同日另做[R05 源码更新与成本复核](../OpenFilm复用复核与开发成本更新_2026-10-19.md)，其 63 通过/1 跳过与产品回归分计。既有 17 项拆取/降本结论见[R04](../OpenFilm最新源码复核与降本清单_2026-10-18.md)；新主链核心字节不变，许可/候选范围继续分别记录。
'''
    save(ROOT/'docs/validation'/REPORT, text)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--final', action='store_true')
    a = p.parse_args(); run(a.final)
