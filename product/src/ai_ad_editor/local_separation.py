"""Explicit native TorchAudio HDemucs registration and offline execution."""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any

from .errors import AppError,argument_error
from .media import ffmpeg_path,probe_media
from .policy import resolve_local_path
from .utils import assert_id,atomic_write_json,now_iso,run_process,sha256_bytes,sha256_file

DEMUCS_ENGINE = 'torchaudio-hdemucs-local-v1'
DEMUCS_PROTOCOL = 'agent-video-hdemucs-separation-v1'
MODEL_SAMPLE_RATE = 44100
MAX_AUDIO_SECONDS = 7200


def settings(*, device: str = 'cpu', threads: int = 4, segment_seconds: float = 6, overlap: float = .25) -> dict:
    if device not in {'cpu','cuda'} or type(threads) is not int or not 1 <= threads <= 32 or isinstance(segment_seconds,bool) or isinstance(overlap,bool) or not all(math.isfinite(float(v)) for v in (segment_seconds,overlap)) or not 1 <= float(segment_seconds) <= 20 or not 0 <= float(overlap) <= .75:
        raise argument_error('HDemucs requires cpu/cuda, threads 1..32, segment-seconds 1..20 and overlap 0..0.75','settings')
    return {'device':device,'threads':threads,'segment_seconds':float(segment_seconds),'overlap':float(overlap),'sample_rate':MODEL_SAMPLE_RATE,'architecture':'torchaudio.models.hdemucs_high','sources':['drums','bass','other','vocals'],'accompaniment_method':'mixture_minus_model_vocals'}


def _entry(path: Path, role: str) -> dict:
    if path.is_symlink() or not path.is_file() or not path.stat().st_size or str(path).startswith('\\\\'):
        raise AppError('SEPARATION_LOCAL_ARTIFACT_INVALID','需要现有非空本地文件',exit_code=10,path=str(path))
    return {'path':str(path.resolve()),'role':role,'bytes':path.stat().st_size,'sha256':'sha256:'+sha256_file(path)}


