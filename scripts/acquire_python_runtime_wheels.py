"""Explicit development acquisition; never imported by runtime or installer."""
from __future__ import annotations
import argparse,hashlib,io,json,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from smoke_fragments import save,sha

ROOT=Path(__file__).resolve().parents[1]
PINS={'jsonschema':'4.26.0','attrs':'25.4.0','jsonschema-specifications':'2025.9.1','referencing':'0.37.0','rpds-py':'2026.6.3','rfc3339-validator':'0.1.4'}


def run(output,evidence):
    output.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    def get(item):
        name,version=item;url=f'https://pypi.org/pypi/{name}/{version}/json'
        with urllib.request.urlopen(url,timeout=40) as response:raw=response.read(4*1024**2)
        data=json.loads(raw);savepath=evidence/(name+'.pypi.json');savepath.write_bytes(raw)
        wheels=[x for x in data['urls'] if x['packagetype']=='bdist_wheel' and ('none-any.whl' in x['filename'] or x['filename'].endswith('cp313-cp313-win_amd64.whl'))]
        assert len(wheels)==1,(name,[x['filename'] for x in wheels]);chosen=wheels[0]
        assert 0<chosen['size']<=64*1024**2 and chosen['url'].startswith('https://files.pythonhosted.org/')
        with urllib.request.urlopen(chosen['url'],timeout=90) as response:body=response.read(64*1024**2+1)
        assert len(body)==chosen['size'] and hashlib.sha256(body).hexdigest()==chosen['digests']['sha256']
        path=output/chosen['filename'];path.write_bytes(body)
        licenses={}
        with zipfile.ZipFile(io.BytesIO(body)) as wheel:
            for key in wheel.namelist():
                if any(part in key.casefold() for part in ('/licenses/','/license','/copying')):
                    target=evidence/'licenses'/name/Path(key).name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(wheel.read(key));licenses[key]=sha(target)
            if name=='rfc3339-validator':
                (evidence/'rfc3339_validator.upstream.py').write_bytes(wheel.read('rfc3339_validator.py'))
        assert licenses,(name,'license absent')
        return {'name':name,'version':version,'filename':path.name,'bytes':len(body),'sha256':sha(path),'pypi_url':url,
            'download_url':chosen['url'],'metadata_sha256':sha(savepath),'license_files':licenses,'runtime_dependency':name!='rfc3339-validator'}
    with ThreadPoolExecutor(max_workers=4) as pool:records=list(pool.map(get,PINS.items()))
    record={'status':'acquired_and_hashed','retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'target':'cp313-win_amd64',
        'development_network_only':True,'installed_to_global_python':False,'signature_verified':False,'artifacts':records,'generator_sha256':sha(Path(__file__))}
    save(evidence/'verification.json',record)
    save(output/'lock.json',{'target':'cp313-win_amd64','artifacts':[{k:r[k] for k in ('name','version','filename','bytes','sha256','runtime_dependency')} for r in records]})
    print(json.dumps({'status':record['status'],'wheels':len(records),'bytes':sum(r['bytes'] for r in records)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();run(a.output.resolve(),a.evidence.resolve())
