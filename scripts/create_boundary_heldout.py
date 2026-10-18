"""Author a predeclared blind alignment holdout; no model or truth adjustment."""
import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]


def main(output):
    output = output.resolve()
    assert output.is_relative_to(ROOT / 'docs/assets')
    output.mkdir(parents=True, exist_ok=False)
    ffmpeg = Path(shutil.which('ffmpeg')).resolve()
    words = 'LOCAL VIDEO EDITOR KEEPS EVERY ORIGINAL WORD'.split()
    gaps = [3200, 5600, 4000, 6400, 4800, 2400, 7200]
    pcm = bytearray(4800 * 2)
    truth, sources = [], []
    for word, gap in zip(words, gaps):
        source = output / (word.lower() + '-rms-raw.wav')
        command = [str(ffmpeg), '-v', 'error', '-nostdin', '-n', '-f', 'lavfi',
                   '-i', 'flite=text=' + word.lower() + ':voice=rms',
                   '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(source)]
        subprocess.run(command, check=True, capture_output=True)
        with wave.open(str(source), 'rb') as stream:
            assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 16000)
            raw = stream.readframes(stream.getnframes())
        samples = array('h', raw)
        if sys.byteorder != 'little':
            samples.byteswap()
        active = [i for i, x in enumerate(samples) if abs(x) >= 32]
        assert active
        first, last = active[0], active[-1] + 1
        start = len(pcm) // 2
        pcm.extend(raw[first * 2:last * 2])
        truth.append({'word': word, 'start_sample': start, 'end_sample': len(pcm) // 2})
        pcm.extend(bytes(gap * 2))
        sources.append({'word': word, 'file': source.name, 'trim_first_sample': first,
                        'trim_end_sample': last, 'following_gap_samples': gap, 'command': command})
    with wave.open(str(output / 'input.wav'), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(pcm)
    (output / 'transcript.txt').write_text(' '.join(words), encoding='utf-8', newline='\n')
    contract = ROOT / 'docs/specs/字词边界模型对照核验契约_v0.1_2026-10-18.md'
    report = {
        'format': 'boundary-heldout-authored-blocks-v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'created_before_candidate_inference': True, 'sample_rate': 16000,
        'samples': len(pcm) // 2, 'words': truth, 'voice': 'rms', 'word_sources': sources,
        'criterion': 'first/last absolute signed PCM >=32; authored blocks, not phonetic labels',
        'quality_goal': {'boundary_error_seconds_max': 2 / 30, 'predeclared_fps': 30},
        'rights': {'text_and_placement': 'CC0-1.0',
                   'speech': 'Flite CMU US rms; separate permissive attribution in docs/third-party/flite-source-20261018',
                   'not_a_human_voice_clone': True},
        'contract_sha256': hashlib.sha256(contract.read_bytes()).hexdigest(),
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ffmpeg_sha256': hashlib.sha256(ffmpeg.read_bytes()).hexdigest(),
        'static_review': False, 'continuous_playback_review': False, 'listening_review': False,
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / 'input-provenance.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n',
                                               encoding='utf-8', newline='\n')
    print(json.dumps({'samples': report['samples'], 'words': len(truth), 'voice': 'rms'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
