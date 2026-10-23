"""Prepare frozen tone install/full/release owners from accepted HSL drivers."""
import ast
import json
from pathlib import Path
import re
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-hsl-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-tone-20261022-lab'


def transform(source):
    numbers={'2623':'2667','2579':'2623','528':'572','484':'528',
        '318':'320','316':'318','190':'191','328':'372'}
    labels={'full2623':'full2667','full2579':'full2623','installed528':'installed572',
        'installed484':'installed528','parent316':'parent318','V105':'V106','V104':'V105','r105':'r106'}
    pattern=re.compile('|'.join(map(re.escape,labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    source=pattern.sub(lambda m:labels.get(m[0],numbers.get(m[0])),source)
    paths={'float-hsl':'float-tone','float-balance':'float-hsl','float_hsl':'float_tone'}
    source=re.sub('|'.join(map(re.escape,paths)),lambda m:paths[m[0]],source)
    source=source.replace('balance_parent_source','hsl_parent_source').replace('balance_published_parent','hsl_published_parent')
    source=source.replace('media-r2','media-r1')
    source=source.replace('passed-public-CLI-floating-selective-HSL-and-native-float-previews',
        'passed-public-CLI-floating-basic-tone-and-native-float-previews')
    source=source.replace('continuous Float32 eight-band HSL and explicit input gamut policies',
        'continuous Float32 basic YCbCr tone and explicit scalar arithmetic')
    source=source.replace('Run the actual eight-band HSL full suite after the frozen balance parent is published.',
        'Run the actual basic-tone full suite after the frozen HSL parent is published.')
    source=source.replace('new_methods=42','new_methods=44')
    return source


def main():
    rows={}
    for stem in ('verify_float_hsl_install','run_float_hsl_complete','publish_float_hsl',
                 'release_float_hsl_after_complete','finish_float_hsl_chain'):
        parent=PARENT/'scripts'/(stem+'.py');source=transform(parent.read_text('utf8'))
        if stem=='verify_float_hsl_install':
            source=source.replace("'test_float_selective_hsl']","'test_float_selective_hsl','test_float_tone']")
            source=source.replace('native_float_selective_hsl_integrated=True,',
                'native_float_selective_hsl_integrated=True, native_float_basic_tone_integrated=True,')
        if stem=='run_float_hsl_complete':
            source=source.replace("'maintenance.auto=false',*args]","'maintenance.auto=false','-c','core.fsmonitor=false',*args]")
        destination=ROOT/'scripts'/(stem.replace('float_hsl','float_tone')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name]={'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    path=REL/'release-drivers-r1.json';assert not path.exists()
    path.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,'target_full_methods':2667,
        'source_methods_gate':372,'installed_methods_target':572,'shipping_resource_target':191,
        'required_parent':'actual published V105/full2623/installed528','force_push':False,'full_capcut_parity':False},
        ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('prepared five immutable owners; actual source372/install572/full2667 are execution gates')


if __name__=='__main__':main()
