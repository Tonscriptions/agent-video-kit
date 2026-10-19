"""Measure native R3 with real source handles; no product mutation or downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATE = 48000


def run(work: Path, binary: Path):
    import numpy as np

    work.mkdir(parents=True, exist_ok=False)
    records = []

    def ff(args):
        p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', *map(str, args)],
                           capture_output=True, timeout=120)
        if p.returncode:
            raise RuntimeError(p.stderr.decode('utf-8', 'replace'))
        return p.stdout

    for source_name, start, expected in [('stereo-tones.wav', .201, [400, 800]),
                                          ('stereo-tones.wav', .507, [400, 800]),
                                          ('pulses.wav', .201, [400, 400])]:
        source = ROOT / 'docs/assets/offline-audio-stretch-20261017' / source_name
        for context_ms in (0, 64):
            left = round(start*RATE)
            right = left + 192
            head = min(left, round(context_ms*RATE/1000))
            tail = round(context_ms*RATE/1000)
            tag = f'{source.stem}-{left}-{context_ms}'
            decoded, output = work / (tag+'-input.wav'), work / (tag+'-output.wav')
            ff(['-i', source, '-map', '0:a:0', '-af',
                f'aresample={RATE},atrim=start_sample={left-head}:end_sample={right+tail},asetpts=N/SR/TB',
                '-c:a', 'pcm_f32le', decoded])
            command = [str(binary), '-3', '--no-threads', '--centre-focus', '-q',
                       '-t', '62.5', str(decoded), str(output)]
            p = subprocess.run(command, capture_output=True, timeout=120)
            (work / (tag+'.stderr.log')).write_bytes(p.stderr)
            if p.returncode:
                raise RuntimeError(p.stderr.decode('utf-8', 'replace'))
            raw = ff(['-i', output, '-map', '0:a:0', '-ac', '2', '-ar', str(RATE),
                      '-f', 'f32le', 'pipe:1'])
            pcm = np.frombuffer(raw, '<f4').reshape(-1, 2)
            selected = pcm[round(head*62.5):round(head*62.5)+12000].copy()
            assert len(selected) == 12000 and np.isfinite(selected).all()
            selected.tofile(work / (tag+'-selected.f32le'))
            middle = selected[1500:10500]
            power = np.abs(np.fft.rfft(middle*np.hanning(len(middle))[:, None], n=262144, axis=0))
            frequencies = np.fft.rfftfreq(262144, 1/RATE)
            search = (frequencies >= 100) & (frequencies <= 1400)
            peaks = frequencies[search][np.argmax(power[search], axis=0)].tolist()
            records.append({'source':str(source.relative_to(ROOT)), 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                            'start_sample':left, 'source_samples':192, 'target_samples':12000,
                            'context_ms':context_ms, 'head_samples':head, 'tail_samples':tail,
                            'native_command':command, 'peaks_hz':peaks, 'expected_hz':expected,
                            'passed_pitch_gate':all(abs(v-hz)<=5 for v,hz in zip(peaks,expected)),
                            'rms':np.sqrt(np.mean(selected.astype(np.float64)**2,axis=0)).tolist(),
                            'continuous_listening':False})
            print(json.dumps(records[-1],ensure_ascii=False),flush=True)
    (work / 'verification.json').write_text(json.dumps({'status':'measured','records':records,
        'scope':'native development probe; not a product option or natural-audio acceptance'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--rubberband',type=Path,required=True)
    a=p.parse_args()
    run(a.work.resolve(),a.rubberband.resolve(strict=True))
