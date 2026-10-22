"""Prepare a reviewable research update; publish only after the existing V108 lineage."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=Path('docs/validation/evidence/openfilm-reuse-20261022-r17')
WORK=ROOT/'product/.runtime/openfilm-r17-release'
PARENT=MAIN/'product/.runtime/float-spatial-lab-20261022'
PWORK=PARENT/'product/.runtime/float-spatial-20261022'
REPORT='docs/OpenFilm当前复用建议与导出恢复增量_2026-10-22.md'
PRIOR='docs/OpenFilm_0.2.5可拆模块与复用成本评估_2026-10-22.md'
MARKER='R17-OPENFILM-REUSE-RECOVERY'


def sha(path): return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    for attempt in range(8):
        try:return json.loads(Path(path).read_bytes())
        except (OSError,json.JSONDecodeError):
            if attempt==7:raise
            time.sleep(.025)
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    os.replace(temporary,path)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module
def git(root,*args):
    result=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','-c','core.fsmonitor=false',*args],
        cwd=root,capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr.decode('utf8',errors='replace')[-3000:]
    return result.stdout


def source_rows():
    capture=read(ROOT/REL/'capture-r1/verification.json');final=read(ROOT/REL/'tests-r3/verification.json')
    assert capture['status']=='passed-pinned-source-capture' and capture['fixed_head']=='cf6cd6fa9b3d4ee50dd963853ee6ca4f8354ecf4'
    assert (capture['source_files'],capture['commits_since_r16'],capture['files_since_r16'])==(790,1,10)
    assert capture['license_unchanged_from_r16']
    assert final['status']=='completed-scoped-research-with-preserved-native-Node-failure'
    assert final['actual_upstream_test_totals']=={'tests':6,'pass':5,'fail':1,'cancelled':0,'skipped':0,'todo':0}
    assert final['actual_worker_probe_cases']==20 and final['actual_commonjs_probe_cases']==2
    for name,digest in final['input_receipts'].items():assert sha(ROOT/REL/name)==digest
    product=load(ROOT/'scripts/run_frozen_regression.py','r17_lab_product')
    assert product.frozen()==capture['frozen_before']==capture['frozen_after']==final['frozen_before']==final['frozen_after']
    assert len(final['frozen_before'])==311 and not final['product_code_adopted'] and not final['new_media']
    archive='sources/upstream/openfilm-025-20261022-r17/repo.zip'
    assert sha(ROOT/archive)==capture['archive_sha256']
    names={REPORT,archive}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('*openfilm_r17*') if p.is_file())
    excluded={'release-manifest-r1.json','staging-preflight-r1.json','publication-r1.json'}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/REL).rglob('*') if p.is_file() and p.name not in excluded)
    rows={}
    for name in sorted(names):
        path=ROOT/name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink() and path.stat().st_size<95*(1<<20)
        rows[name]=sha(path)
    return rows


def documents(destination):
    section=f'''<!-- {MARKER} -->
### R17 OpenFilm 复用清单与导出恢复增量（研究）

固定 main `cf6cd6fa`，release 仍为 v0.2.5；API 快照 2,032 stars /197 forks。HTML 动效、字幕和模板字段已有适配；新增优先候选是有限重试、浏览器池及 SHA 代理去重。本轮没有新增产品功能或成片。

| 编号 | 功能性检查 | 实际结果与边界 | 证据 |
|---|---|---|---|
| R17-01 | 固定源码与差异 | 790 文件逐 SHA，相对 R16 增 1 提交/10 文件；根 MIT 未变 | [固定收据](docs/validation/evidence/openfilm-reuse-20261022-r17/capture-r1/verification.json) |
| R17-02 | 原始上游测试 | 5 通过/1 失败/0 跳过；Node 22.14 缺少 import.meta.main，保留失败，不登记全部通过 | [原始 TAP](docs/validation/evidence/openfilm-reuse-20261022-r17/tests-r1/unmodified-openfilm-command.stdout.txt) |
| R17-03 | 有限重试与取消 | 原 worker、假 renderer，单次/池共 20 组通过；非真实浏览器故障、性能或清理验收 | [观察](docs/validation/evidence/openfilm-reuse-20261022-r17/tests-r1/pinned-worker-probe.stdout.txt) |
| R17-04 | Windows Node 入口 | 同一 CommonJS 2 组原生对照，旧包装 main=false、新预加载 main=true；未启动真实 Agent/Electron | [最终核对](docs/validation/evidence/openfilm-reuse-20261022-r17/tests-r3/verification.json) |
| R17-05 | 拆用工量与历史媒体 | 重试适配 1–3、池 3–6、去重 3–5 人日，存在共享工程；均为估计。无新增 GIF，V79 为历史实测 | [编号模块/预算/失败](docs/OpenFilm当前复用建议与导出恢复增量_2026-10-22.md) · [V79 原片](docs/assets/html-components-20261021-v79-native-r2/original.mp4) · [V79 GIF](docs/assets/html-components-20261021-v79-native-r2/comparison.gif) |
| R17-06 | 产品与执行隔离 | 研究时 311 产品输入不变；私有旧路径和可选文档连接重置失败保留；不累计产品回归或剪映等价完成率 | [输入/失败核对](docs/validation/evidence/openfilm-reuse-20261022-r17/tests-r3/verification.json) |

<!-- /{MARKER} -->
'''
    generated={REPORT:(ROOT/REPORT).read_text('utf8')}
    text=(MAIN/'README.md').read_text('utf8');assert MARKER not in text
    title,rest=text.split('\n',1);generated['README.md']=title+'\n\n'+section+'\n'+rest
    text=(MAIN/'docs/README.md').read_text('utf8');assert MARKER not in text
    title,rest=text.split('\n',1)
    generated['docs/README.md']=title+f'\n\n<!-- {MARKER} -->\nOpenFilm 当前 13 类拆用建议、有限重试观察、Node 原始失败和工量见 [R17 复核]({Path(REPORT).name})。本轮为研究，不新增产品/模型/媒体验收。\n<!-- /{MARKER} -->\n'+rest
    text=(MAIN/PRIOR).read_text('utf8');title,rest=text.split('\n',1)
    generated[PRIOR]=title+'\n\n> 本页保留 R16 的 v0.2.5 快照；main 新增的导出重绘、当前拆用顺序与 Node 版本失败见 [R17 复核](OpenFilm当前复用建议与导出恢复增量_2026-10-22.md)。\n'+rest
    attributes=(MAIN/'.gitattributes').read_text('utf8');assert '# R17 immutable' not in attributes
    generated['.gitattributes']=attributes.rstrip()+'''\n\n# R17 immutable upstream research, raw failures and source archive.
docs/validation/evidence/openfilm-reuse-20261022-r17/** -text -whitespace
sources/upstream/openfilm-025-20261022-r17/** -text -whitespace
scripts/*openfilm_r17* -text whitespace=cr-at-eol
docs/OpenFilm当前复用建议与导出恢复增量_2026-10-22.md text eol=lf
'''
    for name,text in generated.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text,encoding='utf8',newline='\n')
    return list(generated)


def check_links(destination,names):
    rows=[]
    for name in names:
        if not name.endswith('.md'):continue
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',(destination/name).read_text('utf8')):
            if link.startswith(('https:','http:','app:','codex:','#')):continue
            path=Path(os.path.abspath((destination/name).parent/unquote(link.split('#',1)[0].strip('<>'))))
            relative=path.relative_to(destination)
            assert any((base/relative).exists() for base in [destination,ROOT,MAIN]),(name,link)
            rows.append(dict(document=name,target=relative.as_posix()))
    return rows


def preflight(where,rows):
    preview=where/'preview';preview.mkdir(parents=True,exist_ok=False)
    names=documents(preview);references=check_links(preview,names)
    stage=where/'native-staging';stage.mkdir()
    expected={**rows,**{name:sha(preview/name) for name in names}}
    for name in expected:
        source=preview/name if name in names else ROOT/name
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    git(stage,'init','--quiet','--initial-branch=main');git(stage,'config','core.longpaths','true')
    pathspec=where/'paths.nul';pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(expected))+b'\0')
    git(stage,'add','--force','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul')
    helper=load(MAIN/'scripts/native_index_release_tools.py','r17_staging_helper');helper.MAIN=stage
    compared=helper.staged_rows(expected);git(stage,'diff','--cached','--check')
    return preview,names,dict(status='passed-private-native-staging-and-publication-link-check',
        source_rows=rows,files=expected,staged_blobs=len(compared),virtual_publication_links=len(references),
        generator_sha256=sha(Path(__file__)),main_mutated=False,product_tests_executed=0,
        prepared_at_utc=datetime.now(timezone.utc).isoformat())


def prepare():
    WORK.mkdir(parents=True,exist_ok=True)
    rows=source_rows();manifest=ROOT/REL/'release-manifest-r1.json';assert not manifest.exists()
    save(manifest,dict(status='frozen-research-awaiting-V108-publication',files=rows,generator_sha256=sha(Path(__file__)),
        full_product_tests_executed=False,product_code_changed=False,new_media=0,force_push=False))
    rows[manifest.relative_to(ROOT).as_posix()]=sha(manifest)
    preview,names,receipt=preflight(WORK/'prepare-r1',rows)
    receipt['preview_root']=str(preview)
    save(ROOT/REL/'staging-preflight-r1.json',receipt)
    print(json.dumps({k:receipt[k] for k in ['status','staged_blobs','virtual_publication_links','preview_root']},ensure_ascii=False),flush=True)


def wait_and_publish():
    work=WORK/'publication-owner-r1';work.mkdir(parents=True,exist_ok=False)
    state=dict(status='waiting-for-actual-published-V108',pid=os.getpid(),main_mutated=False,published=False,
        force_push=False,started_at_utc=datetime.now(timezone.utc).isoformat(),generator_sha256=sha(Path(__file__)))
    def checkpoint():
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',state)
    checkpoint()
    try:
        manifest=read(ROOT/REL/'release-manifest-r1.json');review=read(ROOT/REL/'staging-preflight-r1.json')
        assert manifest['generator_sha256']==review['generator_sha256']==sha(Path(__file__))
        assert source_rows()==manifest['files']
        while True:
            owner_path=PWORK/'release-chain-r1/run.json'
            if owner_path.exists():
                owner=read(owner_path)
                assert not owner['status'].startswith(('failed','aborted')),owner.get('error',owner['status'])
                if owner['status']=='published-V108-full2774-installed679':break
            time.sleep(5)
        publication=read(PWORK/'publication-r1/run.json');full=read(PARENT/'docs/validation/evidence/float-spatial-20261022-lab/full-r1.json')
        assert publication['status']=='published' and publication['main_clean'] and not publication['force_push']
        parent=owner['commit'];assert parent==owner['remote_main']==publication['commit']==publication['remote_main']
        assert full['terminal_ok'] and full['methods']==2774 and full['skipped']==0 and full['frozen_before']==full['frozen_after']
        product=load(MAIN/'scripts/run_frozen_regression.py','r17_publication_product');inputs=product.frozen()
        assert len(inputs)==326 and inputs==full['frozen_after']
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==parent
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==parent
        assert not git(MAIN,'status','--porcelain','-z') and not git(MAIN,'diff','--cached','--name-only')
        rows=source_rows();assert rows==manifest['files']
        for name in ['release-manifest-r1.json','staging-preflight-r1.json']:
            path=ROOT/REL/name;rows[path.relative_to(ROOT).as_posix()]=sha(path)
        preview,names,fresh=preflight(work/'publication-preflight',rows)
        save(work/'fresh-preflight.json',fresh)
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==parent and product.frozen()==inputs
        state.update(status='publishing-reviewed-R17-research',parent_commit=parent,publication_product_inputs=len(inputs));checkpoint()
        for name,digest in rows.items():
            target=MAIN/name;assert not target.exists(),('Unexpected research destination',name)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target);assert sha(target)==digest
        for name in names:
            target=MAIN/name
            if target.exists():
                backup=work/'original-main'/name;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,backup)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(preview/name,target)
        state['main_mutated']=True;checkpoint()
        expected={**rows,**{name:sha(MAIN/name) for name in names}}
        pathspec=work/'paths.nul';pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(expected))+b'\0')
        git(MAIN,'add','--force','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul')
        helper=load(MAIN/'scripts/native_index_release_tools.py','r17_publication_helper');helper.MAIN=MAIN
        compared=helper.staged_rows({**expected,**inputs});git(MAIN,'diff','--cached','--check')
        assert product.frozen()==inputs and not git(MAIN,'diff','--name-only')
        save(MAIN/REL/'publication-r1.json',dict(status='passed-staged-research-publication-audit',parent_commit=parent,
            research_product_inputs=311,publication_product_inputs=inputs,product_unchanged=True,
            source_manifest_sha256=sha(ROOT/REL/'release-manifest-r1.json'),staged_blobs=compared,
            upstream_test_totals={'tests':6,'pass':5,'fail':1,'skipped':0},fake_worker_cases=20,native_CommonJS_cases=2,
            virtual_publication_links=fresh['virtual_publication_links'],new_product_test_executions=0,new_media=0,force_push=False))
        receipt=(REL/'publication-r1.json').as_posix();git(MAIN,'add','--force','--',receipt)
        helper.staged_rows({receipt:sha(MAIN/receipt)});git(MAIN,'diff','--cached','--check')
        git(MAIN,'commit','--quiet','-m','docs: assess OpenFilm modules and export recovery with native evidence')
        commit=git(MAIN,'rev-parse','HEAD').decode().strip()
        assert git(MAIN,'rev-parse','HEAD^').decode().strip()==parent
        state.update(status='committed-awaiting-ordinary-push',commit=commit);checkpoint()
        git(MAIN,'push','origin','main');remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and not git(MAIN,'status','--porcelain','-z') and product.frozen()==inputs
        state.update(status='published-R17-research-after-V108',published=True,remote_main=remote,main_clean=True);checkpoint()
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc));checkpoint();raise
    finally:
        print(json.dumps({k:state.get(k) for k in ['status','commit','remote_main','error']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--wait',action='store_true');args=parser.parse_args()
    assert args.prepare != args.wait
    prepare() if args.prepare else wait_and_publish()
