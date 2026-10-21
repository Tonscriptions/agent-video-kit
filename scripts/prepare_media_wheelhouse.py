"""Development-only capture of one official pinned wheel; runtime stays offline."""
from datetime import datetime,timezone
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse
from urllib.request import Request,urlopen
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    output=REL/'wheelhouse-r1.json';assert not output.exists()
    wheelhouse=ROOT/'sources/python-runtime/cp313-win_amd64-media';assert not wheelhouse.exists();wheelhouse.mkdir(parents=True)
    started=datetime.now(timezone.utc).isoformat()
    source=MAIN/'sources/python-runtime/cp313-win_amd64-text';lock=json.loads((source/'lock.json').read_bytes())
    assert lock['target']=='cp313-win_amd64' and sum(row['runtime_dependency'] for row in lock['artifacts'])==6
    copied={}
    for row in lock['artifacts']:
        p=source/row['filename'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        target=wheelhouse/p.name;shutil.copyfile(p,target);assert sha(target)==row['sha256'];copied[p.name]=row['sha256']
    url='https://pypi.org/pypi/numpy/2.4.2/json'
    with urlopen(Request(url,headers={'User-Agent':'agent-video-kit-development-source-review/1'}),timeout=30) as response:
        assert urlparse(response.url).hostname=='pypi.org';raw=response.read(4*1024**2)
        headers=dict(response.headers);assert response.read(1)==b''
    metadata=REL/'numpy-2.4.2-pypi.json';metadata.write_bytes(raw)
    data=json.loads(raw);assert data['info']['name']=='numpy' and data['info']['version']=='2.4.2'
    filename='numpy-2.4.2-cp313-cp313-win_amd64.whl'
    artifact=next(row for row in data['urls'] if row['filename']==filename)
    assert artifact['packagetype']=='bdist_wheel' and not artifact['yanked']
    parsed=urlparse(artifact['url']);assert parsed.scheme=='https' and parsed.hostname=='files.pythonhosted.org'
    pending=wheelhouse/(filename+'.partial');assert not pending.exists()
    with urlopen(Request(artifact['url'],headers={'User-Agent':'agent-video-kit-development-source-review/1'}),timeout=45) as response:
        assert urlparse(response.url).hostname=='files.pythonhosted.org'
        download_headers=dict(response.headers)
        with pending.open('xb') as stream:
            total=0
            while chunk:=response.read(1024**2):
                total+=len(chunk);assert total<=artifact['size'];stream.write(chunk)
    assert pending.stat().st_size==artifact['size'] and sha(pending)=='sha256:'+artifact['digests']['sha256']
    target=wheelhouse/filename;pending.rename(target)
    notices={};record_files=0
    with zipfile.ZipFile(target) as archive:
        record=next(n for n in archive.namelist() if n.endswith('.dist-info/RECORD'))
        for name,digest,size in csv.reader(io.StringIO(archive.read(record).decode())):
            payload=archive.read(name)
            if digest:
                algorithm,value=digest.split('=',1);assert algorithm=='sha256'
                assert base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()==value
            if size:assert len(payload)==int(size)
            record_files+=1
        for name in archive.namelist():
            if name.endswith('/') or not any(v in Path(name).name.upper() for v in ('LICENSE','COPYING','NOTICE')):continue
            dest=REL/'numpy-notices'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.read(name))
            notices[name]={'path':dest.relative_to(ROOT).as_posix(),'sha256':sha(dest),'bytes':dest.stat().st_size}
    assert notices and record_files>900
    lock['artifacts'].append({'name':'numpy','version':'2.4.2','filename':filename,'bytes':artifact['size'],
        'sha256':sha(target),'runtime_dependency':True,'source_url':artifact['url'],
        'pypi_json_sha256':sha(metadata),'upload_time_iso_8601':artifact['upload_time_iso_8601']})
    lock['runtime_profile']='media-analysis-v1';save(wheelhouse/'lock.json',lock)
    result={'status':'passed-pinned-wheelhouse-preparation-not-runtime-installation',
        'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
        'development_network':True,'runtime_network':False,'virtualization':False,
        'metadata_url':url,'metadata_sha256':sha(metadata),'metadata_headers':headers,
        'artifact':artifact,'artifact_sha256':sha(target),'download_headers':download_headers,
        'wheelhouse':wheelhouse.relative_to(ROOT).as_posix(),'lock_sha256':sha(wheelhouse/'lock.json'),
        'inherited_wheels':copied,'base_lock_sha256':sha(source/'lock.json'),'new_numpy_wheels':1,
        'runtime_dependency_wheels':7,'product_included':False,'wheel_RECORD_files_verified':record_files,
        'notices':notices,'license_expression':data['info'].get('license_expression'),
        'generator_sha256':sha(__file__)}
    save(output,result)
    print(json.dumps({k:result[k] for k in ('status','artifact_sha256','runtime_dependency_wheels','wheel_RECORD_files_verified','license_expression')},ensure_ascii=False))


if __name__=='__main__':main()
