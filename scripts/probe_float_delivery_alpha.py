"""Measure all 256 final alpha codes without a browser or an intermediate movie."""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path

def main():
    out=ROOT/'docs/validation/evidence/float-standard-20261022-lab/alpha-boundary-r1'
    out.mkdir(parents=True,exist_ok=False)
    executable=Path(ffmpeg_path()).resolve()
    rows=[]
    for name,alpha in [('unit65535',np.rint(np.arange(256,dtype=np.float64)/255*65535).astype('<u2')),
                       ('code8-left-shift8',np.arange(256,dtype='<u2')<<8)]:
        planes=[np.full((2,256),32768,dtype='<u2') for _ in range(3)]
        planes.append(np.tile(alpha,(2,1)))
        payload=b''.join(p.tobytes() for p in planes)
        command=[str(executable),'-nostdin','-hide_banner','-v','error','-threads','1','-filter_threads','1',
                 '-f','rawvideo','-pixel_format','gbrap16le','-video_size','256x2','-i','pipe:0',
                 '-vf','alphaextract,format=gray','-frames:v','1','-f','rawvideo','pipe:1']
        result=subprocess.run(command,input=payload,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.gray')).write_bytes(result.stdout)
        (out/(name+'.stderr.txt')).write_bytes(result.stderr)
        assert result.returncode==0 and len(result.stdout)==512
        actual=np.frombuffer(result.stdout,dtype=np.uint8).reshape(2,256)
        difference=np.abs(actual.astype(np.int16)-np.arange(256,dtype=np.int16))
        rows.append({'id':name,'command':command,'exit_code':result.returncode,
                     'input_sha256':'sha256:'+hashlib.sha256(payload).hexdigest(),
                     'output_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
                     'maximum_code_error':int(difference.max()),'wrong_components':int(np.count_nonzero(difference))})
    data={'status':'measured-all-256-alpha-codes','cases':rows,'actual_native_commands':2,
          'ffmpeg':{'path':str(executable),'sha256':'sha256:'+hashlib.sha256(executable.read_bytes()).hexdigest()},
          'script_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'movie_encoded':False,'browser':False,'network':False,'virtualization':False}
    (out/'verification.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    print(json.dumps(data))

if __name__=='__main__':main()
