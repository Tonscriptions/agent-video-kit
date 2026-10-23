"""Preserve fixed-tag primary format/math references; no runtime networking."""
import base64
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REFERENCES=[
    ('FFmpeg/FFmpeg','n8.1','libavfilter/vf_lut3d.c','FFmpeg-vf_lut3d.c.txt','LGPL-2.1-or-later'),
    ('AcademySoftwareFoundation/OpenColorIO','v2.4.2','src/OpenColorIO/fileformats/FileFormatResolveCube.cpp','OpenColorIO-ResolveCube.cpp.txt','BSD-3-Clause'),
    ('AcademySoftwareFoundation/OpenColorIO','v2.4.2','src/OpenColorIO/fileformats/FileFormatIridasCube.cpp','OpenColorIO-IridasCube.cpp.txt','BSD-3-Clause'),
    ('AcademySoftwareFoundation/OpenColorIO','v2.4.2','LICENSE','OpenColorIO-LICENSE.txt','BSD-3-Clause'),
    ('FFmpeg/FFmpeg','n8.1','COPYING.LGPLv2.1','FFmpeg-COPYING.LGPLv2.1.txt','LGPL-2.1-or-later'),
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--revision',required=True);args=parser.parse_args()
    assert args.revision.startswith('r') and args.revision[1:].isdigit()
    DEST=ROOT/'docs/validation/evidence/float-shaper-20261023-lab'/('source-reference-'+args.revision)
    DEST.mkdir(exist_ok=False)
    (DEST/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
    receipt={'status':'running','at_utc':datetime.now(timezone.utc).isoformat(),'files':[],
        'reference_only':True,'upstream_runtime_code_copied':False,'runtime_network':False,
        'script_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    def save(): (DEST/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    for repo,tag,path,name,license_name in REFERENCES:
        url=f'https://api.github.com/repos/{repo}/contents/{path}?ref={tag}'
        request=urllib.request.Request(url,headers={'User-Agent':'agent-video-kit-local-source-review','Accept':'application/vnd.github+json'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                raw=response.read(); payload=json.loads(raw)
            assert payload['encoding']=='base64'
            data=base64.b64decode(payload['content'])
            (DEST/name).write_bytes(data)
            receipt['files'].append(dict(repository=repo,tag=tag,path=path,api_url=url,
                primary_url=f'https://github.com/{repo}/blob/{tag}/{path}',blob_sha1=payload['sha'],
                file=name,sha256='sha256:'+hashlib.sha256(data).hexdigest(),bytes=len(data),license=license_name))
            save()
        except BaseException as exc:
            receipt.update(status='failed-preserved',error=repr(exc));save();raise
    receipt['status']='captured-fixed-tag-primary-references';save()
    print(json.dumps({'status':receipt['status'],'files':len(receipt['files'])}))

if __name__=='__main__': main()
