"""Document and audit the independently tested, unmerged empty-window candidate."""
from __future__ import annotations
from datetime import datetime,timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
REL=Path('docs/validation/evidence/native-empty-window-20261021-lab')
ASSETS=Path('docs/assets/native-empty-window-20261021-lab')
REPORT=Path('docs/validation/空视频选区与显式音频保留独立实验_2026-10-21.md')
CONTRACT=Path('docs/specs/原生视频空区间契约_实验_v0.1_2026-10-21.md')
MARKER='NATIVE-EMPTY-WINDOW-LAB-20261021'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def write(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')


def save(path,value):write(path,json.dumps(value,ensure_ascii=False,indent=2))


def link(document,target,label):
    return '['+label+']('+os.path.relpath(target,document.parent).replace('\\','/')+')'


def main():
    audit_path=ROOT/REL/'audit-r1.json';assert not audit_path.exists()
    before=frozen();assert len(before)==256
    status={'status':'checking','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'native_windows':sys.platform=='win32','virtualization':False,'network':False,
        'full_suite_executed':False,'main_integrated':False,'published':False}
    try:
        related=read(ROOT/REL/'related-r2.json')
        assert related['status']=='passed-related-regressions' and related['distinct_methods']==293
        assert related['frozen_before']==related['frozen_after']==before
        assert len(set(related['method_ids']))==293 and related['skipped']==0
        for name,digest in related['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
        for label,row in related['families'].items():
            path=ROOT/REL/(label+'-final-r2.json');item=read(path)
            assert sha(path)==row['evidence_sha256'] and item['terminal_ok'] and item['skipped']==0
            assert item['frozen_before']==item['frozen_after']==before
            assert item['external_fixture_count']==8 and item['external_fixtures_equal']
            assert item['verification_scripts_equal'] and item['external_fixture_manifest_unchanged']
        native=read(ROOT/REL/'native-r2/verification.json')
        installed=read(ROOT/REL/'installed-r1/verification.json')
        isolated=read(ROOT/REL/'installed-r1/media/verification.json')
        for item in (native,installed,isolated):
            assert item['status']=='passed' and item['frozen_before']==item['frozen_after']==before
            assert all(row['ok'] for row in item['checks'])
        assert native['cli_calls']==17 and native['native_commands']==18 and len(native['checks'])==23
        assert installed['isolated_cli_calls']==20 and installed['module_origin_probes']==1
        assert len(installed['resource_hashes'])==161
        for name,digest in installed['resource_hashes'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
        base=read(ROOT/REL/'foundation-r1.json')['source_inputs'];assert len(base)==255
        assert set(before)-set(base)=={'product/tests/test_native_empty_window.py'}
        changed={name for name in base if before[name]!=base[name]}
        assert changed=={'product/src/ai_ad_editor/reverse_video_clock.py'}
        old=read(ROOT/REL/'before-r2.json');fixed=read(ROOT/REL/'after-r1.json')
        assert old['methods']==fixed['methods']==8 and old['exit_code']==1 and fixed['terminal_ok']
        assert old['frozen_equal'] and fixed['frozen_equal']
        assert sha(ROOT/REL/'after-r1-clock.py.txt')==sha(ROOT/'product/src/ai_ad_editor/reverse_video_clock.py')
        assert sha(ROOT/REL/'after-r1-test.py.txt')==sha(ROOT/REL/'before-empty-fix-r2/test_native_empty_window.py')
        audio=read(ROOT/REL/'after-r3.json');assert audio['terminal_ok'] and audio['methods']==16
        assert audio['frozen_before']==audio['frozen_after']==before
        assert not read(ROOT/REL/'index-final-r1.json')['suite_launched']
        parent=ROOT.parent/'nested-native-clock-lab-20261021'
        patch=''
        for name in sorted(changed|{'product/tests/test_native_empty_window.py'}):
            previous=(parent/name).read_text('utf8') if name in changed else ''
            patch+=''.join(difflib.unified_diff(previous.splitlines(keepends=True),(ROOT/name).read_text('utf8').splitlines(keepends=True),
                fromfile='a/'+name,tofile='b/'+name))
        write(ROOT/REL/'runtime-and-oracle.patch',patch)
        visual=[]
        for name in native['cases']:
            development=ROOT/ASSETS/'native-r2'/(name+'-actual-frame.png')
            shipped=ROOT/ASSETS/'installed-r1'/(name+'-actual-frame.png')
            assert sha(development)==sha(shipped)
            visual.append({'path':development.relative_to(ROOT).as_posix(),'sha256':sha(development),
                'review':'Viewed the actual decoded MP4 frame: green underlying image and all three text lines remain visible.',
                'installed_identical_png':True,'continuous_playback_reviewed':False,'audio_listened':False})
        save(ROOT/REL/'frame-review-r1.json',{'status':'reviewed-static-frames','frames':visual,
            'all_45_frames_per_case_automatically_compared':True,'full_capcut_parity':False})
        rows=[('EW-E01','修复前后同一 8 项原生测试','修复前 2 项普通正放通过、6 项报错；修复后同一断言 8 项通过。原始源码和测试快照保留。',REL/'before-r2.json'),
            ('EW-E02','有声输入与未知 EOF','16 项、41.686 秒、0 跳过；6 项显式音频轨的 72,000 每声道采样与独立参考逐字节一致；未知尾帧时长拒绝。',REL/'after-r3.json'),
            ('EW-E03','相关回归','293 个不同方法、0 跳过；37 索引＋50 倒放＋63 序列＋22 预览＋105 嵌套＋16 空区间。32 个新嵌套方法包含于 105，16 项包含于 293。',REL/'related-r2.json'),
            ('EW-E04','公开 CLI 与真实导出','17 CLI＋18 原生命令、23 检查；两个 320×180 输出各 45 帧/30000÷1001 fps，完整无损 RGBA 10,368,000 字节及 PCM 576,000 字节均与独立参考一致。',REL/'native-r2/verification.json'),
            ('EW-E05','索引与拒绝行为','首次索引扫描 1 次、再次 0 次；故意损坏索引报 NATIVE_INDEX_CORRUPT/exit 6，未产生成片。计数不含最终解码、编码和 SHA 文件读取。',REL/'native-r2/corrupt-index-empty-window-rejected.stdout.log'),
            ('EW-E06','离线隔离安装','161 资源源码/wheel/site 字节一致，7 个已有依赖 wheel；20 隔离 CLI＋1 来源进程/11 模块，同样完整画面与 PCM 参考一致。',REL/'installed-r1/verification.json'),
            ('EW-E07','保留失败','最初空参考项目缺视频轨；有声扩展漏建音频轨；相关回归首次缺 8 个外部夹具，套件未启动；首个 CLI 请求复用 ID，被验证器拒绝。修正均未放松产品拒绝规则。',REL/'fixture-recovery-r1.json'),
            ('EW-E08','完整回归与发布边界','此 256 输入候选尚未完整回归、未合入 main、未推送。父级嵌套 255 输入候选的完整回归不算本候选验收。自然/HDR、非单位变速音频、长片、总 RSS 和完整剪映等价未验收。',CONTRACT)]
        def table(document):
            return '| 编号 | 实际检查 | 结果与边界 | 证据 |\n|---|---|---|---|\n'+'\n'.join(
                '| '+n+' | '+title+' | '+result+' | '+link(document,target,'记录')+' |' for n,title,result,target in rows)
        def gallery(document):
            a=os.path.relpath(ASSETS/'native-r2',document.parent).replace('\\','/')
            return f'''| 原始八帧内容 | 实际普通倒放空尾段 | 实际嵌套正放空前段 |
|---|---|---|
| ![原始八帧]({a}/source-cards.gif) | ![实际尾段]({a}/direct-reverse-tail.gif) | ![实际前段]({a}/nested-forward-prefix.gif) |

输入 GIF 仅显示原始 8 帧/320 ms。{link(document,ASSETS/'native-r2/source-audio-tail.mkv','原始短视频＋2 秒声音 MKV')} 与 {link(document,ASSETS/'native-r2/source-delayed-video.mkv','视频延迟 1 秒的 MKV')} 保留真实流时钟。两段输出 GIF 来自实际 MP4 的全部 45 帧，因下层图像不变而合为 1 帧/1500 ms；MP4 为 30000/1001 fps，作者总时长 1.5 秒，最后视频显示边界可至 1.5015 秒。GIF 无声音且时间只能落在 10 ms 网格。

{link(document,ASSETS/'native-r2/direct-reverse-tail.mp4','实际普通倒放 MP4')} · {link(document,ASSETS/'native-r2/nested-forward-prefix.mp4','实际嵌套正放 MP4')} · {link(document,REL/'frame-review-r1.json','静态抽帧目检记录')}。完整无损画面与音频是自动核验；只查看两张实际抽帧，未连续播放、未听音。MP4/AAC 与 GIF 为观看副本，未声称编码全像素或有损声音逐字节相同。'''
        intro='此独立实验基于尚未发布的嵌套原生时钟候选，继续修复有效素材选区完全落在首帧前或实际视频 EOF 后的行为。当前 256 产品输入；专项已完成，尚未完整回归、合入 main 或发布。'
        write(ROOT/'README.md','# 原生空视频选区独立实验\n\n'+intro+'\n\n'+table(Path('README.md'))+'\n\n'+gallery(Path('README.md'))+'\n\n'+link(Path('README.md'),REPORT,'实测报告')+' · '+link(Path('README.md'),CONTRACT,'实验契约'))
        write(ROOT/REPORT,'# 空视频选区与显式音频保留独立实验（2026-10-21）\n\n'+intro+'\n\n'+table(REPORT)+'\n\n'+gallery(REPORT)+'''

原始输入为本地生成的 8 帧 FFV1/BGRA，25 Hz，视频实际范围 [0,0.32) 秒；两个独立正弦声道共 2 秒。延迟变体只把视频时间戳平移 1 秒，音频仍始于 0。选区分别为 [1,1.5) 和 [0,0.5)，均不存在视频显示帧，但存在真实声音。

音频需要显式编排在音频轨。测试及公开 CLI 均建立相应根级或子级音频轨，完整参考独立解码源 PCM，按原始范围切片，倒放时按立体声采样对倒序，再放置到 0.11 秒作者起点；不从产品生成的时钟表达式推导参考。画面参考是独立下层 PNG 的完整 45 帧，能识别不透明黑色填补或错误尾帧克隆。

仅改变 `reverse_video_clock.py` 并新增 16 方法测试；原始 `_native_range` 在首帧前报选区无帧，倒放与嵌套正放在音频尾段报无有效视频区间。现在保留合法空选择，帧范围起止相同，显示时钟为 null，倒放栅格预算为零。索引仍绑定和复核；未知尾帧 duration、损坏索引、错误格式和源变化不会转换为合法空区间。图仍可能解码输入前缀，不宣称零解码、总内存或长片延迟已验收。

历史记录：`before-r1` 是空参考项目违反 VIDEO_TRACK_EMPTY 的夹具失败；`before-r2` 才是 2 通过/6 错误的实际行为复现。`after-r1` 在相同 8 项断言下通过；`after-r2` 的 6 个新增音频失败源于漏建音频轨，源码与记录保留，`after-r3` 补齐显式轨后 16 项通过。`related-r1` 在读取缺失外部素材时停止，未执行测试；`external-fixtures-r2` 从已提交 blob 恢复 8 个准确文件，`related-r2` 才是 293 项结果。`native-r1` 的重复轨/剪辑 ID 请求被验证器拒绝，`native-r2` 改用唯一 ID 后完成真实导出。

所有检查运行于原生 Windows，无 Docker、WSL、容器、虚拟环境、网络依赖下载或模型推理。复现入口为 `scripts/smoke_native_empty_window.py` 与 `scripts/verify_native_empty_install.py`，所执行脚本原文和 SHA 随证据保留。
''')
        contract_rows=[('EW-01','有效源选区','作者 source_in/out 合法，但与原生视频显示区间没有正交集，可以是空视频。不得据此改变作者选区。'),
            ('EW-02','首帧前','选区右端不晚于第一原生帧 PTS，返回相同起止帧索引 0；不预填第一帧。'),
            ('EW-03','实际视频 EOF 后','只有末帧 native duration 已知，且选区左端不早于真实 EOF，才返回相同起止索引 N；容器/音频更长不延长视频。'),
            ('EW-04','空时钟元数据','selected_frame_count=0，empty_native_video_interval=true，原因 before-first-native-frame 或 after-final-native-frame。首个显示时间/EOF 时钟为 null；无帧到达占位表达式。'),
            ('EW-05','组合与透明','空视频不遮挡真实下层，不克隆尾帧或填不透明黑色。普通倒放及原生叶子嵌套正/倒放使用同一范围选择。'),
            ('EW-06','音频编排','视频轨不隐式提取声音；需显式音频轨。单位变速完整 PCM 的保留已实测，任意非单位变速声音品质未据此验收。'),
            ('EW-07','预算','零选中帧估计倒放栅格缓冲为 0，不建立分块倒放缓存；源图、解码、编码、索引与 SHA 仍有工作量。'),
            ('EW-08','索引完整性','空选择也必须验证源/运行时及索引内容，并在输出提交前复核。损坏索引 NATIVE_INDEX_CORRUPT/exit 6，原成片不可被覆盖。'),
            ('EW-09','未知信息与错误','未知末帧 duration、无效时间基/尺寸、源探测失败和数据损坏保留明确拒绝；不得捕获所有异常后伪装为空。'),
            ('EW-10','冻结与交付','当前 256 输入，293 专项、真实 CLI、161 资源隔离发行均绑定相同字节；完整回归与生产合入尚未执行。'),
            ('EW-11','边界','虚拟内联表面继续遵守子级 CFR 契约。一般嵌套 VFR、自然/HDR、长片吞吐、进程 RSS、非单位变速音频及完整剪映等价仍未验收。')]
        write(ROOT/CONTRACT,'# 原生视频空区间契约（独立实验 v0.1，2026-10-21）\n\n'+intro+'\n\n| 编号 | 约束 | 行为 |\n|---|---|---|\n'+'\n'.join('| '+' | '.join(row)+' |' for row in contract_rows)+'\n\n'+link(CONTRACT,REPORT,'实际原生/隔离记录与保留失败'))
        skills={};validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
        guidance={
            'video-cut-agent-editor':'A valid source selection wholly before native video begins or after its known EOF can have no video frames. Preserve the authored window and underlying layers. Author audio explicitly on an audio track; video placement alone does not extract sound.',
            'video-cut-timeline':'For native leaves, preserve original PTS and the actual last-frame duration. Empty ranges use equal frame bounds and null display-clock endpoints; do not clone frames or substitute opaque black. Virtual inline surfaces retain their child CFR contract.',
            'video-cut-quality':'Review every lossless RGBA frame and the complete independently selected stereo float PCM. The two actual 45-frame outputs coalesce to a one-frame 1500 ms GIF; this is a viewing artifact and carries no sound. Separate decoded preview equality from MP4/AAC quality.',
            'video-cut-project-ops':'Retain verified source/runtime/index boundaries even when zero frames are selected. NATIVE_INDEX_CORRUPT/exit 6 must still block output. Unknown final native duration remains an error; explicit cache cleanup and authored-reference protection continue to apply.'}
        for name,text in guidance.items():
            relative=Path('skills')/name/'SKILL.md';source=MAIN/relative;assert source.is_file()
            parent_snapshot=ROOT/REL/'skills-parent-r1'/name/'SKILL.md';parent_snapshot.parent.mkdir(parents=True);shutil.copyfile(source,parent_snapshot)
            body=source.read_text('utf8');at=body.index('\n---',3)+4
            block=text+'\nRead the [experimental empty-window contract](../../'+CONTRACT.as_posix()+') and [actual independent evidence](../../'+REPORT.as_posix()+').\nThis is an unregistered laboratory draft; the 256-input candidate has not completed its full suite or been published. Zero selected-frame raster budget is not zero decoding or process RSS.'
            body=body[:at]+'\n\n<!-- '+MARKER+' -->\n'+block+'\n<!-- /'+MARKER+' -->\n'+body[at:]
            write(ROOT/relative,body)
            result=subprocess.run([sys.executable,'-E','-B','-X','utf8',str(validator),str(ROOT/relative.parent)],capture_output=True,timeout=60)
            assert result.returncode==0,name+': '+result.stderr.decode('utf8','replace')
            skills[name]={'path':relative.as_posix(),'sha256':sha(ROOT/relative),'parent_sha256':sha(source),
                'parent_snapshot':parent_snapshot.relative_to(ROOT).as_posix(),'new_block':block,
                'new_block_marker':MARKER,'validator_stdout':result.stdout.decode('utf8','replace').strip(),
                'registered':False,'future_integration':'Apply only this new block onto the then-current main Skill; never replace the complete body with this draft.'}
        save(ROOT/REL/'skills-draft-r1.json',{'status':'passed-four-unregistered-drafts','skills':skills,'registration_changed':False})
        links=[]
        for name in (Path('README.md'),REPORT,CONTRACT,*[Path(row['path']) for row in skills.values()]):
            text=(ROOT/name).read_text('utf8')
            if name.parts[0]=='skills':text=text.split('<!-- '+MARKER+' -->')[1].split('<!-- /'+MARKER+' -->')[0]
            for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',text):
                target=token.strip('<>').split('#',1)[0]
                if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
                path=(ROOT/name.parent/target).resolve();assert path.is_relative_to(ROOT) and path.exists(),(str(name),target)
                links.append({'document':name.as_posix(),'target':path.relative_to(ROOT).as_posix()})
        media={};gifs={}
        for proof in (native,isolated):
            for name,digest in proof['assets'].items():
                path=ROOT/name;assert sha(path)==digest
                media[name]={'sha256':digest,'bytes':path.stat().st_size}
                if path.suffix=='.gif':
                    with Image.open(path) as image:
                        duration=0
                        for n in range(image.n_frames):image.seek(n);duration+=image.info.get('duration',0)
                        gifs[name]={'frames':image.n_frames,'duration_ms':duration}
        assert frozen()==before
        status.update(status='passed-standalone-audit',frozen_inputs=before,targeted_methods=293,
            source_wheel_installed_resources=161,media=media,gifs=gifs,local_links=links,
            documents={name.as_posix():sha(ROOT/name) for name in (Path('README.md'),REPORT,CONTRACT)},
            unregistered_skills=4,skill_draft_sha256=sha(ROOT/REL/'skills-draft-r1.json'),
            source_patch_sha256=sha(ROOT/REL/'runtime-and-oracle.patch'),generator_sha256=sha(__file__))
    except BaseException as caught:
        status.update(status='failed',error={'type':type(caught).__name__,'message':str(caught)});raise
    finally:
        status['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(audit_path,status)
        print(json.dumps({k:status.get(k) for k in ('status','targeted_methods','source_wheel_installed_resources','error')}),flush=True)


if __name__=='__main__':main()
