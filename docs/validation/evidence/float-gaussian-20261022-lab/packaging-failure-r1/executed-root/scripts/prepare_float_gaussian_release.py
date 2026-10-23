"""Prepare isolated Gaussian install/full/publication owners from frozen tone."""
import ast
import json
from pathlib import Path
import re
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-tone-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-gaussian-20261022-lab'


def transform(source):
    numbers={'2667':'2715','2623':'2667','572':'620','528':'572',
        '320':'323','318':'320','191':'193','372':'420'}
    labels={'full2667':'full2715','full2623':'full2667','installed572':'installed620',
        'installed528':'installed572','parent318':'parent320','V106':'V107','V105':'V106','r106':'r107'}
    expression=re.compile('|'.join(map(re.escape,labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    source=expression.sub(lambda m:labels.get(m[0],numbers.get(m[0])),source)
    paths={'float-tone':'float-gaussian','float-hsl':'float-tone','float_tone':'float_gaussian'}
    source=re.sub('|'.join(map(re.escape,paths)),lambda m:paths[m[0]],source)
    source=source.replace('hsl_parent_source','tone_parent_source').replace('hsl_published_parent','tone_published_parent')
    source=source.replace('passed-public-CLI-floating-basic-tone-and-native-float-previews',
        'passed-public-CLI-floating-Gaussian-and-native-float-previews')
    source=source.replace('continuous Float32 basic YCbCr tone and explicit scalar arithmetic',
        'normalized continuous Float32 Gaussian blur with explicit coverage and axis semantics')
    source=source.replace('Run the actual basic-tone full suite after the frozen HSL parent is published.',
        'Run the actual Gaussian full suite after the frozen basic-tone parent is published.')
    source=source.replace('new_methods=44','new_methods=48')
    source=source.replace('len(changed)==5','len(changed)==9')
    return source


def main():
    rows={}
    for stem in ('verify_float_tone_install','run_float_tone_complete','publish_float_tone',
                 'release_float_tone_after_complete','finish_float_tone_chain'):
        parent=PARENT/'scripts'/(stem+'.py');source=transform(parent.read_text('utf8'))
        if stem=='verify_float_tone_install':
            source=source.replace("'test_float_gaussian']","'test_float_tone','test_float_gaussian']")
            source=source.replace('native_float_basic_tone_integrated=True,',
                'native_float_basic_tone_integrated=True, native_float_gaussian_integrated=True,')
        destination=ROOT/'scripts'/(stem.replace('float_tone','float_gaussian')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        rows[destination.name]={'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    path=REL/'release-drivers-r1.json';assert not path.exists()
    path.write_text(json.dumps({'status':'prepared-not-executed','scripts':rows,'target_full_methods':2715,
        'source_methods_gate':420,'installed_methods_target':620,'shipping_resource_target':193,
        'changed_product_paths':9,'required_parent':'actual published V106/full2667/installed572',
        'force_push':False,'full_capcut_parity':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('prepared five owners; actual source420/install620/full2715 are execution gates')


if __name__=='__main__':main()
