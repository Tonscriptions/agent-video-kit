"""Prepare a source-only preflight and a later gate bound to an actual V87 release."""
import ast
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
DONOR = ROOT.parent / 'multicam-stream-coverage-lab-20261021'
REL = ROOT / 'docs/validation/evidence/audio-source-origin-20261021-lab'
TARGET = ROOT / 'scripts/run_audio_origin_after_parent.py'


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


DOCS_STATUS = r'''def docs_status(message):
    base=ROOT/REL;snapshot=base/'before-full-documents-r1.json'
    if not snapshot.exists():
        audit=read(base/'audit-r1.json');directory=base/'before-full-documents-r1';directory.mkdir();rows={}
        for name,digest in audit['documents'].items():
            source=ROOT/name;assert sha(source)==digest;target=directory/source.name
            target.write_bytes(source.read_bytes());rows[name]={'sha256':digest,'snapshot':target.relative_to(ROOT).as_posix()}
        save(snapshot,{'status':'preserved','documents':rows,'audit_sha256':sha(base/'audit-r1.json')})
    marker='AUDIO-SOURCE-ORIGIN-FULL-R1'
    for name in ('README.md',REPORT,CONTRACT):
        path=ROOT/name;value=path.read_text('utf8')
        value=value.replace('完整 **2031** 方法是预计数量，尚未启动，须绑定实际发布的 V87（2019 方法）后再运行；',
            '完整回归状态见文首，已绑定实际发布的 V87（2019 方法）；')
        block='<!-- '+marker+' -->\n'+message+'\n较早阶段的 AO 表和媒体/草稿记录保留当时结果，当前完整回归以本段为准。\n<!-- /'+marker+' -->'
        pattern=re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
        if re.search(pattern,value,re.S):value=re.sub(pattern,lambda _:block,value,flags=re.S)
        else:
            at=value.index('\n');value=value[:at]+'\n\n'+block+'\n'+value[at:]
        path.write_text(value.rstrip()+'\n',encoding='utf8',newline='\n')
'''


