"""Update V49 documentation only after final native regression and install pass."""
import argparse,hashlib,json,os,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORE=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
      'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
      'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
REPORT='docs/validation/离线CTC字词强制对齐实测_2026-10-18.md'
CONTRACT='docs/specs/离线CTC字词强制对齐契约_v0.1_2026-10-18.md'
FULL='docs/validation/evidence/ctc-tests-20261018/full-2.json'


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()


def write(p,t):p.write_text(t,encoding='utf-8',newline='\n')


def run():
    full=json.loads((ROOT/FULL).read_bytes())
    assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0 and full['frozen_equal']
    assert full['frozen_before']==full['frozen_after'] and all(sha(ROOT/k)==v for k,v in full['frozen_after'].items())
    n,seconds,files=full['methods'],full['suite_seconds'],len(full['frozen_after'])
    assert n==1135 and files==170
    native=json.loads((ROOT/'docs/validation/evidence/ctc-native-installed-20261018-b/verification.json').read_bytes())
    assert native['status']=='passed' and native['isolated_cli_calls']==11 and native['installed_package_files']==116
    quality=json.loads((ROOT/'docs/validation/evidence/ctc-real-en-20261018-b/word-boundary-quality.json').read_bytes())
    assert not quality['passed'] and quality['observed_max_error_seconds']==0.2581875
    for name in CORE:
        p=ROOT/name;t=p.read_text(encoding='utf-8-sig');assert '**V49（产品）**' not in t
        def link(label,target):return '['+label+']('+Path(os.path.relpath(ROOT/target,p.parent)).as_posix()+')'
        summary=(f'2026-10-18 **V49（产品）**：新增本地 Wav2Vec2 CTC `subtitle align`、原文码点/样本时钟、长音频重叠窗和 SRT 窗口，'
            '**英文定位门槛未通过：最大 258.1875 ms，高于预声明 66.6667 ms**。'
            f'完整 **{n}/{n}，{seconds} 秒**，0 跳过，**{files} 文件**冻结；28 新增方法为完整子集。'
            '英文开发 15 CLI/3 worker/5 前向，中文 12 CLI/2 worker/3 前向（含一次预期繁体 OOV 拒绝）；'
            '逐帧高亮 236 帧、48 kHz 单声道 377,550 样本核对通过。'
            '最终原生安装 **116 包内文件 /11 隔离 CLI /七轮依赖包**，另一次真实 worker/一次前向，RGB/PCM 与开发版一致；'
            '缺 Pillow 的旧安装、双音轨和错误 16 kHz 预期均保留。**14 Skills /172 引用**通过。'
            '三时刻静帧、未连续播放/听审；自然对齐/歌词、完整声音、长片/HDR、另一台干净机器及完整剪映等价仍未验收。 '
            +link('契约',CONTRACT)+'、'+link('原片/GIF/安装包与失败',REPORT)+'。')
        t=t.replace('2026-10-18 **V48（产品）**：','历史产品 2026-10-18 **V48（产品）**：',1)
        at=t.index('历史产品 2026-10-18 **V48') if name=='README.md' else t.index('\n')+1
        write(p,t[:at]+summary+'\n\n'+t[at:])
    p=ROOT/'README.md';t=p.read_text(encoding='utf-8')
    row=(f'| V49 | 离线 CTC 字词强制对齐 | 中英真实 5 worker/8 前向；236 帧高亮/377,550 个 48 kHz 样本；'
         f'116 文件/11 隔离 CLI/七轮安装，另一次真实模型；完整 {n}/{n}、170 文件冻结；14 Skills/172 引用 | '
         '**定位门槛失败 258.1875 ms >66.6667 ms**；中文无精标；三静帧无播放/听审；自然质量和剪映等价未验 | '
         f'[原片/GIF/发行/失败]({REPORT})、[全量]({FULL}) |')
    t=re.sub(r'(?m)^(\| V48 \|.*)$',lambda m:m[0]+'\n'+row,t,count=1)
    t=re.sub(r'(?m)^\| V13 \|.*$',f'| V13 | 产品自动回归 | 最近 V49 完整 **{n}/{n}**、0 跳过；170 文件冻结，28 新增方法为完整子集 | 开发/安装/专项与历史分计；英文定位门槛失败，完整剪映未验 | [完整日志](docs/validation/evidence/ctc-tests-20261018/full-2.log)、[冻结终态]({FULL}) |',t)
    old='最近产品 V48 完整 **1107/1107**、0 跳过，165 文件冻结；OpenFilm 原描线函数、独立几何、工程包/安装版 RGBA 重建通过。'
    assert old in t
    t=t.replace(old,f'最近产品 V49 完整 **{n}/{n}**、0 跳过，170 文件冻结；本地 CTC、236 帧高亮及七轮隔离安装通过，英文声学定位精度门槛失败（258.1875 ms）。')
    gallery=('\n**V49 本地 CTC 对齐（精度未达标）**：左为原创波形输入，右为真实模型时间驱动的字幕；1280×720、30 fps、236 帧。'
        'GIF 79 帧/7,900 ms，无音频。逐帧高亮与模型时码一致，但词块边界偏差达 258.1875 ms，未通过 66.6667 ms 门槛。\n\n'
        '![离线 CTC 实际对齐前后](docs/assets/ctc-alignment-20261018/comparison.gif)\n\n'
        '[原视频](docs/assets/ctc-alignment-20261018/input.mp4) · [原声音](docs/assets/ctc-alignment-20261018/input.wav) · '
        '[原文](docs/assets/ctc-alignment-20261018/transcript.txt) · [真实成片](docs/assets/ctc-alignment-20261018/result.mp4) · '
        '[原始词块/来源](docs/assets/ctc-alignment-20261018/input-provenance.json) · '
        '[实际安装包](docs/assets/ctc-alignment-20261018/agent-video-kit-cp313-win_amd64.zip) · '+f'[实测/全部失败]({REPORT})\n')
    t=t.replace('## 实测演示素材\n','## 实测演示素材\n'+gallery,1)
    # Add an executable example without changing the existing getting-started commands.
    position=t.index('## 目录')
    example=('### 给定原文的离线字词对齐\n\n'
        '使用已有完整标准 Wav2Vec2 CTC safetensors、原生 Torch/Transformers Python 和权利证明；运行时不下载。'
        '先登记，再预览；执行时去掉 `--dry-run`，按需显式添加 `--apply --track-id captions --font-asset-id font`。'
        '这条路径保留 `ALIGNMENT_REVIEW_REQUIRED`，当前精度门槛未通过。\n\n'
        '```powershell\n'
        'python -m ai_ad_editor asr adapter register --project <项目> --adapter-id ctc --engine transformers-wav2vec2-ctc-local-v1 --python-executable <原生Python> --model-path <本地safetensors目录> --device cuda --evidence <本地证明.json> --license-spdx Apache-2.0\n'
        'python -m ai_ad_editor subtitle align --project <项目> --asset-id speech --adapter-id ctc --transcript <UTF-8原文.txt或.srt> --output assets/aligned/new.json --granularity whitespace --dry-run\n'
        '```\n\n')
    t=t[:position]+example+t[position:];write(p,t)
    p=ROOT/REPORT;t=p.read_text(encoding='utf-8')
    t=t.replace('完整回归待终态。',f'完整回归 **{n}/{n}，{seconds} 秒**，0 跳过，170 文件前后冻结。',1)
    t=t.replace('| CA12 | 完整回归 | 等待最终冻结终态；',f'| CA12 | 完整回归 | **{n}/{n}，{seconds} 秒**、0 跳过、170 文件冻结；28 新增方法为完整子集；')
    t+='\n[最终来源/发行/媒体/文档审计](evidence/ctc-release-audit-20261018.json)核对上述计数、全部公开文件 SHA 及四个发行文件差异；不把核验记录视为声学质量通过。\n';write(p,t)
    p=ROOT/'docs/构建进度总表_2026-10-16.md';t=p.read_text(encoding='utf-8')
    t=re.sub(r'(?m)^\| 10 \|.*$', '| 10 | 文字、字幕与自动转写/对齐 | 部分实现，CTC 精度门槛失败 | 原生排版/高亮、OpenFilm 分句与描线、真实 Whisper；V49 本地中英 CTC、原文码点/长窗/SRT、236 帧高亮 | 英文词块误差 258.1875 ms >66.6667 ms；中文无精标；说话人/歌词/翻译、广泛 CJK/RTL 与自然质量未验 |',t)
    t=re.sub(r'(?m)^\| 24 \|.*$', '| 24 | Agent Skills | 已实现，持续扩展 | 14 个 video-cut- Skill；CTC/七轮离线安装/失败质量边界已同步；14 项格式与联接、172 引用通过 | 实际内容和自然质量持续验收，技能数不代表覆盖率 |',t)
    t=re.sub(r'(?m)^\| 25 \|.*$',f'| 25 | 质量、性能与发行 | 本机隔离发行已核验，整体未完成 | V49 完整 {n}/{n}、170 文件冻结；116 包内文件/七轮包/11 隔离 CLI；安装版真实 CTC 及 236 帧 RGB/PCM 与开发版一致 | 定位精度失败；三静帧无播放/听审；其他机器/平台、长片/HDR、自然 AI/完整剪映待验 |',t);write(p,t)
    p=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md';t=p.read_text(encoding='utf-8')
    row=f'| CTC 字词强制对齐（V49） | 本地中英声学模型、码点/样本时钟、长窗/SRT、字幕入轨、七轮隔离安装 | [真实 worker、236 帧/PCM 与安装结果](./离线CTC字词强制对齐实测_2026-10-18.md)；28 新增方法为完整 {n} 子集 | 英文门槛失败 258.1875 ms >66.6667 ms；中文无精标、无歌词/多说话人/自然广泛验收 |'
    t=re.sub(r'(?m)^(\| 显式逐笔描线（V48）.*)$',lambda m:row+'\n'+m[0],t,count=1);write(p,t)
    p=ROOT/'docs/README.md';t=p.read_text(encoding='utf-8')
    t=t.replace('：仅元数据，0 权重下载/推理，不属于 V48 能力。','：历史 V48 仅元数据；后续 V49 真实推理与失败精度门槛另列。')
    t+='\n- [V49 CTC 对齐契约](specs/离线CTC字词强制对齐契约_v0.1_2026-10-18.md)、[原片/GIF/安装/精度失败](validation/离线CTC字词强制对齐实测_2026-10-18.md)及[模型/语音/依赖来源](third-party/CTC模型与英文演示语音来源_2026-10-18.md)。\n';write(p,t)
    print(json.dumps({'status':'published_locally_with_quality_failure','full_methods':n,'frozen_files':files,'core_docs':len(CORE)}))


if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args();run()
