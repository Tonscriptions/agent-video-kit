"""Prepare the multicamera publisher from the reviewed native release pipeline."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
DONOR = MAIN / 'product/.runtime/native-empty-window-lab-20261021'
REL = 'docs/validation/evidence/multicam-source-range-20261021-lab'
TARGET = ROOT / 'scripts/publish_multicam_source_range.py'


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def function(source, name):
    node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == name)
    return '\n'.join(source.splitlines()[node.lineno - 1:node.end_lineno])


DOCUMENTS = r"""def documents(root,full):
    seconds=full['suite_seconds']
    message=(f'V86 多机位源覆盖策略已完成 {full["methods"]} 方法、{seconds:.3f} 秒、0 跳过的完整回归；'
        '257 个冻结输入、8 个已提交外部夹具及 10 份验证脚本前后相同。'
        '默认拒绝源覆盖不足，显式 trim 保持原速并保留参考事件位置和缺口；stretch 明示事件时钟改变。')
    def link(document,target):
        return os.path.relpath(root/target,(root/document).parent).replace('\\','/')
    rows=[
        ('V86-01','完整回归',f'当轮 {full["methods"]} 方法 /{seconds:.3f} 秒 /0 跳过，冻结 257 输入、8 夹具及 10 验证脚本。',REL+'/full-r1.json'),
        ('V86-02','关联回归','当轮候选 80 个不同方法：22 多机位＋16 空选区＋32 嵌套时钟＋10 既有 CLI；为完整回归子集。',REL+'/related-r1.json'),
        ('V86-03','真实原生 CLI','15 次 CLI＋11 条其他原生命令，23 检查；2 秒 /25 fps /50 帧原创参考，短机位 .4..1.84 秒。',REL+'/native-r1/verification.json'),
        ('V86-04','完整无损帧和显式主音轨','50 帧、11,520,000 RGBA 字节及 768,000 PCM 字节 /每声道 96,000 采样与独立生成参考完全相同；两端缺口均核验。',REL+'/native-r1/verification.json'),
        ('V86-05','编码输出与静态目检','trim/stretch 各 50 帧、全部 PTS=n/25；trim 帧身份色块实测最大误差 1。联系表已静态查看；未连续播放或听审。',REL+'/frame-review-r1.json'),
        ('V86-06','隔离发行与 NumPy 边界','161 资源、7 基础 wheels；另将现有 NumPy 2.4.2 的 933 个 RECORD 文件复制至隔离 E 盘 site。18 次隔离 CLI＋1 次来源探针 /14 模块、12 安装检查。基础包未新增 NumPy。',REL+'/installed-r1/verification.json'),
        ('V86-07','失败、变基与未重跑声明','初次 22 方法 4 FAIL /3 ERROR、数组加载修复及单数 test 解析失误保留。后续仅继承未打包的父 test_cli.py；原媒体/隔离结果保留原冻结图，161 运行时资源相同，未冒称重跑。',REL+'/audit-r2.json'),
        ('V86-08','契约、Skills 与局限','4 份 Skill 只追加本轮指导，全部 17 份再审。单偏移、容器时长边界；设备漂移、每流真实 EOF、自然/HDR/长片/RSS/听审及完整剪映等价未验收。',CONTRACT),
    ]
    for document in LATEST_DOCS:
        table='| 编号 | 核验 | 实际结果及边界 | 证据 |\n|---|---|---|---|\n'
        table+='\n'.join('| '+identifier+' | '+title+' | '+result+' | [记录]('+link(document,target)+') |' for identifier,title,result,target in rows)
        gallery=''
        if document=='README.md':
            gallery=('\n\n原创参考（50 帧 /2000 ms，色卡与确定性音频；非自然机位素材）：\n\n'
                '![V86 原创参考]('+ASSETS+'/native-r1/source-reference.gif)\n\n'
                '实际 trim 输出（GIF 合并为 38 帧 /2000 ms；前后缺口显示背景）：\n\n'
                '![V86 原速留空]('+ASSETS+'/native-r1/trim.gif)\n\n'
                '实际 stretch 输出（GIF 合并为 36 帧 /2000 ms；作为改变同步的显式对照）：\n\n'
                '![V86 显式拉伸对照]('+ASSETS+'/native-r1/stretch.gif)\n\n'
                '[参考原视频]('+ASSETS+'/native-r1/source-reference.mkv) · '
                '[短机位原视频]('+ASSETS+'/native-r1/source-camera.mkv) · '
                '[实际 trim MP4]('+ASSETS+'/native-r1/trim.mp4) · '
                '[实际 stretch MP4]('+ASSETS+'/native-r1/stretch.mp4) · '
                '[源摘要和 CC0 记录]('+ASSETS+'/native-r1/source-origin.json)。'
                'GIF 仅为实际 MP4 的观看副本，不含音频；有损 MP4 不宣称完整 RGBA/PCM 字节相同。')
        block(root/document,'### V86 多机位源覆盖与原速事件同步\n\n'+message+'\n\n'+table+gallery+
            '\n\n[完整实测]('+link(document,REPORT)+')。80 项与原生/隔离检查分别报告，不累计成额外完整方法或剪映等价。')
    report='# 多机位源覆盖与原速同步实测（V86，2026-10-21）\n\n'+message+'\n\n'
    report+='| 编号 | 核验 | 实际结果及边界 | 证据 |\n|---|---|---|---|\n'
    report+='\n'.join('| '+identifier+' | '+title+' | '+result+' | [记录]('+link(REPORT,target)+') |' for identifier,title,result,target in rows)
    report+='\n\n'+'''相对偏移沿用 50 Hz 有界音频包络匹配；参考时刻 r 对应源时刻 r＋relative_delay_seconds。本例偏移 -0.4 秒，参考视频有 50 帧，短机位取 .4..1.84 秒共 36 帧。trim 的作者时间线保留 2 秒：前 10 帧背景、原参考 10..45 帧、后 4 帧背景。完整无损 RGBA 与独立生成的原色卡逐字节比较；显式主音轨的完整立体声 float32 PCM 与生成参考比较，不以是否存在音频流代替采样验收。

视频轨不会自动提取机位音频，调用者须明确选择并创作主音轨。数组和 {segments:[...]} 计划均可用；原请求顺序/重叠、锁轨、dry-run 无作者/报告/快照写入、亚 tick 拒绝和保留原较长作者时长分别检查。完全不相交的区间三种策略均拒绝。显式 stretch 在本例 speed=.72，填满缺口而改变事件位置；保留 MULTICAM_SOURCE_CLOCK_CHANGED 警告，不能称为原速同步。

原 22 方法、兼容性 1 方法以及媒体/安装记录是原实际执行。父版更新只改变未打包的 test_cli.py，当前 257 输入上的 80 方法已重新执行；原媒体/隔离结果仍标记原冻结图，161 运行时资源逐字节相同。随后完整 1995 方法以当前 257 输入执行；80 方法是其子集。兼容性 r1 的 unittest 本身通过，但外层解析器漏认单数 test；该外层失败保留，r2 才是有效接收记录。新增测试最初暴露数组加载错误及测试自身错误字段预期，原失败和源码同样保留。

隔离实验从现有本地 NumPy 2.4.2 的 RECORD 复制 933 个包、numpy.libs 和 metadata 文件，核对原 RECORD 哈希并保留许可；跳过外部 Scripts 和 pycache。所有写入在 E 盘，C 盘源仅只读，没有下载或全局安装。7 wheels 基础离线包并不包含 NumPy；本次不把实验性附加拷贝写成产品安装器的新功能。来源探针包含 NumPy 原生扩展，14 模块均从隔离 site 加载。

只接受原创 320×180、25 fps、2 秒生成素材的限定功能结果。偏移置信度、设备时钟漂移、非零 A/V 原点、自然多机位、每流真实 EOF、HDR、密集切换、长片吞吐、总 RSS、连续播放和听审仍待独立验收；没有完成完整剪映功能或效果等价。容器时长不能替代视频流的真实覆盖终点。

22 个资产、8 个 GIF 包含原生与隔离两组实际素材。联系表做过静态目检；没有伪称连续播放、听审或模型推理。所有素材为本地生成，CC0 与 SHA 随源记录保留。原生 Windows 执行，无 Docker、WSL、容器或虚拟环境。
'''
    report+='\n[原始实验与保留失败]('+link(REPORT,HISTORICAL_REPORT)+') · [契约]('+link(REPORT,CONTRACT)+')\n\n'
    report+='[原创参考]('+link(REPORT,ASSETS+'/native-r1/source-reference.mkv')+') · '
    report+='[实际 trim MP4]('+link(REPORT,ASSETS+'/native-r1/trim.mp4')+') · '
    report+='[实际 stretch MP4]('+link(REPORT,ASSETS+'/native-r1/stretch.mp4')+')\n\n'
    report+='![实际 trim GIF]('+link(REPORT,ASSETS+'/native-r1/trim.gif')+')\n\n'
    report+='复现脚本：scripts/smoke_multicam_source_range.py、scripts/verify_multicam_source_range_install.py；固定源码、命令、原始日志、失败与 SHA 见对应证据目录。\n'
    write(root/REPORT,report)
    lines=(root/HISTORICAL_CONTRACT).read_text('utf8').splitlines()
    constraints='\n'.join(line for line in lines if line.startswith('|'))
    assert constraints.count('| MC-C')==12
    write(root/CONTRACT,'# 多机位源覆盖与显式缺口策略（v0.1 限定验收，2026-10-21）\n\n'+message+'\n\n'+constraints+
        '\n\n[真实原生/隔离实测、原视频/GIF 与保留失败](../validation/'+Path(REPORT).name+')。')
    drafts=read(ROOT/REL/'skills-draft-r1.json')
    assert set(drafts['skills'])==set(SKILLS)
    for name,row in drafts['skills'].items():
        path=root/'skills'/name/'SKILL.md'
        guidance=row['new_block'].replace(HISTORICAL_CONTRACT,CONTRACT).replace(HISTORICAL_REPORT,REPORT)
        pending='This is an unregistered candidate; complete regression and main integration remain pending.'
        assert guidance.count(pending)==1
        guidance=guidance.replace(pending,'')
        assert 'unregistered candidate' not in guidance and 'remain pending' not in guidance
        block(path,guidance)
    attributes=(root/'.gitattributes').read_text('utf8')
    paths=[REL+'/** -text -whitespace',ASSETS+'/** -text -whitespace']
    paths += [f'product/src/ai_ad_editor/{name}.py -text whitespace=cr-at-eol' for name in MODULES]
    paths += [f'product/tests/{name}.py -text whitespace=cr-at-eol' for name in TESTS]
    paths += [f'scripts/{name}.py -text whitespace=cr-at-eol' for name in SCRIPTS]
    write(root/'.gitattributes',attributes+'\n# V86 exact tested multicamera source-coverage bytes.\n'+'\n'.join(paths))
    return {*LATEST_DOCS,REPORT,CONTRACT,'.gitattributes',*('skills/'+name+'/SKILL.md' for name in SKILLS)}"""


def main():
    assert not TARGET.exists(), 'Preserve any previously prepared publisher.'
    donor_path = DONOR / 'scripts/publish_native_empty_window_r2.py'
    original = donor_path.read_text('utf8')
    source = original
    constants = {
        'REL': 'docs/validation/evidence/multicam-source-range-20261021-lab',
        'ASSETS': 'docs/assets/multicam-source-range-20261021-lab',
        'REPORT': 'docs/validation/多机位源覆盖与原速同步实测_2026-10-21.md',
        'CONTRACT': 'docs/specs/多机位源覆盖与显式缺口策略_v0.1_2026-10-21.md',
        'HISTORICAL_REPORT': 'docs/validation/多机位源覆盖与原速同步独立实验_2026-10-21.md',
        'HISTORICAL_CONTRACT': 'docs/specs/多机位源覆盖与显式缺口策略_实验_v0.1_2026-10-21.md',
        'MARKER': 'V86-MULTICAM-SOURCE-COVERAGE',
        'SKILLS': ('video-cut-agent-editor', 'video-cut-timeline', 'video-cut-quality', 'video-cut-video-understand'),
        'MODULES': ('multicam', 'cli', 'capabilities'),
        'TESTS': ('test_multicam_source_range',),
        'SCRIPTS': ('run_multicam_after_empty', 'run_frozen_regression', 'run_with_regression_fixtures',
            'materialize_regression_fixtures', 'run_multicam_related_regressions', 'smoke_multicam_source_range',
            'verify_multicam_source_range_install', 'audit_multicam_related_lab', 'refresh_multicam_parent_contract',
            'prepare_multicam_full_gate', 'finalize_multicam_source_range_lab', 'prepare_multicam_isolated_verifier',
            'prepare_multicam_skills', 'run_multicam_compatibility', 'native_index_release_tools',
            'prepare_multicam_publication', 'publish_multicam_source_range'),
    }
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)]
    lines = source.splitlines()
    for node in reversed(nodes):
        name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
        if name in constants:
            lines[node.lineno - 1:node.end_lineno] = [name + '=' + repr(constants[name])]
    source = '\n'.join(lines) + '\n'
    source = source.replace('"""Publish frozen empty-window bytes only after the exact complete suite."""',
        '"""Publish frozen multicamera source-coverage bytes after the exact complete suite."""')
    source = source.replace("ROOT=Path(__file__).resolve().parents[1]", "ROOT=Path(__file__).resolve().parents[1]\nMODIFIED={'product/src/ai_ad_editor/'+name+'.py' for name in ('multicam','cli','capabilities')}\nADDED={'product/tests/test_multicam_source_range.py'}")
    gate_path = ROOT / 'scripts/run_multicam_after_empty.py'
    gate = function(gate_path.read_text('utf8'), 'source_gate').replace('def source_gate():', 'def source_audit():')
    gate = gate.replace("    for name, digest in audit['documents'].items(): assert sha(ROOT / name) == digest\n", '')
    gate = gate.replace("    return current, previous, {name: sha(ROOT / 'scripts' / name) for name in SCRIPTS}", '    return current')
    assert "audit['documents']" not in gate and gate.endswith('return current')
    source = source.replace(function(source, 'source_audit'), gate)
    complete = function(source, 'complete_gate')
    complete = complete.replace('native-empty-window-20261021/full-after-nested-r1', 'multicam-source-range-20261021/full-after-empty-r1')
    complete = complete.replace('published-nested-alignment-r1.json', 'published-empty-alignment-r1.json')
    complete = complete.replace("full['methods']==1973", "full['methods']==1995")
    complete = complete.replace("len(alignment['upstream_inputs'])==255", "len(alignment['upstream_inputs'])==256")
    complete = complete.replace("    for name,digest in state['verification_scripts'].items():", "    assert len(state['verification_scripts'])==10\n    for name,digest in state['verification_scripts'].items():")
    source = source.replace(function(source, 'complete_gate'), complete)
    source = source.replace(function(source, 'documents'), DOCUMENTS)
    old_main = function(source, 'main')
    new_main = old_main.replace("'full_methods':1973", "'full_methods':1995")
    new_main = new_main.replace("'targeted_methods':293", "'targeted_methods':80")
    new_main = new_main.replace("'frozen_files':256", "'frozen_files':257")
    new_main = new_main.replace('full_methods=1973', 'full_methods=1995')
    new_main = new_main.replace('V85 valid empty video windows with explicit audio and verified indexes; no general or full CapCut parity acceptance',
        'V86 multicamera source coverage with explicit reject/trim/stretch; offset only, no drift or full CapCut parity acceptance')
    new_main = new_main.replace('fix: retain underlying layers and explicit audio for empty video windows',
        'fix: preserve multicamera event sync with explicit source coverage policies')
    assert '1973' not in new_main and '293' not in new_main and 'V85' not in new_main
    source = source.replace(old_main, new_main)
    compile(source, str(TARGET), 'exec')
    shared = ROOT / 'scripts/native_index_release_tools.py'
    shared_source = DONOR / 'scripts/native_index_release_tools.py'
    assert not shared.exists() or sha(shared) == sha(shared_source)
    if not shared.exists():
        shutil.copyfile(shared_source, shared)
    TARGET.write_text(source, encoding='utf8', newline='\n')
    reusable = ('read', 'write', 'save', 'block', 'source_files')
    unchanged = {name: ast.dump(ast.parse(function(original, name))) == ast.dump(ast.parse(function(source, name))) for name in reusable}
    assert all(unchanged.values())
    assert sha(shared) == sha(shared_source)
    receipt = {
        'status': 'prepared-not-executed', 'full_suite_started': False, 'published': False,
        'expected_complete_methods': 1995, 'expected_parent_methods': 1973, 'expected_frozen_inputs': 257,
        'donor': str(donor_path), 'donor_sha256': sha(donor_path),
        'source_gate': str(gate_path), 'source_gate_sha256': sha(gate_path),
        'publisher': TARGET.relative_to(ROOT).as_posix(), 'publisher_sha256': sha(TARGET),
        'shared_helper': shared.relative_to(ROOT).as_posix(), 'shared_sha256': sha(shared),
        'unchanged_generic_function_AST': unchanged,
        'pipeline': 'Exact parent/main/remote, complete frozen suite, 17 Skills, actual media links, 64KiB staged blob hashes, ordinary commit and push.',
        'generator_sha256': sha(__file__),
        'limits': 'Source preflight is not a complete suite, main integration, registered Skill or release; no full CapCut parity.'
    }
    destination = ROOT / REL / 'publication-preparation-r1.json'
    assert not destination.exists()
    destination.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: receipt[key] for key in ('status', 'expected_complete_methods', 'publisher_sha256')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
