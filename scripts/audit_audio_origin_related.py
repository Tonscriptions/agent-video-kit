"""Bind the actual 226 distinct controls and preserve the earlier development documents."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/audio-source-origin-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def main():
    output=REL/'related-audit-r1.json';assert not output.exists()
    audit=read(REL/'development-audit-r1.json');row=read(REL/'related-r1.json');current=frozen()
    assert current==audit['frozen_inputs'] and len(current)==259
    assert row['status']=='passed-related-regressions' and row['methods']==row['distinct_methods']==226
    assert row['terminal_ok'] and row['exit_code']==0 and row['skipped']==0
    assert len(row['method_ids'])==len(set(row['method_ids']))==226
    assert row['frozen_before']==row['frozen_after']==current and row['frozen_equal']
    assert row['fixtures_unchanged'] and row['fixture_manifest_unchanged'] and row['scripts_unchanged']
    assert sha(REL/'related-r1.log')==row['log_sha256']
    assert sha(REL/'foundation-r1.json')==row['fixture_manifest_sha256']
    for name,digest in row['fixture_inputs'].items():assert sha(ROOT/name)==digest
    for name,digest in row['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
    snapshots=REL/'before-related-documents-r1';snapshots.mkdir();preserved={};documents={}
    message=f'''<!-- AUDIO-RELATED-R1 -->
当前相关回归 **226 个不同方法、{row['suite_seconds']:.3f} 秒、0 跳过**：父候选 104＋新 12＋既有音频 110。259 输入、8 夹具、6 验证脚本前后相同；这是相关子集，不是完整套件。
实际产品 CLI 新媒体正在另行执行，隔离安装、Skill、完整回归及生产发布仍待完成。下表保留较早专项阶段的实际记录，完整状态以本段及对应收据为准。
<!-- /AUDIO-RELATED-R1 -->'''
    for name,digest in audit['documents'].items():
        path=ROOT/name;assert sha(path)==digest;target=snapshots/path.name;target.write_bytes(path.read_bytes())
        preserved[name]={'snapshot':target.relative_to(ROOT).as_posix(),'sha256':digest}
        text=path.read_text('utf8');assert '<!-- AUDIO-RELATED-R1 -->' not in text
        at=text.index('\n');text=text[:at]+'\n\n'+message+'\n'+text[at:]
        text=text.replace('226 方法相关回归当前状态为 `running-related-regressions`，不能写成已通过。',
            '当时相关回归仍在运行；现已通过，见文首最新记录。')
        text=text.replace('| AO-08 | 正在进行 |','| AO-08 | 相关回归启动时记录（历史） |')
        text=text.replace('12 方法限定通过；更广相关回归中','12 方法限定通过；当前 226 相关回归通过')
        path.write_text(text,encoding='utf8',newline='\n');documents[name]=sha(path)
    assert frozen()==current
    record={'status':'passed-related-audit-awaiting-media-install-skills-and-complete-suite',
        'at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,'targeted_methods':226,'distinct_methods':226,
        'suite_seconds':row['suite_seconds'],'skipped':0,'related_sha256':sha(REL/'related-r1.json'),
        'documents':documents,'historical_document_snapshots':preserved,'development_audit_sha256':sha(REL/'development-audit-r1.json'),
        'main_integrated':False,'full_suite_started':False,'skills_registered':False,'isolated_install_completed':False,
        'generator_sha256':sha(__file__)}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'distinct_methods':226,'frozen_inputs':259}))


if __name__=='__main__':main()
