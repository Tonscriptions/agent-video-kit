"""Plot actual encoded PCM and publish a silent evidence carousel and AAC preview."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def run(media,output,work):
    for p in (output,work):p.mkdir(parents=True,exist_ok=False)
    os.environ.update(MPLCONFIGDIR=str(work/'matplotlib'),TEMP=str(work),TMP=str(work),TMPDIR=str(work))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image
    shutil.copyfile(Path(__file__),output/'executed-preview.py');receipt=json.loads((media/'verification.json').read_bytes())
    records={r['id']:r for r in receipt['records']};calls=[]
    def command(args,label):
        p=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,timeout=120)
        stdout=output/(label+'.stdout.gz');stderr=output/(label+'.stderr.log')
        stdout.write_bytes(gzip.compress(p.stdout,mtime=0));stderr.write_bytes(p.stderr)
        calls.append({'label':label,'command':list(map(str,args)),'exit_code':p.returncode,'stdout':stdout.name,'stderr':stderr.name,
            'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'decoded_stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest()})
        if p.returncode:raise ValueError(label+' failed '+p.stderr.decode('utf-8','replace'))
        return p.stdout
    def pcm(path,label):
        return np.frombuffer(command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-ac','2','-ar','48000','-f','f32le','pipe:1'],label),'<f4').reshape(-1,2)
    values={}
    for case_id in ('C01','C02','C06','C07'):
        for variant in ('zero','context'):
            values[case_id,variant]=pcm(media/records[case_id]['variants'][variant]['media'],case_id+'-'+variant)[:12000]
    original=pcm(media/'stereo-tones.wav','original-tones')[9648:9840]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':True,'grid.alpha':.2,'figure.facecolor':'#f6f8fa','axes.facecolor':'white'})
    blue,orange='#1769aa','#d8641c';paths=[]
    fig,axes=plt.subplots(3,1,figsize=(11.2,8.4),dpi=100)
    fig.suptitle('C01 | Real source handles improve this 4 ms tone control',fontsize=17,fontweight='bold')
    for ax,array,title,ms in zip(axes,[original,values['C01','zero'],values['C01','context']],
            ['Original selected source: 192 samples / 4 ms','Zero context: actual encoded output (first 20 ms of 250 ms)',
             'Explicit 64 ms real context + apart: actual output (first 20 ms)'],[4,20,20]):
        n=min(len(array),round(ms*48));x=np.arange(n)/48
        ax.plot(x,array[:n,0],color=blue,label='Left');ax.plot(x,array[:n,1],color=orange,label='Right',alpha=.85)
        ax.set_title(title,loc='left');ax.set_xlabel('Time (ms); source and output axes differ');ax.set_ylabel('Float amplitude');ax.legend(loc='upper right',ncols=2)
    fig.text(.05,.018,'Real decoded PCM. Not a GUI capture. Adjacent source can alter transients/phase; natural sound and listening are unaccepted.',fontsize=10)
    fig.tight_layout(rect=(.02,.05,.98,.94));paths.append(output/'waveforms.png');fig.savefig(paths[-1]);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11.2,8.4),dpi=100)
    fig.suptitle('C01 | Pitch gate remains +/-5 Hz, independently per channel',fontsize=17,fontweight='bold')
    for channel,ax in enumerate(axes):
        for variant,color,label in [('zero',orange,'Zero context'),('context',blue,'64 ms real context + apart')]:
            a=values['C01',variant][1500:10500,channel].astype(np.float64);power=np.abs(np.fft.rfft(a*np.hanning(len(a)),n=262144));hz=np.fft.rfftfreq(262144,1/48000)
            ax.plot(hz,power/power.max(),color=color,label=label)
        expected=400 if channel==0 else 800;ax.axvspan(expected-5,expected+5,color='#b7e4c7',alpha=.7,label='Declared +/-5 Hz band')
        ax.set_xlim(expected-70,expected+70);ax.set_ylim(0,1.1);ax.set_title(('Left' if channel==0 else 'Right')+f' | generated original target {expected} Hz',loc='left')
        ax.set_xlabel('Frequency (Hz)');ax.set_ylabel('Spectrum normalized per curve');ax.legend(loc='upper right')
    z=records['C01']['variants']['zero']['peaks_hz'];c=records['C01']['variants']['context']['peaks_hz']
    fig.text(.05,.025,f'Actual peaks: zero {z[0]:.3f}/{z[1]:.3f} Hz; context {c[0]:.3f}/{c[1]:.3f} Hz. Normalization is not loudness evidence.',fontsize=10)
    fig.tight_layout(rect=(.02,.06,.98,.94));paths.append(output/'spectra.png');fig.savefig(paths[-1]);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11.2,8.4),dpi=100)
    fig.suptitle('Negative controls stay failed | Pitch, phase and listening differ',fontsize=17,fontweight='bold')
    a=values['C02','context'][1500:10500,1].astype(np.float64);p=np.abs(np.fft.rfft(a*np.hanning(len(a)),n=262144));hz=np.fft.rfftfreq(262144,1/48000)
    axes[0].plot(hz,p/p.max(),color=orange);axes[0].axvspan(795,805,color='#b7e4c7',alpha=.7);axes[0].set_xlim(750,850)
    axes[0].set_title('C02 together + 64 ms: right peak 789.368 Hz still fails 800 +/-5 Hz',loc='left');axes[0].set_xlabel('Frequency (Hz)');axes[0].set_ylabel('Normalized spectrum')
    for variant,color in [('zero',orange),('context',blue)]:
        a=values['C06',variant];axes[1].plot(np.arange(len(a))/48,a.sum(axis=1),color=color,label=variant+' apart',linewidth=.8)
    axes[1].set_title('C06 antiphase: max |L+R| 0.050574 -> 0.002460; exact cancellation still fails',loc='left')
    axes[1].set_xlabel('Output time (ms)');axes[1].set_ylabel('Left + Right float amplitude');axes[1].legend(loc='upper right')
    fig.text(.05,.025,'C07 together preserves exact L+R=0 in this control. Synthetic tones only. No continuous playback or listening review.',fontsize=10)
    fig.tight_layout(rect=(.02,.06,.98,.94));paths.append(output/'retained-failures.png');fig.savefig(paths[-1]);plt.close(fig)
    images=[Image.open(p).convert('RGB') for p in paths]
    images[0].save(output/'comparison.gif',save_all=True,append_images=images[1:],duration=[2000]*3,loop=0,optimize=True)
    contact=Image.new('RGB',(1120,2520),'white')
    for i,im in enumerate(images):contact.paste(im,(0,840*i));im.close()
    contact.save(output/'contact.png')
    command(['ffmpeg','-nostdin','-v','error','-i',media/'C01-context.mkv','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',output/'C01-context-aac-preview.mp4'],'aac-preview')
    probe=json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',output/'C01-context-aac-preview.mp4'],'preview-probe'))
    with Image.open(output/'comparison.gif') as gif:
        durations=[]
        for i in range(gif.n_frames):gif.seek(i);durations.append(gif.info['duration'])
        meta={'frames':gif.n_frames,'duration_ms':sum(durations),'frame_durations_ms':durations,'width':gif.width,'height':gif.height,'audio':False}
    files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in [*paths,output/'comparison.gif',output/'contact.png',output/'C01-context-aac-preview.mp4']}
    save(output/'verification.json',{'status':'built_actual_pcm_statistics_preview','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'input_receipt_sha256':sha(media/'verification.json'),'gif':meta,'aac_preview_probe':probe,'files':files,'calls':calls,
        'plot_source':'actual decoded original and encoded float32 PCM','spectra_normalized_individually':True,
        'gui_recording':False,'new_model_inference':False,'continuous_playback':False,'audio_listened':False,
        'aac_used_for_bit_exact_evidence':False,'generator_sha256':sha(output/'executed-preview.py')})
    print(json.dumps({'status':'built_actual_pcm_statistics_preview','gif':meta}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('media','output','work'):p.add_argument('--'+name,type=Path,required=True)
    run(**{k:v.resolve() for k,v in vars(p.parse_args()).items()})
