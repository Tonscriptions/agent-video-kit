"""Prepare immutable owners gated by the actual published LUT2455 parent."""
import ast
import json
from pathlib import Path
import re

from run_frozen_regression import sha

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-lut-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-curves-20261022-lab'


def main():
    mapping = {'2455':'2495','2418':'2455','309':'311','306':'309','360':'400','323':'360',
        '185':'186','183':'185','160':'200','123':'160','V101':'V102','V100':'V101','r101':'r102'}
    pattern = re.compile('|'.join(map(re.escape,mapping)))
    rows = {}
    for stem in ('run_float_lut_complete','publish_float_lut','release_float_lut_after_complete','finish_float_lut_chain'):
        parent = PARENT/'scripts'/(stem+'.py')
        source = pattern.sub(lambda match:mapping[match[0]],parent.read_text('utf8'))
        source = source.replace('float_lut','float_curves').replace('float-lut-20261022','float-curves-20261022')
        source = source.replace('float-crop-lab-20261022','float-lut-lab-20261022').replace('float-crop-20261022','float-lut-20261022')
        source = source.replace('crop_parent_source','lut_parent_source').replace('crop_published_parent','lut_published_parent')
        source = source.replace('floating-LUTs','floating-curves').replace('len(changed)==6','len(changed)==5').replace('new_methods=37','new_methods=40')
        source = source.replace('Float32 local five-interpolation LUT and ordered author-clock grading',
            'continuous Float32 RGB curves and direct author-clock control points')
        source = source.replace('media-r1/verification.json','media-r2/verification.json')
        destination = ROOT/'scripts'/(stem.replace('float_lut','float_curves')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name] = {'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    target = REL/'release-drivers-r1.json';assert not target.exists()
    target.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,
        'required_actual_parent_full':2455,'expected_full':2495,'required_installed':400,
        'force_push':False,'main_mutated':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'prepared':list(rows),'full_suite_launched':False,'main_mutated':False}))


if __name__=='__main__':main()
