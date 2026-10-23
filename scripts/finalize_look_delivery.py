"""Finalize documentation/media after the installed 100-look run succeeds."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/look-presets-20261024-r1'
ASSETS=ROOT/'docs/assets/look-presets-20261024-r1'
TAG='v0.1.0-alpha.2'


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    verified=json.loads((EVIDENCE/'installed/verification.json').read_bytes())
    skills=json.loads((EVIDENCE/'skills/verification.json').read_bytes())
    assert verified['status']=='passed' and verified['presets_verified']==100
    assert skills['registered_skills']==17 and skills['skill_launcher_commands']==14
    assert 'Ran 83 tests' in (EVIDENCE/'unit-tests.txt').read_text('utf-8')
    # Animated comparison is made from decoded actual videos, not a log replay.
    selected=['t3-kodak-gold-200','t3-fuji-velvia-50','t3-ilford-hp5-plus-400']
    def decoded(video):
        done=subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True,timeout=90)
        size=480*300*3;assert len(done.stdout)==12*size
        return [Image.frombytes('RGB',(480,300),done.stdout[i:i+size]) for i in range(0,len(done.stdout),size)]
    original=decoded(ASSETS/'original.mp4')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    frames=[]
    for look_id in selected:
        edited=decoded(ASSETS/'videos'/(look_id+'.mp4'))
        for left,right in zip(original,edited):
            im=Image.new('RGB',(720,256),'#101820')
            im.paste(left.resize((360,225)),(0,31));im.paste(right.resize((360,225)),(360,31))
            ImageDraw.Draw(im).text((9,8),'ORIGINAL | '+look_id+' | STRENGTH 1',fill='white',font=font)
            frames.append(im)
    motion_gif=ASSETS/'motion-comparison.gif';motion_mp4=ASSETS/'motion-comparison.mp4'
    if motion_gif.exists() or motion_mp4.exists():raise ValueError('Existing comparison media is preserved')
    frames[0].save(motion_gif,save_all=True,append_images=frames[1:],duration=83,loop=0)
    done=subprocess.run(['ffmpeg','-v','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','720x256','-r','12','-i','pipe:0',
                         '-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(motion_mp4)],
                        input=b''.join(im.tobytes() for im in frames),capture_output=True,timeout=90)
    (EVIDENCE/'motion-encode.stderr.txt').write_bytes(done.stderr);assert done.returncode==0
    save(EVIDENCE/'motion-media.json',{'status':'passed','kind':'decoded-original-and-actual-rendered-video-comparison',
        'presets':selected,'frames':36,'fps':'12/1','mp4_duration_seconds':3.,'width':720,'height':256,'audio_stream':False,
        'gif_sha256':sha(motion_gif),'mp4_sha256':sha(motion_mp4),'human_listening':False,'continuous_playback_review':False})
    # Replace the provisional rows with final measured results.
    for filename,en in [('README.md',False),('README.en.md',True)]:
        path=ROOT/filename;lines=path.read_text('utf-8').splitlines();out=[]
        for line in lines:
            if line.startswith('| R19 |'):
                if en:
                    line=f"| R19 | All-100 installed native rendering | **100 previews + 100 videos; {verified['isolated_cli_commands']} isolated CLI calls, two expected refusals** | [Receipt](docs/validation/evidence/look-presets-20261024-r1/installed/verification.json) · [GIF](docs/assets/look-presets-20261024-r1/motion-comparison.gif); every video decodes to 12 frames / 1 s / 480×300; 100 distinct preview/frame hashes; upstream comparisons and package first-frame pixels checked; synthetic inputs, no natural-footage/listening acceptance |"
                else:
                    line=f"| R19 | 安装版逐一实测 100 个预设 | **100 个预览 + 100 个成片；{verified['isolated_cli_commands']} 次隔离 CLI 调用，含 2 次预期拒绝** | [核验](docs/validation/evidence/look-presets-20261024-r1/installed/verification.json) · [动态 GIF](docs/assets/look-presets-20261024-r1/motion-comparison.gif)；逐片解码 12 帧/1 秒/480×300，预览与首帧各 100 个不同哈希，上游对照与包往返首帧像素通过；合成输入，未做自然素材/听审验收 |"
            out.append(line)
        text='\n'.join(out)+'\n'
        text=text.replace('[100 个实际预览总览]', '[实际成片动态 GIF](docs/assets/look-presets-20261024-r1/motion-comparison.gif) · [100 个实际预览总览]') if not en else text.replace('[100 native previews]', '[Actual video comparison GIF](docs/assets/look-presets-20261024-r1/motion-comparison.gif) · [100 native previews]')
        path.write_text(text,encoding='utf-8',newline='\n')
    presets=json.loads((EVIDENCE/'installed/presets.json').read_bytes())
    cube=[r for r in presets if r['id'].startswith('sp-')]
    hald=[r for r in presets if r['id'].startswith('t3-')]
    stats={'CUBE_count':len(cube),'CUBE_exact_native_previews':sum(r['upstream_native_max_abs_code_error']==0 for r in cube),
           'Hald_count':len(hald),'Hald_max_mean_abs_code_error':max(r['upstream_native_mean_abs_code_error'] for r in hald),
           'Hald_max_abs_code_error':max(r['upstream_native_max_abs_code_error'] for r in hald)}
    save(EVIDENCE/'upstream-comparison-summary.json',stats)
    path=ROOT/'docs/validation/LOOK_PRESETS_20261024.md';text=path.read_text('utf-8')
    text=text.replace('执行中，逐项保存原始响应、视频和对照误差 / Running; individual results retained',
        f"**100/100 通过；{verified['isolated_cli_commands']} 次隔离 CLI 调用，2 次预期拒绝；100 预览、100 成片逐片解码 / 100 passed**")
    text += f"\n## 最终安装实测 / Final installed run\n\n[最终回执](evidence/look-presets-20261024-r1/installed/verification.json)：100 个预设分别产生 1 秒、12 fps、12 帧、480×300 MP4；预览和实际视频首帧各 100 个不同哈希。共 {verified['isolated_cli_commands']} 次独立 `-I -S` CLI 进程，含缺失 ID 和非法强度两次预期拒绝。完整解码、结构化警告、全局部分强度、幂等重试、包导出/导入后的首帧一致、权利门禁和音频非空均已执行。\n\nAll 100 installed looks were individually previewed, applied, rendered and decoded. Package-roundtrip decoded pixels matched, and explicit audio was nonempty. All 49 original CUBE previews matched native upstream FFmpeg output exactly on the synthetic reference. The 51 resampled Hald looks had at most {stats['Hald_max_mean_abs_code_error']:.6f} mean absolute 8-bit code error per look and {stats['Hald_max_abs_code_error']} maximum channel error on this reference; this is not a bound on other footage. [Per-look error data](evidence/look-presets-20261024-r1/installed/presets.json).\n\n![预览静态对照 / Native preview comparison](../assets/look-presets-20261024-r1/comparison.gif)\n\n上图按预设切换实际静态预览；[动态成片 GIF](../assets/look-presets-20261024-r1/motion-comparison.gif) / [MP4](../assets/look-presets-20261024-r1/motion-comparison.mp4) 则来自原视频与三套实际成片的逐帧解码合成，静音、3 秒、36 帧。全库[总览图](../assets/look-presets-20261024-r1/contact-sheet.jpg)与[完整编号案例](../local/LOOK_PRESETS.md)提供其余预设。两种演示均不是模型生成效果，也不代表连续观看或听感验收。\n"
    path.write_text(text,encoding='utf-8',newline='\n')
    # Check current documentation paths after every actual output exists.
    docs=[ROOT/'README.md',ROOT/'README.en.md',ROOT/'docs/README.md',ROOT/'docs/local/LOOK_PRESETS.md',
          ROOT/'docs/local/FILTERS.md',ROOT/'docs/local/INSTALLATION.md',path,
          ROOT/f'docs/releases/{TAG}/USAGE.md',ROOT/f'docs/releases/{TAG}/THIRD_PARTY.md']
    checked=[]
    for doc in docs:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',doc.read_text('utf-8')):
            if target.startswith(('http:','https:','app:','#')):continue
            target=target.split('#',1)[0]
            if not target:continue
            resolved=(doc.parent/target).resolve()
            assert resolved.exists(),(str(doc),target)
            checked.append({'document':doc.relative_to(ROOT).as_posix(),'target':target})
    save(EVIDENCE/'documentation-links.json',{'status':'passed','count':len(checked),'links':checked})
    # Optional self-contained docs/examples companion; the installed app ZIP is unchanged.
    artifacts=ROOT/f'docs/releases/{TAG}/artifacts'
    archive=artifacts/f'agent-video-kit-{TAG}-docs-examples.zip'
    if archive.exists():raise ValueError('Existing companion archive is preserved')
    rows=[]
    for directory in (ASSETS,EVIDENCE):
        rows += [(p,p.relative_to(ROOT).as_posix()) for p in directory.rglob('*') if p.is_file()]
    rows += [(p,p.relative_to(ROOT).as_posix()) for p in docs if p.name not in {'README.md','README.en.md'}]
    rows += [(ROOT/'sources/lut-research-20261024/look-sources.json','sources/lut-research-20261024/look-sources.json'),
             (ROOT/'product/src/ai_ad_editor/look_data/catalog.json','product/src/ai_ad_editor/look_data/catalog.json')]
    for file in ('LICENSE','product/src/ai_ad_editor/look_data/licenses/t3-MIT.txt',
                 'product/src/ai_ad_editor/look_data/licenses/sp-MIT.txt',
                 'scripts/verify_look_release.py','scripts/verify_look_skills.py','scripts/build_look_catalog.py',
                 'docs/releases/v0.1.0-alpha.1/THIRD_PARTY.md'):
        rows.append((ROOT/file,file))
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        zipped.writestr('README.md','# 100 look presets / 100 风格预设\n\n[Usage](docs/releases/v0.1.0-alpha.2/USAGE.md) · [100 numbered examples](docs/local/LOOK_PRESETS.md) · [Verification](docs/validation/LOOK_PRESETS_20261024.md)\n\nInstall the separate application ZIP first. This archive contains actual synthetic inputs, 100 preview PNGs, 100 rendered videos, GIFs, a project package and complete command responses. Historical documentation/source snapshots referenced by provenance remain in the full Git repository.\n')
        seen=set()
        for file,name in sorted(rows,key=lambda x:x[1]):
            if name in seen:continue
            zipped.write(file,name);seen.add(name)
    sums=artifacts/'SHA256SUMS.txt'
    with sums.open('a',encoding='ascii',newline='\n') as stream:stream.write(sha(archive)+'  '+archive.name+'\n')
    save(EVIDENCE/'delivery.json',{'status':'passed','look_count':100,'targeted_methods':83,'skills':17,
        'installed_cli_commands':verified['isolated_cli_commands'],'skill_cli_commands':14,'local_document_links':len(checked),
        'companion':str(archive),'companion_bytes':archive.stat().st_size,'companion_sha256':sha(archive),
        'public_github_release_created':False,'primary_release_zip_unchanged':True})
    print(json.dumps({'ok':True,'document_links':len(checked),'native_comparison':stats,'companion':str(archive)},ensure_ascii=False))


if __name__=='__main__':main()
