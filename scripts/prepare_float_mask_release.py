"""Adapt frozen parent release gates without changing any running predecessor."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-exposure-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-mask-20261022-lab'


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()


def write(p,value):
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    foundation=json.loads((REL/'foundation-r2.json').read_bytes())
    parent_foundation=PARENT/'docs/validation/evidence/float-exposure-20261022-lab/foundation-r1.json'
    original=json.loads(parent_foundation.read_bytes())
    deps={k:v for k,v in foundation['copied_inputs'].items() if k.startswith('sources/python-runtime/cp313-win_amd64-media/')}
    fixtures=original['external_fixtures']
    assert len(deps)==9 and len(fixtures)==8
    for row in fixtures:assert sha(ROOT/row['path'])==row['sha256']
    runtime={**foundation,'dependency_artifact_inputs':deps,'external_fixtures':fixtures,
        'parent_fixture_source_sha256':sha(parent_foundation)}
    assert not (REL/'foundation-runtime-r1.json').exists()
    write(REL/'foundation-runtime-r1.json',runtime)
    replacements={'2369':'2390','2355':'2369','302':'304','300':'302','274':'295','181':'182','74':'95',
        'V98':'V99','V97':'V98','r98':'r99'}
    pattern=re.compile('|'.join(map(re.escape,replacements)))
    receipt={}
    for stem in ('run_float_exposure_complete','publish_float_exposure','release_float_exposure_after_complete'):
        source=PARENT/'scripts'/f'{stem}.py'
        text=source.read_text('utf8')
        text=pattern.sub(lambda m:replacements[m[0]],text)
        text=text.replace('float_exposure','float_mask').replace('float-exposure-20261022','float-mask-20261022')
        text=text.replace("ROOT.parent/'float-preview-lab-20261022'","ROOT.parent/'float-exposure-lab-20261022'")
        text=text.replace("PARENT/'product/.runtime/float-delivery-20261022'","PARENT/'product/.runtime/float-exposure-20261022'")
        text=text.replace("PARENT/'docs/validation/evidence/float-delivery-20261022'","PARENT/'docs/validation/evidence/float-exposure-20261022-lab'")
        text=text.replace('foundation-r1.json','foundation-runtime-r1.json')
        text=text.replace('native-r2/verification.json','native-r3/verification.json')
        text=text.replace('media-r1/verification.json','media-r4/verification.json')
        text=text.replace('installed-r1','installed-r2')
        text=text.replace('passed-public-CLI-linear-exposure-and-native-float-previews','passed-public-CLI-floating-masks-and-native-float-previews')
        text=text.replace('published-V98-cumulative-full2369-installed260','published-V98-full2369-installed274')
        text=text.replace('linear Float32 exposure','Float32 masks, animated cubic paths and alpha feather')
        text=text.replace('static linear Float32 exposure','Float32 masks, animated cubic paths and alpha feather')
        text=text.replace('new_methods=14','new_methods=21')
        destination=ROOT/'scripts'/(stem.replace('float_exposure','float_mask')+'.py')
        assert not destination.exists();ast.parse(text)
        destination.write_text(text,encoding='utf8',newline='\n')
        receipt[destination.name]={'source_sha256':sha(source),'candidate_sha256':sha(destination)}
    assert not (REL/'release-drivers-r1.json').exists()
    write(REL/'release-drivers-r1.json',{'status':'prepared-not-executed','scripts':receipt,
        'expected_full':2390,'required_actual_parent_full':2369,'required_installed':295,
        'force_push':False,'main_mutated':False})
    print(json.dumps({'prepared':list(receipt),'full_suite_launched':False,'main_mutated':False}))


if __name__=='__main__':main()
