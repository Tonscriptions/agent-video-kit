"""Synchronize V70 measured contracts without counting historical reruns."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/openfilm-batch-reuse-20261020-v70'
REPORT = ROOT / 'docs/validation/OpenFilm同批次结果复用实测_2026-10-20.md'
CONTRACT = ROOT / 'docs/specs/同批次相同渲染结果复用契约_v0.1_2026-10-20.md'
DOCUMENTS = ['README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def read(path): return json.loads(path.read_bytes())
def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def relative(source, target): return Path(os.path.relpath(target, source.parent)).as_posix()


def insert(path, content):
    value = path.read_text(encoding='utf8')
    start, end = '<!-- V70-CURRENT -->', '<!-- /V70-CURRENT -->'
    block = start + '\n' + content.rstrip() + '\n' + end
    if start in value:
        a = value.index(start); b = value.index(end, a) + len(end)
        value = value[:a] + block + value[b:]
    else:
        first, rest = value.split('\n', 1)
        value = first + '\n\n' + block + '\n' + rest
    path.write_text(value, encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    current = frozen(); assert len(current) == 214
    full = read(BASE / 'full-r1.json'); focus = read(BASE / 'focus-r5.json')
    dev = read(BASE / 'native-r3/verification.json')
    install = read(BASE / 'installed-r1/verification.json')
    actual = read(BASE / 'installed-r1/media/verification.json')
    container = read(BASE / 'container-r1/verification.json')
    skills = read(BASE / 'skills-r1.json'); media = read(BASE / 'media-inventory-r1.json')
    for value in (focus, dev, install, actual, container):
        assert value['frozen_equal'] and value['frozen_before'] == value['frozen_after'] == current
    assert focus['terminal_ok'] and focus['methods'] == 28 and focus['skipped'] == 0
    assert skills['skill_count'] == 17 and skills['local_links_checked'] == 260
    assert dev['status'] == actual['status'] == install['status'] == media['status'] == 'passed'
    assert len(install['resource_hashes']) == 143 and install['bundle']['wheels'] == 7
    assert install['isolated_cli_calls'] == 13 and install['module_origin_probes'] == 1
    if not args.candidate:
        assert full['terminal_ok'] and full['exit_code'] == 0 and full['methods'] == 1564 and full['skipped'] == 0
        assert full['frozen_equal'] and full['frozen_before'] == full['frozen_after'] == current
    full_note = ('完整回归运行中，尚未验收；最近已发布 V69 为 1536/1536。' if args.candidate else
        f'完整 **{full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过、214 输入冻结**；28 新契约方法为其子集。')
    summary = ('2026-10-20 **V70（' + ('候选，完整回归待验收' if args.candidate else '同批次结果复用限定验收') +
        '）**：参考 OpenFilm 的批次规则，新增显式 `queue run --reuse-identical`，仅本次调用、同项目、单 worker。'
        '实际源字节、有效设置、权利和运行实现绑定摘要；复制另建 operation/manifest，编码证据保留来源身份。' + full_note +
        f'针对性 **28/28、{focus["suite_seconds"]:.3f} 秒、0 跳过**。开发版 **10 次 CLI、22 项检查**；'
        '6 个作业中 5 成功/1 参数拒绝，真实 **3 次编码、2 次复制**；普通 MP4、透明 WebM 的副本逐字节、全部 24 帧、PTS、PCM 相同。'
        '**143 资源/7 wheels/13 次隔离 CLI＋1 次模块来源检查/38 项安装检查**；安装版独立重复样例，全部帧/PTS/PCM 与开发版相同。'
        '真实 ffconcat 伪装登记另 5 CLI＋1 FFprobe，在编码前拒绝；**17 Skills/260 本地引用**。'
        '本次为程序生成的 320×180/12 fps/2 秒技术素材；静看两张首帧联系图，未连续播放或听审。'
        '**未验收自然素材效果、吞吐提升、跨调用缓存或完整剪映等价**。')
    table = '''| 编号 | 功能性核验 | 当前结果与边界 |
|---|---|---|
| V70-01 | 内容签名 | 深层 JSON、归一化默认值、实际媒体/字体/LUT/蒙版/权利/运行摘要；同大小恢复 mtime 仍失效 |
| V70-02 | 原生队列 | 10 CLI、22 检查；5 成功/1 参数拒绝；3 编码/2 复制，不把参数拒绝计作编码 |
| V70-03 | 成片一致 | MP4 与透明 WebM 各一对；文件、全部 24 帧 RGBA、PTS、PCM 相同；256×144 另编码 |
| V70-04 | 透明与来源 | WebM Alpha 最小 0/最大 255；新 manifest 命令为空、标注未执行编码，保留来源证据 |
| V70-05 | 依赖/失败/默认行为 | 默认关闭、跨调用不复用、派生缓存变化、源/manifest 损坏、复制取消与写盘失败等；执行器故障注入属于测试替身 |
| V70-06 | 实际容器重探测 | 真实 ffconcat 伪装 png_pipe；5 CLI＋1 FFprobe，QUEUE_REUSE_UNSUPPORTED，0 编码/0 复制 |
| V70-07 | 原生安装 | 143 资源原字节、7 wheels、13 隔离 CLI＋1 模块来源、38 检查；安装版解码结果与开发版一致 |
| V70-08 | 完整回归 | FULL_NOTE |
| V70-09 | 演示与质量 | 2 张首帧联系图已静看；GIF 实际 12 帧/2 秒；未连续播放/听审、未验收自然素材/性能/剪映等价 |
'''.replace('FULL_NOTE', full_note.replace('**', ''))
    for name in DOCUMENTS:
        path = ROOT / name
        content = summary + ' [契约、原片/GIF、收据与保留的失败](' + relative(path, REPORT) + ')。'
        if name == 'README.md':
            content += ('\n\n' + table + '\n原始输入：[透明 FFV1/PCM](docs/assets/openfilm-batch-reuse-20261020-v70-native-r3/source.mkv)、'
                '[MP4 预览](docs/assets/openfilm-batch-reuse-20261020-v70-native-r3/source-preview.mp4)；实际输出：'
                '[首次 MP4](docs/assets/openfilm-batch-reuse-20261020-v70-native-r3/first.mp4)、'
                '[复制 MP4](docs/assets/openfilm-batch-reuse-20261020-v70-native-r3/renamed.mp4)、'
                '[透明 WebM](docs/assets/openfilm-batch-reuse-20261020-v70-native-r3/alpha-copy.webm)。'
                '下图为复制 MP4 的缩小 GIF，实际 12 帧/2 秒、无声，不代替 24 帧视频和机器核验。\n\n'
                '![批次复用实际输出预览](docs/assets/openfilm-batch-reuse-20261020-v70-native-r3/preview.gif)')
        insert(path, content)
    report = '# OpenFilm 同批次结果复用实测\n\n' + summary + '\n\n' + table + '''
## 来源、实现与测量口径

参考 [OpenFilm 固定源码](https://github.com/openfilm/openfilm/tree/71922644da5d6b67db2cc796d4e057f98999944f) 的 `exports.mjs:startAll/cloneOf`，
在现有 Python CLI、队列与事务中重新实现；既有 MIT 和归属保留。产品契约见 [同批次相同渲染结果复用](../specs/同批次相同渲染结果复用契约_v0.1_2026-10-20.md)。

开发与安装样例各自为 10 次 CLI、37 次**脚本直接发起的进程调用**；37 已含这些 CLI，不是完整子进程树总数。
安装核验另执行 capabilities/schema/help 3 次 CLI、1 次模块来源检查，故安装 CLI 共 13 次；包装脚本的 7 次调用不再累加成媒体执行次数。
首次编码/复制次数由真实进度事件与各输出 manifest 对照，各轮 3/2，不把两轮或历史重跑相加冒充单轮收益。
第一个无效编码器在参数阶段拒绝，没有运行 FFmpeg；执行器错误注入只在契约测试中发生。

## 原片、实际输出与收据

| 类别 | 可复查内容 |
|---|---|
| 原片 | [透明 FFV1＋立体声 PCM](../assets/openfilm-batch-reuse-20261020-v70-native-r3/source.mkv)、[MP4 预览](../assets/openfilm-batch-reuse-20261020-v70-native-r3/source-preview.mp4)、[来源/CC0 声明](../assets/openfilm-batch-reuse-20261020-v70-native-r3/source-origin.json) |
| 普通成片 | [首次编码](../assets/openfilm-batch-reuse-20261020-v70-native-r3/first.mp4)、[同规格改名副本](../assets/openfilm-batch-reuse-20261020-v70-native-r3/renamed.mp4)、[256×144 独立编码](../assets/openfilm-batch-reuse-20261020-v70-native-r3/smaller.mp4) |
| 透明成片 | [首次 WebM](../assets/openfilm-batch-reuse-20261020-v70-native-r3/alpha-first.webm)、[透明副本](../assets/openfilm-batch-reuse-20261020-v70-native-r3/alpha-copy.webm)、[副本 manifest](../assets/openfilm-batch-reuse-20261020-v70-native-r3/alpha-copy.webm.manifest.json) |
| 实际核验 | [28 项针对性](evidence/openfilm-batch-reuse-20261020-v70/focus-r5.json)、[原生样例](evidence/openfilm-batch-reuse-20261020-v70/native-r3/verification.json)、[实际容器](evidence/openfilm-batch-reuse-20261020-v70/container-r1/verification.json)、[完整回归](evidence/openfilm-batch-reuse-20261020-v70/full-r1.json) |
| 原生安装 | [安装与逐帧对照](evidence/openfilm-batch-reuse-20261020-v70/installed-r1/verification.json)、[安装版实际媒体](evidence/openfilm-batch-reuse-20261020-v70/installed-r1/media/verification.json)、[bundle manifest](../assets/openfilm-batch-reuse-20261020-v70-installed-r1/release/bundle-manifest.json)、[安装收据](../assets/openfilm-batch-reuse-20261020-v70-installed-r1/release/install-receipt.json)、[归档摘要](../assets/openfilm-batch-reuse-20261020-v70-installed-r1/release/bundle-archive.json) |
| 展示核验 | [媒体清单/16 次实际探测](evidence/openfilm-batch-reuse-20261020-v70/media-inventory-r1.json)、[静态目检](evidence/openfilm-batch-reuse-20261020-v70/static-review-r1.json)、[17 Skills/260 引用](evidence/openfilm-batch-reuse-20261020-v70/skills-r1.json) |

![原片、首次编码与副本的首帧联系图](../assets/openfilm-batch-reuse-20261020-v70-native-r3/comparison-frame-0.png)

![实际复制 MP4 的缩小预览](../assets/openfilm-batch-reuse-20261020-v70-native-r3/preview.gif)

GIF 为 480×270、12 帧、2 秒、无声。左侧原片在浅灰背景展示；成片背景为黑色。
目检仅查看开发/安装两张首帧联系图，不宣称连续播放或听音。机器检查覆盖完整 24 帧、时间戳与解码音频。
WebM 配对字节完全相同；开发与安装的 WebM 封装文件可因 mux UID 不同而 SHA 不同，跨安装验收的是解码帧/PTS/PCM。

## 保留的失败与历史

- [focus-r1](evidence/openfilm-batch-reuse-20261020-v70/focus-r1.json)：23 项中 1 项失败，测试把参数阶段编码器拒绝计入渲染调用；原日志保留。
- [focus-r3](evidence/openfilm-batch-reuse-20261020-v70/focus-r3.json)：27 项中 1 项失败，测试未建取消目录，实际收到写盘失败；半成品已清理。r4 改正取消夹具。
- [native-r1](evidence/openfilm-batch-reuse-20261020-v70/native-r1/verification.json)：编码、复制和媒体比较通过，但脚本错误调用 `project validate`，整轮收尾失败；[原脚本](evidence/openfilm-batch-reuse-20261020-v70/native-r1/executed-smoke.py)与 stdout/stderr 保留。r2 改用 `validate --project` 重跑。
- [focus-r4](evidence/openfilm-batch-reuse-20261020-v70/focus-r4.json) 与 [native-r2](evidence/openfilm-batch-reuse-20261020-v70/native-r2/verification.json) 是 V68 基线的 206 输入原型收据，不能替代后来派生缓存摘要、实际容器重探测和 V69 合入后的核验。最终源采用 focus-r5/native-r3 与安装版的 214 输入。

## 当前边界

只支持显式开关、本次调用、同项目、单 worker、新目标；默认路径不复用，跨调用无持久缓存。
全部项目资产保守入签名；硬件逐作业探测、外部音频伸缩、外部 ASS/字体回退、跟踪报告绑定、随机颗粒及多文件播放列表拒绝复用。
原生 Python/FFmpeg/FFprobe、包实现、Pillow 和相关目录 DLL 绑定摘要，不声称枚举所有 Windows 系统组件。
既有元数据事务恢复边界仍适用；致命中断后的完整孤立媒体需按原恢复报告审查，不能把复制清理承诺扩展为整个命令的所有媒体原子性。

技术素材由本地程序生成并保存 CC0 声明，字体附 DejaVu 许可证。项目导入后的权利仍为 unverified，广告发布门禁未自动放行。
样例还保留内嵌动态文字颜色混合的既有近似警告；复制一致不代表该效果达到剪映质量。
本版没有新模型前向、GUI 或在线服务。离线包不附 Python、FFmpeg、系统 DLL 或模型。
未检查自然素材、4K/长片吞吐，也没有相同工作量的性能基准，不能宣称提速百分比或完整剪映等价。
'''
    REPORT.write_text(report, encoding='utf8', newline='\n')
    contract = CONTRACT.read_text(encoding='utf8')
    status = ('状态：V70 主分支候选；针对性、真实 CPU 视频与原生安装通过，完整回归运行中；尚未发行。' if args.candidate else
              '状态：V70 同批次复用契约、真实 CPU 视频、原生安装与完整回归限定通过；性能及完整剪映等价未验收。')
    contract = re.sub(r'^状态：.*$', status, contract, count=1, flags=re.M)
    contract = contract.replace('不影响仍进行中的 V69 冻结发行。', '以已发布 V69 为基线，冻结本轮 214 个产品输入后验收。')
    CONTRACT.write_text(contract, encoding='utf8', newline='\n')
    research = ROOT / 'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md'
    insert(research, '后续实现：' + summary + ' [完整实测](' + relative(research, REPORT) + ')。以下 R09 来源时间、Star 快照与原型工时估算保持原口径。')
    path = ROOT / 'video-cut-install-manifest.json'; mapping = read(path)
    for row in mapping['skills']:
        source = ROOT / 'skills' / row['name'] / 'SKILL.md'
        checked = next(v for v in skills['results'] if v['skill'] == row['name'])
        assert sha(source) == checked['sha256']
        value = checked['sha256'][7:]
        if row['skill_md_sha256'] != value:
            row.setdefault('skill_md_sha256_history', []).append({'sha256': row['skill_md_sha256'],
                'replaced_at_utc': datetime.now(timezone.utc).isoformat(), 'reason': 'V70 opt-in single-invocation queue output reuse'})
            row['skill_md_sha256'] = value
        row['description'] = re.search(r'^description: (.+)$', source.read_text(encoding='utf8'), re.M)[1].strip('"')
    old = mapping['current_audit']; history = mapping.setdefault('audit_history', [])
    record_name = (BASE / 'skills-r1.json').relative_to(ROOT).as_posix()
    if old.get('record') != record_name and old not in history: history.append(old)
    mapping['current_audit'] = {'record': record_name, 'record_sha256': sha(BASE / 'skills-r1.json'),
        'checked_at_utc': skills['checked_at_utc'], 'skills': 17, 'local_links_checked': 260,
        'semantics': 'V70 opt-in same-invocation output reuse; source and isolated native media contracts; performance and full CapCut parity unaccepted',
        'candidate': args.candidate}
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': 'candidate_documents' if args.candidate else 'terminal_documents',
        'skills': 17, 'links': 260, 'full_methods': full.get('methods'), 'full_accepted': not args.candidate}))


if __name__ == '__main__': main()