def manifest_hash(record: dict) -> str:
    payload = {k:record.get(k) for k in ('adapter_id','engine','protocol','output_contract','model_path','model_sha256','executable','executable_sha256','settings','artifacts','rights_ref','network')}
    return 'sha256:'+sha256_bytes(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8'))


def prepare_adapter(root: Path, *, adapter_id: str, model_path: str, executable: str, evidence: str, creator: str, license_spdx: str, license_url: str, permitted_uses: list[str], verification_status: str, options: dict | None = None) -> tuple[dict,dict]:
    assert_id(adapter_id,'adapter_id')
    if verification_status not in {'unverified','verified','restricted'}:
        raise argument_error('未知核验状态','verification_status')
    if not model_path or not executable or not evidence:
        raise argument_error('HDemucs 需要显式 model-path、原生 Python executable 和本地 evidence','model_path/executable/evidence')
    model = resolve_local_path(root,model_path,field='model_path')
    python = resolve_local_path(root,executable,field='executable')
    proof = resolve_local_path(root,evidence,field='evidence')
    if model.suffix.lower() not in {'.pt','.pth'} or python.suffix.lower() != '.exe':
        raise argument_error('HDemucs 要求 .pt/.pth 状态字典与原生 Python .exe','model_path/executable')
    entries = [_entry(model,'model'),_entry(python,'python'),_entry(proof,'evidence')]
    entries += [_entry(Path(__file__).with_name(name),role) for name,role in [('demucs_worker.py','worker'),('separation_dsp.py','dsp'),('local_separation.py','controller')]]
    record = {'adapter_id':adapter_id,'kind':'audio-separation','engine':DEMUCS_ENGINE,'protocol':DEMUCS_PROTOCOL,'output_contract':'vocals_accompaniment_wav_v1','model_path':str(model),'model_sha256':entries[0]['sha256'],'model_kind':'file','model_file_count':1,'executable':str(python),'executable_sha256':entries[1]['sha256'],'settings':settings(**(options or {})),'artifacts':entries,'rights_ref':f'audio_adapter_{adapter_id}','network':'disabled','registered_at':now_iso(),'verification_status':verification_status}
    record['sha256'] = manifest_hash(record)
    rights = {'asset_id':record['rights_ref'],'kind':'model-adapter','sha256':record['sha256'],'source_url':f'local://audio-adapter/{adapter_id}','source_version':DEMUCS_ENGINE,'retrieved_at':record['registered_at'],'creator':creator,'license_spdx':license_spdx,'license_url':license_url,'attribution':'','permitted_uses':list(dict.fromkeys(permitted_uses)),'permitted_channels':[],'restrictions':[],'derived_from':[],'evidence':str(proof),'verification_status':verification_status,'verified_by':'ai-ad-editor' if verification_status=='verified' else '','takedown_status':'clear','notes':'Explicit offline HDemucs artifacts; registration does not prove checkpoint compatibility or model licensing'}
    return record,rights


def verify_adapter(record: dict) -> dict:
    findings = []
    try:
        if record.get('engine') != DEMUCS_ENGINE or record.get('protocol') != DEMUCS_PROTOCOL or record.get('output_contract') != 'vocals_accompaniment_wav_v1' or record.get('network') != 'disabled' or manifest_hash(record) != record.get('sha256'):
            raise ValueError('SEPARATION_MANIFEST_INVALID')
        options = {k:record['settings'][k] for k in ('device','threads','segment_seconds','overlap')}
        if settings(**options) != record['settings']:
            raise ValueError('SEPARATION_SETTINGS_INVALID')
        roles = {e['role']:e for e in record['artifacts']}
        if len(roles) != 6 or len(record['artifacts']) != 6 or set(roles) != {'model','python','evidence','worker','dsp','controller'}:
            raise ValueError('SEPARATION_MANIFEST_INCOMPLETE')
        paths = {'model':record['model_path'],'python':record['executable'],'worker':str(Path(__file__).with_name('demucs_worker.py')),'dsp':str(Path(__file__).with_name('separation_dsp.py')),'controller':str(Path(__file__))}
        if any(Path(roles[k]['path']).resolve() != Path(v).resolve() for k,v in paths.items()) or roles['model']['sha256'] != record['model_sha256'] or roles['python']['sha256'] != record['executable_sha256']:
            raise ValueError('SEPARATION_MANIFEST_PATH_INVALID')
        for entry in record['artifacts']:
            if _entry(Path(entry['path']),entry['role']) != entry:
                findings.append({'code':'SEPARATION_ARTIFACT_HASH_MISMATCH','role':entry['role']})
    except (AppError,ValueError,TypeError,KeyError,OSError) as exc:
        findings.append({'code':getattr(exc,'code','SEPARATION_REGISTRY_INVALID'),'message':str(exc)})
    return {'adapter_id':record.get('adapter_id'),'engine':record.get('engine'),'ok':not findings,'network':'disabled','findings':findings}


def separate_native(root: Path, source: Path, vocals: Path, accompaniment: Path, *, adapter: dict, sample_rate: int | None = None) -> dict:
    from .audio_separation import _validate_sample_rate
    target_rate = _validate_sample_rate(sample_rate) or MODEL_SAMPLE_RATE
    if not verify_adapter(adapter)['ok']:
        raise AppError('MODEL_ADAPTER_HASH_INVALID','离线分离登记完整性检查失败',exit_code=10)
    if vocals == accompaniment or any(p.exists() or p.suffix.lower() != '.wav' for p in (vocals,accompaniment)):
        raise argument_error('分离需要两个不同且尚不存在的 .wav 输出','output')
    probe = probe_media(source)
    duration = float(probe.get('duration_seconds') or 0)
    if not probe.get('audio') or not math.isfinite(duration) or not 0 < duration <= MAX_AUDIO_SECONDS:
        raise argument_error('离线分离要求有效音频，时长不超过 7200 秒','input')
    source_hash = 'sha256:'+sha256_file(source)
    cache = root/'cache/audio-separation';cache.mkdir(parents=True,exist_ok=True)
    for p in (vocals,accompaniment):p.parent.mkdir(parents=True,exist_ok=True)
    created = []
    try:
        with tempfile.TemporaryDirectory(prefix='hdemucs-',dir=str(cache)) as raw:
            job = Path(raw); pcm = job/'input.f32'; response = job/'response.json'
            decoded = run_process([ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe','-n','-i',str(source),'-vn','-ac','2','-ar',str(MODEL_SAMPLE_RATE),'-f','f32le',str(pcm)],timeout=1800)
            if decoded.returncode or not pcm.is_file() or not pcm.stat().st_size or pcm.stat().st_size % 8 or pcm.stat().st_size//8 > MAX_AUDIO_SECONDS*MODEL_SAMPLE_RATE:
                raise AppError('SEPARATION_AUDIO_DECODE_FAILED','本地分离音频解码失败或超过预算',exit_code=6,cause=decoded.stderr[-1500:])
            count = pcm.stat().st_size//8
            outputs = {'vocals':job/'vocals.f32','accompaniment':job/'accompaniment.f32'}
            request = {'protocol':DEMUCS_PROTOCOL,'network':'disabled','adapter':adapter,'input':str(pcm),'input_sha256':'sha256:'+sha256_file(pcm),'source_sha256':source_hash,'samples':count,'outputs':{k:str(v) for k,v in outputs.items()},'response':str(response),'runtime_root':str(job/'runtime')}
            request_path = job/'request.json';atomic_write_json(request_path,request)
            worker = Path(__file__).with_name('demucs_worker.py')
            completed = run_process([adapter['executable'],'-I','-B','-X','utf8',str(worker),str(request_path)],timeout=7200)
            try:
                if response.stat().st_size > 1_000_000:raise ValueError('Oversize response')
                payload = json.loads(response.read_text(encoding='utf-8'))
            except (OSError,ValueError) as exc:
                raise AppError('SEPARATION_WORKER_FAILED','离线分离未返回有效响应',exit_code=6,cause=completed.stderr[-2000:]) from exc
            if completed.returncode or not isinstance(payload,dict) or payload.get('protocol') != DEMUCS_PROTOCOL or payload.get('status') != 'succeeded' or payload.get('network') != 'disabled' or payload.get('blocked_network_events') != [] or any(payload.get(k) != request[k] for k in ('input_sha256','source_sha256','samples')) or payload.get('adapter_sha256') != adapter['sha256']:
                raise AppError('SEPARATION_WORKER_FAILED','离线分离协议、模型或输入完整性失败',exit_code=6,cause=json.dumps(payload,ensure_ascii=False)[-4000:])
            metrics = payload.get('metrics') or {}
            try:
                numeric = [metrics['mixture_max_abs_error'],metrics['normalization_mean'],metrics['normalization_std'],metrics['peaks']['vocals'],metrics['peaks']['accompaniment']]
                if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in numeric) or metrics['samples'] != count or metrics['channels'] != 2 or metrics['normalization_std'] <= 0 or not 0 <= metrics['mixture_max_abs_error'] <= 1e-4 or min(metrics['peaks'].values()) < 0:
                    raise ValueError('Invalid signal metrics')
            except (TypeError,ValueError,KeyError) as exc:
                raise AppError('SEPARATION_OUTPUT_INVALID','分离响应缺少有效的信号完整性指标',exit_code=6) from exc
            if 'sha256:'+sha256_file(source) != source_hash or not verify_adapter(adapter)['ok']:
                raise AppError('SEPARATION_INTEGRITY_FAILED','分离过程中输入或模型发生变化',exit_code=10)
            target_samples = max(1,round(count*target_rate/MODEL_SAMPLE_RATE))
            stems = {}
            for role,destination in (('vocals',vocals),('accompaniment',accompaniment)):
                source_pcm = outputs[role]
                details = payload.get('outputs',{}).get(role,{})
                if not source_pcm.is_file() or source_pcm.stat().st_size != count*8 or details.get('sha256') != 'sha256:'+sha256_file(source_pcm):
                    raise AppError('SEPARATION_OUTPUT_INVALID','离线分离输出字节数或哈希不符',exit_code=6,path=role)
                created.append(destination)
                encoded = run_process([ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-n','-f','f32le','-ar',str(MODEL_SAMPLE_RATE),'-ac','2','-i',str(source_pcm),'-af',f'aresample={target_rate},apad=whole_len={target_samples},atrim=end_sample={target_samples}','-ar',str(target_rate),'-c:a','pcm_f32le',str(destination)],timeout=1800)
                if encoded.returncode:
                    raise AppError('SEPARATION_OUTPUT_INVALID','分离 WAV 编码失败',exit_code=6,cause=encoded.stderr[-1500:])
                output_probe = probe_media(destination)
                audio = output_probe.get('audio') or {}
                if audio.get('channels') != 2 or int(audio.get('sample_rate') or 0) != target_rate or abs(float(output_probe.get('duration_seconds') or 0)-target_samples/target_rate) > 2/target_rate:
                    raise AppError('SEPARATION_OUTPUT_INVALID','分离输出时长、采样率或声道不符',exit_code=6,path=role)
                stems[role] = {'output':str(destination),'role':role,'sha256':'sha256:'+sha256_file(destination),'probe':output_probe,'samples':target_samples}
            if 'sha256:'+sha256_file(source) != source_hash or not verify_adapter(adapter)['ok']:
                raise AppError('SEPARATION_INTEGRITY_FAILED','编码期间输入或模型发生变化',exit_code=10)
            # Internal center/side aliases keep the existing asset writer
            # compatible; the CLI publishes the semantic role names.
            return {'version':'0.2.0','engine':DEMUCS_ENGINE,'method':'hdemucs','protocol':DEMUCS_PROTOCOL,'network':'disabled','source':str(source),'source_sha256':source_hash,'adapter_id':adapter['adapter_id'],'model_sha256':adapter['sha256'],'stems':{'center':stems['vocals'],'side':stems['accompaniment']},'worker':payload,'warnings':[{'code':'AUDIO_SEPARATION_MODEL_REVIEW','message':'HDemucs 模型已本地执行；需复核人声泄漏、音乐残留、边界接缝、浮点峰值及模型/素材许可，伴奏为原音减模型人声'}]}
    except BaseException:
        for path in created:path.unlink(missing_ok=True)
        raise
