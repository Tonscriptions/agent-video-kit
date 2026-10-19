"""Publish V67 documentation only after terminal native/install/full receipts."""
from __future__ import annotations
from pathlib import Path
import json
import os
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/pipeline-diagnostics-20261020-v67'
REPORT = ROOT/'docs/validation/本地模型管道诊断与回收前留证实测_2026-10-20.md'
CONTRACT = ROOT/'docs/specs/本地模型管道诊断与有界留证契约_v0.1_2026-10-20.md'

def read(p): return json.loads(p.read_bytes())
def link(source, target): return Path(os.path.relpath(target, source.parent)).as_posix()
def insert(path, marker, content):
    text=path.read_text(encoding='utf8'); start='<!-- '+marker+' -->'; end='<!-- /'+marker+' -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in text:
        a=text.index(start); b=text.index(end,a)+len(end); text=text[:a]+block+text[b:]
    else:
        first,rest=text.split('\n',1); text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')

def main():
    current=frozen(); full=read(BASE/'full-r2.json'); target=read(BASE/'target-r5.json')
    native=read(BASE/'native-r3/verification.json'); installed_native=read(BASE/'installed-native-r1/verification.json')
    media=read(BASE/'lama-r3/verification.json'); install=read(BASE/'installed-r1/verification.json')
    installed_media=read(BASE/'installed-r1/media/verification.json'); skills=read(BASE/'skills-r1.json')
    for v in (full,target,native,installed_native,media,install,installed_media):
        assert v['frozen_equal'] and v['frozen_before']==v['frozen_after']==current
    assert full['terminal_ok'] and full['methods']==1496 and full['exit_code']==0 and full['skipped']==0 and len(current)==202
    assert target['terminal_ok'] and target['methods']==34 and target['exit_code']==0 and target['skipped']==0
    assert native['status']==installed_native['status']==install['status']=='passed'
    assert install['packaged_files']==134 and install['isolated_cli_calls']==25 and all(v['equal'] for v in install['comparisons'])
    assert len(native['calls'])==len(installed_native['calls'])==10 and media['cli_calls']==23 and media['frames']==media['model_calls']==8
    assert skills['skill_count']==17 and skills['local_links_checked']==244
    assert all(c['passed'] for c in media['checks']) and all(c['passed'] for c in installed_media['checks'])
    summary=(f'2026-10-20 **V67（产品限定验收）**：共享 RVM/SAM2/LaMa/VACE 管道新增三角色退出观测、有界脱敏日志、回收前留证和 '
        f'`diagnostics list/show/export`；保留原错误、operation ID 和事务回滚。完整 **1496/1496、{full["suite_seconds"]:.3f} 秒、'
        f'0 跳过、202 输入冻结**，34 新专项为子集。开发 **33 CLI**：真实无效 ONNX 解析失败 1 次（0 有效模型前向），'
        f'LaMa harmonic 真实 **8 次前向/8 帧**；原生离线 **134 包内文件/35 隔离 CLI**，另一次真实解析失败与 8 帧 LaMa 输出，'
        f'全部解码 RGBA/PCM 与开发版相同；**17 Skills/244 引用**。受控生成区 {media["quality"]["psnr_db"]:.3f} dB，'
        f'≥30 dB 单项通过，沿用原质量门槛；静看 4 帧，未连续播放/听审。'
        f'**本轮没有新 VACE 模型推理或新 Torch 崩溃，原访问冲突根因/长期稳定性、自然质量及完整剪映等价仍未验收**。')
    table='''| 编号 | 当轮核验 | 结果 /证据 |
|---|---|---|
| DIA-V01 | 当前冻结完整回归 | 1496/1496、0 跳过；34 新专项为子集，不累加中间轮次 |
| DIA-V02 | 实际读取预算 | 4 GiB 稀疏日志只 read 64 KiB；超 128 KiB 响应不读载荷；UTF-8/无换行/空文件另验 |
| DIA-V03 | 原生失败和回滚 | 开发/安装各 1 次真实无效 ONNX 解析失败；原 CLI 退出码 6/operation ID、退出值、空缓存、作者元数据不变 |
| DIA-V04 | 进程/路径/历史 | 受控三角色/同时失败、启动失败、取消/超时、联接/硬链接/身份替换、32 次/14 天/活动 64 MiB 保护 |
| DIA-V05 | 正常真实视频 | 开发 23 CLI/8 帧 LaMa；安装 25 隔离 CLI/8 帧；RG​​BA、PCM、PTS、原区域保护与既有门槛另核 |
| DIA-V06 | 发行和 Skill | 134 资源、7 wheels；诊断另 10 隔离 CLI，共 35；17 Skills/244 本地引用 |
'''.replace('RG​​BA','RGBA')
    report=f'''# 本地模型管道诊断与回收前留证实测

{summary}

{table}

## 当前源码与真实执行

| 记录 | 本轮范围 |
|---|---|
| [完整回归](evidence/pipeline-diagnostics-20261020-v67/full-r2.json) /[原日志](evidence/pipeline-diagnostics-20261020-v67/full-r2.log) | 当前 202 输入与结束时相同，1496 方法；方法数不证明剪映等价 |
| [诊断专项 r5](evidence/pipeline-diagnostics-20261020-v67/target-r5.json) | 34 方法，{target['suite_seconds']:.3f} 秒、0 跳过；大日志验证实际 read 大小，原生三角色/多失败与清理退出分开 |
| [开发真实异常](evidence/pipeline-diagnostics-20261020-v67/native-r3/verification.json) | 10 CLI；明确无效 ONNX 原创夹具，真正 `onnx.ModelProto` DecodeError；空 stderr 时响应摘要仍保留原因，不是协议模拟、有效模型或 Torch 崩溃 |
| [安装真实异常](evidence/pipeline-diagnostics-20261020-v67/installed-native-r1/verification.json) | 10 个 `-I -S -B` 隔离 CLI，同类真实解析失败；保留哈希核验的 6 文件 ZIP，原始媒体/权重/RGBA 不复制 |
| [开发真实 LaMa](evidence/pipeline-diagnostics-20261020-v67/lama-r3/verification.json) | 23 CLI、8 次前向/8 帧；显式 harmonic；源、模型、adapter、配置和实际输出均绑定 SHA |
| [离线安装与媒体](evidence/pipeline-diagnostics-20261020-v67/installed-r1/verification.json) | 134 包内资源/7 wheels、25 隔离 CLI；8 次前向/8 帧，与开发完整解码 RGBA/PCM 和受控质量值一致；native 异常的 10 CLI 另计 |
| [Skill](evidence/pipeline-diagnostics-20261020-v67/skills-r1.json) | 17 个 `video-cut-`，244 份本地引用，C 盘发现目录仍联接到 E 盘；三份现有 Skill 更新 |

共同控制器覆盖 RVM、SAM2、LaMa、VACE；adapter 新增诊断、错误协议及策略文件的 SHA。旧登记不会静默更改，须重新登记。完整回归包含所有相关模型协议与既有读取测试；本轮未重新执行真实 SAM2/RVM 有效模型推理或真实 VACE 推理。没有使用 Docker、WSL、虚拟环境；本机已有 Python、FFmpeg 和模型资源，发行包不包含模型、Python、FFmpeg 或浏览器下载器。

完整回归结束后，[抽样记录的 6 个进程身份均已退出](evidence/pipeline-diagnostics-20261020-v67/full-observed-cleanup-r1.json)，没有为此终止其它任务。该抽样不是全部历史子进程的穷尽清单；本轮源码研究没有打开浏览器界面 tab。

## 功能约束和可用方式

`errors[]` 内对应错误对象的 `diagnostics` 为可选字段，单错误示例路径为 `errors[0].diagnostics`；`stored` 给 ID、项目相对 manifest 和 SHA，`unavailable` 给次级警告；两者都不替换原错误。未进入管道的预检、预置取消及输出发布后的保存失败可能没有附件。`first_failure_roles` 是首次观测集合，`root_cause=unknown`；主动清理、自然退出、原始值/Windows 无符号和 hex 分开。`cleanup_requested` 记录清理意图及其后退出，不证明该最终值一定由 kill 造成；请求前未观察到自然退出则该字段保留 null。日志不能把 Broken pipe 单独解释为根因。

```powershell
python -X utf8 -m ai_ad_editor diagnostics list --project <root> --operation-id <op>
python -X utf8 -m ai_ad_editor diagnostics show --project <root> --diagnostic-id <id> --expected-manifest-sha256 <sha>
python -X utf8 -m ai_ad_editor diagnostics show --project <root> --diagnostic-id <id> --include-logs
python -X utf8 -m ai_ad_editor diagnostics export --project <root> --diagnostic-id <id> --output <new.zip> --dry-run
```

查询不修改作者工程/快照，也不清历史；正式 export 才写显式新 ZIP，父目录须存在且不能经过联接。诊断历史在新写入时按 32 次/64 MiB/14 天清理，未完成 `.writing_` 留证受保护，不能据过期时间推导后台清理已经执行。32×512 KiB 正常记录本身低于 64 MiB；总量拒绝用 64 MiB 活动稀疏夹具验证，不假称正常 32 份日志累计达到该值。

路径测试实际覆盖 Windows 目录联接、硬链接、打开身份替换和越界参数；一般符号链接也由 reparse/普通文件检查拒绝，但没有单列全部 ACL/文件系统/敌对并发竞态认证。脱敏覆盖已知本地输入、路径、鉴权/token、邮箱、URL 和策略 provider 标记，保留必要 SHA；它不保证识别任意秘密，附件默认本地，不自动上传。

## 原输入、实际输出和检查方法

[原创输入 MP4](../assets/pipeline-diagnostics-20261020-v67-lama-r3/source.mp4) /[实际输出 MP4](../assets/pipeline-diagnostics-20261020-v67-lama-r3/expanded.mp4) /[无损 MOV](../assets/pipeline-diagnostics-20261020-v67-lama-r3/expanded.mov) /[复现与文件 SHA](../assets/pipeline-diagnostics-20261020-v67-lama-r3/provenance.json)。

![原输入填充、实际 LaMa harmonic、独立受控真值；真实成片抽帧的无声 GIF](../assets/pipeline-diagnostics-20261020-v67-lama-r3/comparison.gif)

原创程序化场景沿用 V66 公开 CC0 输入：192×128→256×160、8 fps、1 秒/8 帧，原声 48,000 立体声采样帧；动图为实际 8 帧比较、768×184、1 秒、无声。源有部分 alpha，评估使用无损解码，MP4/GIF 仅预览。已[静态查看 0/3/4/7 帧](evidence/pipeline-diagnostics-20261020-v67/visual-review-r1.json)，未连续播放或听审。所见生成区大体延续上下横向色带，属于合成场景，不能用于自然画面审美结论。

当前开发/安装各 8 帧、生成区 {media['quality']['psnr_db']:.9f} dB，预先 ≥30 dB 单项通过；与 V66 同例相同，诊断功能没有带来新的画质提升。V66 VACE harmonic 约 19.228 dB 未过门槛，继续保留；没有用 LaMa 或精确保护原区域来替它过关。

## 保留的失败、历史对照和未验收项

| 编号 | 保留记录 | 处理与边界 |
|---|---|---|
| DIA-F01 | [target-r1](evidence/pipeline-diagnostics-20261020-v67/target-r1.json) | 31 项中 2 失败/5 错误：测试误用 error 单数、Windows DirEntry 缺失 nlink 及深 JSON；修正后 r2/r3，再补结构化错误与策略测试，最终 r5=34；不累加轮次 |
| DIA-F02 | [native-r1](evidence/pipeline-diagnostics-20261020-v67/native-r1/verification.json) | 原生解析失败确实发生，但检查器误期待 stderr 中 ORT 文案；实际 onnx 前置解析写 DecodeError 到 JSON，stderr 为空；据此补入限长脱敏 worker 摘要 |
| DIA-F03 | [native-r2](evidence/pipeline-diagnostics-20261020-v67/native-r2/verification.json) | 异常/ZIP/回滚成功，但策略把 `DecodeError:` 当 URI，末项拒绝；加入策略兼容格式与裸 provider 标记脱敏，重新登记最终 adapter，r3 通过 |
| DIA-F04 | [停止的 full-r1](evidence/pipeline-diagnostics-20261020-v67/full-r1.json) | 为补上述功能主动停止自己的测试 PID 7024/26980，未作为完整回归通过；[停止范围](evidence/pipeline-diagnostics-20261020-v67/full-r1-owned-stop.json)，未停止其它任务 |
| DIA-F05 | [早期源码封存](evidence/pipeline-diagnostics-20261020-v67/pre-response-error-source.json) /[策略修正前源码](evidence/pipeline-diagnostics-20261020-v67/pre-policy-source.json) | ZIP 保留各自 202 份输入；早期 r1/r2 LaMa 输出和相关协议回归是中间源码，不替代最终 r3 模型/安装/full-r2 |
| DIA-F06 | [V66 历史崩溃映射](evidence/pipeline-diagnostics-20261020-v67/historical-crash-mapping.json) | 只解析已经保存的两份 Application Error：worker 24208/34396、torch_cpu.dll、c0000005。没有读取当前 Windows 日志/转储，没有新 VACE 或访问冲突复现；系统事件 PID 不以 WER 服务进程替代 |

失败返回原错误并且不登记半成品；部分诊断失败给次级 warning。若全部写入失败，活动 staging 可能保留供核验，不能删除其它任务目录来获得空间。预检拒绝可无诊断、全平台/全部 ACL、突然断电、恶意并发替换认证、长片压力、真实崩溃转储分析、完整自然画音质量和剪映全部效果仍在开放范围。

## 复用与发行

OpenFilm 只贡献问题摘要/脱敏/有限历史思路，保留 MIT；其“读全文件后裁尾部”、整套桌面会话收集和静默回收失败不移植。[最新 R08 复用与成本取舍](../OpenFilm最新复用评估与成本取舍_2026-10-20.md)中 9 个上游原测试/1 跳过、8 个提取夹具与本轮产品方法分计。

[原生离线 ZIP](../assets/pipeline-diagnostics-20261020-v67-installed/release/agent-video-kit-cp313-win_amd64.zip) /[发行 manifest](../assets/pipeline-diagnostics-20261020-v67-installed/release/manifest.json)。安装验证只覆盖本机原生 CPython 3.13 Windows 和现有外部工具/模型，摘要提供完整性，不是作者签名。复现入口为 `scripts/run_frozen_regression.py`、`scripts/smoke_pipeline_diagnostics.py`、`scripts/smoke_video_outpainting.py` 与 `scripts/verify_video_outpainting_install.py`；原命令保存在各收据。
'''
    REPORT.write_text(report,encoding='utf8',newline='\n')
    root_readme=ROOT/'README.md'
    r08=ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md'
    insert(root_readme,'R08-RESEARCH','OpenFilm 最新复核固定 `71922644` /0.2.1，1252 stars /128 forks 为 2026-10-20 01:56:20 Asia/Taipei 快照；757 文件；10 套创作 Skill 所在 31 文件、29 个 provider 目录文件未变。建议拆诊断和批量导出规划，按需补透明联系表；现有缩略图已先缩放，无需重复建设。预览缓存须重写 key，FCPXML 按需求实施，在线 provider 不接入。'+f' [编号复用、成本、原测试与失败]({link(root_readme,r08)})。')
    insert(root_readme,'V67-CURRENT',summary+f' [编号核验/失败/发行]({link(root_readme,REPORT)})。\n\n'+table+
        '\n![当前真实 LaMa 样例的无声 GIF](docs/assets/pipeline-diagnostics-20261020-v67-lama-r3/comparison.gif)\n\n'
        '[原视频 MP4](docs/assets/pipeline-diagnostics-20261020-v67-lama-r3/source.mp4) /[实际输出 MP4](docs/assets/pipeline-diagnostics-20261020-v67-lama-r3/expanded.mp4)。诊断包没有可视模型效果，GIF 用于检查同版正常视频输出。')
    relatives=['docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
        'docs/specs/AgentCLI契约_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
    for name in relatives:
        path=ROOT/name; insert(path,'V67-CURRENT',summary+f' [编号核验/原片/GIF/失败/发行]({link(path,REPORT)})。')
    matrix=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md'
    insert(matrix,'V67-DIAGNOSTICS','| 子项 | 实现与当前核验 | 状态 |\n|---|---|---|\n'
        '| 三角色观测/回收前留证/有限历史/显式导出 | 34 专项、当前完整 1496、开发及安装真实解析失败、134 文件发行 | 限定通过 |\n'
        '| 原生崩溃根因/长期稳定性/自然视频质量 | 历史 V66 事件保留，本轮没有新 VACE 推理/访问冲突或自然样例 | 未验收 |')
    text=root_readme.read_text(encoding='utf8'); lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('- 当前模块进度见'):
            lines[i]='- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：V67 完整 1496/1496、34 新专项为子集，134 包内资源/35 隔离 CLI；诊断和正常模型样例分计，完整剪映等价未验收。'
    root_readme.write_text('\n'.join(lines)+'\n',encoding='utf8',newline='\n')
    text=CONTRACT.read_text(encoding='utf8').replace('V67 已实现，验收进行中；最终范围见','V67 已实现并完成本轮限定验收；范围见')
    CONTRACT.write_text(text,encoding='utf8',newline='\n')
    cli=ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md'
    cli.write_text(cli.read_text(encoding='utf8').replace('原生管道诊断接口（V67，验收进行中）','原生管道诊断接口（V67，限定验收通过）'),encoding='utf8',newline='\n')
    print(json.dumps({'documents_updated':len(relatives)+3,'full_methods':full['methods'],'seconds':full['suite_seconds'],'source_files':len(current)},ensure_ascii=False))

if __name__=='__main__': main()
