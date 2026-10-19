"""Real local long-to-short editing with supplied whole-sentence source ranges."""
import argparse
import json
from pathlib import Path
import wave
import numpy as np
from PIL import Image,ImageDraw
from openfilm_workflow_evidence import Evidence,FPS,H,ROOT,SR,TPS,W,append,digest,font,save,sha,wav

TEXTS=[
    'If the source is local, the editor can process it offline.',
    'We do not claim that every automatic caption is correct.',
    'The final export keeps the original meaning and the complete answer.',
]


def run(work,output):
    evidence=Evidence(work,output,Path(__file__));error=None;measurements={}
    try:
        label_font=font(evidence.output)
        save(evidence.output/'provenance.json',{'original_text_and_procedural_background':'CC0-1.0',
            'voice':'local FFmpeg flite output; unverified output rights; internal only',
            'public_previews':'silent RGB picture only; no generated speech distributed',
            'font_notice':'LICENSE_DEJAVU','font_license':'Bitstream-Vera',
            'transcript_source':'known text supplied directly to local TTS; not ASR or acoustic word alignment'})
        speech=evidence.project('speech-source',1); pieces=[]; spans=[];cursor=SR//2
        for index,text in enumerate(TEXTS):
            rel=f'assets/utterance-{index}.wav'
            evidence.cli('tts','synthesize','--project',speech,'--text',text,'--voice','slt','--output',rel,
                         '--sample-rate',SR,'--channels','2')
            path=speech/rel
            with wave.open(str(path),'rb') as reader:
                if reader.getnchannels()!=2 or reader.getframerate()!=SR or reader.getsampwidth()!=2:raise ValueError('unexpected speech PCM format')
                pcm=np.frombuffer(reader.readframes(reader.getnframes()),'<i2').reshape(-1,2).copy()
            # Silence pads are an explicit authored segmentation boundary; no phonetic claim.
            span_start=(cursor//(SR//FPS))*(SR//FPS)
            span_end=((cursor+len(pcm)+(SR//FPS)-1)//(SR//FPS))*(SR//FPS)
            spans.append({'id':f'line-{index}','text':text,'speech_start_sample':cursor,'speech_end_sample':cursor+len(pcm),
                          'range_start_sample':span_start,'range_end_sample':span_end,
                          'start_tick':span_start*TPS//SR,'end_tick':span_end*TPS//SR,
                          'tts_output_sha256':sha(path),'manual_range_basis':'whole generated utterance plus CFR-aligned silence'})
            pieces.append((cursor,pcm));cursor=span_end+SR
        total=((cursor+SR//FPS-1)//(SR//FPS))*(SR//FPS)
        source_pcm=np.zeros((total,2),dtype='<i2')
        for start,pcm in pieces:source_pcm[start:start+len(pcm)]=pcm
        local_audio=evidence.work/'original-speech.wav';wav(local_audio,source_pcm)
        source_frames=[]
        for number in range(total//(SR//FPS)):
            current=next((i for i,s in enumerate(spans) if s['range_start_sample']<=number*(SR//FPS)<s['range_end_sample']),None)
            image=Image.new('RGB',(W,H),(18,27,40));draw=ImageDraw.Draw(image)
            draw.text((26,22),'LOCAL LONG RECORDING / SUPPLIED TEXT',font=label_font,fill=(230,236,246))
            draw.text((26,75),f'SOURCE FRAME {number:03}',font=label_font,fill=(160,180,210))
            if current is None:draw.text((26,150),'PAUSE',font=label_font,fill=(120,135,160))
            else:
                draw.rectangle((26,140,614,245),fill=((40,95,145),(126,66,70),(61,105,74))[current])
                draw.text((42,178),f'COMPLETE STATEMENT {current+1}',font=label_font,fill='white')
            for bit in range(10):
                draw.rectangle((26+bit*20,302,39+bit*20,320),fill='white' if number&(1<<bit) else 'black')
            source_frames.append(np.asarray(image))
        frames=np.stack(source_frames);source=evidence.work/'original-speech.mkv'
        evidence.ffmpeg('-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0',
                        '-i',local_audio,'-c:v','ffv1','-pix_fmt','bgr0','-c:a','pcm_s16le',source,data=frames.tobytes())
        # Public original is silent; the exact AV source and all spoken outputs remain local.
        evidence.ffmpeg('-i',source,'-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p',evidence.output/'original-silent.mp4')
        save(evidence.output/'supplied-transcript.json',{'format':'supplied-whole-utterance-ranges-v1','sample_rate':SR,'source_sha256':sha(source),
            'source_audio_sha256':sha(local_audio),'source_frames':len(frames),'lines':spans,'asr_performed':False,'phonetic_word_boundaries_accepted':False})
        cases=[]
        for index,chosen in enumerate(((0,),(1,2))):
            project=evidence.project(f'short-{index+1}',sum(spans[i]['end_tick']-spans[i]['start_tick'] for i in chosen)/TPS)
            evidence.ingest(project,source,'recording',verified=False)
            operations=[];at=0;indices=[];audio_chunks=[]
            for i in chosen:
                row=spans[i];duration=row['end_tick']-row['start_tick']
                operations.append(append('recording',f'source-line-{i}','track_video_1',at,duration,source=row['start_tick'],link_id=f'pair-{i}'))
                operations.append(append('recording',f'source-audio-{i}','track_audio_1',at,duration,source=row['start_tick'],link_id=f'pair-{i}'))
                indices.extend(range(row['range_start_sample']//(SR//FPS),row['range_end_sample']//(SR//FPS)))
                audio_chunks.append(source_pcm[row['range_start_sample']:row['range_end_sample']].astype(np.float32)/32768)
                at+=duration
            evidence.compose(project,f'short-{index+1}',operations)
            evidence.cli('rights','check','--project',project,expected=7)
            target=evidence.render(project,f'short-{index+1}-base',publish=False,public_video=False)
            local_pcm=evidence.work/f'short-{index+1}-base.f32'
            evidence.ffmpeg('-i',target,'-map','0:a:0','-vn','-ar',SR,'-ac','2','-f','f32le',local_pcm)
            actual_audio=np.fromfile(local_pcm,'<f4').reshape(-1,2);expected_audio=np.concatenate(audio_chunks)
            actual_video=evidence.video(target);expected_video=frames[indices]
            if actual_video.shape!=expected_video.shape or actual_audio.shape!=expected_audio.shape:raise ValueError('short source range duration mismatch')
            rgb=int(np.max(np.abs(actual_video.astype(np.int16)-expected_video.astype(np.int16))))
            pcm_error=float(np.max(np.abs(actual_audio-expected_audio)))
            if rgb>2 or pcm_error>2e-6:raise ValueError(f'short identity mismatch RGB={rgb}, PCM={pcm_error}')
            # Caption full original sentences, split for display with the existing local segmenter.
            evidence.cli('media','ingest','--project',project,'--input',evidence.output/'DejaVuSans.ttf','--asset-id','font',
                         '--license-spdx','Bitstream-Vera','--verification-status','verified','--permitted-use','commercial_ad',
                         '--creator','DejaVu and Bitstream authors','--evidence',evidence.output/'LICENSE_DEJAVU')
            evidence.compose(project,f'short-{index+1}-caption-track',[{'op':'add_track','track_id':'captions','kind':'subtitle','order':10}])
            caption_source=evidence.work/f'short-{index+1}-captions.json';at=0;lines=[]
            for i in chosen:
                row=spans[i];duration=row['end_tick']-row['start_tick'];lines.append({'id':row['id'],'text':row['text'],'start_tick':at,'end_tick':at+duration});at+=duration
            save(caption_source,{'format':'agent-subtitle-source-v1','ticks_per_second':TPS,'lines':lines})
            evidence.cli('subtitle','segment','--project',project,'--input',caption_source,'--output','assets/subtitles/display.json',
                         '--apply','--track-id','captions','--font-asset-id','font','--source-asset-id','recording')
            caption_project=json.loads((project/'project.json').read_bytes())
            caption_clips=next(track for track in caption_project['sequences'][0]['tracks'] if track['id']=='captions')['clips']
            patches=[]
            from PIL import ImageFont
            caption_font=ImageFont.truetype(str(evidence.output/'DejaVuSans.ttf'),24)
            for caption in caption_clips:
                text=caption['subtitle']['text']
                if caption_font.getlength(text)>W-48:raise ValueError('authored caption exceeds explicit horizontal safe width')
                subtitle=caption['subtitle']
                subtitle['style']={**subtitle.get('style',{}),'font_asset_id':'font','fontsize':24,
                    'fontcolor':'white','borderw':2,'bordercolor':'black','x':'(w-text_w)/2','y':'h-text_h-24'}
                patches.append({'op':'update_clip','clip_id':caption['id'],'track_id':'captions','patch':{'subtitle':subtitle}})
            evidence.compose(project,f'short-{index+1}-readable-captions',patches)
            shutil_path=project/'assets/subtitles/display.json'
            (evidence.output/f'short-{index+1}-display.json').write_bytes(shutil_path.read_bytes())
            (evidence.output/f'short-{index+1}-display.srt').write_bytes(shutil_path.with_suffix('.srt').read_bytes())
            # Output rights intentionally stay unverified; internal render must not become a public speech delivery.
            target=evidence.render(project,f'short-{index+1}',publish=False,public_video=False)
            # Decode checks write speech PCM only to ignored local evidence, not the public call archive.
            local_pcm=evidence.work/f'short-{index+1}.f32'
            evidence.ffmpeg('-i',target,'-map','0:a:0','-vn','-ar',SR,'-ac','2','-f','f32le',local_pcm)
            caption_audio=np.fromfile(local_pcm,'<f4').reshape(-1,2);caption_video=evidence.video(target)
            if caption_audio.shape!=actual_audio.shape or not np.array_equal(caption_audio,actual_audio):raise ValueError('captions changed source PCM')
            if caption_video.shape!=actual_video.shape or np.array_equal(caption_video,actual_video):raise ValueError('subtitle pictures were not generated')
            evidence.preview(target,f'short-{index+1}-silent')
            selected=[spans[i] for i in chosen]
            cases.append({'id':index+1,'source_line_ids':[r['id'] for r in selected],'text':' '.join(r['text'] for r in selected),
                'first_line':selected[0]['text'],'source_ranges':[[r['start_tick'],r['end_tick']] for r in selected],
                'frames':len(actual_video),'stereo_sample_frames':len(actual_audio),'max_rgb_error':rgb,'max_pcm_error':pcm_error,
                'original_meaning_review':'whole supplied sentences retained; IF qualifier and NOT negation not removed',
                'selection_reason':'self-contained conditional claim' if index==0 else 'honest limitation followed by complete delivery claim',
                'automatic_semantic_selection':False,'speech_published':False,'commercial_rights_accepted':False,
                'captions_applied':True,'caption_pcm_unchanged':True,
                'decoded_pcm_sha256':digest(actual_audio.tobytes()),'local_output_sha256':sha(target)})
        save(evidence.output/'shorts.json',cases)
        measurements={'case':'long-to-short','source_frames':len(frames),'source_stereo_sample_frames':len(source_pcm),
            'shorts':cases,'model_word_alignment_performed':False,'source_audio_public':False,
            'complete_condition_negation_and_sentences_retained':True,'automatic_semantic_selection_accepted':False,
            'new_neural_model_forwards':0,'new_local_flite_syntheses':3,'new_original_source_scenes':1}
    except Exception as exc:error=exc;raise
    finally:evidence.finish(error,**measurements)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.work,args.output)
