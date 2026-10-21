"""Bind actual native/isolated CLI media and static PCM plots, preserving earlier scope."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/audio-source-origin-20261021-lab'
ASSETS='docs/assets/audio-source-origin-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    output=REL/'media-audit-r1.json';assert not output.exists();current=frozen()
    previous=read(REL/'related-audit-r1.json');assert current==previous['frozen_inputs'] and len(current)==259
    related=read(REL/'related-r1.json');assert related['status']=='passed-related-regressions' and related['methods']==226
    assert related['frozen_before']==related['frozen_after']==current and related['terminal_ok'] and related['skipped']==0
    native=read(REL/'native-r1/verification.json');installed=read(REL/'installed-r1/verification.json')
    installed_media=read(REL/'installed-r1/media/verification.json')
    for row in (native,installed,installed_media):
        assert row['status']=='passed' and row['frozen_before']==row['frozen_after']==current and row['frozen_equal']
        assert all(c['ok'] for c in row['checks'])
    for row in (native,installed_media):
        assert row['cli_calls']==23 and row['native_commands']==32 and len(row['checks'])==39
        assert row['cases']==native['cases'] and set(row['cases'])=={'native','offset'}
        assert len(row['media'])==21 and len(row['GIF'])==7
        assert all(g['duration_ms']==3000 for g in row['GIF'].values())
        for name,g in row['GIF'].items():assert g['actual_mp4_decode']==name.endswith(('-output','-synced'))
    assert installed['isolated_cli_calls']==26 and installed['module_origin_probes']==1 and len(installed['checks'])==15
    assert len(installed['resource_hashes'])==161 and len(installed['optional_numpy_addon']['files'])==933
    for name,digest in installed['resource_hashes'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
    origins=next(c['origins'] for c in installed['checks'] if c['name']=='all-module-origins-under-installed-site');assert len(origins)==14
    assert sha(ROOT/'scripts/smoke_audio_source_origin.py')==native['script_sha256']==installed_media['script_sha256']
    assets={}
    for row in (native,installed_media):
        for name,details in row['media'].items():
            p=ROOT/name;assert p.resolve().is_relative_to(ROOT/ASSETS) and sha(p)==details['sha256'] and p.stat().st_size==details['bytes']
            assert name not in assets;assets[name]=details
    assert len(assets)==42
    static={'kind':'static-actual-decoded-PCM-plot-review','at_utc':datetime.now(timezone.utc).isoformat(),
        'reviewer':'Codex local image inspection','audio_listened':False,'continuous_playback_reviewed':False,'plots':{}}
    for case in ('native','offset'):
        a=ROOT/ASSETS/'native-r1'/(case+'-decoded-PCM.png');b=ROOT/ASSETS/'installed-r1'/a.name
        with Image.open(a) as first,Image.open(b) as second:
            assert first.size==second.size==(320,160) and first.convert('RGBA').tobytes()==second.convert('RGBA').tobytes()
        static['plots'][case]={'native_path':a.relative_to(ROOT).as_posix(),'native_sha256':sha(a),
            'installed_path':b.relative_to(ROOT).as_posix(),'installed_sha256':sha(b),'same_pixels':True,
            'observed':'both channels silent for first third of the 0..3-second plot; original signal appears at 1 second'}
    write(REL/'static-review-r1.json',static)
    write(REL/'media-manifest-r1.json',{'status':'passed','assets':assets,'asset_count':42,'GIF_count':14,
        'new_current_runtime_media':True,'parent_media_reused':False,'native_sha256':sha(REL/'native-r1/verification.json'),
        'installed_sha256':sha(REL/'installed-r1/verification.json'),'generator_sha256':sha(__file__)})
    snapshots=REL/'before-public-media-documents-r1';snapshots.mkdir();preserved={};documents={}
    record_path='docs/validation/evidence/audio-source-origin-20261021-lab'
    for name,digest in previous['documents'].items():
        path=ROOT/name;assert sha(path)==digest;target=snapshots/path.name;target.write_bytes(path.read_bytes())
        preserved[name]={'snapshot':target.relative_to(ROOT).as_posix(),'sha256':digest}
        prefix='' if name=='README.md' else ('../' if name.startswith('docs/specs/') else '')
        link_base=record_path if name=='README.md' else ('../validation/evidence/audio-source-origin-20261021-lab' if name.startswith('docs/specs/') else 'evidence/audio-source-origin-20261021-lab')
        message=f'''<!-- AUDIO-PUBLIC-MEDIA-R1 -->
当前实际原生 CLI/新隔离安装均通过：开发 **23 CLI＋32 其他命令、39 检查**；隔离 **26 CLI＋1 来源进程/14 模块、15 安装＋39 媒体检查**。161 资源源码/wheel/安装同字节。
真实容器原点 0/5 秒、音频首 PTS 1/6 秒，两例相对音频起点均为 1 秒；实际同步偏移 1 秒，原速切换保持参考事件位置与末尾 25 帧背景。每组原始/同步输出各 75 帧：完整 RGBA 17,280,000 字节及立体声 float32 PCM 1,152,000 字节独立相同。无损每声道 144000 样本；AAC 解码为 144384（含编码填充），不作完整字节一致或听审声明。
42 资产、14 GIF，包含两次新执行。实际 MP4 全部 PTS=n/25，身份色块最大误差 1；GIF 3000 ms，来自实际 MP4 解码。实际 PCM 图静态目检，安装图像素相同。基础 7 wheels 不含 NumPy；只读复制既有 2.4.2 的 933 个 RECORD/许可文件，不能视为产品安装器已内置 NumPy。
[原生收据]({link_base}/native-r1/verification.json) · [隔离收据]({link_base}/installed-r1/verification.json) · [逐资产 SHA]({link_base}/media-manifest-r1.json) · [静态目检范围]({link_base}/static-review-r1.json)。
相邻 226 通过仍是子集；Skill 增量、完整回归与发布未完成，剪映全功能和自然效果等价未验收。下面较早阶段的表格与运行状态作为历史记录保留。
<!-- /AUDIO-PUBLIC-MEDIA-R1 -->'''
        text=path.read_text('utf8');assert '<!-- AUDIO-PUBLIC-MEDIA-R1 -->' not in text;at=text.index('\n')
        text=text[:at]+'\n\n'+message+'\n'+text[at:]
        text=text.replace('| AO-09 | 尚缺交付 |','| AO-09 | 媒体执行前尚缺交付（历史） |')
        text=text.replace('实际产品 CLI 新媒体正在另行执行，隔离安装、Skill、完整回归及生产发布仍待完成。',
            '本段记录时新媒体仍在执行；现已完成原生/安装媒体，见文首最新记录。Skill、完整回归及生产发布仍待完成。')
        text=text.replace('尚未替代完整产品 render CLI、权利/队列/发布链和新隔离安装的验收。',
            '该观察当时未覆盖产品 render CLI 或新隔离安装；本次另有实际 CLI/安装检查。队列/发布链按后续完整回归分别验收。')
        text=text.replace('| AO-C09 | 补齐实际产品 CLI/原片/输出/GIF或音频、隔离包、Skill、完整套件、README及普通推送各自证据 | 尚未完成 |',
            '| AO-C09 | 实际产品 CLI/原片/输出/GIF或音频、隔离包、Skill、完整套件、README及普通推送各自证据 | CLI/媒体/隔离已完成；Skill/完整套件/生产发布未完成 |')
        if name=='README.md':
            text+=f'''
| 场景 | 原片 | 保留源音频起点 | 按偏移剪辑＋参考主音轨 |
|---|---|---|---|
| 原点 0，音频从 1 秒开始 | [MKV]({ASSETS}/native-r1/source-native.mkv) | [MP4]({ASSETS}/native-r1/native-output.mp4) · [GIF]({ASSETS}/native-r1/native-output.gif) | [MP4]({ASSETS}/native-r1/native-synced.mp4) · [GIF]({ASSETS}/native-r1/native-synced.gif) |
| 原点 5，音频从 6 秒开始 | [MKV]({ASSETS}/native-r1/source-offset.mkv) | [MP4]({ASSETS}/native-r1/offset-output.mp4) · [GIF]({ASSETS}/native-r1/offset-output.gif) | [MP4]({ASSETS}/native-r1/offset-synced.mp4) · [GIF]({ASSETS}/native-r1/offset-synced.gif) |

![真实保留源起点输出]({ASSETS}/native-r1/native-output.gif)

![实际同步剪辑输出]({ASSETS}/native-r1/native-synced.gif)

![实际无损解码 PCM 采样图]({ASSETS}/native-r1/native-decoded-PCM.png)

GIF 不含声音。采样图取自实际解码样本；两端点、源 PCM 和全部帧由自动检查核对，静态目检不等于播放或听审。素材为本项目原创 CC0 矩形字形、色卡和确定性音频，无外部字体/图片。
'''
        path.write_text(text,encoding='utf8',newline='\n');documents[name]=sha(path)
    assert frozen()==current
    result={'status':'passed-native-and-isolated-media-awaiting-skills-and-complete-suite',
        'at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,'targeted_methods':226,
        'related_sha256':sha(REL/'related-r1.json'),'related_audit_sha256':sha(REL/'related-audit-r1.json'),
        'native_sha256':sha(REL/'native-r1/verification.json'),'installed_sha256':sha(REL/'installed-r1/verification.json'),
        'media':assets,'asset_count':42,'GIF_count':14,'documents':documents,'historical_document_snapshots':preserved,
        'native_cli_calls':23,'native_checks':39,'isolated_cli_calls':26,'isolated_installer_checks':15,
        'runtime_resources':161,'explicit_numpy_addon_files':933,'base_installer_numpy_included':False,
        'new_current_runtime_media':True,'main_integrated':False,'full_suite_started':False,'skills_registered':False,
        'full_capcut_parity':False,'generator_sha256':sha(__file__)}
    write(output,result)
    links=[]
    for name in documents:
        path=ROOT/name
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',path.read_text('utf8')):
            target=(path.parent/token).resolve();assert target.is_relative_to(ROOT) and target.exists(),(name,token)
            links.append({'document':name,'target':target.relative_to(ROOT).as_posix()})
    result['local_links']=links;write(output,result)
    print(json.dumps({'status':result['status'],'assets':42,'GIFs':14,'document_links':len(links),'frozen_inputs':259}))


if __name__=='__main__':main()
