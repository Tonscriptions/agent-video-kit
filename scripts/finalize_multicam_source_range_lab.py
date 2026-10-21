"""Document and audit the bounded camera-coverage experiment and its limits."""
from __future__ import annotations
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
from PIL import Image
from run_frozen_regression import frozen
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = 'docs/validation/evidence/multicam-source-range-20261021-lab'
ASSETS = 'docs/assets/multicam-source-range-20261021-lab'
REPORT = 'docs/validation/多机位源覆盖与原速同步独立实验_2026-10-21.md'
CONTRACT = 'docs/specs/多机位源覆盖与显式缺口策略_实验_v0.1_2026-10-21.md'


def read(path): return json.loads(Path(path).read_bytes())


def markdown(path, text):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf8', newline='\n')


def main():
    base = ROOT / REL
    output = base / 'audit-r1.json'
    assert not output.exists()
    current = frozen()
    assert len(current) == 257
    before = read(base / 'before-r1.json')
    after = read(base / 'after-r3.json')
    compatibility = read(base / 'compatibility-r2.json')
    assert before['methods'] == 3 and not before['terminal_ok'] and before['frozen_equal']
    assert (base / 'before-r1.log').read_text('utf8').count(' ... FAIL') == 2
    for value, count in ((after, 22), (compatibility, 1)):
        assert value['terminal_ok'] and value['methods'] == count and value['skipped'] == 0
        assert value['frozen_before'] == value['frozen_after'] == current and value['frozen_equal']
    assert sha(base / 'after-r3.log') == after['log_sha256']
    assert sha(base / 'compatibility-r2.log') == compatibility['log_sha256']
    native = read(base / 'native-r1/verification.json')
    installed = read(base / 'installed-r1/verification.json')
    isolated = read(base / 'installed-r1/media/verification.json')
    for value in (native, installed, isolated):
        assert value['status'] == 'passed' and value['frozen_before'] == value['frozen_after'] == current
        assert all(row['ok'] for row in value['checks'])
    assert native['cli_calls'] == isolated['cli_calls'] == 15
    assert native['native_commands'] == isolated['native_commands'] == 11
    assert len(native['checks']) == len(isolated['checks']) == 23
    assert installed['isolated_cli_calls'] == 18 and installed['module_origin_probes'] == 1
    assert len(installed['checks']) == 12 and native['cases'] == isolated['cases']
    assert len(installed['resource_hashes']) == 161
    for name, digest in installed['resource_hashes'].items():
        assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
    addon = installed['optional_numpy_addon']
    assert addon['version'] == '2.4.2' and len(addon['files']) == 933 and not addon['base_seven_wheel_bundle_contains_numpy']
    site = ROOT / 'product/.runtime/multicam-source-range-20261021/installed-r1/installed/site'
    for name, row in addon['files'].items():
        assert sha(site / name) == row['sha256'] and (site / name).stat().st_size == row['bytes']
    media = {**native['media'], **isolated['media']}
    assert len(native['media']) == len(isolated['media']) == 11 and len(media) == 22
    gifs = {}
    for name, row in media.items():
        path = ROOT / name
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
        if path.suffix == '.gif':
            with Image.open(path) as image:
                total = 0
                for index in range(image.n_frames):
                    image.seek(index)
                    total += image.info.get('duration', 0)
                gifs[name] = {'frames': image.n_frames, 'duration_ms': total}
    assert len(gifs) == 8
    sheet = ROOT / ASSETS / 'native-r1/trim-event-boundaries.png'
    installed_sheet = ROOT / ASSETS / 'installed-r1/trim-event-boundaries.png'
    assert sha(sheet) == sha(installed_sheet)
    write(base / 'frame-review-r1.json', {'status': 'reviewed-static-native-contact-sheet',
        'native_sheet': sheet.relative_to(ROOT).as_posix(), 'sha256': sha(sheet),
        'observed': 'black at frames 0/9 and 46/49; generated event IDs 10/20/25/45 at their authored positions',
        'installed_sheet_byte_equal': True, 'continuous_playback_reviewed': False,
        'audio_listened': False, 'natural_footage_accepted': False})
    foundation = read(base / 'foundation-r1.json')
    parent = foundation['source_inputs']
    assert len(parent) == 256 and set(current) - set(parent) == {'product/tests/test_multicam_source_range.py'}
    modified = {name for name in parent if parent[name] != current[name]}
    assert modified == {'product/src/ai_ad_editor/' + name + '.py' for name in ('multicam', 'cli', 'capabilities')}
    patch = []
    for name in sorted(modified):
        old = ROOT.parent / 'native-empty-window-lab-20261021' / name
        assert sha(old) == parent[name]
        patch.extend(difflib.unified_diff(old.read_text('utf8').splitlines(True), (ROOT / name).read_text('utf8').splitlines(True), fromfile=name+'@parent', tofile=name+'@candidate'))
    markdown(REL + '/runtime-r1.patch', ''.join(patch))
    drafts = read(base / 'skills-draft-r1.json')
    assert drafts['status'] == 'passed-four-unregistered-drafts' and drafts['skill_count'] == 4 and not drafts['registered']
    for name, row in drafts['skills'].items():
        assert row['validator_exit_code'] == 0 and not row['registered']
        assert sha(ROOT / row['path']) == row['sha256']
        assert sha(ROOT / row['parent_snapshot']) == sha(MAIN / 'skills' / name / 'SKILL.md') == row['parent_sha256']

    table = f'''| 编号 | 实际核验 | 结果与证据 |
|---|---|---|
| MC-01 | 修复前复现 | 3 个方法：1 个完整覆盖控制通过，2 个部分覆盖断言失败；旧代码自动钳制源起点或慢放，改变事件同步。[原始失败]({REL}/before-r1.json) |
| MC-02 | 当前专项 | 22 项 / {after['suite_seconds']:.3f} 秒 /0 跳过，包含最初 3 项；15 个规划方法与 7 个实际双机位 CLI/渲染方法。[当前收据]({REL}/after-r3.json) |
| MC-03 | 既有兼容控制 | 原有 AAC 延迟 0.5 秒、按 1 秒轮换及应用快照控制 1 项 / {compatibility['suite_seconds']:.3f} 秒；与上行合计 23 个不同方法。[收据]({REL}/compatibility-r2.json) |
| MC-04 | 公开 CLI | 15 次 CLI＋11 条其他原生命令，26 条执行命令、23 个检查；原生源 50 帧/2 秒，相机 B 36 帧/1.44 秒。[完整 argv 与检查]({REL}/native-r1/verification.json) |
| MC-05 | 默认拒绝与显式 trim | 同一原始事件覆盖 0.4..1.84 秒；默认拒绝不写项目/报告/快照，trim 保留 1 倍速，前 10 帧和后 4 帧留空。[原输入]({ASSETS}/native-r1/source-reference.mkv) · [短机位]({ASSETS}/native-r1/source-camera.mkv) |
| MC-06 | 完整画面/PCM/PTS | 无损预览 50 帧、11,520,000 RGBA 字节与独立原始帧卡逐字节相同；显式主音轨 768,000 f32 字节、每声道 96,000 样本完全相同；两个 MP4 的全部 50 个 PTS 均为 n/25。[无损原文件]({ASSETS}/native-r1/trim-lossless.nut) |
| MC-07 | 显式 stretch | 仅显式选择后保留旧填充行为；0.72 倍速把短机位填满 2 秒，并警告事件同步改变。实际第一帧显示事件 10，替代原本空档；不能作为同步正确的结果。[实际 MP4]({ASSETS}/native-r1/stretch.mp4) |
| MC-08 | 应用边界 | 锁轨在音频分析前拒绝；dry-run 做音频分析但不写项目/报告；小于一个时间刻度的片段拒绝，不虚构 1 tick；原计划重叠不会因裁切而放行，较长作者时长保留。[专项]({REL}/after-r3.log) |
| MC-09 | 实际隔离安装 | 161 产品资源 source/wheel/site 相同；基础 7 wheels，另按现有 NumPy 2.4.2 安装 RECORD 复制 933 文件到 E 盘。18 次隔离 CLI＋1 来源进程/14 模块、12 安装检查，再通过同样 23 媒体检查。[安装与附加依赖]({REL}/installed-r1/verification.json) |
| MC-10 | 可视证据与 Skill | 原生/隔离共 22 文件、8 GIF；输出 GIF 从实际 MP4 解码。查看一张边界联系表，隔离图与其字节相同。4 份 video-cut Skill 草稿通过 quick_validate，尚未注册。[静态目检]({REL}/frame-review-r1.json) · [草稿]({REL}/skills-draft-r1.json) |
| MC-11 | 保留开发失败 | 扩展初轮 22 项中 4 失败/3 错误：发现 CLI 声称接受数组却调用仅对象 loader 的真实问题，另修复测试对 errors 数组的访问。原源码和日志保留；兼容控制首轮收据未识别单数 test，r2 修复并重跑。[失败原文]({REL}/after-r2.log) · [保全输入]({REL}/after-r2-failed-inputs/sha256.json) |
| MC-12 | 尚未验收/发布 | 此候选未执行完整回归、未合入 main、未推送或注册 Skill。无漂移估计、视觉/发言人导演；container duration 不代表视频流真实 EOF。长片、密集切换、峰值 RSS、自然/HDR、听审与完整剪映等价均未验收。父候选更新旧 CLI 时钟断言后仍需显式变基与新冻结收据。 |
'''
    gallery = f'''| 原始事件 | 实际 trim 原速留空 | 实际显式 stretch |
|---|---|---|
| ![原始事件]({ASSETS}/native-r1/source-reference.gif) | ![实际 trim]({ASSETS}/native-r1/trim.gif) | ![实际 stretch]({ASSETS}/native-r1/stretch.gif) |

[原始 MKV]({ASSETS}/native-r1/source-reference.mkv) · [实际 trim MP4]({ASSETS}/native-r1/trim.mp4) · [实际 stretch MP4]({ASSETS}/native-r1/stretch.mp4) · [边界联系表]({ASSETS}/native-r1/trim-event-boundaries.png)。原始 GIF 50 帧/2000 ms、短机位 36 帧/1440 ms；实际 trim GIF 合并为 38 帧/2000 ms，stretch 为 36 帧/2000 ms。
'''
    context = '''这是独立候选。只在 Windows 原生工具上执行，所有新内容留在 E 盘；没有 Docker、WSL、容器、虚拟环境、浏览器调用或依赖下载。

同步仍为既有 50 Hz 能量包络的有界互相关。固定源公式为 `source_time = reference_time + relative_delay_seconds`。本轮修复的是覆盖缺失时如何规划素材，不改变同步估计算法，也不估计长片设备时钟漂移。`0.2.0` 为多机位局部协议版本，CLI 总版本保持原状。

NumPy 附加复制是本轮实验安装步骤，不是已发布的用户安装器功能；基本七 wheel 包没有 NumPy。原生和隔离程序分别实际执行，父进程的 Pillow 仅用于生成/检查证据。没有使用系统 Python 路径代替隔离产品模块。生成的声道为合成音，不以完整 PCM 相等声称声音自然或已听审。

独立 RGBA/PCM 参考来自源帧卡和确定性合成音。编码 MP4 只核验帧身份色块和 PTS；不声称完整编码 RGBA/PCM 相等。GIF 为观看副本，声音以视频/原始文件为准，未连续播放或听音。
'''
    index = '# 多机位源覆盖与原速同步独立候选\n\n**状态：专项与真实 CLI/隔离实验通过，完整回归、变基与 main 发布待完成。**\n\n' + context + '\n' + table + '\n' + gallery + f'\n[契约]({CONTRACT}) · [完整实验]({REPORT})\n'
    markdown('README.md', index)
    report = '# 多机位源覆盖与原速同步独立实验（2026-10-21）\n\n' + context + '\n' + table + '\n' + gallery
    report = report.replace('](' + REL + '/', '](evidence/multicam-source-range-20261021-lab/').replace('](' + ASSETS + '/', '](../assets/multicam-source-range-20261021-lab/')
    markdown(REPORT, report)
    contract = '''# 多机位源覆盖与显式缺口策略（实验 v0.1，2026-10-21）

本契约仅由独立实验支撑，尚未完整回归、变基、合入 main 或注册 Skill；多机位局部协议 0.2.0。

| 编号 | 约束 |
|---|---|
| MC-C01 | 参考时刻 r 对应源时刻 r＋relative_delay_seconds；沿用既有单偏移估计，不做仿射漂移或非线性时间扭曲。 |
| MC-C02 | source_shortfall 默认 reject；请求源区间越过 [0, container_duration] 超出 1e-9 秒数值容差时拒绝，不自动钳制或慢放。 |
| MC-C03 | 显式 trim 取参考区间与 [-delay, container_duration-delay] 的交集，speed=1，按原参考事件放置并留空；记录原请求与实际覆盖边界。 |
| MC-C04 | 与源覆盖完全不相交时三种策略均拒绝，不补帧、不替换相机、不跳过缺失段。 |
| MC-C05 | 显式 stretch 采用旧钳制/慢放填满策略，任何覆盖缺失都输出 MULTICAM_SOURCE_CLOCK_CHANGED；允许变更事件同步的含义必须保留。 |
| MC-C06 | 本地 switch_plan 支持数组和 {segments:[...]}；按原请求检查顺序与重叠，不能用裁切后的间隙掩盖请求重叠。 |
| MC-C07 | apply（含 dry-run）在分析前拒绝锁轨和非视频轨；dry-run 可解码音频分析，但不写作者项目、同步报告或应用快照。 |
| MC-C08 | 秒字段保留 6 位小数，按项目 TPS 四舍五入；源/输出区间小于一个 tick 则拒绝，不能强制变成 1 tick。此策略不保证亚 tick 连续精度。 |
| MC-C09 | 应用后保留原作者时长，并至少覆盖 timeline_start＋end-start；主音轨须显式创作，视频轨不会自动提取或切换音频。缺口显示下层或背景。 |
| MC-C10 | 核心离线包 7 wheels 不含 NumPy。本轮仅复制现有 2.4.2 RECORD 内的包、numpy.libs 与 metadata；保留许可、验证文件哈希并在 E 盘隔离加载，无下载/全局安装。 |
| MC-C11 | 本轮图像范围为原创 320×180/25 fps/2 秒；短机位 .4..1.84 秒。完整无损 RGBA、显式主音轨 PCM、编码帧身份/PTS 与静态目检分别验收。 |
| MC-C12 | container duration 不是每流真实 EOF；偏移置信度、非零 A/V 原点、设备漂移、自然素材、HDR、密集切换、长片/RSS 与听审未验收。未达到完整剪映等价。 |

[完整实验、失败与原视频/GIF](../validation/多机位源覆盖与原速同步独立实验_2026-10-21.md)。
'''
    markdown(CONTRACT, contract)
    documents = {}
    links = []
    for name in ('README.md', REPORT, CONTRACT):
        path = ROOT / name
        documents[name] = sha(path)
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text('utf8')):
            if target.startswith(('http:', 'https:')): continue
            selected = (path.parent / target.split('#', 1)[0]).resolve()
            assert selected.is_relative_to(ROOT) and selected.exists(), (name, target)
            links.append({'document': name, 'target': target})
    for name, row in drafts['skills'].items():
        path = ROOT / row['path']
        for target in re.findall(r'\]\(([^)]+)\)', row['new_block']):
            selected = (path.parent / target).resolve()
            assert selected.is_relative_to(ROOT) and selected.exists(), (name, target)
            links.append({'document': row['path'], 'target': target})
    record = {'status': 'passed-bounded-lab-audit', 'frozen_inputs': current, 'source_parent_inputs': parent,
        'modified_inputs': sorted(modified), 'added_inputs': ['product/tests/test_multicam_source_range.py'],
        'current_targeted_methods': 22, 'existing_compatibility_methods': 1, 'distinct_methods': 23,
        'public_cli_calls': 15, 'other_native_commands': 11, 'public_checks': 23,
        'isolated_cli_calls': 18, 'module_origin_processes': 1, 'module_origins': 14,
        'source_wheel_installed_resources': 161, 'base_bundle_wheels': 7, 'optional_numpy_version': '2.4.2',
        'optional_numpy_copied_files': 933, 'media': media, 'GIF': gifs, 'local_links': links, 'documents': documents,
        'skill_drafts': 4, 'skills_registered': False, 'full_suite_executed': False, 'main_integrated': False,
        'published': False, 'full_capcut_parity': False, 'parent_contract_refresh_rebase_pending': True,
        'generator_sha256': sha(__file__), 'audited_at_utc': datetime.now(timezone.utc).isoformat()}
    write(output, record)
    print(json.dumps({'status': record['status'], 'distinct_methods': 23, 'frozen_inputs': len(current),
        'media': len(media), 'GIF': len(gifs), 'local_links': len(links), 'registered': False}))


if __name__ == '__main__':
    main()
