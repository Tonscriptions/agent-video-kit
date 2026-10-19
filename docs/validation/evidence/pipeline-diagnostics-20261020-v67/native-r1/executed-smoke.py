"""Real native worker failure from an explicit invalid ONNX fixture, not inference."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
MODEL_PYTHON = Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')

def sha(p): return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--launcher', type=Path)
    args = parser.parse_args()
    args.work = args.work.resolve(); args.evidence = args.evidence.resolve()
    for p in (args.work, args.evidence): p.mkdir(parents=True, exist_ok=False)
    before = frozen(); calls = []
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_before': before, 'calls': calls, 'model_forward_accepted': False,
        'scope': 'actual native FFmpeg and RVM worker; deliberately invalid ONNX, no valid model inference',
        'network': 'disabled', 'virtualization': False}
    shutil.copyfile(__file__, args.evidence/'executed-smoke.py')
    prefix = [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
        "import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())", str(ROOT/'product/src')]
    if args.launcher: prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(args.launcher.resolve())]
    env = dict(os.environ, TEMP=str(args.work), TMP=str(args.work), TMPDIR=str(args.work), PYTHONDONTWRITEBYTECODE='1')
    def cli(values, name, expected=0):
        command = [*prefix, *map(str, values)]
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=120)
        out, err = args.evidence/(name+'.stdout.log'), args.evidence/(name+'.stderr.log')
        out.write_bytes(p.stdout); err.write_bytes(p.stderr)
        calls.append({'name':name, 'command':command, 'exit_code':p.returncode, 'expected_exit':expected,
            'stdout':out.name, 'stderr':err.name, 'stdout_sha256':sha(out), 'stderr_sha256':sha(err)})
        save(args.evidence/'verification.json', record)
        assert p.returncode == expected, (name,p.returncode,p.stderr[-500:],p.stdout[-1000:])
        return json.loads(p.stdout)
    project = args.work/'project'
    try:
        cli(['project','init',project], 'init')
        proof = args.work/'proof.json'; save(proof, {'license_spdx':'CC0-1.0', 'scope':'original controlled broken-model fixture, no model weights'})
        model = args.work/'controlled-invalid.onnx'; model.write_bytes(b'Agent Video Kit controlled INVALID ONNX, not a model')
        source = ROOT/'docs/assets/video-outpainting-20261019-v66-lama-harmonic-r2/source.mov'
        asset = cli(['media','ingest','--project',project,'--input',source,'--license-spdx','CC0-1.0',
            '--verification-status','verified','--permitted-use','commercial_ad','--evidence',proof], 'ingest')['data']['asset']
        adapter = cli(['media','adapter','register','--project',project,'--adapter-id','controlled_invalid',
            '--engine','rvm-onnx-cpu-matting-v1','--model-path',model,'--executable',MODEL_PYTHON,'--evidence',proof], 'register')['data']['adapter']
        metadata_paths = [project/p for p in ('project.json','project.lock.json','rights/ledger.json','models/visual-adapters.json')]
        # Follow the actual ledger helper's canonical location.
        sys.path.insert(0, str(ROOT/'product/src'))
        from ai_ad_editor.project import ledger_file
        metadata_paths[2] = ledger_file(project)
        metadata_before = {p.relative_to(project).as_posix(): sha(p) for p in metadata_paths if p.is_file()}
        failed = cli(['media','matting','--project',project,'--asset-id',asset['id'],'--adapter-id','controlled_invalid',
            '--derived-asset-id','failed_native','--timeout-seconds','60'], 'actual-native-failure', 6)
        error = failed['errors'][0]; ref = error['diagnostics']
        assert error['code'] == 'MATTING_PIPELINE_FAILED' and ref['status'] == 'stored'
        common = ['--project',project,'--diagnostic-id',ref['diagnostic_id'],'--expected-manifest-sha256',ref['manifest_sha256']]
        listed = cli(['diagnostics','list','--project',project,'--operation-id',error['operation_id']], 'list')
        assert len(listed['data']['records']) == 1
        shown = cli(['diagnostics','show',*common], 'show')
        assert 'logs' not in shown['data']
        logs = cli(['diagnostics','show',*common,'--include-logs'], 'show-logs')['data']['logs']
        assert 'INVALID_PROTOBUF' in logs['worker.stderr.log'], 'Failure must be the real native ONNX parser, not a simulated or import error'
        manifest = shown['data']['manifest']; rows = {row['role']:row for row in manifest['processes']}
        assert rows['worker']['observed_exit']['raw'] != 0 and not rows['worker']['cleanup_requested']
        output = args.work/'failure.zip'
        cli(['diagnostics','export',*common,'--output',output,'--dry-run'], 'export-plan'); assert not output.exists()
        exported = cli(['diagnostics','export',*common,'--output',output], 'export')['data']
        assert output.stat().st_size <= 768*1024 and sha(output) == exported['sha256']
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) <= {'manifest.json','request.json','response.json',*(role+'.stderr.log' for role in ('decoder','worker','encoder'))}
            archive_names = archive.namelist()
        shutil.copyfile(output, args.evidence/'failure.zip')
        src = project/'renders/diagnostics/pipelines'/ref['diagnostic_id']
        shutil.copytree(src, args.evidence/'record')
        after_metadata = {p.relative_to(project).as_posix():sha(p) for p in metadata_paths if p.is_file()}
        assert metadata_before == after_metadata and not list((project/'cache/matting').iterdir())
        assert not list((project/'assets/derived').glob('*'))
        cli(['policy','audit','--project',project], 'policy')
        record.update(status='passed', native_worker_failure='onnxruntime INVALID_PROTOBUF from deliberate invalid fixture',
            operation_id=error['operation_id'], diagnostic=ref, processes=manifest['processes'], adapter=adapter,
            metadata_before=metadata_before, metadata_after=after_metadata, cache_empty=True, failed_assets_registered=False,
            archive_names=archive_names, archive_sha256=sha(output), frozen_after=frozen())
        record['frozen_equal'] = record['frozen_after'] == before
        assert record['frozen_equal']
    except Exception as exc:
        record.update(status='failed', error=type(exc).__name__+': '+str(exc)); raise
    finally:
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.evidence/'verification.json', record)
    print(json.dumps({'status':record['status'],'cli_calls':len(calls),'diagnostic':record['diagnostic'],'frozen_equal':record['frozen_equal']}, ensure_ascii=False))

if __name__ == '__main__': main()
