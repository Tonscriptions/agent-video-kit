"""Bind260 distinct controls, fresh eight-wheel media and four unregistered Skill deltas."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    output=REL/'audit-r1.json';assert not output.exists();current=frozen()
    media=read(REL/'media-audit-r1.json');assert media['status']=='passed-native-and-eight-wheel-isolated-media-awaiting-expanded-regression-and-skills'
    assert current==media['frozen_inputs'] and len(current)==260
    development=read(REL/'development-audit-r1.json');parent=development['source_parent_inputs'];assert len(parent)==259
    assert sha(REL/'development-audit-r1.json')==media['development_audit_sha256']
    related=read(REL/'related-r1.json')
    assert related['status']=='passed-related-regressions' and related['terminal_ok'] and related['exit_code']==0
    assert related['methods']==related['distinct_methods']==260 and related['skipped']==0
    assert len(related['method_ids'])==len(set(related['method_ids']))==260
    assert related['frozen_before']==related['frozen_after']==current and related['frozen_equal']
    assert related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert len(related['script_hashes'])==10 and len(related['fixture_inputs'])==8
    assert sha(REL/'related-r1.log')==related['log_sha256'] and sha(REL/'foundation-r1.json')==related['fixture_manifest_sha256']
    for name,digest in related['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
    for name,digest in related['fixture_inputs'].items():assert sha(ROOT/name)==digest
    for name,row in media['media'].items():assert sha(ROOT/name)==row['sha256']
    assert len(media['media'])==42 and media['GIF_count']==14
    installed=read(REL/'installed-r1/verification.json')
    assert installed['status']=='passed' and installed['frozen_before']==installed['frozen_after']==current
    assert len(installed['checks'])==20 and all(row['ok'] for row in installed['checks'])
    assert installed['bundle']['wheels']==8 and not installed['numpy_distribution']['host_site_copied']
    assert len(installed['numpy_distribution']['original_wheel_files_except_rewritten_RECORD'])==931
    drafts=read(REL/'skills-draft-r1.json')
    assert drafts['status']=='passed-four-unregistered-drafts' and drafts['skill_count']==4 and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT/row['path'])==row['sha256'] and row['validator_exit_code']==0 and not row['registered']
        assert sha(ROOT/row['parent_snapshot'])==row['parent_sha256']
    wheelhouse=read(REL/'wheelhouse-r1.json');directory=ROOT/wheelhouse['wheelhouse']
    assert sha(directory/'lock.json')==wheelhouse['lock_sha256']
    lock=read(directory/'lock.json');assert lock['runtime_profile']=='media-analysis-v1'
    for row in lock['artifacts']:assert sha(directory/row['filename'])==row['sha256']
    snapshot_dir=REL/'before-expanded-audit-documents-r1';snapshot_dir.mkdir();documents={};preserved={}
    for name,digest in media['documents'].items():
        path=ROOT/name;assert sha(path)==digest;copy=snapshot_dir/path.name;copy.write_bytes(path.read_bytes())
        preserved[name]={'snapshot':copy.relative_to(ROOT).as_posix(),'sha256':digest}
        prefix='docs/validation/evidence/offline-media-profile-20261021-lab' if name=='README.md' else ('evidence/offline-media-profile-20261021-lab' if name.startswith('docs/validation/') else '../validation/evidence/offline-media-profile-20261021-lab')
        block=f'''<!-- OFFLINE-MEDIA-STANDALONE-AUDIT-R1 -->
当前独立审计：260产品输入，**260个不同相关方法、{related['suite_seconds']:.3f}秒、0跳过**（父226＋22旧安装＋12新安装）。先前34、12是本次子集，不能重复累计。新原生23CLI/39检查、新隔离26CLI/20安装＋39媒体检查均通过；42资产/14GIF。
四份Skill增量已基于真实发布V87父版验证，**未注册**；将来只合入新块与记录的精确V88父版条款更新，不以旧V87全文覆盖后续指导。
完整2043仅为预计数量，尚未启动，须先绑定实际发布V88/2031；当前没有生产合入或推送。NumPy已在本候选八轮包真实交付，不应把此结果写成main当前已发布能力，也不代表全部剪映功能/效果。
[独立审计]({prefix}/audit-r1.json) · [260当前相关方法]({prefix}/related-r1.json) · [四份未注册增量]({prefix}/skills-draft-r1.json)。下面较早阶段“待完成”保留当时状态，当前以本段为准。
<!-- /OFFLINE-MEDIA-STANDALONE-AUDIT-R1 -->'''
        text=path.read_text('utf8');assert '<!-- OFFLINE-MEDIA-STANDALONE-AUDIT-R1 -->' not in text;at=text.index('\n')
        path.write_text(text[:at]+'\n\n'+block+'\n'+text[at:],encoding='utf8',newline='\n');documents[name]=sha(path)
    assert frozen()==current
    record={'status':'passed-standalone-audit','at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_inputs':current,'source_parent_inputs':parent,'modified_runtime_inputs':development['modified_inputs'],
        'added_inputs':development['added_inputs'],'targeted_methods':260,'distinct_methods':260,
        'related_seconds':related['suite_seconds'],'related_sha256':sha(REL/'related-r1.json'),
        'media_audit_sha256':sha(REL/'media-audit-r1.json'),'documents':documents,'historical_document_snapshots':preserved,
        'media':media['media'],'asset_count':42,'GIF_count':14,
        'media_manifest_sha256':sha(REL/'media-manifest-r1.json'),'static_review_sha256':sha(REL/'static-review-r1.json'),
        'native_verification_sha256':sha(REL/'native-r2/verification.json'),'isolated_verification_sha256':sha(REL/'installed-r1/verification.json'),
        'skill_draft_sha256':sha(REL/'skills-draft-r1.json'),'wheelhouse_sha256':sha(REL/'wheelhouse-r1.json'),
        'native_cli_calls':23,'native_other_commands':32,'native_checks':39,
        'isolated_cli_calls':26,'isolated_origin_processes':1,'isolated_origin_modules':14,
        'isolated_installer_checks':20,'isolated_media_checks':39,'runtime_resource_count':161,
        'base_installer_wheels':8,'base_installer_numpy_included':True,'host_numpy_copied':False,
        'original_numpy_files_byte_equal_except_RECORD':931,'unregistered_skill_deltas':4,
        'expected_future_full_methods':2043,'expected_future_parent_full_methods':2031,
        'full_suite_started':False,'main_integrated':False,'skills_registered':False,'parent_media_reused':False,
        'native_windows':True,'virtualization':False,'development_network_for_source_capture':True,
        'network_during_build_install_or_media':False,'continuous_playback_reviewed':False,'audio_reviewed':False,
        'full_capcut_parity':False,'generator_sha256':sha(__file__)}
    save(output,record);links=[]
    for name in documents:
        path=ROOT/name
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',path.read_text('utf8')):
            target=unquote(token.strip('<>').split('#',1)[0])
            if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            resolved=(path.parent/target).resolve();assert resolved.is_relative_to(ROOT) and resolved.exists(),(name,target)
            links.append({'document':name,'target':resolved.relative_to(ROOT).as_posix()})
    record['local_links']=links;save(output,record)
    (REL/'finalize-audit-r1.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'frozen_inputs':260,'related_methods':260,
        'assets':42,'GIFs':14,'unregistered_deltas':4,'document_links':len(links)}))


if __name__=='__main__':main()
