"""Document measured V59 ROSE research without changing V58 product acceptance."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from sync_color_automation_documents import marked, line

REPORT = 'ROSE本地对象移除与原始全画面输出实测_2026-10-19.md'
CONTRACT = 'ROSE离线对象移除与副作用核验契约_v0.1_2026-10-19.md'
EVIDENCE = 'validation/evidence/rose-native-20261019-v59'
ASSETS = 'assets/rose-native-20261019-v59'


def run():
    receipt = json.loads((ROOT/'docs'/EVIDENCE/'verification.json').read_bytes())
    independent = json.loads((ROOT/'docs/validation/evidence/rose-independent-20261019-v59/verification.json').read_bytes())
    static_review = json.loads((ROOT/'docs'/EVIDENCE/'static-review.json').read_bytes())
    if static_review['status'] != 'agent_static_contacts_reviewed':
        raise ValueError('ROSE_ACTUAL_STATIC_CONTACT_REVIEWS_REQUIRED')
    public_observations = '\n'.join('- '+value for value in static_review['public']['observations'])
    natural_observations = '\n'.join('- '+value for value in static_review['natural']['observations'])
    public, natural = receipt['public'], receipt['natural']
    rose = {r['region']: r for r in public['rose_scores']}
    fgt = {r['region']: r for r in public['fgt_scores']}
    lama = {r['region']: r for r in public['lama_scores']}
    overall = rose['overall']
    prestart = [row for row in natural.get('global_gpu_snapshots', [])
                if row['worker_last_recorded_phase'] == 'verifying-frozen-local-inputs']
    resource_note = ''
    if prestart:
        resource_note = (f"自然轮模型加载前的 {len(prestart)} 次离散 nvidia-smi 快照可用 "
            f"{min(row['free_mib'] for row in prestart)}–{max(row['free_mib'] for row in prestart)} MiB，"
            f"利用率 {min(row['utilization_percent'] for row in prestart)}–{max(row['utilization_percent'] for row in prestart)}%；"
            f"worker 的 PyTorch 准入读数为 {natural['worker']['cuda_free_before_bytes']/1024**2:.0f} MiB。"
            '两者未建立同一瞬时测量，现有入口只检查 PyTorch API，没有全局显存二次核验。'
            '**共享显卡的全局预算准入仍未验收**；模型运行/像素核验不能证明显存预约或隔离。'
            '本轮没有回收其它用户 GPU 任务，时长不作为独占设备的速度指标。')
    passed = public['controlled_quality_passed']
    gate = '通过' if passed else '未通过'
    score = f"{overall['masked_psnr_db']:.6f} dB /运动残差 {overall['known_motion_residual_mae_rgb']:.6f}"
    summary = ('2026-10-19 **V59（研究）**：固定 ROSE 作者 Transformer、Wan T5/VAE 在现有 Windows 原生 CUDA Python '
        '真实运行两条既有样例，各 32 帧@8 fps、50 步；补末帧至 33 后裁回，不改原时钟。'
        f'受控整体 **{score}**，沿用 ≥30 dB、MAE≤5 且不差于 FGT 的门槛，结果 **{gate}**。'
        '原始全画面和限于选区的合成分别保存；区外 RGB/原 Alpha/每帧 PTS 与自然 768,000 字节 PCM 核对。'
        'ROSE 仍为独立研究 runner，未注册生产引擎；#56 自然背景/纹理/阴影反射、全局显存准入与完整剪映等价未验收。'
        '186 产品输入未改，未重跑产品全量；最近完整产品回归仍为 V58 1357/1357。')
    rows = []
    for name, label in [('upper', '上表面 +2 px/帧'), ('lower', '下表面 −3 px/帧'), ('overall', '合计选区')]:
        r, f, l = rose[name], fgt[name], lama[name]
        rows.append(f"| {label} | {l['masked_psnr_db']:.6f} | {f['masked_psnr_db']:.6f} | {r['masked_psnr_db']:.6f} | "
                    f"{l['known_motion_residual_mae_rgb']:.6f} | {f['known_motion_residual_mae_rgb']:.6f} | {r['known_motion_residual_mae_rgb']:.6f} |")
    worker_rows = []
    memory_rows = []
    for name, label, record in [('public', '原创双表面', public), ('natural', '既有私有自然', natural)]:
        worker = record['worker']
        worker_rows.append(f"| {label} | {worker['elapsed_seconds']:.3f} s | {worker['cuda_peak_allocated_bytes']/1024**3:.3f} GiB | "
                           f"{worker['model_calls']['T5']} /{worker['model_calls']['transformer']} /{worker['model_calls']['VAE_encode']} /{worker['model_calls']['VAE_decode']} /0 | "
                           f"{record['raw_outside_selection_changed_pixels']:,} | 0 |")
        observed = record['windows_process_observation']
        memory_rows.append(f"| {label} | {observed['last_observed_os_peak_working_set_bytes']/1024**3:.3f} GiB | "
                           f"{observed['sampled_peak_private_bytes']/1024**3:.3f} GiB | {observed['samples']} |")
    report = f'''# ROSE 本地对象移除与原始全画面输出实测

{summary}

本轮推进自然背景修复候选的真实验证，依据[先行契约](../specs/{CONTRACT})；成功加载、运行完整性与画质门槛分别判定。三行评分是同一原创样例的重叠统计，不能当作三个独立场景；自然沿用 V44 输入/选区，没有增加自然来源场景。该结果不能推广到长视频、其它设备或全部自然广告。

## 实际检查

| 编号 | 检查 | 结果与边界 |
|---|---|---|
| R59-F01 | 原始来源与权重 | ROSE 代码 `6be41c54`、模型 `8a5e57c9`、Wan-Fun 基础 `9bcbbcf6`；13 文件逐项 SHA/LFS 或 Git blob 验证。模型不进入 Git |
| R59-F02 | 严格真实加载 | T5 5,680,910,336 参数、ROSE 1,564,428,608 参数、VAE 126,892,531 参数；meta/mmap/strict assign，缺失/额外键均 0；PTH 使用 weights_only=True |
| R59-F03 | 本地执行 | 原生 Python 3.13.14 /Torch 2.13.0+cu130 /diffusers 0.39.0 /transformers 5.14.1 /accelerate 1.14.0，RTX 3060 12 GiB；没有虚拟化、GUI、浏览器或运行时安装 |
| R59-F04 | 内存与精度 | T5 显式 GPU 7168 MiB/CPU 8192 MiB 权重预算、BF16，释放后再加载视频网络；Transformer BF16、时间嵌入/投影 FP32、VAE FP32，无量化/TeaCache/分布式路径。精度与作者全 FP16 示例不同，不能据此声称作者实现字节等价 |
| R59-F05 | 无参考 CLIP 分支 | 作者无参考图路径把 CLIP 输出完全清零；ViT-H/14 224/14→257 token、宽 1280，直接构造同形零 context；0 次 CLIP 前向，未下载 CLIP。参考图输入明确不支持 |
| R59-F06 | 原时钟/输入 | 同一被遮挡输入、同一二值选区，条件视频保留对象；32→33 重复末帧，交付裁回 32@8 fps。真值只交给父进程评分，未传 worker |
| R59-F07 | 受控预声明画质 | ≥30 dB、运动残差≤5，且两指标分别不差于 FGT；本轮 **{gate}**，没有放宽门槛。LaMa/FGT 为有 SHA 的历史实际输出，未重跑或重复计模型调用 |
| R59-F08 | 原始/选区输出 | 原始全画面输出和限于选区结果分别编码。最终区外和 Alpha 精确保留来自显式合成约束，不表示模型自动识别并保护全部区外内容，也不证明自动选中阴影/反射 |
| R59-F09 | 实际编码 | 两例 raw/final QTRLE MOV 全帧重解码与 PTS 对齐；六份公开 RGB 无损 MP4 共 192 帧包含重复对照视图，不能算 192 条新样例。Alpha 皆为 255，不能证明 H.264 任意透明度 |
| R59-F10 | 自然音频/质量 | 源/交付 48 kHz 立体声 PCM 768,000 字节一致；0/10/21/31 帧 Agent 静态目检。自然无隐藏背景真值，未做连续播放或听审，质量未验收。私有像素不进入 Git |
| R59-F11 | 独立评分 | 新 runner 用整数逐行与显式运动坐标累计；审计器对公开编码重新解码，再用未改 V44 roll 评分独立核对，三路模型/三行逐项一致 |
| R59-F12 | 产品与失败 | 前后 186 产品输入不变；未注册生产适配器，未重跑 V58 全量；初次准备/解释器错误与受控质量失败均保留，不能以研究执行计产品通过 |
| R59-F13 | 全局 GPU 预算 | T5 权重映射按 7168/8192 MiB 规划；准入仅使用 PyTorch 可用量，模型加载前 nvidia-smi 快照与之不同；共享显卡全局预算条款未验收，不能据执行成功宣称全局资源保护成立 |

旧预检文档生成器的执行原件按历史 SHA 封存；当前入口会在已有推理请求或实测报告时拒绝写回“0 次前向”。[实际拒绝记录](evidence/rose-preflight-sync-history-20261019-v59/verification.json)确认 12 份文档字节未变；这是文档工具核验，不增加模型或产品回归计数。

## 同一选区对照

| 区域 | LaMa PSNR dB | FGT PSNR dB | ROSE PSNR dB | LaMa 运动残差 MAE | FGT 运动残差 MAE | ROSE 运动残差 MAE |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

门槛使用源尺度选区内 PSNR 和已知两种刚体运动下的残差；不是自然感知质量、完整人体分割或真实广告泛化的分数。ROSE 为生成模型，FGT 为光流/梯度传播模型，上下文和精度处理不同；不能把此表解释为仅替换一个算子的因果试验。

| 既有样例 | worker 时长 | CUDA 峰值 allocated | T5/Transformer/VAE 编/解/CLIP 实际调用 | 原始区外变化像素 | 最终区外变化像素 |
|---|---:|---:|---|---:|---:|
{chr(10).join(worker_rows)}

时长包含本机模型读取、SHA 核对和运行，不是其它硬件速度保证；CUDA allocated 不是整机显存或 RAM 峰值。

| 既有样例 | 最后观察到的 Windows 进程峰值工作集 | 采样 private bytes 最大值 | 30 秒采样数 |
|---|---:|---:|---:|
{chr(10).join(memory_rows)}

Windows 观察器只读核验过路径的进程句柄，不修改优先级、内存或其它用户进程。工作集、private bytes 与 CUDA allocated 含义不同，不能相加；30 秒采样可能漏掉退出前最后一次峰值。原逐次计数与观察器源码随证据保存。

{resource_note}

各 worker 在运行前后完整读取并核对权重 SHA。后续独立审计绑定这两次核对和获取记录，对三个大 checkpoint 检查当前长度，不再额外扫描约 15 GB；其余冻结小文件与公开交付逐项重算 SHA，公开原片重新解码评分。

## Agent 静态抽帧目检

通过原尺寸联系图查看两条既有样例的第 0、10、21、31 帧。受控联系图 SHA 与下方实际发布文件一致；自然预览在最终文件核对前查看，发布时与最终联系图 SHA 完全一致。自然图留在忽略目录，只公开摘要和观察，不公开像素。[实际目检记录](evidence/rose-native-20261019-v59/static-review.json)。这是 Agent 图像观察，未执行连续播放或音频听审。

受控样例：

{public_observations}

自然样例：

{natural_observations}

## 原输入和实际输出

![原创输入、历史 LaMa/FGT、实际 ROSE 原始/选区输出、背景真值](../{ASSETS}/comparison.gif)

[六格完整 MP4](../{ASSETS}/comparison.mp4)、[四时刻静态联系表](../{ASSETS}/contact.png)。GIF 32 帧、120/130 ms 交替共 4 秒，半尺寸/128 色/无声，仅供展示；MP4/GIF 为有损衍生，不用于像素评分。

| 内容 | 预览 MP4 | 实际 RGB 无损原片 |
|---|---|---|
| 原始被遮挡输入 | [原输入](../{ASSETS}/source.mp4) | [无损](../{ASSETS}/source-lossless.mp4) |
| ROSE 原始全画面 | [实际输出](../{ASSETS}/rose-raw.mp4) | [无损](../{ASSETS}/rose-raw-lossless.mp4) |
| ROSE 选区合成 | [实际输出](../{ASSETS}/rose-selected.mp4) | [无损](../{ASSETS}/rose-selected-lossless.mp4) |
| 历史 FGT | [对照](../{ASSETS}/fgt.mp4) | [无损](../{ASSETS}/fgt-lossless.mp4) |
| 历史 LaMa | [对照](../{ASSETS}/lama.mp4) | [无损](../{ASSETS}/lama-lossless.mp4) |
| 独立背景真值 | [真值](../{ASSETS}/truth.mp4) | [无损](../{ASSETS}/truth-lossless.mp4) |

原创输入/真值 CC0-1.0；模型结果是研究证据，未自动进入可商用内容库。[逐文件 SHA/原命令/实际调用](evidence/rose-native-20261019-v59/verification.json)、[独立重解码](evidence/rose-independent-20261019-v59/verification.json)、[来源/显示边界](../{ASSETS}/provenance.json)。公开的精简原源码 ZIP 仅包括用到的 12 个来源/配置/许可文件，没有演示媒体、模型、ProPainter 或分布式加速器。[获取和严格加载预检](ROSE本地模型获取与离线预检_2026-10-19.md)是此前 0 次前向的历史阶段，不能作为本轮运行状态；[早期准备/解释器错误](evidence/rose-preflight-collection-20261019-v59/development-errors.json)独立保留。

## 复现和接入决策

来源：[ROSE 作者仓库](https://github.com/Kunbyte-AI/ROSE)、[作者模型](https://huggingface.co/Kunbyte/ROSE)、[Wan-Fun 基础](https://huggingface.co/alibaba-pai/Wan2.1-Fun-1.3B-InP)。代码/权重声明 Apache-2.0，与演示组件、训练数据、原拍摄和生成结果分别处理，见[本轮来源范围](../third-party/ROSE原生研究依赖与来源说明_2026-10-19.md)。

研究脚本位于 `scripts/prepare_rose_research.py`、`scripts/run_rose_research.py`、`research/temporal-neural/rose_worker.py`。需要已固定、显式获取的原源码/本地权重及现有原生 CUDA Python；干净克隆不包含权重或私有自然镜头，运行脚本不自动下载。准备与运行使用全新 work 目录，先以 `--mode prepare --case public` 建立输入，再以 `--mode run` 指定本地 prepared/bundle/acquisition。实际命令和执行脚本原件已存本轮证据；准备时锁定代码，改动必须建立新轮次，不覆盖首轮。

OpenFilm 的字幕、编辑规则、片段组与 HTML 动效可以降低宿主/工作流成本，详见[10 项复用决策](../OpenFilm复用复核与开发成本更新_2026-10-19.md)。这些模块不会补出对象移除神经权重或自然背景质量；本轮独立验证 ROSE，仍需按结果选择修复路径、完善选区/时序、加入取消/预算/权利闭包并扩充授权自然场景后再接入产品。当前 #56 保持 degraded。
'''
    (ROOT/'docs/validation'/REPORT).write_text(report, encoding='utf-8', newline='\n')
    docs = ('README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')
    for name in docs:
        path = ROOT/name
        text = path.read_text(encoding='utf-8')
        prefix = 'docs/validation/' if name == 'README.md' else ('./' if name.startswith('docs/validation/') else 'validation/')
        contract_prefix = 'docs/specs/' if name == 'README.md' else ('../specs/' if name.startswith('docs/validation/') else 'specs/')
        block = summary+f' [原片/GIF/失败与范围]({prefix}{REPORT})、[先行契约]({contract_prefix}{CONTRACT})。'
        if '<!-- V59-RESEARCH -->' in text:
            text = marked(text, 'V59-RESEARCH', block)
        else:
            first = text.find('\n')+1
            text = text[:first]+'\n<!-- V59-RESEARCH -->\n'+block+'\n<!-- /V59-RESEARCH -->\n'+text[first:]
        if name == 'README.md':
            row = (f'| V59 | ROSE 离线对象移除研究 | 两条既有 32 帧/50 步；受控 {score}，门槛{gate}；原始/选区输出和自然 PCM 独立核对 | '
                   '未接入生产；自然质量/阴影反射/全局显存准入未验；186 产品文件未改，未重跑 V58 全量 | '
                   f'[原输入/实际 MP4/GIF/失败]({prefix}{REPORT}) |')
            if '| V59 |' in text:
                text = line(text, '| V59 |', row)
            else:
                lines = text.splitlines()
                index = next(i for i, value in enumerate(lines) if value.startswith('| V58 |'))
                lines.insert(index+1, row)
                text = '\n'.join(lines)+'\n'
            demo = ('**V59 研究原片对照**：六格依次为原输入、历史 LaMa、历史 FGT、实际 ROSE 原始全画面、ROSE 限于选区合成和独立真值；'
                    f'受控门槛{gate}，自然与生产未验收。'
                    f'[原视频](docs/{ASSETS}/source.mp4)、[实际选区输出](docs/{ASSETS}/rose-selected.mp4)、[完整对照](docs/{ASSETS}/comparison.mp4)。\n\n'
                    f'![V59 真实离线 ROSE 研究对照](docs/{ASSETS}/comparison.gif)')
            if '<!-- V59-DEMO -->' in text:
                text = marked(text, 'V59-DEMO', demo)
            else:
                text = text.replace('<!-- V58-DEMO -->', '<!-- V59-DEMO -->\n'+demo+'\n<!-- /V59-DEMO -->\n\n<!-- V58-DEMO -->', 1)
        if name == 'docs/构建进度总表_2026-10-16.md':
            text = line(text, '| 研究状态与历史快照 |', f'| 研究状态与历史快照 | V59 ROSE 两例各 32 帧/50 步真实离线研究，受控 {score}、门槛{gate}，自然未验收/未接入；OpenFilm R05 727 文件/63 通过/1 跳过另计 |')
            text = line(text, '| 06 |', '| 06 | 时间线与基础剪辑 | 已实现，有边界 | V57 完整作者输出速度/曲线/反向/定格及长度自动随动；V56 持久磁吸/跨剪口同步拆分；保留作者可编辑图 | 全手势/屏幕吸附、复杂全局自动化/跟踪重规划/自然/VFR/HDR/长片未验 |')
            text = line(text, '| 1 | 解决自然背景', f'| 1 | 解决自然背景重建、遮挡与时序 | V59 ROSE 真实运行两条既有样例，受控 {score}、预声明门槛{gate}；V44 FGT 33.14 dB/0.91 仍为受控对照。自然无真值，完整对象/阴影/反射、纹理与时序未验收；完善选区和可见支持，扩充授权自然场景及连续视听，#56 仍 degraded |')
        if name.endswith('能力覆盖与验收矩阵_v0.1_2026-10-13.md'):
            row = (f'| ROSE 离线修复候选（V59 研究） | 原作者 Transformer/T5/VAE、分阶段原生 CUDA、原始全画面与显式选区合成分别记录 | '
                   f'[两例 32 帧/50 步真实输出]({REPORT})，受控 {score}、门槛{gate}；独立评分/编码/PCM | '
                   '未注册生产适配器；自然/完整对象、副作用与全局显存准入未验收，#56 degraded；未重跑 V58 全量 |')
            if '| ROSE 离线修复候选（V59 研究） |' in text:
                text = line(text, '| ROSE 离线修复候选（V59 研究） |', row)
            elif '| ROSE 候选预检（V59 研究） |' in text:
                text = line(text, '| ROSE 候选预检（V59 研究） |', row)
            else:
                marker = '| 本地区域修复与对象移除 |'
                lines = text.splitlines()
                index = next(i for i, value in enumerate(lines) if value.startswith(marker))
                lines.insert(index, row)
                text = '\n'.join(lines)+'\n'
        path.write_text(text, encoding='utf-8', newline='\n')
    history = ROOT/'docs/validation/ROSE本地模型获取与离线预检_2026-10-19.md'
    text = history.read_text(encoding='utf-8')
    note = ('**历史阶段记录**：以下正文保留推理前的 0 次前向快照，显存资源对应 UTC 2026-10-18 19:35；'
            '后来 worker 的 PyTorch 检查通过并进行了真实运行；共享显卡全局准入仍未验收，当前结果见'
            f'[{REPORT}]({REPORT})。旧资源快照和待执行清单不代表后续运行状态。')
    if '<!-- V59-PREFLIGHT-HISTORY -->' in text:
        text = marked(text, 'V59-PREFLIGHT-HISTORY', note)
    else:
        first = text.find('\n')+1
        text = text[:first]+'\n<!-- V59-PREFLIGHT-HISTORY -->\n'+note+'\n<!-- /V59-PREFLIGHT-HISTORY -->\n'+text[first:]
    history.write_text(text, encoding='utf-8', newline='\n')
    license_report = ROOT/'docs/third-party/时序修复候选源码与许可说明_2026-10-18.md'
    text = license_report.read_text(encoding='utf-8')
    existing = next(value for value in text.splitlines() if value.startswith('| L07 |'))
    prefix = existing.rsplit('|', 2)[0]
    updated = (prefix+'| V44 当时仅源码/导入；后续 '
        f'[V59 真实运行](../validation/{REPORT}) 两条既有 32 帧/50 步，受控门槛{gate}，'
        '自然质量未验收，未注册生产引擎；演示组件不采用 |')
    text = line(text, '| L07 |', updated)
    license_report.write_text(text, encoding='utf-8', newline='\n')
    skill = ROOT/'skills/video-cut-local-models/SKILL.md'
    text = skill.read_text(encoding='utf-8')
    start = text.index('clearance from that gate. V44 only imported ROSE;')
    end = text.index("ProPainter's noncommercial terms", start)
    replacement = ('clearance from that gate. V44 only imported ROSE; the later\n'
        '[V59 loading evidence](../../docs/validation/ROSE本地模型获取与离线预检_2026-10-19.md)\n'
        'is a historical zero-forward snapshot. The subsequent\n'
        f'[V59 real inference](../../docs/validation/{REPORT})\n'
        'runs the author T5/ROSE/VAE on two unchanged 32-frame, 50-step cases.\n'
        f'The controlled gate {"passed" if passed else "failed"}; natural quality and global GPU\n'
        'admission remain unaccepted.\n'
        'Raw full-frame results and selected-region composites are separate;\n'
        'outside-region preservation comes from explicit composition. No ROSE\n'
        'production adapter is registered. Research acquisition is an explicit\n'
        'development operation, never a runtime or Skill download.\n')
    text = text[:start]+replacement+text[end:]
    skill.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'documents_updated': len(docs)+3, 'skills_updated': 1, 'research_version': 'V59',
                      'current_product_version': 'V58', 'controlled_quality_passed': passed}))


if __name__ == '__main__':
    run()
