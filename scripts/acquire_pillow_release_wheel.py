"""Development-only Pillow wheel acquisition into a new pinned E-drive profile."""
import argparse,hashlib,io,json,shutil,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    output,evidence=args.output.resolve(),args.evidence.resolve()
    assert output.is_relative_to(ROOT/'sources') and evidence.is_relative_to(ROOT/'docs')
    evidence.mkdir(parents=True,exist_ok=False)
    source=ROOT/'sources/python-runtime/cp313-win_amd64'
    lock=json.loads((source/'lock.json').read_text(encoding='utf-8'))
    assert not output.exists();shutil.copytree(source,output)
    try:
        url='https://pypi.org/pypi/Pillow/12.1.0/json'
        with urllib.request.urlopen(url,timeout=40) as r:raw=r.read(4*1024*1024)
        (evidence/'pillow.pypi.json').write_bytes(raw)
        candidates=[p for p in json.loads(raw)['urls'] if p['filename'].endswith('cp313-cp313-win_amd64.whl')]
        assert len(candidates)==1
        chosen=candidates[0];assert chosen['url'].startswith('https://files.pythonhosted.org/') and 0<chosen['size']<16*1024*1024
        with urllib.request.urlopen(chosen['url'],timeout=60) as r:body=r.read(16*1024*1024)
        assert len(body)==chosen['size'] and hashlib.sha256(body).hexdigest()==chosen['digests']['sha256']
        wheel=output/chosen['filename'];wheel.write_bytes(body)
        licenses={}
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            for name in z.namelist():
                if not name.endswith('/') and any(s in Path(name).name.upper() for s in ('LICENSE','COPYING','NOTICE')):
                    path=evidence/'licenses'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name));licenses[name]=sha(path)
        assert licenses
        row={'name':'pillow','version':'12.1.0','filename':wheel.name,'bytes':len(body),'sha256':sha(wheel),'runtime_dependency':True}
        lock['artifacts'].append(row);(output/'lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
        (evidence/'verification.json').write_text(json.dumps({'status':'acquired_and_hashed','artifact':row,'pypi_url':url,
            'download_url':chosen['url'],'metadata_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'license_files':licenses,
            'development_network_only':True,'global_install':False,'generator_sha256':sha(Path(__file__))},indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':'acquired_and_hashed','bytes':len(body),'licenses':len(licenses)}))
    except Exception as exc:
        (evidence/'failure.json').write_text(json.dumps({'error':repr(exc),'partials_preserved':True})+'\n',encoding='utf-8');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);main(p.parse_args())
