"""Synchronize V52 documentation only after completed, matching verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence'
REPORT = '透明视频交付与音画端点实测_2026-10-18.md'
CONTRACT = '透明视频交付与音画端点契约_v0.1_2026-10-18.md'
DOCUMENTS = [
    'README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
]


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(name):
    return json.loads((EVIDENCE / name).read_bytes())


def main():
    full = receipt('delivery-precision-tests-20261018/full-1.json')
    target = receipt('delivery-precision-tests-20261018/targeted-3.json')
    smoke = receipt('delivery-precision-real-20261018/verification.json')
    install = receipt('delivery-precision-native-install-20261018/verification.json')
    skills = receipt('delivery-precision-skills-20261018.json')
    media = receipt('delivery-precision-real-20261018/media-audit.json')
    current = frozen()
    assert full.get('terminal_ok') and full['exit_code'] == 0
    assert full['methods'] == 1183 and full['skipped'] == 0 and len(current) == 173
    for value in (full, target, smoke, install):
        assert value['frozen_before'] == value['frozen_after'] == current
    assert target['methods'] == 22 and target['terminal_ok']
    assert smoke['status'] == 'passed_scoped_delivery_precision'
    assert smoke['development_cli_calls'] == 36 and smoke['baseline_cli_calls'] == 4
    assert smoke['main_frames'] == 251 and smoke['main_stereo_sample_frames'] == 1191904
    assert install['status'] == 'passed' and install['installed_package_files'] == 117
    assert install['isolated_cli_calls'] == 13 and install['actual_new_frames'] == 98
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 186
    assert media['status'] == 'passed_scoped_media_audit'
    seconds = f"{full['suite_seconds']:.3f}"
    changes = {}
    for name in DOCUMENTS:
        path = ROOT / name
        text = path.read_text(encoding='utf-8-sig')
        assert '**V52（产品）**' not in text, name
        report_path = ('docs/validation/' if name == 'README.md' else
                       '' if name.startswith('docs/validation/') else 'validation/') + REPORT
        summary = (
            '2026-10-18 **V52（产品）**：受控 VP9 无损交付及重新入轨的 Alpha 最大差 **0**；'
            '4.01 秒工程按作者时钟核对端点，保留原始 90 ms 差及 **80 ms** 门槛，真实偏移仍拒绝。'
            f'完整 **1183/1183，{seconds} 秒**、0 跳过、**173 文件**冻结；22 新增专项是全量子集。'
            '**36 当前 CLI /251 主帧**，另有 4 次 V51 对照；'
            '**117 包内文件 /13 隔离 CLI /98 安装帧**，**14 Skills /186 引用**通过。'
            '有损 VP9 /VP8 的 Alpha 差 **12 /4**，仍不接受精确交付；YUV 4:2:0 不代表 RGB 无损。'
            '8 时刻静帧、未连续播放/听审；自然 AI/声音、另一台机器、长片/HDR与完整剪映等价仍未验收。'
            f' [原输入/GIF/原视频/安装包与失败]({report_path})。'
        )
        head, rest = text.split('\n', 1)
        rest = rest.replace('2026-10-18 **V51（产品）**', '历史产品 2026-10-18 **V51（产品）**', 1)
        text = head + '\n\n' + summary + '\n\n' + rest.lstrip('\n')
        if name == 'README.md':
            lines = []
            for line in text.splitlines():
                if line.startswith('| V13 |'):
                    line = (
                        f'| V13 | 产品自动回归 | 最近 V52 完整 **1183/1183**、{seconds} 秒、0 跳过；'
                        '173 文件冻结，22 新增专项为完整子集 | 开发/安装/反事实与历史分计；'
                        '有损 Alpha 未过精确门槛，自然质量与完整剪映未验 | '
                        '[完整日志](docs/validation/evidence/delivery-precision-tests-20261018/full-1.log)、'
                        '[冻结终态](docs/validation/evidence/delivery-precision-tests-20261018/full-1.json) |'
                    )
                if line.startswith('- 当前模块进度见'):
                    line = (
                        '- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：'
                        '最近产品 V52 完整 **1183/1183**、0 跳过、173 文件冻结；'
                        '无损 VP9 精确 Alpha、透明重新入轨及非整帧端点已受控验证，80 ms 门槛不变。'
                        '有损 Alpha 未过精确门槛；CTC 声学边界、FGT 自然修复、声音/听审、另一台机器、'
                        '长片/HDR、内容库及完整剪映等价仍未验收。'
                    )
                lines.append(line)
                if line.startswith('| V51 |'):
                    lines.append(
                        '| V52 | 透明交付、重新入轨与作者端点门禁 | 22 专项/完整 1183；'
                        '36 当前 CLI、251 主帧/119.1904 万解码采样帧；4 次旧版对照另计；'
                        '117 文件/13 隔离 CLI/98 安装帧；14 Skills/186 引用 | '
                        '受控 lossless VP9 Alpha 差 0；真实偏移拒绝，80 ms 不变；'
                        '有损 VP9 /VP8 Alpha 差 12 /4，RGB 4:2:0 非无损；无连续播放/听审或完整等价 | '
                        f'[原输入/GIF/成片/失败/发行包](docs/validation/{REPORT})、'
                        '[完整回归](docs/validation/evidence/delivery-precision-tests-20261018/full-1.json) |'
                    )
            text = '\n'.join(lines) + '\n'
            marker = '## 实测演示素材\n'
            assert marker in text
            demo = (
                '\nV52 实际交付对照：原覆盖率、固定 V51 成片与当前无损 VP9。'
                'Alpha 一个灰阶差由全像素测量确定；GIF 是实际解码结果的棋盘投影。'
                '只做 8 时刻静帧检查，未连续播放或听审。'
                ' [原透明源](docs/assets/delivery-precision-20261018/source-ramp.mkv)、'
                '[原源预览](docs/assets/delivery-precision-20261018/source-checkerboard.mp4)、'
                '[原 WAV](docs/assets/delivery-precision-20261018/source-audio.wav)、'
                '[当前 WebM](docs/assets/delivery-precision-20261018/DP01-vp9-freeze.webm)、'
                f'[全部数据/失败](docs/validation/{REPORT})。\n\n'
                '![V52 透明交付实际对照](docs/assets/delivery-precision-20261018/alpha-before-after.gif)\n\n'
                '4.01 秒作者区间的实际 MP4：10 fps 下 41 帧显示到 4.1 秒，'
                '音轨元数据 4.01 秒；AAC 解码多出 32 采样帧的填充另行报告。'
                '结尾留黑和计数/字幕叠置为诊断布局，未作为自然广告排版验收。'
                ' [实际 MP4](docs/assets/delivery-precision-20261018/DP09-fractional-mp4.mp4)。\n\n'
                '![V52 非整帧时长实际 MP4](docs/assets/delivery-precision-20261018/fractional-mp4.gif)\n'
            )
            text = text.replace(marker, marker + demo, 1)
        if '构建进度总表' in name:
            old = 'V51 祖先定格受控支持；正式 VP9 精确 alpha 失败'
            assert old in text
            text = text.replace(old, 'V51 祖先定格、V52 无损 VP9 精确 alpha 受控通过；有损路径不保证')
            text = text.replace('端点容器/曲线/定格/跟踪/blend、V51',
                                '端点容器、部分曲线/定格/跟踪/blend 组合仍受限；V51')
        if '能力覆盖与验收矩阵' in name:
            marker = '| 完整复合片段定格（V51） |'
            assert marker in text
            row = (
                '| 透明交付与作者端点（V52） | 无损 VP9 Alpha 分离编码、WebM 显式解码/RGBA 合成；'
                '流起止与作者 tick/有理帧率比较，保留原始差与 80 ms 门槛 | '
                f'[22 专项/1183 完整、11 组实际成片及独立安装](./{REPORT})；'
                '251 主帧，原 PCM 独立 76800 采样帧，兼容控制另计 | '
                '有损 VP9/VP8 最大差 12/4 未通过精确 Alpha；RGB 4:2:0 非无损；'
                '需显式 sequence-id 才有作者 D，未知 D 不猜量化；口型内容/自然声音/完整等价未验 |\n'
            )
            text = text.replace(marker, row + marker, 1)
            text = text.replace('内核 alpha 精确；正式 VP9 128→129、326,400 像素失败；'
                                '10 fps /4.01 秒 MP4 被 AV 门禁拒绝；',
                                'V51 当轮内核 alpha 精确，但正式 VP9 与 4.01 秒 MP4 失败；V52 上行补验；')
        if '产品实现入口' in name:
            text += (
                '\n## V52 透明交付与作者端点入口\n\n'
                'VP9 显式 CRF=0 且无视频码率覆盖才启用 lossless；Alpha 保真与 RGB 4:2:0 分开报告。'
                'WebM alpha_mode=1 素材会显式选择 libvpx 解码器并在合成前固定 RGBA。\n\n'
                '```powershell\n'
                'python -X utf8 -m ai_ad_editor render --project <工程> --output <工程>/renders/alpha.webm '
                '--container webm --video-codec libvpx-vp9 --audio-codec libopus '
                '--pixel-format yuva420p --crf 0 --publish\n'
                'python -X utf8 -m ai_ad_editor quality check --project <工程> '
                '--input <工程>/renders/output.mp4 --sequence-id <序列ID> --require-audio\n'
                '```\n\n'
                '独立 quality 必须显式绑定序列才知道作者 D；省略时仍按未知 D 的原严格逻辑。'
                '报告保留 raw duration delta、预期帧/样本数、量化差、开始/结束偏移和剩余误差，'
                '默认 80 ms 不变；这不是检测内容口型错位的算法。'
                f'见 [契约](specs/{CONTRACT}) 与 [原片/正负控制/安装包](validation/{REPORT})。\n'
            )
        changes[path] = text

    path = ROOT / 'docs/validation' / REPORT
    text = path.read_text(encoding='utf-8')
    assert text.count('V52_FULL_PENDING') == text.count('V52_SKILLS_PENDING') == 1
    text = text.replace('V52_FULL_PENDING',
                        f'**1183/1183，{seconds} 秒，0 跳过**；[终态](evidence/delivery-precision-tests-20261018/full-1.json)、'
                        '[原日志](evidence/delivery-precision-tests-20261018/full-1.log)')
    text = text.replace('V52_SKILLS_PENDING',
                        '**14 Skills /186 本地引用**通过；[原验证](evidence/delivery-precision-skills-20261018.json)')
    text += ('\n## 8. 发布前独立复核\n\n'
             '[媒体复核](evidence/delivery-precision-real-20261018/media-audit.json) 重新解码十一组实际文件，'
             '按独立公式复算 Alpha、PCM 和背景合成，核对原 CLI 日志与所有公开文件 SHA-256。'
             '[静态检查记录](evidence/delivery-precision-real-20261018/static-review.json) 固定两张联系图及八个时刻。'
             '原生成回执中的 static_review_pending 保留为生成当时状态，由此后置记录补齐，未改写旧回执。\n')
    changes[path] = text

    path = ROOT / 'docs/OpenFilm当前复用决策_2026-10-18.md'
    text = path.read_text(encoding='utf-8')
    assert 'V52 进一步' not in text
    text += (
        '\nV52 进一步补齐 [透明正式交付与作者端点核验](validation/' + REPORT + ')：'
        '受控无损 VP9 的 Alpha 最大差 0，导出后重新入轨保持覆盖率；'
        '非整帧作者时长按整数 tick/有理帧率核对，原 80 ms 门槛不变，并拒绝旧版漏过的流开始/共同偏移。'
        '这些为本项目 FFmpeg/质量链的新实现，没有新增 OpenFilm 原码采用。'
        '有损 VP9/VP8 的 Alpha 差 12/4 仍不接受精确交付，RGB 4:2:0 也不代表无损；'
        '复用帧时钟、模板和描线规则能省去重复规则工程，无法替代编码、声学对齐、自然 AI 与完整剪映质量验收。'
        '本补充未重新查询上游或星数，未安装官方十份 Skill；前文 853/91 仍仅对应原快照。\n'
    )
    changes[path] = text

    path = ROOT / 'video-cut-install-manifest.json'
    manifest = json.loads(path.read_bytes())
    old_audit = manifest['current_audit']
    assert old_audit['record'].endswith('nested-freeze-skills-final-20261018.json')
    if old_audit not in manifest['audit_history']:
        manifest['audit_history'].append(old_audit)
    audit_path = 'docs/validation/evidence/delivery-precision-skills-20261018.json'
    manifest['current_audit'] = {
        'record': audit_path, 'record_sha256': sha(ROOT / audit_path),
        'checked_at_utc': skills['checked_at_utc'], 'skills': 14, 'local_links_checked': 186,
        'semantics': 'V52 exact alpha for scoped lossless VP9 and authored endpoint checks; lossy/RGB limits retained; historical audits preserved',
    }
    changed_skills = []
    checked = {row['skill']: row for row in skills['results']}
    for row in manifest['skills']:
        digest = sha(Path(row['canonical_directory']) / 'SKILL.md').split(':', 1)[1]
        assert checked[row['name']]['sha256'] == 'sha256:' + digest
        if row['skill_md_sha256'] != digest:
            changed_skills.append(row['name'])
            history = row.setdefault('skill_md_sha256_history', [])
            if row['skill_md_sha256'] not in history:
                history.append(row['skill_md_sha256'])
            row['skill_md_sha256'] = digest
    assert set(changed_skills) == {'video-cut-agent-editor', 'video-cut-quality'}
    changes[path] = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    for path, text in changes.items():
        path.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'updated_files': len(changes), 'full_methods': 1183,
                      'suite_seconds': full['suite_seconds'], 'changed_skill_content': changed_skills,
                      'all_capcut_features_and_quality_accepted': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
