"""Publish the exact tested native-index bytes after the complete suite passes."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from native_index_release_tools import MAIN,sha,git,staged_rows
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/native-frame-index-20261021-lab'
ASSETS='docs/assets/native-frame-index-20261021-lab'
REPORT='docs/validation/原生帧索引缓存与倒放复用实测_2026-10-21.md'
CONTRACT='docs/specs/原生帧索引缓存契约_v0.1_2026-10-21.md'
HISTORICAL_REPORT='docs/validation/原生帧索引缓存独立实验_2026-10-21.md'
HISTORICAL_CONTRACT='docs/specs/原生帧索引缓存契约_实验_v0.1_2026-10-21.md'
SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-quality','video-cut-project-ops')
SCRIPTS=('smoke_native_frame_index','verify_native_frame_index_install','finalize_native_index_lab',
         'run_native_index_after_v82','native_index_release_tools','publish_native_frame_index')
MODULES=('capabilities','cli','preview','render','reverse_cache','reverse_video_clock','native_video_index','derived_cache')
TESTS=('test_native_video_index','test_native_video_index_ops','test_native_video_index_render')
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md')


def read(path):return json.loads(path.read_bytes())


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value.rstrip()+'\n',encoding='utf8',newline='\n')


def block(path,value):
    marker='V83-NATIVE-INDEX';text=path.read_text(encoding='utf8')
    replacement=f'<!-- {marker} -->\n{value.rstrip()}\n<!-- /{marker} -->'
    pattern=re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
    if re.search(pattern,text,re.S):text=re.sub(pattern,lambda _:replacement,text,flags=re.S)
    else:
        position=text.index('\n---',3)+4 if text.startswith('---\n') else text.index('\n')
        text=text[:position]+'\n\n'+replacement+'\n'+text[position:]
    write(path,text)


def source_files():
    paths={f'product/src/ai_ad_editor/{name}.py' for name in MODULES}
    paths|={f'product/tests/{name}.py' for name in TESTS}
    paths|={f'scripts/{name}.py' for name in SCRIPTS}|{HISTORICAL_REPORT,HISTORICAL_CONTRACT}
    for prefix in (REL,ASSETS):
        paths.update(path.relative_to(ROOT).as_posix() for path in (ROOT/prefix).rglob('*') if path.is_file())
    for name in paths:
        path=ROOT/name;assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),name
    return {name:sha(ROOT/name) for name in sorted(paths)}


def source_audit():
    current=frozen();assert len(current)==254
    audit=read(ROOT/REL/'audit-r2.json');assert audit['status']=='passed-standalone-audit' and audit['frozen_inputs']==current
    assert audit['targeted_methods']==172 and audit['source_wheel_installed_resources']==161
    for name,digest in read(ROOT/REL/'installed-r1/verification.json')['resource_hashes'].items():
        assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest,name
    for name,row in audit['media'].items():assert sha(ROOT/name)==row['sha256']
    for name,count in (('integration-r2',37),('reverse-r1',50),('nested-r1',63),('preview-r1',22)):
        item=read(ROOT/REL/(name+'.json'))
        assert item['terminal_ok'] and item['methods']==count and item['skipped']==0
        assert item['frozen_before']==item['frozen_after']==current
        assert sha(ROOT/REL/(name+'.log'))==item['log_sha256']
    return current


def complete_gate(current):
    state=read(ROOT/'product/.runtime/native-index-20261021/full-after-v82-r2/run.json')
    assert state['status']=='passed-complete-suite-awaiting-reviewed-integration'
    full=read(ROOT/REL/'full-r1.json');alignment=read(ROOT/REL/'published-v82-alignment-r1.json')
    assert full['status']=='passed' and full['terminal_ok'] and full['methods']==1925 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==current
    assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['verification_scripts_equal']
    assert full['external_fixture_manifest_unchanged'] and alignment['status']=='passed'
    assert alignment['candidate_inputs']==current and alignment['remote_main']==alignment['published_commit']
    assert state['full_sha256']==sha(ROOT/REL/'full-r1.json')
    snapshots=read(ROOT/REL/'before-full-documents-r1.json')
    for name,row in snapshots['documents'].items():
        assert sha(ROOT/row['snapshot'])==row['sha256']==read(ROOT/REL/'audit-r2.json')['documents'][name]
    return full,alignment


def documents(root,full):
    message=f"完整原生回归 **1925 项、{full['suite_seconds']:.3f} 秒、0 跳过**；254 产品输入与 8 外部夹具不变（本轮限定验收）"
    table=f'''| 编号 | 实际功能核验 | 结果与边界 | 证据 |
|---|---|---|---|
| V83-01 | 原生 PTS/duration 索引与实际执行 | 37 项；真实二次渲染不再扫描源帧，VFR 小数源区间独立全帧参考、取消、篡改/删除拒绝和只读规划通过 | [索引专项]({REL}/integration-r2.json) |
| V83-02 | 既有倒放、嵌套和预览 | 50＋63＋22 项；与 37 项合为 172 不同方法，均 0 跳过；13 清理方法包含在 50 项内 | [倒放]({REL}/reverse-r1.json) · [嵌套]({REL}/nested-r1.json) · [预览]({REL}/preview-r1.json) |
| V83-03 | 公开 CLI /真实 4K | 17 CLI 属于 26 原生命令；24 检查。9 帧源选 8 帧/0.32 秒，原生 RGBA 哈希与独立无损整帧参考一致；首次索引扫描 1 次、命中 0 次，删除后数组重建一致 | [实测]({REL}/native-r1/verification.json) · [源视频]({ASSETS}/native-r1/source-review.mp4) · [实际输出]({ASSETS}/native-r1/reverse-review.mp4) |
| V83-04 | 离线隔离发行 | 161 资源源码/wheel/site 字节一致、7 现有 wheels；20 隔离 CLI＋1 来源进程，10 模块位于安装目录，同一 4K 输出哈希一致 | [安装]({REL}/installed-r1/verification.json) |
| V83-05 | 完整回归与发布基线 | {message}；绑定 V82 已发布提交，全部专项为完整回归子集 | [完整收据]({REL}/full-r1.json) · [基线差异]({REL}/published-v82-alignment-r1.json) |
| V83-06 | 显式索引清理 | `cache list/prune --kind native-video-index`；256 目录、固定三文件、当前作者引用保护、未知文件与目录联接拒绝；盘点不认证内容完整性 | [契约]({CONTRACT}) |
| V83-07 | 历史保留 | 早期 14/24 方法、审计脚本链接门槛失败、排队状态写入冲突及修正均保留，按各自源码区分；完整套件在首次排队失败时未启动 | [独立实验记录]({HISTORICAL_REPORT}) · [排队失败]({REL}/queue-r1-state-write-failure.json) · [原生重试复现]({REL}/state-write-retry-native-r2.json) |
| V83-08 | 尚未验收 | 命中仍读取源/程序 SHA；音频、最终视频解码/编码不包含在源索引扫描计数内。未验收长片延迟/总 RSS、自然/HDR 质量、一般嵌套 VFR或完整剪映等价 | [完整限制]({CONTRACT}) |'''
    gallery=f'''| 原输入的实际编码预览 | 实际倒放成片的编码预览 |
|---|---|
| ![原创源]({ASSETS}/native-r1/source.gif) | ![实际输出]({ASSETS}/native-r1/reverse.gif) |

GIF 均由实际 MP4 解码生成，8 帧/320 ms；源是原创 CC0 几何画面。已查看 8 帧静态总览，未连续播放、未听音，无新模型推理。二次有损编码观察误差与原生平面/无损预览的零误差分别记录。'''
    block(root/'README.md',f'2026-10-21 **V83（持久原生帧索引与倒放复用）**：{message}。普通原生倒放复用验证后的源时间索引，重复渲染不再全源扫描帧；保留 V82 帧区间、像素缓存与磁盘预约限制。\n\n'+table+'\n\n'+gallery)
    for name in LATEST_DOCS[1:]:
        relative='' if name!='docs/README.md' else ''
        links=('[实测与原视频/GIF](validation/'+Path(REPORT).name+') · [索引契约](specs/'+Path(CONTRACT).name+')')
        block(root/name,'2026-10-21 V83：'+message+'。新增持久原生帧索引和显式三文件清理，重复倒放避免全源帧扫描。172 个不同专项方法、实际 4K/安装结果分别记录；完整剪映功能与效果目标保持不变。\n\n'+links)
    report=f'# 原生帧索引缓存与倒放复用实测（2026-10-21）\n\n{message}。\n\n'+table+'\n\n'+gallery+'''

索引保存小端 int64 PTS/duration，绑定源、ffprobe、解码器与实现字节；命中校验缓存后跳过完整源帧扫描，仍有 SHA 文件读取和最终渲染。根作者图及递归剪辑窗口共用索引上下文，发布前再次验证索引文件；源或缓存变化会阻止提交成片。

V82 的 128 GiB 保守预约仍可能在约 20 秒 4K/25 fps 选区触达上限；本次未解除这个限制。只验收 8 帧几何样例、有限原生/alpha/10-bit 相邻专项与真实离线安装，不代表长片吞吐、总进程内存、自然画质、HDR、声音质量或一般嵌套 VFR 已验收。

开发复现脚本为 `scripts/smoke_native_frame_index.py`；隔离安装复现为 `scripts/verify_native_frame_index_install.py`，使用现有本地 wheelhouse。所有运行均为原生 Windows，无依赖下载、Docker、WSL、容器或虚拟环境。历史失败及各阶段的源码、文档快照保留在独立实验记录中。
'''
    report=report.replace(']('+REL+'/','](evidence/native-frame-index-20261021-lab/').replace(']('+ASSETS+'/','](../assets/native-frame-index-20261021-lab/').replace(']('+CONTRACT+')','](../specs/'+Path(CONTRACT).name+')').replace(']('+HISTORICAL_REPORT+')',']('+Path(HISTORICAL_REPORT).name+')')
    write(root/REPORT,report)
    contract=(root/HISTORICAL_CONTRACT).read_text(encoding='utf8')
    contract=contract.replace('（独立实验 v0.1，2026-10-21）','（v0.1 限定验收，2026-10-21）').replace(
        '本契约描述独立实验目录中的实现，尚未合入 main。','本契约定义普通原生视频倒放的持久源时间索引。')
    contract=contract.replace(Path(HISTORICAL_REPORT).name,Path(REPORT).name)
    write(root/CONTRACT,contract)
    for name in SKILLS:
        text=f'''When capabilities advertise `native_video_frame_index`, ordinary native reverse reuses verified source PTS/duration arrays.
`source_index_decode_calls=0` skips full-source frame scans; source/runtime SHA reads, audio, final video decoding and encoding still apply.
Use `cache list --project P --kind native-video-index` before explicit `cache prune --project P --kind native-video-index --key KEY --dry-run`.
Current authored references are protected; keep corrupt indexes for diagnosis until explicit cleanup. Do not edit derived arrays.
Read the [index contract](../../{CONTRACT}) and [actual native/isolated evidence](../../{REPORT}).
The 256-entry limit, V82 disk reservation and unaccepted long-duration, peak RSS, natural/HDR quality, nested VFR and full CapCut parity limits still apply.'''
        skill_path=root/'skills'/name/'SKILL.md'
        previous=skill_path.read_text(encoding='utf8')
        old_probe='index probe that still runs on cache hits. Raster estimates are not process RSS guarantees.'
        assert previous.count(old_probe)==1,name
        previous=previous.replace(old_probe,
            'index probe. When capabilities expose native_video_frame_index, verified index hits skip that probe;\n'
            'source/runtime SHA reads remain. Raster estimates are not process RSS guarantees.')
        write(skill_path,previous)
        block(skill_path,text)
    attributes=(root/'.gitattributes').read_text(encoding='utf8')
    lines=[REL+'/** -text -whitespace',ASSETS+'/** -text -whitespace']
    lines += [f'product/src/ai_ad_editor/{name}.py -text whitespace=cr-at-eol' for name in MODULES]
    lines += [f'product/tests/{name}.py -text whitespace=cr-at-eol' for name in TESTS]
    lines += [f'scripts/{name}.py -text whitespace=cr-at-eol' for name in SCRIPTS]
    write(root/'.gitattributes',attributes+'\n# V83 exact tested index bytes and evidence.\n'+'\n'.join(lines))
    return {*LATEST_DOCS,REPORT,CONTRACT,'.gitattributes',*('skills/'+name+'/SKILL.md' for name in SKILLS)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args();work=args.work.resolve()
    assert work.is_relative_to(ROOT/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    state={'status':'checking-source','started_at_utc':datetime.now(timezone.utc).isoformat(),'calls':[],'force_push':False}
    def checkpoint():save(work/'run.json',state)
    try:
        current=source_audit();reviewed=source_files()
        state.update(status='passed-source-preflight-awaiting-full',frozen_inputs=current,source_files=reviewed);checkpoint()
        if args.preflight_only:return
        full,alignment=complete_gate(current);base=alignment['published_commit']
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==base
        assert git(MAIN,'remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==base
        assert not git(MAIN,'status','--porcelain','-z'),'Main changed; preserve it and refuse implicit integration'
        spec=importlib.util.spec_from_file_location('native_index_main_freeze',MAIN/'scripts/run_frozen_regression.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert module.frozen()==alignment['upstream_inputs']
        tracked={p.decode('utf8') for p in git(MAIN,'ls-files','-z').split(b'\0') if p}
        generated={REPORT,CONTRACT,REL+'/skills-release-r1.json',REL+'/release-main-r1.json',REL+'/publication-copy-r1.json',REL+'/staged-release-r1.json'}
        for name in set(reviewed)|generated:
            path=MAIN/name;assert path.resolve().is_relative_to(MAIN) and not path.is_symlink()
            assert name in tracked or not path.exists(),'Existing untracked destination: '+name
        assert source_files()==reviewed and frozen()==current
        state.update(status='copying-reviewed-source',base_commit=base);checkpoint()
        for name,digest in reviewed.items():
            target=MAIN/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            assert sha(target)==digest,name
        assert module.frozen()==current
        modified_docs=documents(MAIN,full)
        command=[sys.executable,'-E','-B','-X','utf8',str(MAIN/'scripts/audit_source_edit_skills.py'),
                 '--expected-count','17','--output',str(MAIN/REL/'skills-release-r1.json')]
        result=subprocess.run(command,cwd=MAIN,capture_output=True,timeout=600)
        (work/'main-skills.stdout.log').write_bytes(result.stdout);(work/'main-skills.stderr.log').write_bytes(result.stderr)
        state['calls'].append({'command':command,'exit_code':result.returncode});checkpoint();assert result.returncode==0
        skills=read(MAIN/REL/'skills-release-r1.json');mapping_path=MAIN/'video-cut-install-manifest.json';mapping=read(mapping_path)
        mapping.setdefault('audit_history',[]).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row=next(item for item in skills['results'] if item['skill']==entry['name'])
            old,new=entry['skill_md_sha256'],row['sha256'][7:]
            if old!=new:
                entry.setdefault('skill_md_sha256_history',[]).append(old);entry['previous_manifest_skill_md_sha256']=old
            entry.update(skill_md_sha256=new,validation=row['validator_stdout'],prefix_verified=True,registration_verified=True)
            assert Path(entry['canonical_directory']).resolve()==(MAIN/'skills'/entry['name']).resolve()
        mapping['current_audit']={'date':'2026-10-21','skill_count':17,'local_links_checked':skills['local_links_checked'],
            'record':REL+'/skills-release-r1.json','record_sha256':sha(MAIN/REL/'skills-release-r1.json'),
            'previous_hashes_preserved':True,'semantics':'V83 native frame-index reuse and safe pruning; no full CapCut parity acceptance'}
        save(mapping_path,mapping)
        links=[]
        for name in sorted(modified_docs-{'.gitattributes'}):
            path=MAIN/name;text=path.read_text(encoding='utf8')
            if name in LATEST_DOCS or name.startswith('skills/'):
                text=text.split('<!-- V83-NATIVE-INDEX -->',1)[1].split('<!-- /V83-NATIVE-INDEX -->',1)[0]
            for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',text):
                target=token.strip('<>').split('#',1)[0]
                if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
                resolved=(path.parent/target).resolve();assert resolved.is_relative_to(MAIN) and resolved.exists(),(name,token)
                links.append({'document':name,'target':resolved.relative_to(MAIN).as_posix()})
        for name,digest in current.items():assert sha(MAIN/name)==digest
        for name,row in full['external_fixtures_expected'].items():assert sha(MAIN/name)==row['sha256']
        save(MAIN/REL/'release-main-r1.json',{'status':'passed-main-byte-and-document-audit','base_commit':base,
            'frozen_inputs':current,'full_methods':1925,'full_skipped':0,'full_sha256':sha(MAIN/REL/'full-r1.json'),
            'targeted_methods':172,'resources':161,'skills':17,'local_links':links,
            'documents':{name:sha(MAIN/name) for name in sorted(modified_docs)},'generator_sha256':sha(Path(__file__))})
        save(MAIN/REL/'publication-copy-r1.json',{'status':'passed-reviewed-copy','source':str(ROOT),
            'copied_files':reviewed,'frozen_inputs':current,'base_commit':base})
        changed={p.decode('utf8') for p in git(MAIN,'diff','--name-only','-z').split(b'\0') if p}
        changed.update(p.decode('utf8') for p in git(MAIN,'ls-files','--others','--exclude-standard','-z').split(b'\0') if p)
        allowed=set(reviewed)|modified_docs|generated|{'video-cut-install-manifest.json'}
        assert changed<=allowed,sorted(changed-allowed)
        stage=work/'stage-paths.nul';stage.write_bytes(b'\0'.join(name.encode('utf8') for name in sorted(changed))+b'\0')
        git(MAIN,'add','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        git(MAIN,'add','--renormalize','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        assert not git(MAIN,'diff','--name-only')
        assert {p.decode('utf8') for p in git(MAIN,'diff','--cached','--name-only','-z').split(b'\0') if p}==changed
        git(MAIN,'diff','--cached','--check');rows=staged_rows({**{name:sha(MAIN/name) for name in changed},**current})
        receipt=REL+'/staged-release-r1.json'
        save(MAIN/receipt,{'status':'passed','frozen_files':254,'compared_blobs':len(rows),'files':rows,
            'all_staged_bytes_equal_workspace':True,'all_frozen_bytes_equal_staged':True,
            'stream_buffer_bytes':65536,'full_sha256':sha(MAIN/REL/'full-r1.json'),'base_commit':base})
        git(MAIN,'add','--',receipt);staged_rows({receipt:sha(MAIN/receipt)})
        assert module.frozen()==current and not git(MAIN,'diff','--name-only')
        git(MAIN,'diff','--cached','--check');state.update(status='passed-staged-audit');checkpoint()
        git(MAIN,'commit','--quiet','-m','feat: persist native frame indexes across reverse renders')
        commit=git(MAIN,'rev-parse','HEAD').decode().strip();assert git(MAIN,'rev-parse','HEAD^').decode().strip()==base
        state.update(status='committed-awaiting-ordinary-push',commit=commit);checkpoint()
        git(MAIN,'push','origin','main');remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and not git(MAIN,'status','--porcelain','-z') and module.frozen()==current
        state.update(status='published',remote_main=remote,main_clean=True,full_methods=1925)
    except BaseException as caught:
        state.update(status='failed',error={'type':type(caught).__name__,'message':str(caught)});raise
    finally:
        checkpoint();print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
