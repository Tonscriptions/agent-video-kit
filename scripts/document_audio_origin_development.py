"""Document real audio-origin observations and controls, without promoting an unshipped candidate."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/audio-source-origin-20261021-lab'
REPORT='docs/validation/原生音频起点与同步独立实验_2026-10-21.md'
CONTRACT='docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def main():
    base=ROOT/REL;output=base/'development-audit-r1.json';assert not output.exists()
    current=frozen();foundation=read(base/'foundation-r1.json');parent=foundation['source_inputs']
    assert len(parent)==258 and len(current)==259
    assert set(current)-set(parent)=={'product/tests/test_audio_source_origin.py'}
    modified={'product/src/ai_ad_editor/'+name+'.py' for name in ('multicam','render','audio_stretch','capabilities')}
    assert {name for name in parent if parent[name]!=current[name]}==modified
    receipts={name:read(base/(name+'.json')) for name in ('before-controls-r1','after-controls-r1','after-controls-r2','after-controls-r3')}
    test='product/tests/test_audio_source_origin.py';runner=None
    for name,row in receipts.items():
        assert row['methods']==row['distinct_methods']==12 and row['skipped']==0 and row['frozen_equal']
        assert row['source_snapshots'][test]==current[test]
        assert sha(base/(name+'.log'))==row['log_sha256']
        if runner is None:runner=row['runner_sha256']
        assert row['runner_sha256']==runner
    before=receipts['before-controls-r1'];after=receipts['after-controls-r3']
    assert before['failed_methods']==7 and before['error_methods']==1
    assert after['status']=='passed' and after['terminal_ok'] and after['frozen_before']==after['frozen_after']==current
    probe=read(base/'after-r1/observations.json');assert probe['status']=='completed-observation' and probe['frozen_equal']
    assert probe['frozen_before']==probe['frozen_after']==current
    assert probe['observations']['renderer']['complete_PCM_preserves_original_audio_start']
    assert probe['observations']['multicam']['actual_delay_seconds']==1 and probe['observations']['multicam']['score']==1
    related=read(base/'related-r1.json');assert related['expected_methods']==226 and related['frozen_before']==current
    for name,digest in related['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
    for name,digest in related['fixture_inputs'].items():assert sha(ROOT/name)==digest
    summary=f'''状态：独立候选，**未合入 main、未推送、未注册 Skill，尚未完整回归**。多机位协议由父候选 0.3.0 扩展为 0.4.0。当前相同 12 方法全部通过，{after['suite_seconds']:.3f} 秒、0 跳过；226 方法相关回归当前状态为 `{related['status']}`，不能写成已通过。完整 2031 方法只是未来预计数量，须等待真实发布的 V87 父版及新媒体/安装验收。

| 编号 | 实际执行 | 结果及边界 | 证据 |
|---|---|---|---|
| AO-01 | 固定父候选 | 258 父输入、8 既有外部夹具和 3 验证脚本，共 269 文件同字节复制；只改 4 运行时模块并加 12 方法，当前 259 输入 | [创建记录]({REL}/foundation-r1.json) |
| AO-02 | 实际修复前观察 | MKV 视频从 0 开始、音频首 PTS=1000、TB=1/1000、容器 3 秒；实际同步误报 0 秒，渲染丢开头静音 | [有效原生观察]({REL}/before-r2/observations.json) |
| AO-03 | 相同 12 控制修复前 | 14.337 秒，7 FAIL /1 ERROR /4 通过，0 跳过；R3 报实际源采样数不足。包含原本就通过的零起点、反向及空窗控制 | [原始日志]({REL}/before-controls-r1.log) |
| AO-04 | 中间失败保留 | first_pts 修正后 11/12 通过，置信度仍约 .9156；仅改重叠归一化后同一断言仍失败。没有降低 .95 置信度断言 | [中间 r1]({REL}/after-controls-r1.json)、[中间 r2]({REL}/after-controls-r2.json) |
| AO-05 | 当前相同控制 | 12/12、{after['suite_seconds']:.3f} 秒；测试正文、运行器未改。普通/选区/反向/曲线/嵌套、非零容器原点、实际 R3、同步分别核对 | [当前收据]({REL}/after-controls-r3.json) |
| AO-06 | 实际完整 PCM | 3 秒、立体声 48 kHz、1,152,000 float32 字节；原生渲染与“1 秒静音＋原 2 秒 PCM”独立预期全部相同，原内容字节未变 | [修复后观察]({REL}/after-r1/observations.json) |
| AO-07 | 同步时钟及置信度 | 实际偏移恢复 1 秒，生成音频得分 1.0；按真实重叠做 Pearson，排除缺少共同前史的首个一阶差分点。不能外推自然音频校准质量 | [原始同步报告]({REL}/after-r1/actual-sync.json) |
| AO-08 | 正在进行 | 226 个不同相关方法：父候选 104＋新 12＋既有音频 110；6 份脚本与 8 夹具固定，尚未接收终态结果 | [运行收据]({REL}/related-r1.json) |
| AO-09 | 尚缺交付 | 没有本候选的新公开 MP4/GIF/音频资产、离线安装、Skill 增量、完整回归或生产发布；不复用父版媒体冒称本轮执行 | [实验契约]({CONTRACT}) |
'''
    readme='# 原生音频源起点实验\n\n'+summary+f'\n[详细原生实测]({REPORT}) · [作者采样时钟契约]({CONTRACT})。\n'
    assert not (ROOT/'README.md').exists();(ROOT/'README.md').write_text(readme,encoding='utf8',newline='\n')
    report_summary=summary.replace(']('+REL+'/','](evidence/audio-source-origin-20261021-lab/').replace(']('+CONTRACT+')','](../specs/'+Path(CONTRACT).name+')')
    report='# 原生音频起点与同步独立实验（2026-10-21）\n\n'+report_summary+'''

本地原创 32×18 色卡和确定性立体声信号：参考音频从 0 秒开始；机位只保存前 2 秒同一 PCM，并把音频 PTS 放到 1..3 秒，机位视频开头有 1 秒无对应事件的画面。真实音频 `first_pts=0` 规范化会保留源时间里的 1 秒静音，随后才取作者选区、反向或变速。不开启 async，不把补齐源起点误写为设备漂移校正。

首轮 before-r1 的图入口夹具误将音轨字段写成 type，而实际工程用 kind，导致音轨被当作视频、输出全静音；该轮渲染不能用于证明产品音频缺陷。原脚本、图和结果保留。改成真实 kind 并补显式画面后才运行 before-r2；产品代码当时未改。该轮真实同步和独立 FFmpeg 对照本身仍有效。

只补 first_pts 后，同步位置已正确，但置信度仍未达到原 .95 断言。前缀静音改变全局均值/方差，且首个公共差分点的前史不一致。当前按实际公共窗口计算 Pearson，评分时排除这个边界点；至少 1 秒的物理重叠门槛保留，评分向量少一个点。使用前缀和计算各候选窗口统计，未增加每个候选重新扫描整个窗口的开销。原 50 Hz 包络、单一偏移、搜索上限和低置信警告仍有局限。

普通选区、非零封装原点、速度曲线的实际 source 样本窗，以及嵌套音频叶片均在作者选择前规范化。相同非零音频/容器原点不会虚加 5 秒静音；相对晚 1 秒的文件保留 1 秒。R3 的输入长度/全静音窗和输出采样数实际执行核验，不代表 R3 输出与输入 PCM 相同、音高/相位或听感已验收。计划包含源时钟说明及实现 SHA，旧派生身份不会被静默复用。

本页原生观察使用实际 FFmpeg、项目素材登记及内部滤镜图入口；尚未替代完整产品 render CLI、权利/队列/发布链和新隔离安装的验收。音频为原生 float32 PCM；压缩编解码器 priming、负时间与 edit-list、稀疏/不连续时间戳、设备漂移、自然录音、长片/RSS、连续播放与听审均未验收。没有完整剪映功能或效果等价。全程原生 Windows，无 Docker、WSL、虚拟环境或远程模型。
'''
    path=ROOT/REPORT;path.parent.mkdir(parents=True,exist_ok=True);assert not path.exists();path.write_text(report,encoding='utf8',newline='\n')
    contract='''# 原生音频起点与作者采样时钟（实验 v0.1，2026-10-21）

独立候选，不能据局部控制宣称完整发行或剪映等价。

| 编号 | 契约 | 当前证据 |
|---|---|---|
| AO-C01 | 源音频时间相对于 demux 原点；首音频 PTS 以前保留静音，再按作者范围取样，不把实际内容提前 | 原生 PCM、3 秒完整样本限定通过 |
| AO-C02 | 所有进入选区/反向/曲线/嵌套/R3 的物理源路径遵循相同起点；已处理表面保持自身既有时钟 | 12 方法限定通过；更广相关回归中 |
| AO-C03 | 同步包络按同一源时间规范化，r 对应 source r＋delay；音轨存在与视频覆盖分别报告 | 真实 PCM 延迟例 1 秒通过 |
| AO-C04 | 至少一秒物理重叠；置信度基于实际公共窗口，排除一阶差分无共同前史的首点 | 真实生成例；自然校准/歧义尚未验收 |
| AO-C05 | 不启用 async，不宣称补源起点就是漂移校正；保留 50 Hz 偏移分辨率和搜索预算 | 当前实现与原生证据 |
| AO-C06 | 零起点和音频/容器同原点控制不得改变原 PCM；非零封装原点须用相对起点 | 原生控制通过 |
| AO-C07 | 物理源缺口产生的静音与时域引擎输出不足不得混淆；R3 仍明确拒绝错误输出长度及非零内容丢失 | 实际 R3 输入/输出帧及静音窗通过 |
| AO-C08 | 实现 SHA 与时钟协议进入 R3 计划身份；既有缓存不能因新时钟误命中 | 实现描述，完整产品重放待验收 |
| AO-C09 | 补齐实际产品 CLI/原片/输出/GIF或音频、隔离包、Skill、完整套件、README及普通推送各自证据 | 尚未完成 |
| AO-C10 | 负 priming/edit-list、不连续音频、设备漂移、自然/长片/RSS/播放听审及完整剪映功能效果分别验收 | 尚未验收 |

[实际执行与保留失败](../validation/原生音频起点与同步独立实验_2026-10-21.md)。
'''
    path=ROOT/CONTRACT;path.parent.mkdir(parents=True,exist_ok=True);assert not path.exists();path.write_text(contract,encoding='utf8',newline='\n')
    docs={name:sha(ROOT/name) for name in ('README.md',REPORT,CONTRACT)}
    links=[]
    for name in docs:
        path=ROOT/name
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',path.read_text('utf8')):
            target=(path.parent/token).resolve();assert target.is_relative_to(ROOT) and target.exists(),(name,token)
            links.append({'document':name,'target':target.relative_to(ROOT).as_posix()})
    assert frozen()==current
    record={'status':'passed-twelve-controls-awaiting-related-media-install-and-complete-suite',
        'at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,'parent_inputs':parent,
        'modified_runtime_inputs':sorted(modified),'new_test_methods':12,'current_controls_seconds':after['suite_seconds'],
        'current_controls_sha256':sha(base/'after-controls-r3.json'),'same_test_and_runner_in_all_four_attempts':True,
        'native_observation_sha256':sha(base/'after-r1/observations.json'),'related_at_document_time':related['status'],
        'related_expected_methods':226,'related_tool_handle':59378,'full_suite_started':False,'main_integrated':False,
        'skills_registered':False,'new_public_media_present':False,'new_isolated_install_completed':False,
        'expected_future_full_methods':2031,'expected_future_parent_full_methods':2019,'documents':docs,'local_links':links,
        'generator_sha256':sha(__file__),'native_windows':True,'virtualization':False,'network':False,
        'limits':['PCM generated fixtures only','compressed priming and audio discontinuities unaccepted',
            'no async drift correction','no natural long RSS playback listening or full CapCut parity acceptance']}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'current_controls':12,'related_expected':226,'links':len(links),'frozen_inputs':259}))


if __name__=='__main__':main()
