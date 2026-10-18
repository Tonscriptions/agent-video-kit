"""Independently remeasure pinned FGT research and publish only original media."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_fragments import frozen, save, sha
from run_fgt_research import command, decode


def measure(value, truth, selection):
    """Integer row accumulation, independent of runner's rolled-array scoring."""
    import numpy as np
    result=[]
    error=value[:,:,:,:3].astype(np.int32)-truth[:,:,:,:3].astype(np.int32)
    stats=[]
    for name, start, stop, dx in [('upper',0,144,2),('lower',144,240,-3)]:
        square=total=temporal=count=0
        for t in range(len(value)):
            for y in range(start,stop):
                xs=np.flatnonzero(selection[t,y])
                samples=error[t,y,xs].astype(np.int64)
                square+=int((samples*samples).sum()); total+=samples.size
                if t:
                    old_x=xs-dx
                    valid=(old_x>=0)&(old_x<value.shape[2])
                    xs,old_x=xs[valid],old_x[valid]
                    both=selection[t-1,y,old_x]
                    deltas=error[t,y,xs[both]]-error[t-1,y,old_x[both]]
                    temporal+=int(np.abs(deltas).sum()); count+=deltas.size
        stats.append((square,total,temporal,count))
        result.append({'region':name,'mse':square/total,'temporal':temporal/count,'rgb_samples':total,'temporal_rgb_samples':count})
    summed=tuple(sum(v[i] for v in stats) for i in range(4))
    result.append({'region':'overall','mse':summed[0]/summed[1],'temporal':summed[2]/summed[3],
                   'rgb_samples':summed[1],'temporal_rgb_samples':summed[3]})
    for row in result: row['psnr']=float(10*np.log10(255.**2/row['mse']))
    return result


def verify_upstream(audit, work):
    records=[]
    expected={'Kunbyte-AI__ROSE':('6be41c5420bf331c6d491277d5a6feaf9b3a779a','09543caea118949b4fcb4cae1dca125c0e737ae525f1a0509e8a54bca130821d'),
              'hitachinsk__FGT':('b6b01e3fc82931e050cf4d7062f3879f70677bad','7ba923312a8d1edde47bdce7fed5701389e6e0b9430051f31fb0c453ebabb4d7')}
    for name,(commit,digest) in expected.items():
        directory=audit/name; archive=directory/(commit+'.zip')
        assert sha(archive)=='sha256:'+digest
        acquired=json.loads((directory/'acquisition.json').read_text())
        assert acquired['commit']==commit and acquired['archive_sha256']==digest
        with zipfile.ZipFile(archive) as bundle:
            for entry in acquired['selected']:
                data=bundle.read(name.split('__',1)[1]+'-'+commit+'/'+entry['path'])
                assert hashlib.sha256(data).hexdigest()==entry['sha256']
                assert (directory/'source'/entry['path']).read_bytes()==data
        records.append({'repository':acquired['repository'],'commit':commit,'archive_sha256':'sha256:'+digest,
                        'archive_bytes':archive.stat().st_size,'selected_source_files_checked':len(acquired['selected'])})
    original=audit/'hitachinsk__FGT/source'
    differences=[]
    for path in sorted((work/'source').rglob('*')):
        if path.is_file() and path.read_bytes()!=(original/path.relative_to(work/'source')).read_bytes():
            differences.append(path.relative_to(work/'source').as_posix())
    assert differences==['tool/video_inpainting.py']
    return {'sources':records,'fgt_changed_files':differences,'patch_sha256':sha(work/'compatibility.patch')}


def panels(arrays, labels, *, indices=None):
    from PIL import Image, ImageDraw
    indices=range(len(arrays[0])) if indices is None else indices
    n,h,w,_=arrays[0].shape; output=[]
    for t in indices:
        canvas=Image.new('RGB',(w*len(arrays),h+24),(24,26,33)); draw=ImageDraw.Draw(canvas)
        for i,(array,label) in enumerate(zip(arrays,labels)):
            canvas.paste(Image.fromarray(array[t,:,:,:3]),(i*w,24))
            draw.text((i*w+6,5),f'{label} | frame {t:02}',fill='white')
        output.append(canvas)
    return output


