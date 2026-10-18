"""Cross-check V43 documentation, historical failed research and actual evidence."""
from __future__ import annotations
import argparse, ast, hashlib, json, re, sys, urllib.parse, zipfile
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_fragments import frozen,save,sha


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def run(output):
    assert not output.exists();output.parent.mkdir(parents=True,exist_ok=True)
    save(output,{'status':'checking'})
    documents=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))]
    local=external=anchors=0;broken=[]
    for path in documents:
        text=path.read_text(encoding='utf-8-sig');assert text.strip(),path
        text=re.sub(r'^\s*```.*?^\s*```[^\n]*','',text,flags=re.M|re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) and not re.match(r'^[A-Za-z]:[/\\]',target):
                external+=1;continue
            target=target.split('#',1)[0]
            if not target:anchors+=1;continue
            local+=1
            if not (path.parent/urllib.parse.unquote(target)).resolve().exists():broken.append({'document':str(path),'target':raw})
    assert not broken,broken
    readme=(ROOT/'README.md').read_text('utf-8-sig')
    assert [int(n) for n in re.findall(r'^\| V(\d{2}) \|',readme,re.M)]==list(range(1,44))
    assert readme.index('V43（产品）')<readme.index('V42（研究）')
    core=[ROOT/n for n in ('README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')]
    for path in core:
        text=path.read_text('utf-8-sig')
        for term in ('V43（产品）','1005/1005','141 文件','261','768,000','自然背景仍涂抹','完整剪映'):
            assert term in text,(path,term)
    progress=(ROOT/'docs/构建进度总表_2026-10-16.md').read_text('utf-8-sig')
    assert '| Skill 审计 | 14 Skills、140 引用' in progress
    assert '[当前审计](validation/evidence/docs-audit-mask-edits-20261018.json)' in progress
    report=ROOT/'docs/validation/本地蒙版笔刷与关键帧修正实测_2026-10-18.md'
    contract=ROOT/'docs/specs/本地蒙版笔刷与关键帧修正契约_v0.1_2026-10-18.md'
    text=report.read_text('utf-8-sig');assert all(f'| M{i:02} |' in text for i in range(1,13))
    assert '进行中' not in text and '正在运行' not in text
    assert '正式实现' in contract.read_text('utf-8-sig') and '--edits-from-asset' in contract.read_text('utf-8-sig')
    ev=ROOT/'docs/validation/evidence';primary=load(ev/'mask-edits-20261018/verification.json')
    assert primary['full']['methods']==1005 and primary['specific']['methods']==30 and primary['specific_is_subset_of_full']
    assert primary['full']['terminal_ok'] and primary['full']['frozen_equal'] and primary['full']['skipped']==0
    assert primary['frozen_product']==frozen() and len(primary['frozen_product'])==141
    for name,expected in primary['frozen_product'].items():
        assert sha(ROOT/name)==expected
        if name.endswith('.py'):ast.parse((ROOT/name).read_text('utf-8-sig'),filename=name)
    for name,expected in primary['generator_sources'].items():assert sha(ROOT/name)==expected,name
    for name,item in primary['support_files'].items():
        path=ev/'mask-edits-20261018'/name;assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],name
        if path.suffix in {'.zip','.whl'}:
            with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
    with zipfile.ZipFile(ev/'mask-edits-20261018/final-source.zip') as archive:
        assert set(archive.namelist())==set(primary['frozen_product'])
        for name,expected in primary['frozen_product'].items():assert 'sha256:'+hashlib.sha256(archive.read(name)).hexdigest()==expected
    gallery=ROOT/primary['public_media']['directory'];media=load(gallery/'verification.json')
    assert sha(gallery/'verification.json')==primary['public_media']['verification_sha256']
    assert len(media['files'])+1==27 and not media['natural_media_published']
    for name,item in media['files'].items():assert sha(gallery/name)==item['sha256'],name
    skills_path=ev/'mask-edit-skills-20261018.json';skills=load(skills_path)
    assert skills['skill_count']==14 and skills['local_links_checked']==140
    for item in skills['results']:
        assert item['installed_directory_resolves_to_repo'] and item['validator_exit_code']==0
        assert sha(ROOT/'skills'/item['skill']/'SKILL.md')==item['sha256']
    manifest=load(ROOT/'video-cut-install-manifest.json')
    assert manifest['current_audit']['record_sha256']==sha(skills_path)
    for item in manifest['skills']:
        assert sha(ROOT/'skills'/item['name']/'SKILL.md')=='sha256:'+item['skill_md_sha256']
    old=load(ev/'coherent-reference-20261018/verification.json')
    assert old['status']=='research_completed_quality_gate_failed' and not old['candidate_promoted'] and old['failed_scored_regions']==4
    assert primary['goal_still_active'] and not primary['broad_natural_quality_accepted'] and not primary['complete_capcut_parity_accepted']
    result={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(Path(__file__)),
        'documents_checked':len(documents),'local_file_references_checked':local,'broken_local_references':broken,
        'external_references_not_fetched':external,'anchor_only_references_not_validated':anchors,'readme_numbered_rows':43,
        'full_product_methods':1005,'new_specific_methods_subset':30,'product_frozen_file_count':141,
        'public_media_files_checked':27,'natural_pixels_published':False,'natural_quality_accepted':False,
        'historical_v42_failed_gate_preserved':True,'skills_count':14,'skills_local_links':140,
        'install_manifest_current_hashes_checked':14,'install_manifest_sha256':sha(ROOT/'video-cut-install-manifest.json'),
        'primary_evidence_sha256':sha(ev/'mask-edits-20261018/verification.json'),
        'document_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [*core,report,contract,ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md']},
        'complete_capcut_parity_accepted':False,'goal_still_active':True}
    save(output,result);print(json.dumps({k:result[k] for k in ('status','documents_checked','local_file_references_checked','readme_numbered_rows')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();run(args.output.resolve())
