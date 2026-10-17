"""Run one local NPZ research fixture; no production asset or rights registration."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'research/temporal-background'
sys.path[:0]=[str(ROOT/'product/src'),str(RESEARCH)]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.rvm_worker import install_network_guard
EVENTS=[]
install_network_guard(EVENTS)
import cv2
import numpy as np
from coherent_reference import run as repair, ALGORITHM


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scene-cut-frame',type=int,action='append',default=[])
    parser.add_argument('--min-donors',type=int,default=3)
    parser.add_argument('--array-budget-mib',type=int,default=1536)
    parser.add_argument('--timeout-seconds',type=float,default=1800)
    parser.add_argument('--cancel-file',type=Path)
    args=parser.parse_args()
    target=args.output.resolve()
    assert target.is_relative_to(ROOT/'product/.runtime'), 'research outputs must stay in project .runtime'
    target.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'algorithm':ALGORITHM,
        'product_integrated':False,'natural_quality_accepted':False,'truth_loaded_by_repair':False,
        'generator':'scripts/run_coherent_reference_fixture.py','generator_sha256':sha(Path(__file__)),
        'research_sources':{p.name:sha(p) for p in sorted(RESEARCH.glob('*.py'))},
        'network_guard_events':EVENTS,'checkpoint_timeout_is_not_hard_native_call_deadline':True}
    def save():
        (target/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    def checkpoint(*_):
        if args.cancel_file and args.cancel_file.exists():
            raise RuntimeError('RESEARCH_CANCELLED')
        if time.monotonic()-started>args.timeout_seconds:
            raise TimeoutError('RESEARCH_TIMEOUT')
    save()
    try:
        if (not np.isfinite(args.timeout_seconds) or not 1<=args.timeout_seconds<=7200
                or not 1<=args.array_budget_mib<=2048):
            raise ValueError('RESEARCH_OPTIONS_INVALID')
        checkpoint()
        if args.input.startswith(('\\\\','//')) or '://' in args.input:
            raise ValueError('RESEARCH_INPUT_LOCAL_ONLY')
        source=Path(args.input).resolve(strict=True)
        if source.suffix!='.npz' or not source.is_file() or source.stat().st_size>512*1024**2:
            raise ValueError('RESEARCH_INPUT_BUDGET')
        before=sha(source)
        keys=('source','forbidden','selected','fallback')
        shapes={}
        with zipfile.ZipFile(source) as archive:
            infos=archive.infolist()
            if len(infos)>32 or sum(i.file_size for i in infos)>1024**3 or len({i.filename for i in infos})!=len(infos):
                raise ValueError('RESEARCH_ARCHIVE_BUDGET')
            for key in keys:
                info=archive.getinfo(key+'.npy')
                with archive.open(info) as stream:
                    if np.lib.format.read_magic(stream)!=(1,0):
                        raise ValueError('RESEARCH_NPY_VERSION_UNSUPPORTED')
                    shape,fortran,dtype=np.lib.format.read_array_header_1_0(stream)
                    expected=np.dtype(np.uint8 if key in {'source','fallback'} else np.bool_)
                    if fortran or dtype!=expected or len(shape)!=(4 if expected==np.uint8 else 3):
                        raise ValueError('RESEARCH_ARRAY_HEADER_INVALID')
                    if (not 2<=shape[0]<=65 or min(shape[1:3])<16 or shape[1]*shape[2]>1_048_576
                            or (len(shape)==4 and shape[3]!=4)
                            or info.file_size!=stream.tell()+int(np.prod(shape))*dtype.itemsize):
                        raise ValueError('RESEARCH_ARRAY_BUDGET')
                    shapes[key]=shape
        if (shapes['source']!=shapes['fallback'] or shapes['source'][:3]!=shapes['selected']
                or shapes['selected']!=shapes['forbidden']):
            raise ValueError('RESEARCH_ARRAY_SHAPES_DIFFER')
        with np.load(source,allow_pickle=False) as arrays:
            values=[arrays[key] for key in keys]
        checkpoint()
        cv2.setNumThreads(4);cv2.ocl.setUseOpenCL(False);cv2.setRNGSeed(17018)
        output,used,report=repair(*values,min_donors=args.min_donors,scene_cuts=args.scene_cut_frame,
            budget=args.array_budget_mib*1024**2,checkpoint=checkpoint)
        checkpoint()
        assert sha(source)==before,'RESEARCH_INPUT_CHANGED'
        artifact=target/'result.npz'
        np.savez_compressed(artifact,output=output,contributed=used)
        record.update(status='completed',input=str(source),input_sha256=before,output_sha256=sha(artifact),
            output_rgba_sha256='sha256:'+hashlib.sha256(output.tobytes()).hexdigest(),report=report,
            seconds=time.monotonic()-started,opencv=cv2.__version__,numpy=np.__version__)
        save()
        print(json.dumps({'status':record['status'],'frames':len(output),'report':str(target/'verification.json')}))
        return 0
    except BaseException as exc:
        record.update(status='failed',error=repr(exc),seconds=time.monotonic()-started)
        (target/'exception.log').write_text(traceback.format_exc(),encoding='utf-8',newline='\n')
        save()
        print(json.dumps({'status':'failed','error':repr(exc),'report':str(target/'verification.json')}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
