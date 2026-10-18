"""Publish the completed V50 comparison while preserving the V49 product baseline."""
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CORE = ['README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
REPORT = 'docs/validation/开源字词边界模型对照实测_2026-10-18.md'


def main():
    full = json.loads((ROOT / 'docs/validation/evidence/ctc-tests-20261018/full-2.json').read_bytes())
    assert len(full['frozen_after']) == 170
    assert all('sha256:' + hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value
               for name, value in full['frozen_after'].items())
    score = json.loads((ROOT / 'docs/validation/evidence/boundary-final-score-20261018.json').read_bytes())
    assert [r['model_forward_calls'] for r in score['results']] == [2, 3, 1]
    assert all(not c['passed'] for r in score['results'] for c in r['cases'])
    for name in CORE:
        path = ROOT / name
        text = path.read_text(encoding='utf-8-sig')
        assert '**V50（研究）**' not in text
        report_link = Path(os.path.relpath(ROOT / REPORT, path.parent)).as_posix()
        summary = ('2026-10-18 **V50（研究）**：完成字词边界三方案对照，**3 个实际模型 worker /6 次新前向**；'
            'Qwen 两组最大误差 **220 /161 ms**，仍未过既定 **66.6667 ms** 门槛，中文一字零时长/六处相邻重叠；'
            'Whisper-DTW 与新留出 CTC 也失败。两组最终研究图 **458 帧**核对 PTS、**243,835 个原 PCM 样本**精确保留，'
            '两个中间静帧可读性检查，未连续播放/听审。**170 产品/测试/发行文件与 V49 相同，本轮没有重跑历史 1135/1135**；'
            'Qwen 尚未成为正式 engine，完整剪映等价仍未达成。'
            f' [原输入/GIF/逐词失败/来源]({report_link})。\n\n')
        if name == 'README.md':
            at = text.index('2026-10-18 **V49（产品）**')
        else:
            at = text.index('\n') + 1
        text = text[:at] + summary + text[at:]
        path.write_text(text, encoding='utf-8', newline='\n')
    path = ROOT / 'README.md'
    text = path.read_text(encoding='utf-8')
    row = ('| V50 | 开源字词边界模型对照（研究） | 3 模型 worker/6 新前向；CTC 4 CLI；两份最终图 458 帧/243,835 原 PCM；170 产品文件未变 | '
           'Qwen 220 /161 ms 仍失败；中文零时长/重叠，未接入正式 engine；两静帧无播放/听审；1135/1135 为历史 | '
           f'[原 WAV/GIF/实测]({REPORT})、[逐词评分](docs/validation/evidence/boundary-final-score-20261018.json) |')
    text = re.sub(r'(?m)^(\| V49 \|.*)$', lambda m: m[0] + '\n' + row, text, count=1)
    position = text.index('## 开源复用核查')
    gallery = ('**V50 研究对照**：下图来自真实 CTC /Whisper /Qwen 时间，灰色是作者词块参考；'
        '全部未通过原门槛。图为测量可视化，正式内核沿用 V49。'
        f' [原 WAV、原稿、两组 MP4/MKV、逐词误差和失败记录]({REPORT})。\n\n'
        '![V50 七词留出研究对照](docs/assets/boundary-heldout-readable-20261018/comparison.gif)\n\n')
    text = text[:position] + gallery + text[position:]
    path.write_text(text, encoding='utf-8', newline='\n')
    path = ROOT / 'docs/OpenFilm当前复用决策_2026-10-18.md'
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\nV50 进一步进行了[本地字词边界模型对照](validation/开源字词边界模型对照实测_2026-10-18.md)：'
            '真实 Qwen /Whisper /CTC 共 3 个模型 worker、6 次新前向，仍没有满足原词块门槛；'
            '中文 Qwen 原始预测有零时长和相邻重叠，尚未接入正式 engine。'
            'OpenFilm 的分句/描线复用不提供这部分声学能力；没有把下载模型、研究图或历史产品回归计成新的 OpenFilm 实现。\n')
    print(json.dumps({'core_documents_updated': len(CORE), 'product_files_unchanged': 170}))


if __name__ == '__main__':
    main()
