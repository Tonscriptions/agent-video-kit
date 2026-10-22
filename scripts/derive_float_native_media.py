"""Adapt the already audited stereo demo to direct original-native windows."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'float-stream-lab-20261022'


def main():
    target = ROOT / 'scripts/smoke_float_native_media.py'
    assert not target.exists()
    value = (PARENT / 'scripts/smoke_float_stream_media.py').read_text('utf8')
    replacements = [
        ('Stream real 16-bit originals plus authored stereo sound; retain demos/proofs.',
         'Decode original-native windows to real authored stereo demos; no input float bundle.'),
        ('from ai_ad_editor.float_bundle_source import BundleSurfaceSource',
         'from ai_ad_editor.float_native_source import NativeSurfaceSource\nfrom ai_ad_editor.float_yuv import YUVSpec'),
        ('float-stream-20261022', 'float-render-20261022'),
        ('len(before)==292', 'len(before)==296'),
        ('all292 product inputs unchanged', 'all296 product inputs unchanged'),
        ('launches=[];encoders=[]', 'launches=[];encoders=[];source_receipts=[]'),
        ("'encoder_receipts':encoders,", "'encoder_receipts':encoders,'native_window_source_receipts':source_receipts,"),
        ('SHA-copied procedural V93 RGB/YUV16 originals/bundles plus newly authored stereo PCM; originals CC0',
         'SHA-copied procedural V93 RGB/YUV16 originals and explicit signal recipes; no input float bundles; newly authored stereo PCM; originals CC0'),
        ("        p=json.loads((source/'project.json').read_bytes());copied={}",
         "        p=json.loads((source/'project.json').read_bytes());copied={};specs={}"),
        ("            for original in sorted((source/'bundles'/name).iterdir()):\n                target=out/'bundles'/name/original.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target);assert sha(original)==sha(target);copied[target.relative_to(ROOT).as_posix()]=sha(target)",
         "            specification=json.loads((source/'bundles'/name/'bundle.json').read_bytes())['recipe']\n            specs[name]={k:specification[k] for k in ('source_signal','working_signal','pixel_family','YCbCr','scan','alpha_association')}\n            write(out/'source-specs'/(name+'.json'),specs[name]);copied[target.relative_to(ROOT).as_posix()]=sha(target)"),
        ("'two originals, six bundle files and historical pixel reference copied exactly',len(copied)==6",
         "'two registered originals and historical oracle copied exactly; no input float bundles',len(copied)==2 and not (out/'bundles').exists()"),
        ("                with BundleSurfaceSource(ROOT,out/'bundles/background',assets['background']) as background,BundleSurfaceSource(ROOT,out/'bundles/foreground',assets['foreground']) as foreground:",
         "                def open_source(name):\n                    spec=specs[name]\n                    return NativeSurfaceSource(ROOT,assets[name],source_signal=ColorSignal(**spec['source_signal']),working_signal=ColorSignal(**spec['working_signal']),yuv_spec=YUVSpec(**spec['YCbCr']) if spec['YCbCr'] else None,scan=spec['scan'],alpha_association=spec['alpha_association'],window_frames=2,cache_bytes=2*160*96*16)\n                with open_source('background') as background,open_source('foreground') as foreground:"),
        ("                check(name+' original input mmap handles closed and author IR unchanged',background.closed and foreground.closed and project==authored)",
         "                source_receipts.extend([copy.deepcopy(background.metadata),copy.deepcopy(foreground.metadata)])\n                check(name+' native inputs, owned windows, processes and locks closed; author IR unchanged',background.closed and foreground.closed and not background.guard.entries and not foreground.guard.entries and project==authored)\n                check(name+' both pixel caches stay within two native Float32 frames',all(s.metadata['maximum_cached_float_bytes']<=2*160*96*16 and not s.metadata['whole_movie_pixel_cache'] for s in (background,foreground)))"),
        ('procedural fixed V93 originals/bundles; newly authored stereo sine/chirp PCM',
         'procedural fixed V93 original RGB/YUV16 media; native window decoding; newly authored stereo sine/chirp PCM'),
        ('passed-real-bounded-FFV1-and-independent-authored-PCM',
         'passed-real-native-window-FFV1-and-independent-authored-PCM'),
    ]
    for old, new in replacements:
        assert old in value, old
        value = value.replace(old, new)
    compile(value, str(target), 'exec')
    target.write_text(value, encoding='utf8', newline='\n')
    print(target)


if __name__ == '__main__':
    main()
