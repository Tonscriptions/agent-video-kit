"""Prepare immutable owners gated by the actual published curves2495 parent."""
import ast
import json
from pathlib import Path
import re

from run_frozen_regression import sha

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-curves-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-levels-20261022-lab'


def main():
    numbers = {'2495':'2537','2455':'2495','311':'314','309':'311',
        '400':'442','360':'400','186':'188','185':'186','200':'242','160':'200'}
    labels = {'full2495':'full2537','full2455':'full2495','installed400':'installed442','installed360':'installed400',
        'parent309':'parent311','V102':'V103','V101':'V102','r102':'r103'}
    pattern = re.compile('|'.join(map(re.escape,labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    rows = {}
    for stem in ('run_float_curves_complete','publish_float_curves','release_float_curves_after_complete','finish_float_curves_chain'):
        parent = PARENT/'scripts'/(stem+'.py')
        source = pattern.sub(lambda m:labels.get(m[0],numbers.get(m[0])),parent.read_text('utf8'))
        source = source.replace('float_curves','float_levels').replace('float-curves-20261022','float-levels-20261022')
        source = source.replace('float-curves-lab-20261022','float-levels-lab-20261022')
        source = source.replace('float-lut-lab-20261022','float-curves-lab-20261022').replace('float-lut-20261022','float-curves-20261022')
        source = source.replace('lut_parent_source','curves_parent_source').replace('lut_published_parent','curves_published_parent')
        source = source.replace('floating-curves','floating-levels').replace('len(changed)==5','len(changed)==6').replace('new_methods=40','new_methods=42')
        source = source.replace('continuous Float32 RGB curves and direct author-clock control points',
            'Float32 RGBA levels and direct author-clock animated exposure')
        source = source.replace('native-r3/verification.json','native-r2/verification.json').replace('media-r2/verification.json','media-r1/verification.json')
        destination = ROOT/'scripts'/(stem.replace('float_curves','float_levels')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name] = {'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    path = REL/'release-drivers-r1.json';assert not path.exists()
    path.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,
        'target_full_methods':2537,'required_parent':'actual published V102/full2495/installed400',
        'force_push':False,'full_capcut_parity':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('prepared four release owners; no complete regression or publication claimed')


if __name__=='__main__':main()
