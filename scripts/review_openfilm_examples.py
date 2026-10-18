"""Read source inventories and pinned example text, without fetching media or running it."""
from __future__ import annotations
import argparse, base64, hashlib, json, urllib.error, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/validation/evidence/openfilm-examples-review-final-20261018'
MEDIA={'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.mov','.mkv','.webm','.wav','.mp3','.m4a','.ogg','.flac','.ttf','.otf','.woff','.woff2','.onnx','.safetensors','.pth','.pt','.ckpt'}


def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def run():
    OUTPUT.mkdir(parents=True,exist_ok=False)
    def fetch(item):
        name,url=item;started=datetime.now(timezone.utc).isoformat()
        request=urllib.request.Request(url,headers={'User-Agent':'Agent-Video-Kit-source-review','Cache-Control':'no-cache'})
        try:
            with urllib.request.urlopen(request,timeout=30) as reply:raw=reply.read(4*1024**2);status=reply.status
        except urllib.error.HTTPError as error:raw=error.read(1024**2);status=error.code
        (OUTPUT/name).write_bytes(raw)
        return name,{'url':url,'status':status,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'bytes':len(raw),'sha256':sha(raw)}
    archive=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip'
    with zipfile.ZipFile(archive) as original:
        files={n.split('/',1)[1]:original.read(n) for n in original.namelist() if not n.endswith('/')}
    index=json.loads(files['packages/openfilm/examples-index/examples.json'])
    media=[{'path':name,'bytes':len(raw),'sha256':sha(raw)} for name,raw in files.items() if Path(name).suffix.lower() in MEDIA]
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests=dict(pool.map(fetch,[('repository.raw.json','https://api.github.com/repos/openfilm/examples'),('main.raw.json','https://api.github.com/repos/openfilm/examples/commits/main')]))
    assert all(row['status']==200 for row in requests.values())
    repository=json.loads((OUTPUT/'repository.raw.json').read_bytes());head=json.loads((OUTPUT/'main.raw.json').read_bytes())['sha']
    requests.update([fetch(('tree.raw.json',f'https://api.github.com/repos/openfilm/examples/git/trees/{head}?recursive=1'))])
    tree=json.loads((OUTPUT/'tree.raw.json').read_bytes());assert not tree['truncated']
    names={row['path'] for row in tree['tree'] if row['type']=='blob'}
    text_paths=['README.md','LICENSE','examples.json','one-prompt/README.md','one-prompt/CREDITS.md','one-prompt/film.html','openfilm-intro/README.md','openfilm-intro/CREDITS.md','openfilm-intro/film.html']
    selected=[path for path in text_paths if path in names]
    blobs={row['path']:row['sha'] for row in tree['tree'] if row['type']=='blob'}
    with ThreadPoolExecutor(max_workers=3) as pool:
        requests.update(dict(pool.map(fetch,[(path.replace('/','__')+'.blob.raw.json',f'https://api.github.com/repos/openfilm/examples/git/blobs/{blobs[path]}') for path in selected])))
    assert all(row['status']==200 for row in requests.values())
    for path in selected:
        blob=json.loads((OUTPUT/(path.replace('/','__')+'.blob.raw.json')).read_bytes());assert blob['encoding']=='base64'
        raw=base64.b64decode(blob['content']);assert len(raw)==blob['size']
        (OUTPUT/(path.replace('/','__')+'.raw.txt')).write_bytes(raw)
    remote_media=[{'path':row['path'],'bytes':row.get('size'),'git_blob_sha':row['sha']} for row in tree['tree'] if row['type']=='blob' and Path(row['path']).suffix.lower() in MEDIA]
    record={'status':'read_only_inventory_verified','checked_at_utc':datetime.now(timezone.utc).isoformat(),'main_source_archive_sha256':sha(archive.read_bytes()),'main_repository_file_count':len(files),'main_repository_media':media,'main_bundled_examples_index':index,'examples_source_pointer':files['packages/openfilm/examples-index/SOURCE'].decode(),'examples_repository':repository['full_name'],'examples_commit':head,'examples_stars':repository['stargazers_count'],'examples_forks':repository['forks_count'],'examples_tree_blobs':len(names),'examples_media_inventory':remote_media,'selected_text_sources':selected,'unavailable_text_paths':[path for path in text_paths if path not in names],'requests':requests,'media_files_downloaded':0,'examples_rendered':0,'new_model_inference':0,'browser_tabs_opened':0,'runtime_network':False,'development_source_inspection_network':True,'generator_sha256':sha(Path(__file__).read_bytes())}
    (OUTPUT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({key:record[key] for key in ('status','main_repository_file_count','examples_commit','examples_stars','examples_forks','examples_tree_blobs','media_files_downloaded')}))


if __name__=='__main__':run()
