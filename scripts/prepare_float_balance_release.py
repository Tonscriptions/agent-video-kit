"""Prepare immutable release owners gated by actual V103 publication."""
import ast
import json
from pathlib import Path
import re

from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-levels-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-balance-20261022-lab'

def main():
    numbers={'2537':'2579','2495':'2537','314':'316','311':'314',
             '442':'484','400':'442','188':'189','186':'188','242':'284','200':'242'}
    labels={'full2537':'full2579','full2495':'full2537','installed442':'installed484','installed400':'installed442',
            'parent311':'parent314','V103':'V104','V102':'V103','r103':'r104'}
    pattern=re.compile('|'.join(map(re.escape,labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    rows={}
    for stem in ('run_float_levels_complete','publish_float_levels','release_float_levels_after_complete','finish_float_levels_chain'):
        parent=PARENT/'scripts'/(stem+'.py')
        source=pattern.sub(lambda m:labels.get(m[0],numbers.get(m[0])),parent.read_text('utf8'))
        source=source.replace('float_levels','float_balance').replace('float-levels','float-balance')
        source=source.replace('float-curves','float-levels').replace('curves_parent_source','levels_parent_source').replace('curves_published_parent','levels_published_parent')
        source=source.replace('len(changed)==6','len(changed)==5')
        source=source.replace("'media-r1/verification.json'","'media-r2/verification.json'")
        source=source.replace('Float32 RGBA levels and direct author-clock animated exposure',
                              'continuous Float32 three-way balance and creative Kelvin author channels')
        source=source.replace('Run one actual LUT full suite after the final309 parent is published.',
                              'Run the actual balance full suite after the frozen levels parent is published.')
        destination=ROOT/'scripts'/(stem.replace('float_levels','float_balance')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name]={'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    path=REL/'release-drivers-r1.json';assert not path.exists()
    path.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,'target_full_methods':2579,
        'required_parent':'actual published V103/full2537/installed442','force_push':False,'full_capcut_parity':False},
        ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('prepared four balance owners; full2579 and installed484 remain actual execution gates')

if __name__=='__main__':main()
