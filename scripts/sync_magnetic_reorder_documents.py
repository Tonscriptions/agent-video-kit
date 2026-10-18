"""Publish V53 docs only after matching complete regression, media and installation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'docs/validation/evidence'
REPORT = '主轨磁吸重排与关联附着实测_2026-10-18.md'
CONTRACT = '主轨磁吸重排与关联附着契约_v0.1_2026-10-18.md'
PUBLIC = 'magnetic-reorder-v53-r5-20261018'
DOCUMENTS = ['README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def receipt(name): return json.loads((EVIDENCE/name).read_bytes())


def replace_line(text, prefix, value):
    assert sum(line.startswith(prefix) for line in text.splitlines()) == 1, prefix
    return '\n'.join(value if line.startswith(prefix) else line for line in text.splitlines())+'\n'


def main():
    full = receipt('magnetic-reorder-tests-20261018/full-1.json')
    target = receipt('magnetic-reorder-tests-20261018/targeted-2.json')
    smoke = receipt('magnetic-reorder-real-r5-20261018/verification.json')
    install = receipt('magnetic-reorder-native-install-20261018/verification.json')
    media = receipt('magnetic-reorder-real-r5-20261018/media-audit.json')
    skills = receipt('magnetic-reorder-skills-20261018.json')
    current = frozen()
    assert full.get('terminal_ok') and full['exit_code'] == 0 and full['skipped'] == 0 and full['methods'] == 1223
    assert target['methods'] == 40 and target['terminal_ok'] and target['skipped'] == 0
    assert len(current) == 175
    for value in (full, target, smoke, install): assert value['frozen_before'] == value['frozen_after'] == current
    assert smoke['status'] == 'passed_scoped_magnetic_reorder' and smoke['development_cli_calls'] == 69
    assert smoke['main_frames'] == 380 and smoke['main_stereo_sample_frames'] == 1824000
    assert install['status'] == 'passed' and install['installed_package_files'] == 118
    assert install['isolated_cli_calls'] == 19 and install['actual_new_frames'] == 190
    assert media['status'] == 'passed_scoped_media_audit' and media['independent_PCM_sample_frames'] == 1152000
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 190
    seconds = f"{full['suite_seconds']:.3f}"
    changes = {}
    for name in DOCUMENTS:
        path = ROOT/name;text = path.read_text(encoding='utf-8-sig');assert '**V53（产品）**' not in text
        report_path = ('docs/validation/' if name == 'README.md' else '' if name.startswith('docs/validation/') else 'validation/')+REPORT
        summary = ('2026-10-18 **V53（产品）**：新增明确的主轨整片段 `reorder`，自动紧邻排列，'
            '被挤动镜头的关联配音/字幕随动，复杂作者与有效转场保留；断开的转场默认拒绝。'
            f'完整 **1223/1223，{seconds} 秒**、0 跳过、**175 文件**冻结；40 新增专项为全量子集。'
            '**69 CLI /380 主帧**；独立原 PCM **115.2 万采样帧差 0**，复杂块参考另计；'
            '**118 包内文件 /19 隔离 CLI /190 安装帧**，**14 Skills /190 引用**通过。'
            '四轮开发夹具失败保留；9 时刻静帧，未连续播放/听审。'
            '持久磁吸模式/全手势、自然 AI/声音、长片/HDR、另一台机器及完整剪映等价仍未验收。'
            f' [原输入/GIF/成片/失败/发行包]({report_path})。')
        head, rest = text.split('\n', 1)
        rest = rest.replace('2026-10-18 **V52（产品）**', '历史产品 2026-10-18 **V52（产品）**', 1)
        text = head+'\n\n'+summary+'\n\n'+rest.lstrip('\n')
        if name == 'README.md':
            text = replace_line(text, '| V13 |', f'| V13 | 产品自动回归 | 最近 V53 完整 **1223/1223**、{seconds} 秒、0 跳过；175 文件冻结，40 新增方法为完整子集 | 开发/安装/固定 V52 与历史分计；自然质量、全磁吸模式与完整剪映未验 | [完整日志](docs/validation/evidence/magnetic-reorder-tests-20261018/full-1.log)、[冻结终态](docs/validation/evidence/magnetic-reorder-tests-20261018/full-1.json) |')
            text = replace_line(text, '- 当前模块进度见', '- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：最近 V53 完整 **1223/1223**、0 跳过、175 文件冻结；新增整片段主轨重排和关联附着保持，独立源帧/PCM 与复杂作者块分计。持久磁吸模式、跨剪口自动拆声、CTC 精度、自然修复/声音、长片/HDR、另一台机器、内容库及完整剪映等价继续开放。')
            lines = []
            for line in text.splitlines():
                lines.append(line)
                if line.startswith('| V52 |'):
                    lines.append('| V53 | 主轨整片段磁吸重排与关联附着 | 40 专项/完整 1223；69 CLI、380 主帧/182.4 万解码采样帧；独立 PCM 115.2 万差 0，复杂块另计；118 文件/19 隔离 CLI/190 安装帧；14 Skills/190 引用 | 纯切 RGB/Alpha 差 0；作者/转场按重排前完整块比较；四轮夹具失败保留；无持久磁吸/全手势、连续播放/听审或完整等价 | '+f'[契约](docs/specs/{CONTRACT})、[原输入/GIF/成片/失败/发行包](docs/validation/{REPORT})、[完整回归](docs/validation/evidence/magnetic-reorder-tests-20261018/full-1.json) |')
            text = '\n'.join(lines)+'\n'
            marker = '## 实测演示素材\n';assert marker in text
            demo = ('\nV53 实际主轨重排：左为 A/B/C/D，右为 CLI 输出 C/A/B/D，帧号和关联配音逐项核对。'
                '五组独立纯切 RGB、独立 Alpha 差 0；115.2 万原 PCM 采样帧差 0。'
                '复杂作者/转场使用重排前完整块参考，分别计数。9 时刻静帧，未连续播放/听审。'
                f' [原视频](docs/assets/{PUBLIC}/source-frames.mkv)、[原输入 MP4](docs/assets/{PUBLIC}/source-preview.mp4)、'
                f'[原 WAV](docs/assets/{PUBLIC}/source-audio.wav)、[实际 MP4](docs/assets/{PUBLIC}/MR01.mp4)、'
                f'[无损成片](docs/assets/{PUBLIC}/MR01.mkv)、[全部数据与失败](docs/validation/{REPORT})。\n\n'
                f'![V53 实际主轨重排前后](docs/assets/{PUBLIC}/reorder-before-after.gif)\n')
            text = text.replace(marker, marker+demo, 1)
        if name == 'docs/README.md':
            text += f'\nV53 文档入口：[主轨重排契约](specs/{CONTRACT})、[实际音画/失败/发行记录](validation/{REPORT})。\n'
        if '构建进度总表' in name:
            rows = {
                '| 本次状态快照 |': '| 本次状态快照 | 2026-10-18，README V53；1223 完整/40 新增子集，175 文件冻结；历史失败保留 |',
                '| 最近产品增量 |': '| 最近产品增量 | V53 整片段主轨重排与关联附着；V51 复合定格、V52 无损 Alpha/作者端点已受控补验；完整剪映仍开放 |',
                '| 本轮研究增量 |': '| 研究状态与历史快照 | OpenFilm 853 stars/91 forks、702 文件复核仅为原请求时点；V53 没有新 API/原码采用或模型推理；FGT 自然质量与来源链未关闭 |',
                '| 核对范围 |': '| 核对范围 | 完整 1223/1223、0 跳过；69 当前 CLI/380 主帧；118 包内文件/19 隔离 CLI/190 安装帧；独立 PCM 115.2 万采样帧差 0，复杂块参考另计 |',
                '| 06 |': '| 06 | 时间线与基础剪辑 | 已实现，有边界 | 多轨/独立画布/嵌套/分层音频；V53 稳定多选主轨重排/自动闭隙/挤动镜头配音与字幕/转场关系；作者窗口/六种范围编辑/关联真实源 slip | 持久磁吸/屏幕吸附/全拖拽与不同位移同步片段自动拆声未实现；源外扩重新处理、嵌套再归一化旧时钟、VFR/HDR/长片/自然质量未验 |',
                '| 24 |': '| 24 | Agent Skills | 已实现，持续扩展 | 14 个 video-cut- Skill；主轨重排/作者保持/转场策略/实际安装入口同步；14 项格式/联接/SHA 与 190 引用通过 | 实际内容和自然质量持续验收，技能数不代表覆盖率 |',
                '| 25 |': '| 25 | 质量、性能与发行 | 本机隔离发行已核验，整体未完成 | V53 完整 1223/1223、175 文件冻结；118 包内文件/七个本地 wheel/19 隔离 CLI；安装 190 帧与开发版画面/Alpha/解码 PCM 一致 | 九时刻静帧无连续播放/听审；其他机器/平台、自然对齐/AI/声音、长片/HDR 与完整剪映待验 |',
                '| 当前生产代码 |': '| 当前生产代码 | 产品/测试/Schema/发行输入共 175 文件；最终完整、40 专项、公开媒体和安装前后冻结一致 | 原始失败和旧轮记录保留；175 不是纯运行时文件数，发行包内为 118 |',
                '| 最近完整产品回归 |': f'| 最近完整产品回归 | V53 **1223/1223，{seconds} 秒**，0 跳过；175 文件冻结 | [完整日志](validation/evidence/magnetic-reorder-tests-20261018/full-1.log)；耗时不是性能基准 |',
                '| 最近产品新增子集 |': '| 最近产品新增子集 | V53 的 40 方法，包含在本轮完整中 | 固定 V52 的同测 15 失败/23 报错/2 控制通过，主要为缺动作；研究与历史不相加 |',
                '| 最近产品实际核验 |': f'| 最近产品实际核验 | V53 69 CLI/380 主帧，另 19 隔离 CLI/190 安装帧；纯切 RGB/Alpha 和原 PCM 差 0 | [原片/失败/发行](validation/{REPORT})；复杂块同渲染器参考另计，九时刻静帧无播放/听审 |',
                '| Skill 审计 |': '| Skill 审计 | 14 Skills、190 引用，目录联接/格式/SHA 通过 | [本轮记录](validation/evidence/magnetic-reorder-skills-20261018.json)；引用检查不证明自然质量 |',
                '| 文档 |': '| 文档 | README/进度/契约/矩阵/基线/原片 GIF 同步，修正旧当前状态行 | [当前审计](validation/evidence/magnetic-reorder-release-final-20261018.json)；不证明外链、锚点、自然质量或许可 |',
                '“已实现”表示': '“已实现”表示列出的实现和验证，不表示完整剪映等价。最近 V53 为 1223/1223、175 文件冻结；上游研究、原媒体和安装计数分别记录，V42/V44 的自然质量/来源链及 CTC/声音缺口继续保留。',
            }
            for prefix, replacement in rows.items(): text = replace_line(text, prefix, replacement)
            text = text.replace('一般非整帧项目时长仍被发布门禁拒绝。', 'V52 已以作者 tick/帧样本量化核对非整帧端点，真实偏移仍按原 80 ms 拒绝；该修复不证明声音内容对齐。')
            text = text.replace('长片/并发进程 RSS、深层 freeze/VFR 与子级时基/色彩语义', '长片/并发进程 RSS、复合定格的广泛深层组合/VFR 与子级时基/色彩语义')
        if '能力覆盖与验收矩阵' in name:
            marker = '| 透明交付与作者端点（V52） |';assert marker in text
            row = ('| 主轨整片段重排（V53） | 稳定多选插入块、全主轨闭隙、挤动镜头关联配音、sync/rider、字幕补偿、轨道引用和转场策略 | '
                f'[40 专项/1223 完整、10 组媒体及安装](./{REPORT})；380 主帧、独立 PCM 115.2 万采样帧差 0；作者块参考另计 | '
                '持久磁吸/屏幕吸附/全拖拽、不同位移跨剪口自动拆声未实现；全局总线自动化新时钟、自然质量/听审/长片仍未验 |\n')
            text = text.replace(marker, row+marker, 1)
        if '产品实现入口' in name:
            text += ('\n## V53 主轨整片段重排入口\n\n'
                '`timeline edit` 新动作 `reorder`：`clip_ids` 选择主轨完整片段，`before_clip_id` 必须显式给出，null 为末尾。'
                '稳定原顺序组成插入块，全部主轨从零闭隙；被挤动镜头的链接也随动。sync 优先于 linkage，不同位移跨剪口同步片段要求先拆分。\n\n'
                '```json\n{"action":"reorder","clip_ids":["c"],"before_clip_id":"a","options":{"linked":true,"linkage":true},"transition_policy":"preserve"}\n```\n\n'
                '沿用 `--dry-run`、`--expected-project-sha256`、`--idempotency-key`；compose 的 linked_edit 参与原子批次。'
                '默认保留转场，不能保留则拒绝；drop_broken 只能显式选择，计划列出实际移除项。marker 保持绝对时间。'
                f'见 [契约](specs/{CONTRACT}) 与 [原片/音频/失败/安装](validation/{REPORT})。\n')
        changes[path] = text
    path = ROOT/'docs/validation'/REPORT;text = path.read_text(encoding='utf-8')
    substitutions = {
        'V53_FULL_PENDING': f'**1223/1223，{seconds} 秒，0 跳过**；[终态](evidence/magnetic-reorder-tests-20261018/full-1.json)、[原日志](evidence/magnetic-reorder-tests-20261018/full-1.log)',
        'V53_MEDIA_PENDING': '**69 次 CLI**，10 主输出 **380 帧 /1,824,000 解码立体声采样帧**；原始 PTS 全帧核对',
        'V53_INSTALL_PENDING': '**118 包内文件 /19 隔离 CLI /190 新帧 /912000 采样帧**；与开发版解码画面/Alpha/PCM 完全一致',
        'V53_STATIC_PENDING': '**三张联系图 /9 个时刻静帧**，没有连续播放或听审；原复杂图的字幕/计数叠置保留，未作为广告排版验收',
    }
    for marker, replacement in substitutions.items(): assert text.count(marker) == 1;text = text.replace(marker, replacement)
    text += f'\n发行 ZIP SHA-256：`{install["release_zip_sha256"]}`；清单：`{install["manifest_sha256"]}`。所有九组 PCM 内容比较最大差 0；MR08 Opus 只记录解码长度与有限性。\n'
    changes[path] = text
    path = ROOT/'docs/OpenFilm当前复用决策_2026-10-18.md';text = path.read_text(encoding='utf-8')
    assert 'V53 新增' not in text
    text += (f'\nV53 新增 [整片段主轨重排与关联附着](validation/{REPORT})，复用现有事务、兼容副轨、字幕时钟、权利和包交换基础设施；'
        '排序/附着规则由本项目实现，没有追加 OpenFilm 原码采用量，也没有重新查询上游或星数。'
        '69 CLI/380 主帧与 19 安装 CLI/190 帧分计；独立纯切/PCM/Alpha 和同渲染器作者块参考分开。'
        '这减少了再次搭建基础设施的工作，但没有实测人时，不能宣称节省比例；持久磁吸/全手势、自然质量/声音、长片和完整剪映等价仍需独立开发验收。\n')
    changes[path] = text
    path = ROOT/'video-cut-install-manifest.json';manifest = json.loads(path.read_bytes())
    previous = manifest['current_audit'];assert previous['record'].endswith('delivery-precision-skills-20261018.json')
    if previous not in manifest['audit_history']: manifest['audit_history'].append(previous)
    audit = 'docs/validation/evidence/magnetic-reorder-skills-20261018.json'
    manifest['current_audit'] = {'record': audit, 'record_sha256': sha(ROOT/audit), 'checked_at_utc': skills['checked_at_utc'],
        'skills': 14, 'local_links_checked': 190, 'semantics': 'V53 explicit whole-clip magnetic reorder; independent truth versus author block references; full goal unaccepted'}
    checked = {row['skill']: row for row in skills['results']};changed = []
    for row in manifest['skills']:
        digest = sha(Path(row['canonical_directory'])/'SKILL.md').split(':', 1)[1]
        assert checked[row['name']]['sha256'] == 'sha256:'+digest
        if row['skill_md_sha256'] != digest:
            history = row.setdefault('skill_md_sha256_history', [])
            if row['skill_md_sha256'] not in history: history.append(row['skill_md_sha256'])
            row['skill_md_sha256'] = digest;changed.append(row['name'])
    assert set(changed) == {'video-cut-agent-editor', 'video-cut-timeline'}
    changes[path] = json.dumps(manifest, ensure_ascii=False, indent=2)+'\n'
    for path, text in changes.items(): path.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'updated_files': len(changes), 'full_methods': 1223, 'changed_skills': changed,
                      'all_capcut_features_and_quality_accepted': False}, ensure_ascii=False))


if __name__ == '__main__': main()
