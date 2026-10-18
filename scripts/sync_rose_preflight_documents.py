"""Publish completed ROSE loading evidence while leaving inference explicitly pending."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from sync_color_automation_documents import marked, line

REPORT = 'ROSE本地模型获取与离线预检_2026-10-19.md'
CONTRACT = 'ROSE离线对象移除与副作用核验契约_v0.1_2026-10-19.md'
RECEIPT = ROOT/'docs/validation/evidence/rose-preflight-collection-20261019-v59/verification.json'


def run():
    if ((ROOT/'docs/validation/ROSE本地对象移除与原始全画面输出实测_2026-10-19.md').exists()
            or any((ROOT/f'product/.runtime/rose-{name}-r2-20261019-v59/request.json').exists()
                   for name in ('public', 'natural'))):
        raise RuntimeError('ROSE_HISTORICAL_PREFLIGHT_STAGE_CLOSED_DO_NOT_OVERWRITE_REAL_INFERENCE_DOCS')
    result = json.loads(RECEIPT.read_bytes())
    assert result['status'] == 'strict_local_loading_verified_inference_pending'
    assert result['model_forward_calls'] == 0 and not result['quality_scores_available']
    resource = result['resource']
    native = json.loads((RECEIPT.parent/'native-verification.json').read_bytes())
    summary = ('2026-10-19 **V59（研究预检）**：取得固定 ROSE/Wan-Fun 的 13 文件、15,019,977,880 字节，'
        '三组件 T5/Transformer/VAE 完成原生离线 strict 加载，缺失/额外键均 0；精简 12 个原源码/配置/许可文件并保留补丁。'
        '**0 次模型前向、0 条 ROSE 成片、没有画质分数**；同一 V44 受控/自然输入与选区准备完成。'
        f'资源快照可用显存 {resource["free_mib"]} MiB，预声明最低 8192 MiB，未启动推理；保留其它用户进程。'
        '未接入产品，#56 自然修复与完整剪映等价未验收。186 产品输入未改、未重跑全量，最近仍为 V58 1357/1357。')
    report = f'''# ROSE 本地模型获取与离线预检

{summary}

本轮完成来源、文件获取、单 GPU 研究副本和严格结构加载。后续真实推理遵循[先行契约](../specs/{CONTRACT})，50 步、原 32 帧@8 fps、不放宽 FGT 对照门槛。预检不代表该契约的画质、编码交付、时序或自然场景条款已经通过。

| 编号 | 已实际执行 | 结果 /边界 |
|---|---|---|
| R59-P01 | 模型文件获取与完整性 | 固定作者代码 `6be41c54`、模型 `8a5e57c9`、基础 `9bcbbcf6`；13 文件/15,019,977,880 字节；大文件 LFS SHA、小文件 Git blob 校验 |
| R59-P02 | 来源和离线副本 | 12 个原模型/包/配置/Apache LICENSE 文件逐项校验；不复制 GUI、演示媒体、ProPainter、分布式/专有加速器；单设备入口拒绝分布式，补丁和原源码 ZIP 保留 |
| R59-P03 | 真实原生导入 | Windows Python {native['versions']['python']}、Torch {native['versions']['torch']}、diffusers {native['versions']['diffusers']}、transformers {native['versions']['transformers']}、accelerate {native['versions']['accelerate']}；断网、0 网络阻断事件，未安装新包或新建环境 |
| R59-P04 | 三套原权重严格加载 | T5 5,680,910,336 参数、ROSE 1,564,428,608 参数、VAE 126,892,531 参数；meta→strict assign，全部键/形状匹配；PTH weights_only/mmap，Transformer safetensors CPU。没有前向 |
| R59-P05 | 无参考 CLIP 形状证明 | 原代码 ViT-H/14：224/14→257 token、width 1280；无参考路径最后 zeros_like，研究副本直接构造同形零 context。有参考图明确拒绝。未下载 CLIP、0 次 CLIP 前向；数值端到端尚未运行 |
| R59-P06 | 受控输入 | 原 V44 32 帧/432×240 双运动表面、原二值选区；重新生成后与已公开 source/truth 无损 MP4 解码字节相等；背景真值不会传 worker |
| R59-P07 | 自然输入 | 原 V44 32 帧/512×288、原修正 mask 同样 grow 4；与旧原片/选区数组相等，0 新自然来源场景。私有像素不公开 |
| R59-P08 | 独立历史基线复算 | 整体 FGT 33.137925 dB/运动残差 0.908588；LaMa 26.143899/5.213643，逐行整数/显式坐标重算与原记录相同；没有新执行 FGT/LaMa |
| R59-P09 | GPU 资源检查 | 采样 UTC {resource['checked_at_utc']}：{resource['name']}，总 {resource['total_mib']} MiB、可用 {resource['free_mib']} MiB、利用率 {resource['utilization_percent']}%；文本预算 7168+余量 1024=8192 MiB；未启动 worker、未停止其它任务 |
| R59-P10 | 产品与失败 | 当前 186 产品输入与 V58 全量前后摘要相等；本轮未重跑 1357 项。初次来源清单含未选取 README、错误普通 Python 缺 accelerate 均发生在前向前，原执行脚本/错误记录保留 |
| R59-P11 | 待执行 | ROSE 真实 T5/视频网络/VAE 前向、原始/选区输出、独立画质评分、全帧编码/PTS/自然 PCM、可公开 MP4/GIF、自然视听；当前一律未验收 |

资源不足是推理尚未启动的实际原因；未把执行时限或观察超时当作模型失败，也没有重启下载、终止其它 Python 任务、改用线上服务或放低预算。当前资源快照只证明采样时的状态，后续必须重新检查。

## 可复现内容

[获取原始记录](evidence/rose-acquisition-20261019-v59/verification.json)、[原生三组件 strict 预检](evidence/rose-preflight-r3-20261019-v59/verification.json)、[汇总/原文件摘要/源码 ZIP](evidence/rose-preflight-collection-20261019-v59/verification.json)、[显存快照](evidence/rose-preflight-collection-20261019-v59/resources.json)、[来源与许可](../third-party/ROSE原生研究依赖与来源说明_2026-10-19.md)。

仅本地保存权重及自然像素。作者代码、模型和基础来源均固定 SHA；获取属于显式开发网络操作，产品运行没有自动下载。干净克隆不包含权重、此前完整来源审查目录或私有自然场景，不能承诺克隆后立即执行完整研究。

当前原生解释器为 `D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe`，只使用既有 Python/库，不启动 ComfyUI 服务。缓存/临时/研究源和权重均在 E 盘。本次 source 位于 `.runtime/rose-source-r2-20261019-v59`，两条输入在 `.runtime/rose-public-r2-20261019-v59` / `.runtime/rose-natural-r2-20261019-v59`。`scripts/run_rose_research.py --mode run` 是待真实执行的研究入口，不能当作已注册 CLI 引擎。

`research/temporal-neural/rose_worker.py`、发布/独立评分/成片文档生成器已经编写但尚未执行端到端；本页不为它们提供“通过”标记。准备时固定代码和输入，后续修改需新目录，保留首轮。没有 ROSE 结果就不生成展示 GIF；前序实际 FGT/LaMa 原片仍见[历史研究](开源FGT时序修复候选实测_2026-10-18.md)。

OpenFilm 的字幕/片段组/HTML/编辑规则复用结论独立见[10 项模块与成本](../OpenFilm复用复核与开发成本更新_2026-10-19.md)，不能以其服务商封装代替本地 ROSE 或自然质量。下一步在资源满足时执行两条固定样例，再按原门槛决定是否继续接入；当前完整产品目标保持开放。
'''
    (ROOT/'docs/validation'/REPORT).write_text(report, encoding='utf-8', newline='\n')
    documents = ('README.md', 'docs/README.md', 'docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md', 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')
    for name in documents:
        path = ROOT/name
        text = path.read_text(encoding='utf-8')
        prefix = 'docs/validation/' if name == 'README.md' else ('./' if name.startswith('docs/validation/') else 'validation/')
        block = summary+f' [实际预检/失败/资源/待执行项]({prefix}{REPORT})。'
        if '<!-- V59-RESEARCH -->' in text:
            text = marked(text, 'V59-RESEARCH', block)
        else:
            first = text.find('\n')+1
            text = text[:first]+'\n<!-- V59-RESEARCH -->\n'+block+'\n<!-- /V59-RESEARCH -->\n'+text[first:]
        if name == 'README.md':
            row = ('| V59 | ROSE 获取与严格加载（研究） | 13 文件/15,019,977,880 字节；3 组件 strict 加载；12 原来源文件；两条既有输入准备 | '
                   '0 前向/0 ROSE 成片/无画质分数；显存不足未启动；186 产品输入未改，未重跑 V58 全量 | '
                   f'[真实预检/失败/资源](docs/validation/{REPORT}) |')
            if '| V59 |' in text:
                text = line(text, '| V59 |', row)
            else:
                rows = text.splitlines()
                index = next(i for i, value in enumerate(rows) if value.startswith('| V58 |'))
                rows.insert(index+1, row)
                text = '\n'.join(rows)+'\n'
        if name == 'docs/构建进度总表_2026-10-16.md':
            text = line(text, '| 研究状态与历史快照 |', '| 研究状态与历史快照 | V59 ROSE 取得固定权重并 strict 加载 3 组件，0 前向/无新成片，显存不足未启动；OpenFilm R05 727 文件/63 通过/1 跳过另计 |')
            text = line(text, '| 06 |', '| 06 | 时间线与基础剪辑 | 已实现，有边界 | V57 完整作者输出速度/曲线/反向/定格及长度自动随动；V56 持久磁吸/跨剪口同步拆分；保留作者可编辑图 | 全手势/屏幕吸附、复杂全局自动化/跟踪重规划/自然/VFR/HDR/长片未验 |')
            text = line(text, '| 1 | 解决自然背景', '| 1 | 解决自然背景重建、遮挡与时序 | V59 ROSE 权重与三组件 strict 加载通过、两条原输入/选区已准备，显存不足尚未推理；V44 FGT 受控 33.14 dB/0.91，自然残留仍未验收。执行固定 ROSE 对照、完善对象/阴影/反射选区、扩充授权自然样例和连续视听；#56 degraded |')
        if name.endswith('能力覆盖与验收矩阵_v0.1_2026-10-13.md'):
            row = (f'| ROSE 候选预检（V59 研究） | 固定权重、精简原源码、三组件原生 strict 加载、同源输入准备 | [13 文件/3 加载/0 前向]({REPORT}) | '
                   '显存不足未启动；无 ROSE 画质/编码结果；未注册生产引擎，#56 仍 degraded |')
            if '| ROSE 候选预检（V59 研究） |' in text:
                text = line(text, '| ROSE 候选预检（V59 研究） |', row)
            else:
                rows = text.splitlines()
                index = next(i for i, value in enumerate(rows) if value.startswith('| 本地区域修复与对象移除 |'))
                rows.insert(index, row)
                text = '\n'.join(rows)+'\n'
        path.write_text(text, encoding='utf-8', newline='\n')
    path = ROOT/'skills/video-cut-local-models/SKILL.md'
    text = path.read_text(encoding='utf-8')
    old = ('clearance from that gate. ROSE was imported offline only; no ROSE inference\n'
           'or weights acquisition passed. ProPainter\'s noncommercial terms and missing\n')
    new = ('clearance from that gate. V44 only imported ROSE; the later\n'
           '[V59 loading evidence](../../docs/validation/'+REPORT+')\n'
           'pins and strict-loads all three ROSE/Wan components with zero forwards.\n'
           'GPU memory was below the declared budget, so inference, output quality\n'
           'and a production adapter remain unverified. Research acquisition is an\n'
           'explicit development operation, never a runtime or Skill download.\n'
           'ProPainter\'s noncommercial terms and missing\n')
    if old in text:
        text = text.replace(old, new, 1)
    else:
        assert '[V59 loading evidence]' in text
    path.write_text(text, encoding='utf-8', newline='\n')
    path = ROOT/'docs/third-party/时序修复候选源码与许可说明_2026-10-18.md'
    text = path.read_text(encoding='utf-8')
    old = '只取得源码并完成断网导入，**没有下载 ROSE 权重、运行其模型或验收其画质**；交互演示组件另行审查'
    new = 'V44 当时仅取得源码/断网导入；后续 [V59](../validation/'+REPORT+') 已取得权重并 strict 加载，仍 0 次前向/无画质结果；交互演示组件不采用'
    if old in text:
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'documents': len(documents)+2, 'new_model_forwards': 0, 'production_version': 'V58'}, ensure_ascii=False))


if __name__ == '__main__':
    run()
