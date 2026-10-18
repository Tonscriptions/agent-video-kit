"""Current V44 research/docs integrity; no product or model regression rerun."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import urllib.parse
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_fragments import frozen,save,sha


def load(path):return json.loads(path.read_text('utf-8-sig'))


def run(output):
    assert not output.exists()
    save(output,{'status':'checking'})
    documents=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))]
    local=external=anchors=0;broken=[]
    for path in documents:
        text=path.read_text('utf-8-sig'); assert text.strip(),path
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
    assert [int(n) for n in re.findall(r'^\| V(\d{2}) \|',readme,re.M)]==list(range(1,45))
    assert readme.index('V44（研究）')<readme.index('V43（产品）')
    core=[ROOT/name for name in ('README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')]
    for path in core:
        text=path.read_text('utf-8-sig')
        for term in ('V44（研究）','26.143899→33.137925','5.213643→0.908588','141 文件','1005/1005','未验收','未重跑'):
            assert term in text,(path,term)
    evidence=ROOT/'docs/validation/evidence/fgt-temporal-20261018'
    primary=load(evidence/'verification.json')
    assert primary['production_sha256']==frozen() and len(frozen())==141
    previous=load(ROOT/'docs/validation/evidence/mask-edits-20261018/verification.json')
    assert previous['frozen_product']==frozen() and previous['full']['methods']==1005
    assert primary['controlled']['controlled_quality_passed'] and not primary['natural']['natural_quality_accepted']
    assert not primary['product_integrated'] and not primary['full_product_regression_rerun']
    assert primary['model_calls_this_batch']=={'RAFT':124,'LAFC':124,'FGT':14,'LaMa':32,'ROSE':0}
    for item in primary['public_files']:
        path=ROOT/item['path']; assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes']
    assert len(primary['public_files'])==12
    assert primary['collector_sha256']==sha(ROOT/'scripts/publish_fgt_research.py')
    assert not primary['continuous_playback_reviewed'] and not primary['audio_listening_reviewed']
    scripts=[ROOT/'scripts/run_fgt_research.py',ROOT/'scripts/publish_fgt_research.py',ROOT/'research/temporal-neural/fgt_worker.py',Path(__file__)]
    for path in scripts:ast.parse(path.read_text('utf-8-sig'),filename=str(path))
    for case in ('public','natural'):
        record=load(evidence/(case+'-verification.json'))
        assert record['runner_sha256']==sha(scripts[0]) and record['worker_sha256']==sha(scripts[2])
        assert record['contract_sha256']==sha(ROOT/'docs/specs/开源时序修复候选核验契约_v0.1_2026-10-18.md')
        assert record['raw_upstream_outside_selection_changed_pixels']==record['final_outside_selection_changed_pixels']==0
        assert record['every_pts_exact'] and record['original_alpha_exact'] and record['rgba_roundtrip_exact']
    assert primary['natural']['audio']['identical'] and primary['natural']['audio']['decoded_pcm_bytes']==768000
    independent=load(evidence/'independent-remeasurement.json')
    for kind in ('fgt','lama'):
        for actual,row in zip(independent[kind],primary['controlled'][kind+'_scores']):
            assert abs(actual['mse']-row['masked_mse'])<1e-12 and abs(actual['temporal']-row['known_motion_residual_mae_rgb'])<1e-12
    old=load(ROOT/'docs/validation/evidence/coherent-reference-20261018/verification.json')
    assert old['failed_scored_regions']==4 and not old['candidate_promoted']
    skills_path=ROOT/'docs/validation/evidence/fgt-temporal-skills-20261018.json';skills=load(skills_path)
    assert skills['skill_count']==14 and skills['local_links_checked']==144
    for item in skills['results']:
        assert item['validator_exit_code']==0 and item['installed_directory_resolves_to_repo']
        assert sha(ROOT/'skills'/item['skill']/'SKILL.md')==item['sha256']
    manifest=load(ROOT/'video-cut-install-manifest.json')
    assert manifest['current_audit']['record_sha256']==sha(skills_path)
    for item in manifest['skills']:assert sha(ROOT/'skills'/item['name']/'SKILL.md')=='sha256:'+item['skill_md_sha256']
    report=ROOT/'docs/validation/开源FGT时序修复候选实测_2026-10-18.md'
    text=report.read_text('utf-8-sig'); assert all('| F'+str(i).zfill(2)+' |' in text for i in range(1,11))
    assert '0 次 ROSE 推理' in text and '不新增自然来源场景' in text
    metadata=load(evidence/'openfilm-current/repository.json');commit=load(evidence/'openfilm-current/commit.json')
    assert metadata['stargazers_count']==836 and metadata['forks_count']==90 and metadata['license']['spdx_id']=='MIT'
    assert commit['sha']=='eefd6a8d379289102141359a4718dbab12170526'
    for path in evidence.rglob('*.zip'):
        with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
    result={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'documents_checked':len(documents),'local_file_references_checked':local,
        'broken_local_references':broken,'external_references_not_fetched':external,'anchor_only_references_not_validated':anchors,
        'readme_numbered_rows':44,'product_files_unchanged_from_v43':141,'product_regression_rerun':False,'last_full_product_methods':1005,
        'controlled_quality_passed':True,'natural_quality_accepted':False,'complete_capcut_parity_accepted':False,'goal_still_active':True,
        'public_media_files_checked':12,'public_media_total_bytes':sum(item['bytes'] for item in primary['public_files']),
        'private_natural_pixels_published':False,'skills_count':14,'skills_local_references':144,
        'install_manifest_sha256':sha(ROOT/'video-cut-install-manifest.json'),'primary_evidence_sha256':sha(evidence/'verification.json'),
        'research_sources_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in scripts},
        'document_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [*core,report,ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md',ROOT/'docs/specs/开源时序修复候选核验契约_v0.1_2026-10-18.md',ROOT/'docs/third-party/时序修复候选源码与许可说明_2026-10-18.md']},
        'support_evidence_sha256':{p.relative_to(evidence).as_posix():sha(p) for p in sorted(evidence.rglob('*')) if p.is_file()}}
    save(output,result)
    print(json.dumps({k:result[k] for k in ('status','documents_checked','local_file_references_checked','readme_numbered_rows','public_media_total_bytes')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve())
