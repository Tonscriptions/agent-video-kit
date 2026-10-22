"""Prepare reviewed immutable owners gated by actual published crop2418."""
import ast
import json
from pathlib import Path
import re

from run_frozen_regression import sha

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-crop-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-lut-20261022-lab'


def main():
    mapping = {'2418':'2455','2390':'2418','306':'309','304':'306','323':'360','295':'323',
        '183':'185','182':'183','123':'160','V100':'V101','V99':'V100','r100':'r101'}
    pattern = re.compile('|'.join(map(re.escape,mapping)))
    rows = {}
    for stem in ('run_float_crop_complete','publish_float_crop','release_float_crop_after_complete','finish_float_crop_chain'):
        parent = PARENT/'scripts'/(stem+'.py')
        source = pattern.sub(lambda match:mapping[match[0]],parent.read_text('utf8'))
        source = source.replace('float_crop','float_lut').replace('float-crop-20261022','float-lut-20261022')
        source = source.replace('float-mask-lab-20261022','float-crop-lab-20261022').replace('float-mask-20261022','float-crop-20261022')
        source = source.replace('mask_parent_source','crop_parent_source').replace('mask_published_parent','crop_published_parent')
        source = source.replace('native-r2/verification.json','native-r3/verification.json').replace('floating-crops','floating-LUTs')
        source = source.replace('len(changed)==5','len(changed)==6').replace('new_methods=28','new_methods=37')
        source = source.replace('Float32 author crop and single-pass crop-fit-TRS projection','Float32 local five-interpolation LUT and ordered author-clock grading')
        source = source.replace('actual exposure full suite','actual LUT full suite')
        source = source.replace('full_suite_passed=True,','full_suite_started=True,full_suite_passed=True,')
        destination = ROOT/'scripts'/(stem.replace('float_crop','float_lut')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name] = {'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    target = REL/'release-drivers-r1.json';assert not target.exists()
    target.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,
        'required_actual_parent_full':2418,'expected_full':2455,'required_installed':360,
        'force_push':False,'main_mutated':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'prepared':list(rows),'full_suite_launched':False,'main_mutated':False}))


if __name__=='__main__':main()
