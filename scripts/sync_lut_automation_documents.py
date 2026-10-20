"""Publish measured V73 documentation from retained terminal receipts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/lut-intensity-20261020-v73'
BASE=ROOT/REL
REPORT=ROOT/'docs/validation/LUT强度关键帧与中性调色修复实测_2026-10-20.md'
CONTRACT=ROOT/'docs/specs/LUT强度关键帧契约_v0.1_2026-10-20.md'
DOCUMENTS=('README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')
NATIVE='docs/assets/lut-intensity-20261020-v73-native-r5'
INSTALLED='docs/assets/lut-intensity-20261020-v73-installed-r1'


def read(path):return json.loads(Path(path).read_bytes())
def link(source,target):return Path(os.path.relpath(target,source.parent)).as_posix()
def insert(path,body):
    text=path.read_text(encoding='utf8');start='<!-- V73-CURRENT -->';end='<!-- /V73-CURRENT -->'
    block=start+'\n'+body.rstrip()+'\n'+end
    if start in text:
        a=text.index(start);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        first,rest=text.split('\n',1);text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true')
    args=parser.parse_args();current=frozen();focus=read(BASE/'targeted-r5.json')
    dev=read(BASE/'native-r5/verification.json');install=read(BASE/'installed-r1/verification.json')
    media=read(BASE/'installed-r1/media/verification.json')
    assert focus['terminal_ok'] and focus['methods']==30 and focus['skipped']==0
    for value in (focus,dev,install,media):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    assert dev['status']==install['status']==media['status']=='passed'
    assert install['bundle']['wheels']==7 and len(install['resource_hashes'])==145
    assert dev['decoded_sha256']==media['decoded_sha256']
    clocks=[read(BASE/(name+'/verification.json')) for name in ('clocks-native-r2','clocks-installed-r2')]
    for value in clocks:
        assert value['status']=='passed' and value['frozen_equal'] and value['frozen_after']==current
    assert [row['decoded_sha256'] for row in clocks[0]['cases']]==[row['decoded_sha256'] for row in clocks[1]['cases']]
    full=read(BASE/'full-r1.json')
    if not args.candidate:
        assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1644 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['verification_scripts_equal']
    full_note=('完整回归正在运行，尚未验收；不把预计方法数计为通过。' if args.candidate else
        f'完整原生回归 **{full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过、{len(current)} 冻结输入＋8 外部夹具前后相同**；30 个新方法为其子集。')
    skills_path=BASE/'skills-r1.json';skills=read(skills_path) if skills_path.exists() else None
    skills_note=(f'**17 Skills/{skills["local_links_checked"]} 本地引用**。' if skills else '4 份 Skill 已更新，主工作区发现联接与本地引用待发布核验。')
    summary=('2026-10-20 **V73（'+('隔离候选，尚未发行' if args.candidate else 'LUT 强度关键帧限定验收')+'）**：'
        'catalog **0.6.0** 新增 `lut3d.intensity`，共 6 类/20 个数值通道；四别名、六种插值、作者时钟及共享预算。'
        '修复中性 CUBE 静态半强度红蓝索引、常速祖先效果时钟、区间调节层输入分流及项目包 LUT 依赖。'+full_note+
        f'专项 **30/30、{focus["suite_seconds"]:.3f} 秒、0 跳过**；原生 **{dev["cli_calls"]} CLI/{len(dev["checks"])} 检查**，'
        '24 帧逐帧独立 RGB 对照最大误差 1/255、alpha 全字节一致。'
        f'**145 资源/7 wheels/{install["isolated_cli_calls"]} 隔离 CLI＋1 模块来源/{len(install["checks"])} 安装检查**，'
        '开发/安装完整解码摘要与每帧 PTS 相同。'+skills_note+
        '另各 **7 CLI/2 组解析时钟核验**，线性速度曲线 22 帧、外套 2x 倒放 11 帧，与独立积分逆函数的 RGB 误差≤1；不并入方法数。'
        '保留所有旧专项与演示失败；静看对照 PNG，未连续审片或听审。8-bit 编码 RGB 混合；HDR、线性光、全部厂商 LUT 方言、自然调色质量和完整剪映等价未验收。')
    table='''| 编号 | 功能性核验 | 实测结果与边界 |
|---|---|---|
| V73-01 | 中性 CUBE 与缓存修复 | 旧 0.5 强度将 (32,96,192,128) 改为 (112,96,112,128)；修复 red-fastest，五档静态中性控制通过；v2 缓存不命中旧错误表 |
| V73-02 | 可编辑动态强度 | 0..1、四别名、六种插值；静态默认 0 不再吞掉关键帧，未知通道/越界/损坏缓存拒绝 |
| V73-03 | 原生像素与透明 | 独立 RGB 算术、逐字节 alpha；原生 24 帧实际视频，单阶段误差≤1 个色值；多级量化单独计界 |
| V73-04 | 时钟与层级 | 非零起点、NTSC、裁切/分割、嵌套自身效果、透明文字和区间调节层；另在开发/安装实际验证线性速度曲线＋外套 2x 倒放，独立积分时钟对照 |
| V73-05 | 本地 LUT 格式 | 实际执行 CUBE 2³、3DL 17³、CSP 2³、DAT 33³；小尺寸 DAT 首轮失败保留，不推断全部方言兼容 |
| V73-06 | 包/片段/重放 | 路径或 lut_id 解析为包内哈希路径，保留原 LUT 字节和可编辑关键帧；导入/片段跨项目像素一致；缺失或登记变更在建包前拒绝 |
| V73-07 | 资源与配额 | 独立 blend target、LUT SHA、命令缓存 SHA、根图共享四项预算；队列绑定实际 LUT 字节 |
| V73-08 | 离线安装 | 7 个已有 wheel，145 资源逐字节匹配；-I -S 新进程重做 CLI/原生参考和解码/PTS 比对 |
| V73-09 | 原视频与 GIF | 精确 NUT 输入含 25 帧端点保护，实际输出/预览各 24 帧；MP4/GIF 为有损预览，RGB 核验使用无损输出 |
| V73-10 | 全量与限制 | 本轮完整回归收据单独记录；专项为子集。LUT 新增专项未调用浏览器；既有完整回归包含 HTML 浏览器测试。无模型/GPU 前向、GUI、网络媒体、Docker/WSL/虚拟环境；不宣称剪映等价 |
'''
    for name in DOCUMENTS:
        path=ROOT/name;body=summary+' [契约、实际输入输出与失败记录]('+link(path,REPORT)+')。'
        if name=='README.md':
            body+='\n\n'+table+'\n![真实 LUT 强度动画对照]('+link(path,ROOT/NATIVE/'comparison.gif')+')\n\n'
            body+='[原视频 MP4]('+link(path,ROOT/NATIVE/'source-preview.mp4')+') · [实际 CLI 输出]('+link(path,ROOT/NATIVE/'edited-cli.mp4')+') · [无损输出]('+link(path,ROOT/NATIVE/'edited-lossless.mkv')+') · [精确源 NUT]('+link(path,ROOT/NATIVE/'source-original.nut')+') · [可编辑请求]('+link(path,ROOT/NATIVE/'timeline-request.json')+')'
        insert(path,body)
    matrix=ROOT/DOCUMENTS[-1];text=matrix.read_text(encoding='utf8')
    lines=[]
    for line in text.splitlines():
        if line.startswith('| 效果参数关键帧 |'):
            line='| 效果参数关键帧 | 原七项表达式；色温、色彩平衡、九色轮、曝光、色阶加 LUT intensity 共 6 类/20 数值通道，逐 CFR 帧 native 命令、完整作者时钟和递归共享预算 | [V58](逐帧调色参数自动化实测_2026-10-19.md)、[V73 实测/包/安装](LUT强度关键帧与中性调色修复实测_2026-10-20.md) | 布尔/枚举/曲线字符串、其它插件、物理白平衡/HDR/跨渲染器等效仍未实现或未验 |'
        elif line.startswith('| 项目内 LUT3D |'):
            line='| 项目内 LUT3D | 本地登记、SHA-256、Rights Ledger；四别名/路径/lut_id；CUBE 静态 identity 表已修复 red-fastest，动态 intensity 以 8-bit 编码 RGB 混合并保持 alpha；包导出闭合 LUT 字节依赖 | [V73 原生像素、四格式、片段与离线安装](LUT强度关键帧与中性调色修复实测_2026-10-20.md) | 静态非 CUBE 部分强度、HDR/线性光、全部厂商方言、LUT 预览和跨渲染器视觉等效未验收 |'
        elif line.startswith('| 序列级全局/局部调节层 |') and 'V73' not in line:
            line=line.replace(' | `test_sequence_adjustment_stack', '；V73 区间显式 split 合成面，保留原 fps 与画面 | `test_sequence_adjustment_stack')
        lines.append(line)
    matrix.write_text('\n'.join(lines)+'\n',encoding='utf8')
    def local(target):return link(REPORT,ROOT/target)
    report='# LUT 强度关键帧与中性调色修复实测（V73）\n\n'+summary+'\n\n'+table
    report+='\n![实际对照]('+local(NATIVE+'/comparison.gif')+')\n\n'
    report+='[原视频 MP4]('+local(NATIVE+'/source-preview.mp4')+') · [CLI MP4]('+local(NATIVE+'/edited-cli.mp4')+') · [无损成片]('+local(NATIVE+'/edited-lossless.mkv')+') · [精确原 NUT]('+local(NATIVE+'/source-original.nut')+') · [关键帧请求]('+local(NATIVE+'/timeline-request.json')+') · [原创 LUT]('+local(NATIVE+'/warm.cube')+') · [发布许可]('+local(NATIVE+'/LICENSE.txt')+')。\n\n'
    report+='[开发执行收据]('+local(REL+'/native-r5/verification.json')+')、[安装收据]('+local(REL+'/installed-r1/verification.json')+')、[安装原生重做]('+local(REL+'/installed-r1/media/verification.json')+')、[30 项专项]('+local(REL+'/targeted-r5.json')+')、[完整回归]('+local(REL+'/full-r1.json')+')、[夹具原字节]('+local(REL+'/fixture-manifest-r1.json')+')。\n\n'
    report+='[开发解析时钟核验]('+local(REL+'/clocks-native-r2/verification.json')+') 与 [安装解析时钟核验]('+local(REL+'/clocks-installed-r2/verification.json')+') 各实际执行 7 次 CLI，输出线性速度曲线 22 帧和外套 2x 倒放 11 帧。独立参考积分 ds/(0.5+0.5s)，以解析指数逆函数求原作者时刻，再计算 LUT 强度；逐像素 RGB 最大误差 1，alpha 精确，开发/安装解码 SHA 相同。这是额外真实原生执行，不是额外 unittest 方法。\n\n'
    report+='动态路径采用本机 FFmpeg lut3d 和 blend，四个别名均只开放 intensity 数值关键帧。普通局部作者时钟、祖先常速/曲线/倒放、片段窗口和区间调节层沿用统一时钟编译；路径/ID/插值枚举保持静态。每个实例分配独立 target，混合前从同一画面分出原始/调色两路，RGB opacity 三通道接收命令，alpha 通道保持完整。根图累计 2,000,000 状态、200,000 命令、16 MiB 命令字节、1,024 实例，不通过拆分子图绕过。\n\n'
    report+='新建包逻辑同时扫描序列、片段、文字与 settings 的 LUT 引用，解析登记 ID，校验项目内路径与登记哈希，把原文件写入 assets/luts/<SHA>.<后缀>；登记 ID 在包中变为可移植路径，关键帧不烘焙。缺失或登记摘要改变须在打开 ZIP 前失败。派生命令和缓存不当作作者资源打包。队列依赖摘要已有 LUT 原字节绑定，本轮以实际文件变更核验。\n\n'
    report+='| 失败/修正编号 | 实际观察 | 处理与当前边界 |\n|---|---|---|\n'
    report+='| F01 | [旧版原生探针]('+local(REL+'/baseline-r1.json')+')：中性 0.5 强度 RGB 变成 (112,96,112) | 修正 CUBE 文件 red-fastest；缓存算法 v2＋精确浮点键，逐字节校验损坏；原错误缓存保留不覆盖 |\n'
    for i,count in ((1,26),(2,27),(3,30),(4,30)):
        report+=f'| F0{i+1} | [专项 r{i}]('+local(REL+f'/targeted-r{i}.json')+f')：{count} 个方法未全通过 | 保留原日志；分别定位时钟/调节层/包依赖，之后修正 raw 输出 vsync、逐级量化、正确字号/透明配置、片段权利登记及 DAT 样例尺寸；通过结果仅用 r5 |\n'
    for i,reason in ((1,'输出在工程外，被既有路径门禁拒绝'),(2,'12fps MKV 毫秒 PTS 与独立源帧序号不等价，周期性抽帧差异'),(3,'NUT duration 为末帧 PTS，2s 范围缺少显式端点'),(4,'许可证元数据 URL 被本地策略拒绝')):
        report+=f'| M0{i} | [原生演示 r{i}]('+local(REL+f'/native-r{i}/verification.json')+')：'+reason+' | 保留失败产物和收据；r5 使用工程内输出、精确 NUT＋25 帧端点保护及本地许可元数据，未放宽门禁或像素阈值 |\n'
    report+='| C01 | [开发时钟 r1]('+local(REL+'/clocks-native-r1/verification.json')+')、[安装时钟 r1]('+local(REL+'/clocks-installed-r1/verification.json')+')：custom 32×16 被画布最小尺寸拒绝 | 修正核验输入为实际支持的 64×64，门禁不变；r2 两环境均通过 |\n'
    report+='\nCUBE 静态部分强度是对网格 identity 混合；动态强度混合完整调色结果与原像素，两者在域外、非线性映射及舍入时不保证相同。本轮小尺寸 DAT 未通过原生独立像素对照，实际通过的 DAT 是 33³；不将扩展名支持描述为全部方言兼容。所有新原生执行均为 CPU，不调用模型。GIF/MP4 的有损压缩不参与精确 RGB 门禁；无损逐帧误差≤1 个色值、多级混合允许每级量化，alpha 精确核对。只静看第 12 帧对照 PNG，未连续播放或听审；样例无声，不接受自然素材画质、HDR、线性光、4K 长片性能或全剪映等价。\n\n'
    report+='复现脚本为 [原生演示]('+local('scripts/smoke_lut_automation.py')+')、[新安装]('+local('scripts/verify_lut_automation_install.py')+')、[完整原生回归]('+local('scripts/run_with_regression_fixtures.py')+')。使用新 work/evidence/assets 路径以保留失败原件；原始基线探针须在旧提交 5c09628 上复现，不能把修复后的运行称为旧版观察。所有发布媒体及每次原生命令、编码 PTS 和 SHA-256 均在对应收据中。\n'
    REPORT.write_text(report,encoding='utf8',newline='\n')
    print(json.dumps({'status':'candidate' if args.candidate else 'verified-documents','documents':len(DOCUMENTS),'methods':focus['methods'],'full_terminal':bool(full.get('terminal_ok'))}))


if __name__=='__main__':main()
