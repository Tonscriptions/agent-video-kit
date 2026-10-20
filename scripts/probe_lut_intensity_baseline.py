"""Reproduce the pre-V73 neutral-LUT error with native CPU FFmpeg."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.render import _effect_filters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT/'docs') and not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    project = ROOT/'product/.runtime/lut-intensity-baseline'
    project.mkdir(parents=True, exist_ok=True)
    lut = project/'neutral.cube'
    lut.write_text('LUT_3D_SIZE 2\n'+''.join(f'{r} {g} {b}\n' for b in (0,1) for g in (0,1) for r in (0,1)), encoding='utf8')
    exe = ffmpeg_path()
    original = bytes((32,96,192,128))*4
    record = {'kind':'pre-change-native-baseline','network':False,'virtualization':False,
              'ffmpeg':exe,'ffmpeg_sha256':hashlib.sha256(Path(exe).read_bytes()).hexdigest(),
              'cube_file_order':'red-fastest','input_rgba':[32,96,192,128], 'observations':[]}
    for strength in (0., .5, 1.):
        warnings=[]
        chain=_effect_filters([{'type':'lut3d','path':str(lut),'intensity':strength}], warnings, 'baseline', root=project)
        command=[exe,'-hide_banner','-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
                 '-video_size','2x2','-framerate','1','-i','pipe:0','-vf',','.join(chain) or 'null',
                 '-frames:v','1','-f','rawvideo','-pix_fmt','rgba','pipe:1']
        result=subprocess.run(command,input=original,capture_output=True,cwd=project)
        assert result.returncode==0,result.stderr.decode(errors='replace')
        record['observations'].append({'strength':strength,'pixel_rgba':list(result.stdout[:4]),
            'neutral_preserved':result.stdout==original,'chain':chain,'warnings':warnings})
    help_result=subprocess.run([exe,'-hide_banner','-h','filter=blend'],capture_output=True)
    (output.parent/'blend-help-baseline.txt').write_bytes(help_result.stdout+help_result.stderr)
    record['neutral_half_strength_bug_reproduced']=not record['observations'][1]['neutral_preserved']
    record['baseline_source_sha256']={name:hashlib.sha256((ROOT/'product/src/ai_ad_editor'/name).read_bytes()).hexdigest()
                                    for name in ('lut_library.py','render.py','effect_automation.py')}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'observations':[{'strength':x['strength'],'pixel_rgba':x['pixel_rgba']} for x in record['observations']],
                      'neutral_half_strength_bug_reproduced':record['neutral_half_strength_bug_reproduced']}))


if __name__=='__main__':main()