def main():
    output=REL/'full-gate-preparation-r1.json'
    assert not output.exists() and not TARGET.exists()
    current=frozen();audit=json.loads((REL/'audit-r1.json').read_bytes())
    assert audit['status']=='passed-standalone-audit' and current==audit['frozen_inputs'] and len(current)==259
    donor_path=DONOR/'scripts/run_multicam_stream_after_parent.py'
    source=donor_path.read_text('utf8');tree=ast.parse(source)
    funcs={node.name:ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef)}
    gate=funcs['source_gate']
    substitutions={
        "audit['targeted_methods']==104":"audit['targeted_methods']==226",
        'len(current)==258':'len(current)==259',
        "len(audit['media'])==38":"len(audit['media'])==42",
        "related['methods']==related['distinct_methods']==104":"related['methods']==related['distinct_methods']==226",
        "len(related['method_ids'])==len(set(related['method_ids']))==104":"len(related['method_ids'])==len(set(related['method_ids']))==226",
        "installation['isolated_cli_calls']==36":"installation['isolated_cli_calls']==26",
        "len(installation['checks'])==14":"len(installation['checks'])==15",
        "item['cli_calls']==33 and item['native_commands']==25":"item['cli_calls']==23 and item['native_commands']==32",
        "len(item['checks'])==54":"len(item['checks'])==39",
        'len(previous)==257':'len(previous)==258',
    }
    for before,after in substitutions.items():
        assert gate.count(before)==1,before
        gate=gate.replace(before,after)
    gate=gate.replace('related-r2','related-r1')
    gate=gate.replace("    related=read(base/'related-r1.json')", "    assert sha(base/'media-audit-r1.json')==audit['media_audit_sha256']\n    related=read(base/'related-r1.json')")
    main_tree=ast.parse(funcs['main'])
    class UpdateParent(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is int and node.value in {1995,2019}:
                return ast.copy_location(ast.Constant(value={1995:2019,2019:2031}[node.value]),node)
            if isinstance(node.value,str):
                changed=node.value.replace('published-multicam-alignment-r1','published-stream-alignment-r1')
                changed=changed.replace('multicam_published_freeze','stream_published_freeze')
                changed=changed.replace('passed-source-preflight-awaiting-published-multicam','passed-source-preflight-awaiting-published-stream')
                changed=changed.replace('已绑定多机位源覆盖发布提交','已绑定原生视频覆盖发布提交').replace('2019 方法','2031 方法')
                changed=changed.replace('258 产品输入','259 产品输入')
                return ast.copy_location(ast.Constant(value=changed),node)
            return node
        def visit_keyword(self,node):
            node=self.generic_visit(node)
            if node.arg=='published_multicam_commit':node.arg='published_stream_commit'
            return node
    adapted=ast.unparse(ast.fix_missing_locations(UpdateParent().visit(main_tree)))
    imports='\n'.join(ast.get_source_segment(source,node) for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom)))
    constants='''ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
UPSTREAM = MAIN / 'product/.runtime/multicam-stream-coverage-lab-20261021'
REL = 'docs/validation/evidence/audio-source-origin-20261021-lab'
UPSTREAM_REL = 'docs/validation/evidence/multicam-stream-coverage-20261021-lab'
REPORT = 'docs/validation/原生音频起点与同步独立实验_2026-10-21.md'
CONTRACT = 'docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md'
MODIFIED = {'product/src/ai_ad_editor/' + name + '.py' for name in ('multicam','render','audio_stretch','capabilities')}
ADDED = {'product/tests/test_audio_source_origin.py'}
SCRIPTS = ('run_audio_origin_after_parent.py','run_frozen_regression.py','run_with_regression_fixtures.py',
    'materialize_regression_fixtures.py','run_audio_origin_related.py','run_audio_origin_regressions.py',
    'probe_audio_source_origin.py','smoke_audio_source_origin.py','verify_audio_source_origin_install.py',
    'prepare_audio_origin_lab.py','prepare_audio_origin_skills.py','prepare_audio_origin_smoke.py',
    'prepare_audio_origin_install.py','finalize_audio_origin_media.py','finalize_audio_origin_lab.py',
    'audit_audio_origin_related.py','document_audio_origin_development.py','prepare_audio_origin_full_gate.py')
'''
    text='"""Run one frozen audio-source-origin complete suite after an actually published V87 parent."""\n'
    text+='\n\n'.join([imports,constants,*[funcs[name] for name in ('read','sha','save','git')],gate,DOCS_STATUS,adapted])
    text+='\n\nif __name__=="__main__":main()\n'
    parsed=ast.parse(text);compile(parsed,str(TARGET),'exec')
    same={}
    for name in ('read','sha','save','git'):
        original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        rewritten=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name==name)
        same[name]=ast.dump(original,include_attributes=False)==ast.dump(rewritten,include_attributes=False)
    assert all(same.values())
    assert "item['methods'] == 2031" in text and "full_previous['methods'] == 2019" in text
    fixture_source=DONOR/'docs/validation/evidence/multicam-stream-coverage-20261021-lab/external-fixtures-r1.json'
    foundation=json.loads((REL/'foundation-r1.json').read_bytes())
    assert sha(fixture_source)==foundation['external_fixture_manifest_sha256']
    fixture=json.loads(fixture_source.read_bytes());assert fixture['status']=='passed' and fixture['fixture_count']==8
    for row in fixture['fixtures']:
        path=ROOT/row['path'];assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
    fixture_target=REL/'external-fixtures-r1.json';assert not fixture_target.exists()
    TARGET.write_text(text,encoding='utf8',newline='\n')
    fixture_target.write_bytes(fixture_source.read_bytes())
    assert frozen()==current
    record={'status':'prepared-not-launched','expected_future_methods':2031,'required_actual_parent_methods':2019,
        'frozen_inputs':current,'pinned_script_count':18,'donor_script':str(donor_path),'donor_sha256':sha(donor_path),
        'shared_helpers_AST_unchanged':same,'launcher':TARGET.relative_to(ROOT).as_posix(),'launcher_sha256':sha(TARGET),
        'external_fixture_count':8,'fixture_manifest_sha256':sha(fixture_target),'network':False,'virtualization':False,
        'full_suite_started':False,'main_integrated':False,'generator_sha256':sha(__file__)}
    write(output,record)
    print(json.dumps({k:record[k] for k in ('status','expected_future_methods','required_actual_parent_methods','pinned_script_count','full_suite_started')}))


if __name__=='__main__':main()
