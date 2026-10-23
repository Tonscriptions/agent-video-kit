"""Prepare immutable release owners gated by the actual V104 publication."""
import ast
import json
from pathlib import Path
import re
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-balance-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-hsl-20261022-lab'

def main():
    numbers={'2579':'2623','2537':'2579','316':'318','314':'316',
        '484':'528','442':'484','189':'190','188':'189','284':'328','242':'284'}
    labels={'full2579':'full2623','full2537':'full2579','installed484':'installed528',
        'installed442':'installed484','parent314':'parent316','V104':'V105','V103':'V104','r104':'r105'}
    pattern=re.compile('|'.join(map(re.escape,labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    rows={}
    for stem in ('run_float_balance_complete','publish_float_balance','release_float_balance_after_complete','finish_float_balance_chain'):
        parent=PARENT/'scripts'/(stem+'.py')
        source=pattern.sub(lambda m:labels.get(m[0],numbers.get(m[0])),parent.read_text('utf8'))
        source=source.replace('float_balance','float_hsl').replace('float-balance','float-hsl')
        source=source.replace('float-levels','float-balance').replace('levels_parent_source','balance_parent_source').replace('levels_published_parent','balance_published_parent')
        source=source.replace('passed-public-CLI-floating-levels-and-native-float-previews',
            'passed-public-CLI-floating-selective-HSL-and-native-float-previews')
        source=source.replace('continuous Float32 three-way balance and creative Kelvin author channels',
            'continuous Float32 eight-band HSL and explicit input gamut policies')
        source=source.replace('Run the actual balance full suite after the frozen levels parent is published.',
            'Run the actual eight-band HSL full suite after the frozen balance parent is published.')
        destination=ROOT/'scripts'/(stem.replace('float_balance','float_hsl')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name]={'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    path=REL/'release-drivers-r1.json';assert not path.exists()
    path.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,'target_full_methods':2623,
        'required_parent':'actual published V104/full2579/installed484','force_push':False,'full_capcut_parity':False},
        ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('prepared four HSL owners; full2623 and installed528 remain actual execution gates')

if __name__=='__main__':main()
