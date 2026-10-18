"""Read a bounded set of example-engine text files via pinned Git blob IDs."""
import base64,hashlib,json,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/openfilm-examples-review-final-20261018'
FILES=['one-prompt/src/px/'+name for name in ('README.md','LICENSE-pdoom-video.txt','engine.js','gl.js','post.js','stroke.js','type.js')]+['one-prompt/src/section.js']


def run():
    output=BASE/'px';output.mkdir(exist_ok=False)
    tree=json.loads((BASE/'tree.raw.json').read_bytes());blobs={row['path']:row['sha'] for row in tree['tree'] if row['type']=='blob'}
    digest=lambda data:'sha256:'+hashlib.sha256(data).hexdigest()
    def fetch(path):
        url='https://api.github.com/repos/openfilm/examples/git/blobs/'+blobs[path]
        request=urllib.request.Request(url,headers={'User-Agent':'Agent-Video-Kit-source-review'})
        with urllib.request.urlopen(request,timeout=30) as response:body=response.read(4*1024**2);status=response.status
        data=json.loads(body);assert status==200 and data['encoding']=='base64'
        raw=base64.b64decode(data['content']);assert len(raw)==data['size'] and data['sha']==blobs[path]
        name=Path(path).name;(output/(name+'.blob.raw.json')).write_bytes(body);(output/name).write_bytes(raw)
        return {'path':path,'url':url,'http_status':status,'git_blob_sha':blobs[path],'bytes':len(raw),'sha256':digest(raw),'reply_sha256':digest(body)}
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,FILES))
    record={'status':'text_sources_verified','checked_at_utc':datetime.now(timezone.utc).isoformat(),'examples_commit':json.loads((BASE/'verification.json').read_bytes())['examples_commit'],'sources':rows,'code_adopted':False,'engine_executed':False,'media_downloaded':False,'runtime_network':False,'generator_sha256':digest(Path(__file__).read_bytes())}
    (output/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':record['status'],'text_sources':len(rows),'code_adopted':False}))


if __name__=='__main__':run()
