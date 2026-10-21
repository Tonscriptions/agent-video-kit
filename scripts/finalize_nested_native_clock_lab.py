"""Bind the independent nested VFR experiment, current proofs and honest docs."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
REL = 'docs/validation/evidence/nested-native-clock-20261021-lab'
ASSETS = 'docs/assets/nested-native-clock-20261021-lab'
REPORT = 'docs/validation/嵌套原生VFR时钟独立实验_2026-10-21.md'
CONTRACT = 'docs/specs/嵌套原生VFR时钟契约_实验_v0.1_2026-10-21.md'


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + '\n', encoding='utf8', newline='\n')


def save(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / REL) and not output.exists()
    record = {'status': 'auditing', 'full_regression_executed': False, 'main_integrated': False,
              'full_capcut_parity': False}
    save(output, record)
    try:
        current = frozen()
        assert len(current) == 255
        base = ROOT / REL
        foundation = read(base / 'foundation-r1.json')
        previous = foundation['source_inputs']
        assert len(previous) == 254
        added = set(current) - set(previous)
        modified = {name for name in previous if previous[name] != current[name]}
        assert added == {'product/tests/test_nested_native_clock.py'}
        assert modified == {'product/src/ai_ad_editor/' + name + '.py'
                            for name in ('capabilities', 'render', 'reverse_video_clock')}
        related = read(base / 'related-r1.json')
        assert related['status'] == 'passed-related-regressions' and related['distinct_methods'] == 277
        assert related['frozen_before'] == related['frozen_after'] == current and related['skipped'] == 0
        assert len(set(related['method_ids'])) == len(related['method_ids']) == 277
        assert {name: row['methods'] for name, row in related['families'].items()} == {
            'index': 37, 'reverse': 50, 'sequence': 63, 'preview': 22, 'nested': 105}
        for name, digest in related['script_hashes'].items():
            assert sha(ROOT / 'scripts' / name) == digest, name
        for name, row in related['families'].items():
            path = base / (name + '-final-r1.json')
            item = read(path)
            assert item['status'] == 'passed' and item['terminal_ok'] and item['skipped'] == 0
            assert item['methods'] == row['methods'] and sha(path) == row['evidence_sha256']
            assert item['frozen_before'] == item['frozen_after'] == current
            assert item['external_fixture_count'] == 8 and item['external_fixtures_equal']
            assert item['external_fixture_manifest_unchanged'] and item['verification_scripts_equal']
            inner = read(path.with_name(path.stem + '.source.json'))
            assert sha(path.with_name(path.stem + '.source.log')) == inner['log_sha256']
        clock = read(base / 'final-native-clock-r1.json')
        assert clock['terminal_ok'] and clock['methods'] == 32 and clock['skipped'] == 0
        assert clock['frozen_before'] == clock['frozen_after'] == current
        assert sha(base / 'final-native-clock-r1.log') == clock['log_sha256']
        native = read(base / 'native-r4/verification.json')
        installed = read(base / 'installed-r1/verification.json')
        isolated = read(base / 'installed-r1/media/verification.json')
        for value in (native, installed, isolated):
            assert value['status'] == 'passed' and value['frozen_before'] == value['frozen_after'] == current
            assert all(row['ok'] for row in value['checks'])
        assert native['cli_calls'] == isolated['cli_calls'] == 16
        assert native['native_commands'] == isolated['native_commands'] == 26
        assert len(native['checks']) == len(isolated['checks']) == 22
        assert installed['isolated_cli_calls'] == 19 and installed['module_origin_probes'] == 1
        assert len(installed['resource_hashes']) == 161
        for name, digest in installed['resource_hashes'].items():
            assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest
        assert sha(ROOT / 'scripts/smoke_nested_native_clock.py') == sha(base / 'native-r4/executed-smoke.py.txt')
        assert sha(ROOT / 'scripts/smoke_nested_native_clock.py') == sha(base / 'installed-r1/media/executed-smoke.py.txt')
        assert sha(ROOT / 'scripts/verify_nested_native_clock_install.py') == sha(base / 'installed-r1/executed-install.py.txt')
        media = {}
        gifs = {}
        for value in (native, isolated):
            for name, digest in value['assets'].items():
                path = ROOT / name
                assert sha(path) == digest
                media[name] = {'sha256': digest, 'bytes': path.stat().st_size}
                if path.suffix == '.gif':
                    with Image.open(path) as image:
                        total = 0
                        for n in range(image.n_frames):
                            image.seek(n)
                            total += image.info.get('duration', 0)
                        gifs[name] = {'frames': image.n_frames, 'duration_ms': total}
        assert len(media) == 28 and len(gifs) == 6
        for name, row in native['cases'].items():
            other = isolated['cases'][name]
            assert row['frames'] == 45 and row['fps'] == '30000/1001'
            assert row['preview_bytes'] == 10368000 and row['preview_max_RGBA_error'] == 0
            assert row['preview_sha256'] == other['preview_sha256']
            assert row['expected_source_frame_ids'] == row['encoded_source_frame_ids'] == other['encoded_source_frame_ids']
        upstream = Path(foundation['source'])
        patch = []
        for name in sorted(modified):
            assert sha(upstream / name) == previous[name], name
            patch.extend(difflib.unified_diff((upstream / name).read_text('utf8').splitlines(keepends=True),
                         (ROOT / name).read_text('utf8').splitlines(keepends=True), fromfile='a/' + name, tofile='b/' + name))
        for name in sorted(added):
            patch.extend(difflib.unified_diff([], (ROOT / name).read_text('utf8').splitlines(keepends=True),
                         fromfile='/dev/null', tofile='b/' + name))
        write(base / 'runtime-and-oracle.patch', ''.join(patch))
        table = '''| 编号 | 实际检查 | 结果与边界 | 证据 |
|---|---|---|---|
| NC-E01 | 原问题与控制组 | 普通嵌套 7 项通过；加入语义相同的常速曲线后，8 项中的 1 项失败，输出第 0、8、25 帧选错源帧。7 ms 原生区间被预先 CFR 化丢失 | [原基线失败](evidence/nested-native-clock-20261021-lab/before-r3.json) · [原 7 项](evidence/nested-native-clock-20261021-lab/before-r2.json) |
| NC-E02 | 修复过程留档 | 首次修复 8 项中 2 项因 origin_text 引用遗漏出错，修正后同 8 项通过；后续 16、26 和旧版 99 方法的源码分别留档，不重复计数 | [首轮错误](evidence/nested-native-clock-20261021-lab/after-r1.json) · [修正 8 项](evidence/nested-native-clock-20261021-lab/after-r2.json) · [旧 99 项](evidence/nested-native-clock-20261021-lab/nested-r1.json) |
| NC-E03 | 当前新增逐帧时钟参考 | 32 项、0 跳过；60 位 Decimal 独立逆积分，单层/两层非线性、父/子/双重/三重倒放、5.117123 s 封装偏移、7 ms 区间、真实短视频 EOF；每输出帧全部 RGBA 字节核对 | [32 项](evidence/nested-native-clock-20261021-lab/final-native-clock-r1.json) |
| NC-E04 | 当前相邻回归 | 277 个不同方法、0 跳过：索引 37、倒放 50、序列 63、预览 22、嵌套 105。32 项属于 105 的子集；255 产品输入和 8 外部夹具不变 | [总收据](evidence/nested-native-clock-20261021-lab/related-r1.json) · [嵌套 105](evidence/nested-native-clock-20261021-lab/nested-final-r1.json) |
| NC-E05 | 公开 CLI/原生样例 | 16 CLI 属于 26 原生命令，22 检查；两段实际成片各 45 帧、30000/1001 fps，无损预览各 10,368,000 字节且 RGBA 误差 0；二次渲染索引扫描 0 次 | [原生实测](evidence/nested-native-clock-20261021-lab/native-r4/verification.json) |
| NC-E06 | 离线隔离发行 | 161 资源源码/wheel/site 字节一致、7 个现有 wheels；19 隔离 CLI＋1 来源进程，11 模块位于安装目录；两段完整无损预览哈希/成片帧编号与开发版相同 | [隔离安装](evidence/nested-native-clock-20261021-lab/installed-r1/verification.json) |
| NC-E07 | 样例脚本失败留档 | 首轮工程外输出被拒绝；第三轮误把同一索引描述符在两处元数据中的重复出现当作两次调用。修正为工程内输出和完整相同描述符去重；产品断言/阈值未放宽 | [路径拒绝](evidence/nested-native-clock-20261021-lab/native-r1/verification.json) · [元数据计数错误](evidence/nested-native-clock-20261021-lab/native-r3/verification.json) |
| NC-E08 | 版本差异与状态 | 对帧索引实验 254 输入，仅修改 render/reverse_video_clock/capabilities，新增一个 32 方法文件；未运行该版本完整套件、未合入 main、未推送此实验 | [来源](evidence/nested-native-clock-20261021-lab/foundation-r1.json) · [完整差异](evidence/nested-native-clock-20261021-lab/runtime-and-oracle.patch) |
| NC-E09 | 验收边界 | 中间合成表面保留子级 CFR；一般嵌套 VFR 效果组合、长片延迟、总 RSS、自然/HDR/音频质量和完整剪映等价尚未验收 | [实验契约](../specs/嵌套原生VFR时钟契约_实验_v0.1_2026-10-21.md) |'''
        gallery = '''| 原输入编码观看副本 | 实际正放成片 | 实际曲线倒放成片 |
|---|---|---|
| [原生 NUT](../assets/nested-native-clock-20261021-lab/native-r4/source-native-vfr.nut) · [MP4 副本](../assets/nested-native-clock-20261021-lab/native-r4/source-review.mp4) | [实际 MP4](../assets/nested-native-clock-20261021-lab/native-r4/forward-short-hold.mp4) | [实际 MP4](../assets/nested-native-clock-20261021-lab/native-r4/reverse-ramp.mp4) |
| ![原创源帧预览](../assets/nested-native-clock-20261021-lab/native-r4/source.gif) | ![实际正放成片](../assets/nested-native-clock-20261021-lab/native-r4/forward-short-hold.gif) | ![实际倒放成片](../assets/nested-native-clock-20261021-lab/native-r4/reverse-ramp.gif) |

源 GIF 来自独立生成的源帧卡片，12 帧/1840 ms；两段输出 GIF 来自实际 MP4 解码，分别 7/9 帧（重复帧合并）及 1500 ms，采用 10 ms 时间格。精确 7 ms 源区间以原生 NUT、逐帧 PTS 和全部像素对照为准。成片 MP4 各 45 帧，有损编码身份采样处最大 RGBA 误差实测为 1；不宣称编码成片整帧像素相等。

[正放 45 帧总览](../assets/nested-native-clock-20261021-lab/native-r4/forward-short-hold-all-frames.png) · [倒放 45 帧总览](../assets/nested-native-clock-20261021-lab/native-r4/reverse-ramp-all-frames.png) · [可编辑正放请求](../assets/nested-native-clock-20261021-lab/native-r4/forward-short-hold-request.json) · [可编辑倒放请求](../assets/nested-native-clock-20261021-lab/native-r4/reverse-ramp-request.json) · [CC0 来源和哈希](../assets/nested-native-clock-20261021-lab/native-r4/rights.json)。
'''
        report = '''# 嵌套原生 VFR 时钟独立实验（2026-10-21）

状态：**当前 277 个不同专项方法通过，尚未执行该版本完整回归、尚未合入 main。** 先前 7、8、16、26、99 方法属于其各自源码阶段；不相加，也不替代当前源码的 277 项。

''' + table + '\n\n' + gallery + '''
普通原生视频叶片保留原始 PTS/duration，并输入现有解析嵌套时间映射；正放和倒放共用原生源区间选取，倒放共用已有缓冲/分块助手。没有新增作者字段或改写作者/权利账本。首次与二次渲染分别记录源时间索引扫描 1/0 次；后者仍有源/程序 SHA 读取、最终视频解码和编码。

所有样例使用本机原生 Windows、FFmpeg 和现有离线 wheelhouse；无下载、云调用、Docker、WSL、容器或虚拟环境。未做连续播放或听音检查，无新模型推理。原生卡片与无损参考的数值结论不代表自然画面或 HDR 质量。

[独立审计](evidence/nested-native-clock-20261021-lab/''' + output.name + ''') 绑定当前 255 个产品输入、五组回归、161 个发行资源、28 个最终公开样例文件和 6 个 GIF。
'''
        write(ROOT / REPORT, report)
        old_contract = (ROOT / CONTRACT).read_text('utf8')
        note = '\n当前验收：277 个不同专项方法、0 跳过；32 项独立原生帧参考包含在嵌套 105 项中。公开 CLI 与离线隔离证明分别记录；此版本完整回归、合入和推送仍未执行。\n'
        assert '当前验收：277' not in old_contract
        write(ROOT / CONTRACT, old_contract + note)
        root_table = table.replace('](evidence/', '](docs/validation/evidence/').replace('](../specs/', '](docs/specs/')
        root_gallery = gallery.replace('](../assets/', '](docs/assets/')
        write(ROOT / 'README.md', '# 嵌套原生 VFR 时钟独立实验\n\n277 个不同专项方法通过；255 个产品输入不变，尚未完整回归或合入 main。\n\n'
              + root_table + '\n\n' + root_gallery + '\n[完整记录](' + REPORT + ') · [实验契约](' + CONTRACT + ')')
        links = []
        for name in ('README.md', REPORT, CONTRACT):
            path = ROOT / name
            for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)', path.read_text('utf8')):
                target = token.strip('<>').split('#', 1)[0]
                if not target or re.match(r'^[a-zA-Z][\w+.-]*:', target):
                    continue
                resolved = (path.parent / target).resolve()
                assert resolved.is_relative_to(ROOT) and resolved.is_file(), (name, token)
                links.append({'document': name, 'target': resolved.relative_to(ROOT).as_posix()})
        assert frozen() == current
        record.update(status='passed-standalone-audit', targeted_methods=277, new_clock_methods=32,
            frozen_inputs=current, source_wheel_installed_resources=161, public_native_cli_calls=16,
            public_native_commands=26, public_native_checks=22, isolated_cli_calls=19,
            module_origins=11, source_parent_inputs=previous, modified_inputs=sorted(modified), added_inputs=sorted(added),
            media=media, GIF=gifs, local_links=links,
            documents={name: sha(ROOT / name) for name in ('README.md', REPORT, CONTRACT)},
            generator_sha256=sha(Path(__file__)))
    except BaseException as error:
        record.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        save(output, record)
        print(json.dumps({k: record.get(k) for k in ('status', 'targeted_methods', 'source_wheel_installed_resources', 'error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
