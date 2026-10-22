"""Adapt immutable parent release owners with explicit reviewed count mappings."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-mask-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-crop-20261022-lab'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    # Large method/resource/input counts are simultaneous, so parent counts
    # never get recursively replaced. The 95MiB artifact cap stays unchanged.
    replacements={'2390':'2418','2369':'2390','304':'306','302':'304','295':'323','274':'295','182':'183','181':'182',
        'V99':'V100','V98':'V99','r99':'r100'}
    pattern=re.compile('|'.join(map(re.escape,replacements)))
    record={}
    for stem in ('run_float_mask_complete','publish_float_mask','release_float_mask_after_complete','finish_float_mask_chain'):
        parent=PARENT/'scripts'/(stem+'.py')
        source=pattern.sub(lambda match:replacements[match[0]],parent.read_text('utf8'))
        source=source.replace('float_mask','float_crop').replace('float-mask-20261022','float-crop-20261022')
        source=source.replace('float-exposure-lab-20261022','float-mask-lab-20261022').replace('float-exposure-20261022','float-mask-20261022')
        source=source.replace('foundation-runtime-r1.json','foundation-r1.json')
        source=source.replace('native-r3/verification.json','native-r2/verification.json')
        source=source.replace('media-r4/verification.json','media-r1/verification.json').replace('installed-r2','installed-r1')
        source=source.replace('floating-masks','floating-crops')
        source=source.replace("native['methods']==95","native['methods']==123").replace("'native_methods':95","'native_methods':123").replace('native_methods=95','native_methods=123')
        source=source.replace('new_methods=21','new_methods=28')
        source=source.replace('static Float32 masks, animated cubic paths and alpha feather','Float32 author crop and single-pass crop-fit-TRS projection')
        source=source.replace('Float32 masks, animated cubic paths and alpha feather','Float32 author crop and single-pass crop-fit-TRS projection')
        source=source.replace('actual-readme-preview-r3','actual-readme-preview-r2').replace("'--revision','r3'","'--revision','r2'")
        source=source.replace('exposure_parent_source','mask_parent_source').replace('exposure_published_parent','mask_published_parent')
        if stem=='publish_float_mask':
            assert 'path.stat().st_size < 95*1024**2' in source
        destination=ROOT/'scripts'/(stem.replace('float_mask','float_crop')+'.py')
        assert not destination.exists();ast.parse(source)
        destination.write_text(source,encoding='utf8',newline='\n')
        record[destination.name]={'source_sha256':sha(parent),'candidate_sha256':sha(destination)}
    path=REL/'release-drivers-r1.json';assert not path.exists()
    path.write_text(json.dumps({'status':'prepared-not-executed','scripts':record,
        'required_actual_parent_full':2390,'expected_full':2418,'required_installed':323,
        'force_push':False,'main_mutated':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'prepared':list(record),'full_suite_launched':False,'main_mutated':False}))


if __name__=='__main__':main()
