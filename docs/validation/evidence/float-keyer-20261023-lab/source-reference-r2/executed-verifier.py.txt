"""Record official n8.1 source references and the actual local binary, not runtime downloads."""
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = ROOT/'docs/validation/evidence/float-keyer-20261023-lab'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision',required=True)
    parser.add_argument('--transport',choices=('raw','api'),default='raw')
    args = parser.parse_args()
    assert args.revision.startswith('r') and args.revision[1:].isdigit()
    work = REL/('source-reference-'+args.revision); work.mkdir(parents=True, exist_ok=False)
    state = {'status':'running', 'at_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'development-only official source and native option reference',
        'sources':[], 'calls':[], 'runtime_network_added':False, 'copied_C_into_runtime':False,
        'native_windows':True, 'virtualization':False, 'transport':args.transport}
    def save():
        (work/'verification.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        for name in ('vf_colorkey.c','vf_chromakey.c'):
            url = ('https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/'+name if args.transport == 'raw'
                   else 'https://api.github.com/repos/FFmpeg/FFmpeg/contents/libavfilter/'+name+'?ref=n8.1')
            request = urllib.request.Request(url, headers={'User-Agent':'agent-video-kit-source-review'})
            with urllib.request.urlopen(request,timeout=30) as response:
                wire = response.read(); status = response.status
            payload = wire
            if args.transport == 'api':
                (work/(name+'.api.json')).write_bytes(wire)
                api = json.loads(wire)
                assert api['encoding'] == 'base64'
                payload = base64.b64decode(api['content'])
                assert hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest() == api['sha']
            path = work/(name+'.txt'); path.write_bytes(payload)
            assert b'GNU Lesser General Public' in payload and b'FFmpeg' in payload
            state['sources'].append({'url':url,'http_status':status,'file':path.name,
                'bytes':len(payload),'sha256':sha(path),'git_blob_sha1':hashlib.sha1(
                    b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()})
            save()
        license_source = MAIN/'sources/upstream/ffmpeg/COPYING.LGPLv2.1'
        shutil.copyfile(license_source,work/'COPYING.LGPLv2.1.txt')
        state['reference_license'] = {'license':'LGPL-2.1-or-later','original_source':str(license_source),
            'file':'COPYING.LGPLv2.1.txt','sha256':sha(work/'COPYING.LGPLv2.1.txt')}
        sys.path.insert(0,str(ROOT/'product/src'))
        from ai_ad_editor.runtime import configure_local_runtime
        configure_local_runtime()
        from ai_ad_editor.media import ffmpeg_path
        binary = Path(ffmpeg_path()).resolve()
        state['local_binary'] = {'path':str(binary),'sha256':sha(binary)}
        for name, arguments in [('version',['-version']),('colorkey',['-hide_banner','-h','filter=colorkey']),
                                ('chromakey',['-hide_banner','-h','filter=chromakey'])]:
            command = [str(binary),*arguments]
            result = subprocess.run(command,capture_output=True,timeout=30)
            row = {'name':name,'command':command,'exit_code':result.returncode}
            for channel in ('stdout','stderr'):
                path = work/(name+'.'+channel+'.log'); path.write_bytes(getattr(result,channel))
                row[channel] = {'file':path.name,'sha256':sha(path)}
            state['calls'].append(row); save(); assert result.returncode == 0
        state['status'] = 'passed-official-n8.1-source-and-actual-local-binary-reference'
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc)); raise
    finally:
        state['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(); (work/'executed-verifier.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({'status':state['status'],'sources':len(state['sources']),'calls':len(state['calls'])}),flush=True)


if __name__ == '__main__':
    main()