def publish(public,natural,audit,output,evidence):
    import numpy as np
    from PIL import Image
    assert not output.exists() and not evidence.exists()
    records=[json.loads((directory/'verification.json').read_text()) for directory in (public,natural)]
    for directory,record in zip((public,natural),records):
        assert json.loads((directory/'product-before.json').read_text())==frozen()==json.loads((directory/'product-after.json').read_text())
        assert record['runner_sha256']==sha(ROOT/'scripts/run_fgt_research.py')
        assert record['worker_sha256']==sha(ROOT/'research/temporal-neural/fgt_worker.py')
        assert record['contract_sha256']==sha(ROOT/'docs/specs/开源时序修复候选核验契约_v0.1_2026-10-18.md')
        assert record['parent_network']=='disabled' and not record['parent_blocked_network_events']
        worker=record['worker']; assert worker['status']=='succeeded' and not worker['blocked_network_events']
        assert worker['model_calls']=={'RAFT':62,'LAFC':62,'FGT':7}
        assert len(worker['loaded_checkpoints'])==3 and all(x['weights_only'] for x in worker['loaded_checkpoints'])
        request=json.loads((directory/'request.json').read_text())
        for item in request['frozen_files']: assert sha(Path(item['path']))==item['sha256']
    assert records[0]['controlled_quality_passed']
    source=np.load(public/'input.npy',allow_pickle=False)
    truth=np.load(public/'independent-truth.npy',allow_pickle=False)
    selected=np.load(public/'effective-selection.npy',allow_pickle=False)
    final=np.load(public/'final.npy',allow_pickle=False)
    baseline=np.load(public/'lama.npy',allow_pickle=False)
    independent={}
    for name,value in [('fgt',final),('lama',baseline)]:
        measured=measure(value,truth,selected); independent[name]=measured
        for row,saved in zip(measured,records[0][name+'_scores']):
            assert abs(row['mse']-saved['masked_mse'])<1e-12
            assert abs(row['psnr']-saved['masked_psnr_db'])<1e-9
            assert abs(row['temporal']-saved['known_motion_residual_mae_rgb'])<1e-12
            assert row['temporal_rgb_samples']==saved['temporal_samples_rgb']
    # Re-check original alpha and unselected pixels from actual encoded outputs.
    for directory,record in zip((public,natural),records):
        original=np.load(directory/'input.npy',allow_pickle=False)
        mask=np.load(directory/'effective-selection.npy',allow_pickle=False)
        value=decode(directory/'final.mov',record['frames'],record['height'],record['width'])
        assert np.array_equal(value,np.load(directory/'final.npy',allow_pickle=False))
        assert np.array_equal(value[:,:,:,3],original[:,:,:,3])
        assert np.array_equal(value[:,:,:,:3][~mask],original[:,:,:,:3][~mask])
    upstream=verify_upstream(audit,public)
    assert sha(public/'compatibility.patch')==sha(natural/'compatibility.patch')
    acquired=json.loads((audit/'fgt-model-acquisition.json').read_text())
    for item in acquired['files']: assert sha(audit/'fgt-weights'/item['path'])=='sha256:'+item['sha256']
    output.mkdir(parents=True); evidence.mkdir(parents=True)
    lossless=[]
    for name in ('source.mov','truth.mov','lama.mov','final.mov'):
        target=output/(Path(name).stem+'-lossless.mp4')
        command(['ffmpeg','-nostdin','-v','error','-i',public/name,'-an','-c:v','libx264rgb','-crf','0','-preset','slow','-pix_fmt','rgb24','-movflags','+faststart',target])
        original=decode(public/name,32,240,432); actual=decode(target,32,240,432)
        assert np.all(original[:,:,:,3]==255) and np.array_equal(original,actual)
        from fractions import Fraction
        pts=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=pts_time','-of','json',target]))
        assert [Fraction(x['pts_time']) for x in pts['frames']]==[Fraction(i,8) for i in range(32)]
        lossless.append({'path':target.name,'decoded_rgba_sha256':'sha256:'+hashlib.sha256(actual.tobytes()).hexdigest(),'rgba_bytes':actual.nbytes,'every_pts_exact':True})
        command(['ffmpeg','-nostdin','-v','error','-i',public/name,'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',output/Path(name).with_suffix('.mp4')])
    frames=panels([source,baseline,final,truth],['INPUT','LaMa framewise','FGT research','INDEPENDENT TRUTH'])
    pixels=np.stack([np.asarray(frame) for frame in frames])
    command(['ffmpeg','-nostdin','-v','error','-f','rawvideo','-pix_fmt','rgb24','-video_size',f'{pixels.shape[2]}x{pixels.shape[1]}','-framerate','8','-i','pipe:0','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',output/'comparison.mp4'],data=pixels.tobytes())
    gif_source=[frame.resize((frame.width//2,frame.height//2),Image.Resampling.LANCZOS) for frame in frames]
    palette=gif_source[0].quantize(colors=64).getpalette()
    palette_image=Image.new('P',(1,1)); palette_image.putpalette(palette)
    gifs=[frame.quantize(palette=palette_image,dither=Image.Dither.NONE) for frame in gif_source]
    gifs[0].save(output/'comparison.gif',save_all=True,append_images=gifs[1:],duration=[120,130]*16,loop=0,disposal=2,optimize=False)
    with Image.open(output/'comparison.gif') as gif:
        durations=[]
        for i in range(gif.n_frames): gif.seek(i); durations.append(gif.info['duration'])
        assert gif.n_frames==32 and sum(durations)==4000
    contact=Image.new('RGB',(frames[0].width,frames[0].height*4))
    for i,t in enumerate((0,10,21,31)): contact.paste(frames[t],(0,i*frames[0].height))
    contact.save(output/'contact.png')
    nat_source=np.load(natural/'input.npy',allow_pickle=False)
    nat_final=np.load(natural/'final.npy',allow_pickle=False)
    project=ROOT/'product/.runtime/mask-edit-natural-20261018/project'
    assets={x['id']:project/x['uri'] for x in json.loads((project/'project.json').read_text(encoding='utf-8'))['assets']}
    nat_lama=decode(assets['repaired'],32,288,512)
    private=panels([nat_source,nat_lama,nat_final],['SOURCE private','LaMa historical','FGT research'],indices=[0,10,21,31])
    contact_private=Image.new('RGB',(private[0].width,private[0].height*4))
    for i,frame in enumerate(private): contact_private.paste(frame,(0,i*frame.height))
    contact_private.save(natural/'private-contact.png')
    # Public artifacts contain no frames, masks, truth or previews from the private case.
    for label,directory in [('public',public),('natural',natural)]:
        for name in ('verification.json','worker-response.json','worker.log','product-before.json','product-after.json','compatibility.patch'):
            shutil.copyfile(directory/name,evidence/(label+'-'+name))
    failure=ROOT/'product/.runtime/fgt-public-dev1-20261018'
    for name in ('failure.json','product-before.json','product-after.json'):
        shutil.copyfile(failure/name,evidence/('development-1-'+name))
    shutil.copyfile(public/'lama.json',evidence/'public-lama.json')
    shutil.copyfile(audit/'verification.json',evidence/'repository-acquisition.json')
    shutil.copyfile(audit/'fgt-model-acquisition.json',evidence/'fgt-model-acquisition.json')
    shutil.copyfile(audit/'rose-native-import.json',evidence/'rose-native-import.json')
    acquisition_files=[]
    for path in sorted(audit.rglob('*')):
        if path.is_file() and ('/source/' not in path.as_posix()) and (path.name in {'repository.json','commit.json','tree.json','metadata.json'} or path.name.endswith('.blob.json')):
            relative=path.relative_to(audit); target=evidence/'upstream'/relative
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
            acquisition_files.append({'path':target.relative_to(evidence).as_posix(),'sha256':sha(target)})
    with zipfile.ZipFile(evidence/'developer-acquisition-scripts.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in ('temporal_model_probe_20261018.py','acquire_temporal_sources_20261018.py','probe_temporal_weights_20261018.py','fetch_fgt_development_20261018.py','probe_rose_import_20261018.py'):
            archive.write(ROOT/'product/.runtime'/name,name)
    save(evidence/'independent-remeasurement.json',independent)
    save(evidence/'source-verification.json',upstream)
    for target in (output/'provenance.json',):
        save(target,{'source':'original procedural fixture authored in scripts/run_fgt_research.py','source_truth_license':'CC0-1.0',
                     'model_outputs':'actual local FGT/LaMa research; not an approved commercial content library asset',
                     'frames':32,'fps':'8/1','duration_seconds':4,'audio':False,'gif_frame_durations_ms':durations,
                     'lossless_originals':lossless,'lossless_encoding':'libx264rgb CRF 0; this fixture is fully opaque; decoded RGBA exact',
                     'display_mp4_and_gif':'YUV420 MP4 / half-size 64-color GIF; not byte-accuracy references','natural_pixels_published':False})
    record={'status':'execution_verified_controlled_gate_passed_natural_unaccepted','research_only':True,'product_integrated':False,
            'production_files_frozen':len(frozen()),'production_sha256':frozen(),
            'full_product_regression_rerun':False,'last_full_product_regression':{'batch':'V43','passed':1005,'skipped':0},
            'controlled':records[0],'natural':records[1],'independent_remeasurement':independent,'upstream_verification':upstream,
            'model_calls_this_batch':{'RAFT':124,'LAFC':124,'FGT':14,'LaMa':32,'ROSE':0},
            'new_natural_source_scenes':0,'new_controlled_sequences':1,'developer_first_attempt_model_calls':0,
            'developer_failure_preserved':True,'public_files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()],
            'acquisition_evidence_files':acquisition_files,'collector_sha256':sha(Path(__file__)),'continuous_playback_reviewed':False,'audio_listening_reviewed':False}
    save(evidence/'verification.json',record)
    print(json.dumps({'status':record['status'],'public_files':len(record['public_files']),'production_frozen':len(frozen()),'calls':record['model_calls_this_batch']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',type=Path,required=True); parser.add_argument('--natural',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args(); publish(*[getattr(args,name).resolve() for name in ('public','natural','audit','output','evidence')])
