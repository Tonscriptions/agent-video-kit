"""Publish V64 only after terminal frozen regression and actual native evidence."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
from run_frozen_regression import frozen
from sync_color_automation_documents import marked

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/audio-source-context-20261019-v64'
MEDIA=ROOT/'docs/assets/audio-source-context-20261019-v64-r2'
AUDIT=ROOT/'docs/validation/evidence/audio-context-media-20261019-v64-r1'
INSTALL=ROOT/'docs/validation/evidence/audio-context-install-20261019-v64-r1'
OFFLINE=ROOT/'docs/assets/audio-context-offline-20261019-v64-r1'
REPORT='离线音频真实源上下文与短窗音高实测_2026-10-19.md'
CONTRACT='离线音频真实源上下文与精确选区契约_v0.1_2026-10-19.md'
V63='VACE共享显存真实重试与准入拒绝_2026-10-19.md'
DOCS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
    'docs/specs/AgentCLI契约_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
def read(p):return json.loads(p.read_bytes())
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def run():
    current=frozen();full=read(BASE/'full-r1.json');unit=read(BASE/'unit-r1.json');media=read(MEDIA/'verification.json')
    audit=read(AUDIT/'verification.json');install=read(INSTALL/'verification.json');skills=read(BASE/'skills-r1.json')
    for item in (full,unit,media,audit,install):
        if not item.get('frozen_equal') or item.get('frozen_before')!=current or item.get('frozen_after')!=current:raise ValueError('current frozen qualification missing')
    if not full.get('terminal_ok') or full['exit_code'] or full['methods']!=1410 or full['skipped'] or len(current)!=196:raise ValueError('terminal 1410-method full suite required')
    if not unit['terminal_ok'] or unit['methods']!=9 or unit['exit_code'] or unit['skipped']:raise ValueError('9 unit subset missing')
    if audit['status']!='passed_independent_source_context_media_negative_quality_retained' or install['status']!='passed_isolated_install_and_decoded_audio_context':raise ValueError('independent media or actual installation missing')
    if skills['skill_count']!=17 or skills['local_links_checked']!=232:raise ValueError('current Skill registration missing')
    review=read(MEDIA/'preview/static-review.json')
    if review['reviewed_samples']!=3 or review['audio_listened'] or review['continuous_playback']:raise ValueError('static review scope missing')
    manifest_path=ROOT/'video-cut-install-manifest.json';manifest=read(manifest_path)
    previous=manifest.get('current_audit');history=manifest.setdefault('audit_history',[])
    if previous and not any(x.get('record')==previous.get('record') for x in history):history.append(previous)
    for entry in manifest['skills']:
        digest=sha(ROOT/'skills'/entry['name']/'SKILL.md').split(':',1)[1]
        if digest!=entry['skill_md_sha256']:
            old=entry['skill_md_sha256'];hashes=entry.setdefault('skill_md_sha256_history',[])
            if old not in hashes:hashes.append(old)
            entry['previous_manifest_skill_md_sha256']=old;entry['skill_md_sha256']=digest
    manifest['current_audit']={'record':(BASE/'skills-r1.json').relative_to(ROOT).as_posix(),'record_sha256':sha(BASE/'skills-r1.json'),
        'checked_at_utc':skills['checked_at_utc'],'skills':17,'local_links_checked':232,
        'semantics':'V64 explicit real-source audio context and exact authored crop; pitch/phase/natural gates separate; V63 real GPU rejection retained; no full CapCut parity acceptance'}
    save(manifest_path,manifest)
    rows=[]
    labels=['4 ms 双音/apart','4 ms 双音/together','4 ms 脉冲/正向','4 ms 脉冲/反向','嵌套 Bezier/1.5 秒',
            '125 ms 反相/apart','125 ms 反相/together','源头 4 ms/只后句柄']
    for r,label in zip(media['records'],labels,strict=True):
        z,c=r['variants']['zero'],r['variants']['context']
        def freq(v):return '/'.join(f'{x:.6f}' for x in v['peaks_hz'])
        result='音高通过' if c['pitch_gate_passed'] else '**音高失败**'
        if r['id']=='C06':result+='；**反相失败**，残差 0.00246022013'
        if r['id']=='C07':result+='；本例反相残差 0'
        rows.append(f"| {r['id']} | {label} | {freq(z)} | {freq(c)} | {result} | [0 ms](../assets/{MEDIA.name}/{z['media']}) /[64 ms](../assets/{MEDIA.name}/{c['media']}) |")
    seconds=full['suite_seconds']
    text=f'''# V64：离线音频真实源上下文与短窗音高实测

2026-10-19，产品增加可选 `settings.audio_stretch.source_context_ms`：**0..1000 整数，默认 0**。本地 Rubber Band R3 使用实际相邻源采样处理，再精确裁回原作者输出；不会延长时间线，也不循环或补零伪造音频。选定受控短音的音高改善，**不代表自然音频或完整剪映等价通过**。

## 实际结果与计数

| 编号 | 核验 | 实际结果和范围 |
|---|---|---|
| V64-01 | 完整产品回归 | **1410/1410，{seconds:.3f} 秒，0 跳过，196 输入前后冻结一致**；新增 9 项专项已包含在全量，不能相加 |
| V64-02 | 开发版真实 CLI | 8 组 × 零上下文/64 ms，**144 CLI，408 最终帧/PTS，816,000 立体声采样帧**；独立原始 V62 基线另 9 CLI/24 帧/48,000 采样帧 |
| V64-03 | 独立原始输入参考 | 从原 WAV 的真实前后句柄重新执行 **8 次 native R3**，每个作者选区裁切与成片的 float32 PCM 最大差均为 0；不是重用产品缓存作为答案 |
| V64-04 | 画面、时钟和边界 | 16 个成片中，上下文/零上下文对应画面逐帧相同；CFR 全帧 PTS 门槛 1 ms；作者音频区间后的采样严格为 0，反向发生在裁切之后 |
| V64-05 | 原生离线安装 | 7 个锁定 wheel、**131 包内文件**与源码/轮包字节相同；安装版 **146 隔离 CLI（2 控制+144 媒体）/408 帧/816,000 采样帧**，与开发版解码音画完全相同；安装流程另有旧基线 9 次 source CLI，不冒充安装命令 |
| V64-06 | 嵌套工程往返 | 安装版另 **5 隔离 CLI /36 帧/72,000 采样帧**；包导出/导入、校验、策略、重渲染保留 64 ms 设置和完整曲线，实际 RGB/PCM 与开发版相同，不加进上行 408 帧 |
| V64-07 | Skills | **17 个 `video-cut-` Skill /232 本地引用**，全部快速校验和 C→E 目录联接通过；3 份音频使用/质量说明与 1 份 VACE 失败说明更新 |
| V64-08 | 可视演示 | 实际 PCM 波形/频谱/负例 GIF，1120×840、**3 页/6 秒、无声统计图**；实际 C01 AAC MP4 是有损预览，逐采样证据使用 float32 MKV；只静看 3 张图，未连续播放或听审 |

`立体声采样帧` 每项含左右两个采样，不能与单声道采样个数混用。C05 每版 36 帧，其余 7 组每版 24 帧；同一工程有显式静音尾部/黑场尾部，均计入最终视频。新训练模型前向为 0，没有新的自然场景盲测。

## 原始媒体与音高、相位分项

[原视频](../assets/{MEDIA.name}/source.mp4)、[400/800 Hz 原 WAV](../assets/{MEDIA.name}/stereo-tones.wav)、[原脉冲](../assets/{MEDIA.name}/pulses.wav)、[原反相 WAV](../assets/{MEDIA.name}/antiphase.wav)、[实际 C01 AAC 预览](../assets/{MEDIA.name}/preview/C01-context-aac-preview.mp4)、[嵌套工程包](evidence/audio-context-media-20261019-v64-r1/C05-context-project.zip)、[安装版重导出成片](evidence/audio-context-media-20261019-v64-r1/C05-roundtrip.mkv)。输入为本项目既有 CC0 程序夹具；Rubber Band 的 GPL 许可另附，未打包其二进制。

![实际采样统计图，非 GUI 录屏或模型动画](../assets/{MEDIA.name}/preview/comparison.gif)

主峰门槛沿用 **±5 Hz**，按输出中间 75% 加 Hann 窗、262144 点 FFT，在 100..1400 Hz 范围选主峰，左右分开；频谱图各曲线独立归一化，不表示响度保持。反相 float32 对照要求 `L+R=0`；普通容器/音峰 `quality check` 通过不能替代音高或相位检查。

| 编号 | 源与处理 | 零上下文主峰 Hz：L/R | 64 ms 主峰 Hz：L/R | 内容门槛 | 实际 float32 MKV |
|---|---|---|---|---|---|
{chr(10).join(rows)}

C01 的原选区仅 192 个源采样；64 ms 前后句柄使输入为 6,336 采样，62.5 倍伸长得到 **396,000 原始输出采样帧**，再裁 `[192000,204000)` 得原 12,000 目标采样帧。只交付原作者时段，R3 分析仍会受邻近瞬态影响。C05 保留原曲线全部锚点，含上下文共 **110 点**，裁 `[3775,75775)`，独立原生参考最大差 0。C08 到真实源头时前句柄为 0，未补齐；尾部边界另有专项覆盖。

**持续失败**：C02 together 的右声道为 789.367676 Hz；C06 apart 的反相残差虽从 0.050574481487 降到 0.002460220130，仍不满足精确相消。另 28 次研究探针中 together 扩到 256/512 ms 也未修复该右声道门槛；4 ms 反相 apart 残差为 0.217855900526。不能把一个改善参数宣称为所有声音、瞬态或立体声质量都修复。

## 接口、失败记录和复现

[契约](../specs/{CONTRACT})描述字段、源边界、有理首尾斜率、512 MiB 每份 PCM 上限、精确裁切、警告与缓存约束。设置通过完整有效的项目 JSON 输入，沿用 `render`；没有新增虚构的 settings 子命令。`schema show` /`capabilities` 已包含该字段和限制。无上下文仍保留原 native 时间图参数行为，C01 用固定 `c4fa4609` 的旧代码真实编码作逐字节解码对照。

| 编号 | 原失败/研究 | 保留与处理 |
|---|---|---|
| DEV64-01 | 隔离候选 r1：新增 Schema 后遗漏硬编码摘要，9 项中 4 项失败 | [原 log](evidence/audio-source-context-20261019-v64/development/isolated-candidate/candidate-unit-r1.log)及四份当时输入保存；更新真实 Schema 摘要后继续，无放宽验证 |
| DEV64-02 | 候选 r2：一个断言把 JSON list 误写为 tuple，8 通过/1 失败 | [原 log](evidence/audio-source-context-20261019-v64/development/isolated-candidate/candidate-unit-r2.log)、[完整冻结源 ZIP](evidence/audio-source-context-20261019-v64/development/isolated-candidate/candidate-unit-r2-sources.zip)；r3 9/9，候选次数不叠加正式全量 |
| DEV64-03 | 第一轮真实媒体：把 render 输出放到项目外，既有路径门禁拒绝 | [r1 failure](../assets/audio-source-context-20261019-v64-r1/failure.json)和原执行脚本/日志保留；仅修正验证脚本，在项目内渲染后复制演示。产品源未为此改变 |
| DEV64-04 | 28 次原生参数探针，包括扩大上下文仍失败的 together 与反相 apart | [完整探针收据](evidence/audio-source-context-20261019-v64/development/verification.json)，公开实际选区 float32 gzip、原输入和 stderr；较大的扩展 WAV 本地保留并公开摘要；最后两轮没有启动时脚本收据，复制件标为当前复现脚本 |

[完整回归](evidence/audio-source-context-20261019-v64/full-r1.json)、[9 项子集](evidence/audio-source-context-20261019-v64/unit-r1.json)、[接入前后源核对](evidence/audio-source-context-20261019-v64/applied-candidate.json)、[开发媒体逐命令收据](../assets/{MEDIA.name}/verification.json)、[独立参考与工程往返](evidence/audio-context-media-20261019-v64-r1/verification.json)、[安装和字节核对](evidence/audio-context-install-20261019-v64-r1/verification.json)、[Skills](evidence/audio-source-context-20261019-v64/skills-r1.json)、[静态目检](../assets/{MEDIA.name}/preview/static-review.json)。rawvideo/float stdout 原样 gzip 压缩，各命令保存退出码和摘要；自动化 checks 与实片/研究分别计数。

[离线发行 ZIP](../assets/{OFFLINE.name}/agent-video-kit-cp313-win_amd64.zip)、[独立 manifest](../assets/{OFFLINE.name}/release-manifest.json)、[本机安装收据](../assets/{OFFLINE.name}/install-receipt.json)。不包含原生 Python、FFmpeg、R3、模型或其外部运行时，也不代表另一台机器验收。商业广告权利检查本轮按未核验登记 **退出 7**，internal 渲染不等于发布授权。

复现可使用 `scripts/smoke_audio_source_context.py`、`scripts/audit_audio_source_context_media.py` 和 `scripts/verify_audio_source_context_install.py`，各自 `--help` 给出本地参数；输出/工作目录必须新建。所有 runtime/temp 在 E 盘，使用既有原生 Windows Python、FFmpeg/R3；无 Docker、WSL、venv 或交互浏览器。全量回归中的既有 HTML 生命周期用例自行清理其持有的 headless 子进程，不声称本轮无任何浏览器测试。

V63 的真实 VACE 重试另见[物理显存拒绝](./{V63})：模型加载前拒绝，无新修复视频。完整剪映等价、自然声音/画面、长片性能、跨平台、空间音频及未经实测的所有极端输入均未验收。
'''
    (ROOT/'docs/validation'/REPORT).write_text(text,encoding='utf-8',newline='\n')
    summary=(f'2026-10-19 **V64（产品）**：显式 R3 `source_context_ms` 0..1000、默认 0；真实源前后句柄、有理边缘时间图、原作者采样裁切后反向。'
        f'完整 **1410/1410、{seconds:.3f} 秒、0 跳过、196 输入冻结**；9 新专项为子集。开发版 **144 CLI/408 最终帧/816,000 立体声采样帧**；'
        '8 次独立原生 R3 裁切 PCM 最大差 0，零上下文与固定 V62 基线解码相同。**131 包内文件/146 隔离 CLI/408 安装帧**；'
        '工程往返另 5 隔离 CLI/36 帧/72,000 采样帧；**17 Skills/232 引用**。选定 4 ms 双音 apart 从 375/819.946 改善为 400.085/799.988 Hz，'
        '**together 右声道 789.368 Hz 仍失败，apart 反相残差 0.00246022013 仍失败**。28 研究探针/旧代码基线分别计数。'
        'GIF 是实际采样统计图、3 页/6 秒、无声；静帧已看，未听审/连续播放。自然质量及完整剪映等价未验收。')
    rejection='2026-10-19 **V63（真实资源拒绝）**：不变 V62 产品/原 VACE 模型流程在 `text-weights` 前因物理可用 3,718 MiB、要求 7,936 MiB 拒绝；0 新模型前向/修复视频。失败、空项目状态与事后自有进程快照保留；未终止其它任务，显存观测不预约资源。'
    for name in DOCS:
        p=ROOT/name;body=p.read_text(encoding='utf-8')
        body=body.replace('2026-10-19 **V62（产品）**','历史产品 2026-10-19 **V62（产品）**',1) if '历史产品 2026-10-19 **V62（产品）**' not in body else body
        r=os.path.relpath(ROOT/'docs/validation'/REPORT,p.parent).replace('\\','/');c=os.path.relpath(ROOT/'docs/specs'/CONTRACT,p.parent).replace('\\','/')
        v=os.path.relpath(ROOT/'docs/validation'/V63,p.parent).replace('\\','/')
        body=marked(body,'V63-REJECTION',rejection+f' [真实日志与限制]({v})。')
        body=marked(body,'V64-CURRENT',summary+f' [原输入/GIF/失败/发行]({r})；[契约]({c})。')
        if name=='README.md':
            if '| V63 |' not in body:
                old=next(x for x in body.splitlines() if x.startswith('| V62 |'))
                body=body.replace(old,old+'\n| V63 | VACE 不变输入真实重试 | 物理 free 3,718 MiB /要求 7,936 MiB；模型加载前拒绝 | 无新模型前向/修复视频；V62 195 输入冻结不变，未重跑全量 | [原日志/状态/范围](docs/validation/'+V63+') |\n'
                    +'| V64 | R3 真实源上下文与作者采样裁切 | 1410/1410；144 CLI/408 帧/816,000 采样帧；131 包内文件/146 隔离 CLI；17 Skills | apart 选定短窗音高改善；together 右声道/反相 apart 仍失败；自然质量及完整等价未验 | [原 WAV/实际 MKV/GIF/失败/发行](docs/validation/'+REPORT+') |')
            hero=f'**V64 音频上下文实测**：原 WAV、实际成片与失败均公开。下图为实际 PCM 的 **3 页/6 秒无声统计图**，非 GUI 录屏；只验证受控音高与采样。\n\n![原输入/实际采样频谱与负例](docs/assets/{MEDIA.name}/preview/comparison.gif)\n\n[原 WAV](docs/assets/{MEDIA.name}/stereo-tones.wav) · [实际有声 AAC 预览](docs/assets/{MEDIA.name}/preview/C01-context-aac-preview.mp4) · [无损 float32 MKV](docs/assets/{MEDIA.name}/C01-context.mkv) · [完整结果](docs/validation/{REPORT})'
            body=marked(body,'V64-DEMO',hero)
        p.write_text(body,encoding='utf-8',newline='\n')
    spec=ROOT/'docs/specs'/CONTRACT;body=spec.read_text(encoding='utf-8')
    body=body.replace('完整回归单独记录。',f'完整回归 1410/1410、{seconds:.3f} 秒、0 跳过、196 输入冻结一致。')
    spec.write_text(body,encoding='utf-8',newline='\n')
    save(BASE/'document-sync.json',{'status':'published_terminal_v64_scope','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'full_sha256':sha(BASE/'full-r1.json'),'report_sha256':sha(ROOT/'docs/validation'/REPORT),
        'manifest_sha256':sha(manifest_path),'documents':DOCS,'generator_sha256':sha(Path(__file__))})
    print(json.dumps({'status':'published_terminal_v64_scope','methods':1410,'skills':17}))

if __name__=='__main__':run()
