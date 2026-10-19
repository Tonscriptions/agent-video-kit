"""Publish V65 documentation only against terminal frozen and installed evidence."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/hardware-acceleration-20261019-v65'
REPORT = '硬件编解码与显式回退实测_2026-10-19.md'
CONTRACT = '硬件编解码探测与显式回退契约_v0.1_2026-10-19.md'


def read(p): return json.loads(p.read_bytes())
def sha(p): return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def insert(path, marker, content):
    text = path.read_text(encoding='utf8'); start='<!-- '+marker+' -->'; end='<!-- /'+marker+' -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in text:
        a=text.index(start); b=text.index(end,a)+len(end); text=text[:a]+block+text[b:]
    else:
        first, rest=text.split('\n',1); text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')


def main():
    current=frozen();full=read(BASE/'full-r1.json');unit=read(BASE/'subset-r6.json')
    dev=read(BASE/'development-r6/verification.json'); install=read(BASE/'installed-r1/verification.json')
    installed_media=read(BASE/'installed-r1/media/verification.json');skills=read(BASE/'skills-r1.json')
    for item in (full,unit,dev,install,installed_media):
        assert item['frozen_equal'] and item['frozen_before']==item['frozen_after']==current
    assert len(current)==198 and full['terminal_ok'] and full['methods']==1430 and full['exit_code']==0 and full['skipped']==0
    assert unit['terminal_ok'] and unit['methods']==20 and unit['exit_code']==0 and unit['skipped']==0
    assert install['status']=='passed' and install['packaged_files']==132 and install['isolated_cli_calls']==22
    assert len(dev['artifacts'])==8 and dev['cli_calls']==20 and len(dev['checks'])==49
    assert all(c['passed'] for c in dev['checks']) and all(c['decoded_video_equal'] and c['decoded_pcm_equal'] for c in install['comparisons'])
    assert skills['skill_count']==17 and skills['local_links_checked']==235
    summary=(f"2026-10-19 **V65（产品）**：接入 OpenFilm 固定 `f6a65ae5` 的硬件参数/H.273 策略，保留 Python/FFmpeg 主链；"
        f"独立 `off/prefer/require` 编码/解码、四帧实测、强制硬件帧与 CPU 对照、NV12/P010 输入、帧级/码流色彩标签、有限回退、队列/续跑及持久诊断。"
        f"完整 **1430/1430、{full['suite_seconds']:.3f} 秒、0 跳过、198 输入冻结**；20 新专项为子集。开发 **20 CLI/49 断言/8 成片/384 帧/768,000 立体声采样帧**；"
        f"离线 **132 包内文件/22 隔离 CLI**，8 成片解码视频/PCM 均与开发版相同；**17 Skills/235 引用**。"
        f"本机 RTX 3060 的 H.264 NVENC＋D3D11VA/CUDA、HEVC 10-bit NVENC＋CUDA 通过；AMF 不可用和 H.264 10-bit 设备拒绝均保留。"
        f"GIF 为实际成片 8-fps 采样、16 帧/2.01 秒/无声；已查看 6 个静帧，未听审/连续播放。"
        f"这是位流格式/传输与受控合成样例核验，**不验收内部全精度 10-bit 合成、所有设备、自然画质、提速或完整剪映等价**。")
    report_path=ROOT/'docs/validation'/REPORT
    report=f'''# 硬件编解码与显式回退实测

{summary}

## 编号功能核验

| 编号 | 功能与真实执行 | 结果及边界 |
|---|---|---|
| HA-F01 | 默认软件路径、原作者时钟/滤镜/权利门禁 | CPU 对照与全量回归；不分配硬件，软件逻辑 codec 继续作为可复现声明 |
| HA-F02 | H.264 NVENC＋D3D11VA | 真实嵌套画布、亮度、水平位置关键帧和非静音音轨；48 帧/96,000 立体声采样帧 |
| HA-F03 | H.264 NVENC＋CUDA | 同上；探测强制硬件帧/hwdownload，首四帧 PTS/字节/MD5 与 CPU 相同 |
| HA-F04 | HEVC 10-bit NVENC＋CUDA | 原 10-bit 低两位有非零信息；硬件传输 P010 与输出 yuv420p10le 核验通过。**不是内部合成精度、HDR 外观或专业调色验收** |
| HA-F05 | AMF prefer /require | 本机候选物理失败；prefer 留证回到 libx264，require 返回 6，并保留旧成片字节与失败报告 |
| HA-F06 | 1 MiB 像素探测预算 | prefer 软件输出，require 拒绝；预算不代表驱动全部显存硬上限 |
| HA-F07 | H.264 10-bit 必须 NVENC | 本机设备不支持，拒绝；没有交付降为 8-bit 的成片。模拟格式误配另由专项门禁测试覆盖 |
| HA-F08 | 预取消与续跑 | 标记存在返回 8、零硬件探测；移除标记按原设置重新探测并输出 48 帧/96,000 采样帧 |
| HA-F09 | 持久队列 | 作业保留四个模式/后端字段及预算，真实 GPU 队列输出 48 帧/96,000 采样帧 |
| HA-F10 | 透明度边界 | 专项中真实 VP9 透明度软件回退仍有透明度变化，require 拒绝扁平化；该单测样片不并入公开 384 帧统计 |
| HA-F11 | 运行中重试、必须轴保持、超时/取消/IO/输入变化 | 专项用可控进程结果验证有限重试和禁止路径；不冒充真实断电、显卡掉线或压力试验 |
| HA-F12 | 独立离线发行 | 7 wheel、132 包内文件逐字节与源码/安装相同；22 隔离 CLI；8 实际输出的完整解码视频及 PCM 与开发版一致 |
| HA-F13 | 公开来源与预览 | 数学图样及正弦均原创 CC0；源 MKV/实际 MKV、GIF、静帧、SHA/脚本/元信息。MP4 仅复制视频流、另转 AAC，独立 96 预览帧不加到 384 帧 |
| HA-F14 | Skills 与许可 | 17 个 `video-cut-` 联接及 235 本地引用通过；编辑/质量/队列三个 Skill 增加新契约。OpenFilm 原 MIT 随 wheel，未带入 GUI/provider/网络依赖 |

## 原输入、实际输出与查看范围

| 内容 | 原始/实际文件 |
|---|---|
| 原 8-bit 数学图样与 440 Hz 音轨 | [原 MKV](../assets/hardware-acceleration-20261019-v65-r6/source-8bit.mkv) /[便于播放的 MP4 副本](../assets/hardware-acceleration-20261019-v65-r6/preview-r3/original.mp4) |
| 原 10-bit 图样 | [原 MKV](../assets/hardware-acceleration-20261019-v65-r6/source-10bit.mkv) |
| 实际 H.264/CUDA 成片 | [原 MKV](../assets/hardware-acceleration-20261019-v65-r6/nvenc-cuda.mkv) /[MP4 副本](../assets/hardware-acceleration-20261019-v65-r6/preview-r3/edited.mp4) |
| 实际 H.264/D3D11VA 与 HEVC10/CUDA | [D3D11 MKV](../assets/hardware-acceleration-20261019-v65-r6/nvenc-d3d11.mkv) /[HEVC10 MKV](../assets/hardware-acceleration-20261019-v65-r6/hevc10-cuda.mkv) |
| 原始→输出接触表 | [6 个静帧](../assets/hardware-acceleration-20261019-v65-r6/contact-sheet.png)：0/24/47 帧的源计数一致，输出出现预期横移/亮度；没有连续播放或听审 |
| 复现/许可/文件 hash | [CC0 来源清单](../assets/hardware-acceleration-20261019-v65-r6/provenance.json) /[MP4 转码来源](../assets/hardware-acceleration-20261019-v65-r6/preview-r3/provenance.json) |

![真实 CUDA 成片的无声 GIF](../assets/hardware-acceleration-20261019-v65-r6/nvenc-cuda.gif)

GIF 16 帧，8-fps 采样；GIF 百分之一秒量化后的总时长 **2010 ms**，原视频 48 帧/24 fps/2 秒。GIF 无音频，不作连续播放、听感或全部原帧检查的证据。PSNR 仅是同图 CPU/NVENC 输出差异的观察值，不能推出自然内容或剪映画质等价。

## 失败与开发修正（不叠加为当前通过数）

| 记录 | 原问题与处置 |
|---|---|
| subset-r1 /r2 | 流级 ffprobe 缺少 H.264 原色/传递函数；保留失败，增加码流写入和解码帧标签检查 |
| subset-r5 | 透明 VP9 中，输出选项未能在解码帧保留原色/传递函数；增加最终输出帧 setparams，再按 stream＋frame 验真；r6 为最终 20 专项 |
| development-r1 | 核验脚本误写 `utf8-sig`；版本命令完成后失败，未执行产品 CLI |
| development-r2 | 原 lossless H.264 在本机 **D3D11VA** 路径失败；独立 r3 审计复查发现 CUDA 可解码且四帧与 CPU 相同，不把单后端失败推广为整个 GPU 不支持 |
| development-r2 诊断 | 旧 validation 诊断受作者事务回滚；改为 renders/diagnostics，随后真实 CLI require 失败验证完整日志仍在 |
| development-r3 | D3D11VA 与 NVENC 独立短测成功，组合因 planar 输入 CreateInputBuffer 失败；独立 NV12/CUDA-device 对照后采用 NV12/P010 传输，保留失败与三种原生对照 |
| development-r4 /r5 | 历史范围分别通过 6 样片；r6 显式加入音轨、非静音检查和队列/续跑完整解码，最终 8 样片，不合计重复运行 |
| media-audit-r1 /r2 | 审计夹具错误地固定 FFmpeg 退出值，随后又把 CUDA 当成同样失败；保留记录，r3 按后端分别断言并核对 CPU/CUDA 四帧；不修改产品以迎合夹具 |

## 机器证据与复现

- [完整冻结回归](evidence/hardware-acceleration-20261019-v65/full-r1.json) /[最终 20 专项](evidence/hardware-acceleration-20261019-v65/subset-r6.json)，专项属于全量子集。
- [开发 20 CLI/46 外部命令](evidence/hardware-acceleration-20261019-v65/development-r6/verification.json)，49 断言；8 成片 384 帧/768,000 采样帧。
- [132 文件/22 隔离 CLI 发行](evidence/hardware-acceleration-20261019-v65/installed-r1/verification.json) /[安装版实片](evidence/hardware-acceleration-20261019-v65/installed-r1/media/verification.json)。32 次额外 FFmpeg 比较调用独立计数。
- [11 次独立原生媒体审计](evidence/hardware-acceleration-20261019-v65/media-audit-r3/verification.json) /[实际静帧查看记录](evidence/hardware-acceleration-20261019-v65/media-audit-r3/static-review.json)。原型/组合调试、失败及旧实测另计。
- [Skill 注册/引用](evidence/hardware-acceleration-20261019-v65/skills-r1.json) /[最终交付绑定](evidence/hardware-acceleration-20261019-v65/release-r1.json)。
- [契约](../specs/{CONTRACT}) /[固定 OpenFilm 研究](../OpenFilm_0.2.1复用清单与成本复核_2026-10-19.md) /[MIT 采用声明](../third-party/OpenFilm复用声明_2026-10-17.md)。

```powershell
# 真实渲染，码率显式指定；require 不允许静默回到 CPU。
ai-ad-editor render --project E:/your-project --hardware-encode require --hardware-encoder nvenc --hardware-decode require --hardware-decoder cuda --video-bitrate 4M
# 原生复现：每次换新目录，保留失败和输出；不创建 venv，不调用 Docker/WSL。
C:/Python313/python.exe -B -X utf8 scripts/smoke_hardware_acceleration.py --output docs/validation/evidence/<新目录> --work product/.runtime/<新工作目录> --assets docs/assets/<新媒体目录>
```

候选集为 Windows NVENC/QSV/AMF/MF；实际认证仅覆盖本机原生 FFmpeg 8.1/RTX 3060 的上述组合。驱动默认设备没有完整 UUID 认证，探测不预约显存。CPU 滤镜未移植到 GPU，没有固定提速承诺。离线包不包含 Python、FFmpeg、显卡驱动或模型；异机、其他厂商/OS、长片压力、真实广告/人物素材、自然画音质量和完整剪映功能等价均仍待验。
'''
    report_path.write_text(report,encoding='utf8',newline='\n')
    # Keep history while updating only reviewed Skill bytes.
    manifest_path=ROOT/'video-cut-install-manifest.json';manifest=read(manifest_path)
    old=manifest.get('current_audit');history=manifest.setdefault('audit_history',[])
    if old and old not in history: history.append(old)
    for entry in manifest['skills']:
        digest=sha(ROOT/'skills'/entry['name']/'SKILL.md').split(':',1)[1]
        if digest!=entry['skill_md_sha256']:
            entry.setdefault('skill_md_sha256_history',[]).append({'sha256':entry['skill_md_sha256'],'replaced_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'V65 hardware policy/quality/queue contract'})
            entry['skill_md_sha256']=digest
    manifest['current_audit']={'record':str((BASE/'skills-r1.json').relative_to(ROOT)).replace('\\','/'),
        'record_sha256':sha(BASE/'skills-r1.json'),'checked_at_utc':skills['checked_at_utc'], 'skills':17,
        'local_links_checked':235,'semantics':'V65: native hardware encode/decode policy and controlled media; no full CapCut parity claim'}
    save(manifest_path,manifest)
    root_link='docs/validation/'+REPORT
    insert(ROOT/'README.md','V65-CURRENT',summary+f' [原片/GIF/失败/发行]({root_link})；[契约](docs/specs/{CONTRACT})。\n\n'
        '![实际 H.264/CUDA 成片的无声 GIF](docs/assets/hardware-acceleration-20261019-v65-r6/nvenc-cuda.gif)\n\n'
        '[原视频 MP4](docs/assets/hardware-acceleration-20261019-v65-r6/preview-r3/original.mp4) /'
        '[实际输出 MP4](docs/assets/hardware-acceleration-20261019-v65-r6/preview-r3/edited.mp4)；MP4 视频流复制、音频另转 AAC，PCM 相等证据使用原 MKV。')
    for relative in ['docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
        'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']:
        path=ROOT/relative; target=Path(__import__('os').path.relpath(report_path,path.parent)).as_posix()
        insert(path,'V65-CURRENT',summary+f' [原片/GIF/编号核验/失败与发行]({target})。')
    text=(ROOT/'README.md').read_text(encoding='utf8')
    if '| V65 |' not in text:
        row=f'| V65 | 硬件编解码探测、严格模式与显式回退 | 1430/1430；20 CLI/384 帧/768,000 采样帧；132 包内文件/22 隔离 CLI；17 Skills | 单机 H.264/HEVC10 格式通过；全精度合成、异机、自然质量及完整等价待验 | [原片/GIF/失败/发行]({root_link}) |\n'
        text=text.replace('| V64 |',row+'| V64 |',1)
    text=text.replace('**V64（产品）**','**V64（历史产品验收）**',1)
    (ROOT/'README.md').write_text(text,encoding='utf8',newline='\n')
    matrix=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md';text=matrix.read_text(encoding='utf8')
    text=text.replace('硬件编码和平台码率仍待补','V65 已补硬件候选短测/严格模式/显式回退；单机格式实测，平台码率策略与全设备认证仍待验')
    matrix.write_text(text,encoding='utf8',newline='\n')
    adoption=(f'V65 将固定 `f6a65ae54fa1c10ec482eeb84dc9ffa6ef33c4d8` 的 `packages/openfilm/src/encoders.mjs` '
        f'逐后端选项与 H.273 表适配到 [hardware_acceleration.py](../../product/src/ai_ad_editor/hardware_acceleration.py)，'
        f'保留 Copyright (c) 2026 OpenFilm contributors 和完整随包 MIT。新的强制硬件帧核验、NV12/P010 传输、'
        f'帧标签、严格模式、事务外诊断、队列与取消/续跑由本地实现；未导入上游 CLI、GUI、provider 或 Node 依赖。'
        f'[实测范围](../validation/{REPORT})与[契约](../specs/{CONTRACT})按本机和格式核验，不认定完整硬件/画质等价。')
    insert(ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md','V65-ENCODERS',adoption)
    for file in ['docs/OpenFilm当前复用决策_2026-10-18.md','docs/OpenFilm_0.2.1复用清单与成本复核_2026-10-19.md']:
        insert(ROOT/file,'V65-ADOPTION',f'后续产品进展：OFR07-08 已按限定范围接入 V65；原研究表仍保留 R07 请求时点状态。'
            f'[真实硬件、成片、失败与发行](validation/{REPORT})。不据此推导实际节省了研究估计的全部人日。')
    print(json.dumps({'full_methods':1430,'frozen':198,'new_subset':20,'skills':17,'links':235,'report':str(report_path)}))


if __name__=='__main__':main()
