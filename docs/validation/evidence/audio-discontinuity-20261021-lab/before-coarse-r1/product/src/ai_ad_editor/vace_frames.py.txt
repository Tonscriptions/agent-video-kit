"""Bounded joint-video windows, explicit padding and masked overlap composition."""
from __future__ import annotations

import hashlib
import time
import numpy as np
from PIL import Image, ImageFilter

from .local_vace import buffer_budget, window_plan, plan_digest
from .matting_frames import read_frame
from .repair_blend import harmonize_region, required_blend_bytes, joint_blend_overhead, new_blend_report, record_blend
from .vace_context import ConditioningTrace, PROTOCOL


def _selected(mask, channel, options):
    if channel not in {'alpha', 'luma'}: raise ValueError('VACE_MASK_CHANNEL_INVALID')
    values=mask[:,:,3] if channel=='alpha' else np.einsum('...k,k->...',mask[:,:,:3],np.array([.2126,.7152,.0722],np.float32))
    selected=values>options['threshold']*255
    if options['grow']:
        selected=np.asarray(Image.fromarray(selected.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(options['grow']*2+1)))!=0
    return selected


def _predict_window(entries, spec, *, options, generation, infer, contexts=None, trace=None):
    start,end=spec['start'],spec['end']; items=[entries[i] for i in range(start,end)]
    previous=generation.get('temporal_context')=='previous'
    contexts=contexts if contexts is not None else {}
    union=np.zeros(items[0][1].shape,dtype=bool)
    for _, selected in items:union|=selected
    stats={'start':start,'end':end,'model_frames':spec['model_frames'],'seed':spec['seed'],
           'model_calls':0,'roi':None,'resized':False,'model_pixels':0,'padded_frames':0,'clipped_model_values':0}
    if previous:
        stats['context_inputs']=[]
        # A completed selected prefix alone needs no new generation. These
        # windows still emit their new, unselected original frames exactly once.
        if not any(selected.any() and i not in contexts for i,(_,selected) in enumerate(items,start)):
            return None,stats
    if not union.any():return None,stats
    ys,xs=np.flatnonzero(union.any(axis=1)),np.flatnonzero(union.any(axis=0));h,w=union.shape;context=options['context']
    x1,y1=max(0,int(xs.min())-context),max(0,int(ys.min())-context)
    x2,y2=min(w,int(xs.max())+1+context),min(h,int(ys.max())+1+context)
    rw,rh=x2-x1,y2-y1;scale=min(1.,options['model_max_edge']/max(rw,rh))
    mw,mh=max(1,round(rw*scale)),max(1,round(rh*scale));pw,ph=max(64,(mw+15)//16*16),max(64,(mh+15)//16*16)
    images=[];masks=[]
    for index,(source, selected) in enumerate(items,start):
        # VACE inpainting expects absent content at 127, not the object to remove.
        # Erase before resizing so interpolation cannot leak selected source RGB.
        conditioning=source[y1:y2,x1:x2,:3].copy()
        conditioning[selected[y1:y2,x1:x2]]=127
        effective=selected[y1:y2,x1:x2]
        if previous and index in contexts:
            completed=contexts[index]
            if completed.dtype!=np.uint8 or completed.shape!=source.shape:
                raise ValueError('VACE_GENERATED_CONTEXT_FRAME_INVALID')
            conditioning[effective]=completed[y1:y2,x1:x2,:3][effective]
            effective=np.zeros_like(effective)
            stats['context_inputs'].append({'frame':index,'pixels':int(np.count_nonzero(selected)),
                'rgba_sha256':'sha256:'+hashlib.sha256(memoryview(completed).cast('B')).hexdigest()})
        rgb=np.asarray(Image.fromarray(conditioning).resize((mw,mh),Image.Resampling.BILINEAR)).copy()
        mask=np.asarray(Image.fromarray(effective.astype(np.uint8)*255).resize((mw,mh),Image.Resampling.NEAREST))
        if effective.any() and not mask.any():raise ValueError('VACE_MASK_LOST_DURING_RESIZE_INCREASE_MODEL_MAX_EDGE_OR_REDUCE_CONTEXT')
        rgb[mask!=0]=127
        images.append(np.pad(rgb,((0,ph-mh),(0,pw-mw),(0,0)),mode='edge'))
        masks.append(np.pad(mask,((0,ph-mh),(0,pw-mw)),mode='edge'))
    factor=generation.get('model_input_scale',1)
    if type(factor) is not int or factor not in {1,2,4}:raise ValueError('VACE_MODEL_INPUT_SCALE_INVALID')
    if factor!=1:
        images=[np.asarray(Image.fromarray(rgb).resize((pw*factor,ph*factor),Image.Resampling.BILINEAR)).copy() for rgb in images]
        masks=[np.asarray(Image.fromarray(mask).resize((pw*factor,ph*factor),Image.Resampling.NEAREST)) for mask in masks]
        for rgb,mask in zip(images,masks):rgb[mask!=0]=127
    padded=spec['model_frames']-len(items)
    images.extend([images[-1]]*padded);masks.extend([masks[-1]]*padded)
    model_images,model_masks=np.stack(images),np.stack(masks)
    if trace is not None:trace.add(model_images,model_masks)
    predicted=infer(model_images,model_masks,{**generation,'seed':spec['seed']})
    if not isinstance(predicted,np.ndarray) or predicted.dtype!=np.float32 or predicted.shape!=(spec['model_frames'],ph*factor,pw*factor,3) or not np.isfinite(predicted).all():
        raise ValueError('VACE_MODEL_OUTPUT_INVALID')
    clipped=int(np.count_nonzero((predicted<0)|(predicted>1)))
    if factor!=1:
        predicted=np.array([np.stack([np.asarray(Image.fromarray(frame[:,:,c]).resize((pw,ph),Image.Resampling.BILINEAR),dtype=np.float32) for c in range(3)],axis=2) for frame in predicted])
    # Keep float reconstruction through resize and overlap; quantize once on emit.
    projections=[]
    for frame in predicted[:end-start,:mh,:mw]:
        generated=np.stack([np.asarray(Image.fromarray(np.clip(frame[:,:,c],0,1)).resize((rw,rh),Image.Resampling.BILINEAR),dtype=np.float32) for c in range(3)],axis=2)*255
        projections.append(generated)
    stats.update(model_calls=1,roi=[x1,y1,x2,y2],resized=scale<1 or factor!=1,model_pixels=pw*ph*factor**2*spec['model_frames'],base_model_size=[pw,ph],model_size=[pw*factor,ph*factor],model_input_scale=factor,padded_frames=padded,clipped_model_values=clipped)
    return projections,stats


def process_frames(source, destination, *, width, height, frames, infer, options, generation, channel, budget=512*1024**2, progress=None):
    if any(type(v) is not int or v<1 for v in (width,height,frames,budget)) or width*height>16_777_216:raise ValueError('VACE_FRAME_BUDGET_INVALID')
    owned=buffer_budget(width,height,generation,options['model_max_edge'])+joint_blend_overhead(width,height,options)
    if owned>budget:raise ValueError('VACE_WINDOW_BUFFER_BUDGET_EXCEEDED')
    windows=window_plan(frames,generation)
    previous=generation.get('temporal_context')=='previous'
    contexts={};context_peak=context_windows=context_frames=context_pixels=scene_resets=0
    trace=ConditioningTrace() if previous else None
    blend_report=new_blend_report(options);blend_peak=0
    entries={};accum={};weights={};read=emitted=0
    hashes={k:hashlib.sha256() for k in ('rgba','source','mask','input_alpha','output_alpha')}
    transparent=opaque=alpha_sum=masked=empty_frames=blended=0;alpha_min=255;alpha_max=0
    calls=empty_windows=padded=clipped=model_peak=resized_frames=0;samples=[]
    for wi,spec in enumerate(windows):
        if previous and wi and spec['scene_start']!=windows[wi-1]['scene_start']:
            contexts.clear();scene_resets+=1
        while read<spec['end']:
            raw=read_frame(source,width*height*8)
            paired=np.frombuffer(raw,np.uint8).reshape(height,width*2,4)
            original,mask=paired[:,:width],paired[:,width:]
            hashes['source'].update(original.tobytes());hashes['mask'].update(mask.tobytes())
            hashes['input_alpha'].update(original[:,:,3].tobytes())
            entries[read]=(original,_selected(mask,channel,options));read+=1
        needed=max(required_blend_bytes(width,height,int(np.count_nonzero(entries[i][1])),options) for i in range(spec['start'],spec['end']))
        if owned+needed>budget:raise ValueError('REPAIR_HARMONIZE_ARRAY_BUDGET_EXCEEDED')
        blend_peak=max(blend_peak,needed)
        projections,stats=_predict_window(entries,spec,options=options,generation=generation,infer=infer,contexts=contexts,trace=trace)
        calls+=stats['model_calls'];empty_windows+=not stats['model_calls'];padded+=stats['padded_frames']
        clipped+=stats['clipped_model_values'];model_peak=max(model_peak,stats['model_pixels'])
        resized_frames+=(spec['end']-spec['start']) if stats['resized'] else 0
        next_window=windows[wi+1] if wi+1<len(windows) else None
        if previous:
            rows=stats['context_inputs']
            context_windows+=bool(rows);context_frames+=len(rows);context_pixels+=sum(row['pixels'] for row in rows)
            # Prediction has consumed this window's conditions. Retain only
            # those also needed by the next window before adding any new frame,
            # including when overlap is larger than the stride.
            contexts={i:value for i,value in contexts.items() if next_window is not None
                      and next_window['scene_start']==spec['scene_start'] and i>=next_window['start']}
        if len(samples)<16:samples.append(stats)
        for i in range(spec['start'],spec['end']):
            if previous and i<emitted:continue
            original,selected=entries[i]
            if not selected.any():continue
            if projections is None:raise ValueError('VACE_NONEMPTY_MASK_WITHOUT_PREDICTION')
            local=i-spec['start'];overlap=generation['window_overlap'];weight=1.
            if not previous:
                if spec['start']>spec['scene_start'] and local<overlap:weight=min(weight,(local+1)/(overlap+1))
                if spec['end']<spec['scene_end'] and spec['end']-i<=overlap:weight=min(weight,(spec['end']-i)/(overlap+1))
            if i not in accum:accum[i]=np.zeros((height,width,3),np.float32);weights[i]=0.;
            x1,y1,x2,y2=stats['roi']
            accum[i][y1:y2,x1:x2]+=projections[local]*weight
            weights[i]+=weight
        stop=spec['end'] if previous else next_window['start'] if next_window is not None else frames
        for i in range(emitted,stop):
            original,selected=entries[i] if previous else entries.pop(i)
            output=original.copy();count=int(np.count_nonzero(selected))
            masked+=count;empty_frames+=count==0
            if count:
                if i not in accum or weights.get(i,0)<=0:raise ValueError('VACE_MISSING_WINDOW_CONTRIBUTION')
                generated=accum.pop(i)/weights.pop(i)
                if options.get('blend_mode')=='harmonic':
                    generated=np.clip(generated,0,255)
                    began=time.monotonic()
                    generated,detail=harmonize_region(original,generated,selected,max_iterations=options['blend_max_iterations'],
                        relative_tolerance=options['blend_tolerance'],array_budget=budget-owned,checkpoint=(lambda:progress(emitted)) if progress else None)
                    record_blend(blend_report,i,detail,time.monotonic()-began)
                alpha=selected.astype(np.float32)
                if options['feather']:
                    alpha*=np.asarray(Image.fromarray(selected.astype(np.uint8)*255).filter(ImageFilter.GaussianBlur(options['feather'])),dtype=np.float32)/255
                mixed=original[:,:,:3].astype(np.float32)*(1-alpha[:,:,None])+generated*alpha[:,:,None]
                output[:,:,:3]=np.rint(np.clip(mixed,0,255)).astype(np.uint8)
                # Count frames covered by more than one nonempty window.
                if not previous:blended+=sum(s['start']<=i<s['end'] for s in windows[max(0,wi-generation['window_frames']):wi+1])>1
            if not np.array_equal(original[:,:,3],output[:,:,3]) or np.any((output[:,:,:3]!=original[:,:,:3])&(~selected[:,:,None])):raise ValueError('VACE_UNMASKED_OR_ALPHA_CHANGED')
            raw=output.tobytes();hashes['rgba'].update(raw);hashes['output_alpha'].update(output[:,:,3].tobytes())
            a=output[:,:,3];transparent+=int(np.count_nonzero(a==0));opaque+=int(np.count_nonzero(a==255));alpha_sum+=int(a.sum(dtype=np.uint64))
            alpha_min=min(alpha_min,int(a.min()));alpha_max=max(alpha_max,int(a.max()))
            destination.write(raw);emitted=i+1
            if previous and count and next_window is not None and next_window['scene_start']==spec['scene_start'] and i>=next_window['start']:
                contexts[i]=output
                context_peak=max(context_peak,len(contexts))
                if len(contexts)>generation['window_overlap']:raise ValueError('VACE_GENERATED_CONTEXT_CAPACITY_EXCEEDED')
            if progress:progress(emitted)
        if previous:
            keep_from=next_window['start'] if next_window is not None else frames
            entries={i:value for i,value in entries.items() if i>=keep_from}
        # The model output and projections need not survive into the next window.
        del projections
    if read!=frames or emitted!=frames or entries or accum or weights or contexts:raise ValueError('VACE_WINDOW_STREAM_INCOMPLETE')
    if source.read(1):raise ValueError('VACE_INPUT_EXTRA_FRAMES')
    destination.flush();pixels=width*height*frames
    result={'frames':frames,'width':width,'height':height,'rgba_sha256':'sha256:'+hashes['rgba'].hexdigest(),'rgba_bytes':pixels*4,
            'source_rgba_sha256':'sha256:'+hashes['source'].hexdigest(),'decoded_mask_rgba_sha256':'sha256:'+hashes['mask'].hexdigest(),
            'input_alpha_sha256':'sha256:'+hashes['input_alpha'].hexdigest(),'output_alpha_sha256':'sha256:'+hashes['output_alpha'].hexdigest(),
            'state_updates':frames,'state_peak_bytes':owned+blend_peak,'base_state_peak_bytes':owned,'blend':blend_report,'state_reset':'per-joint-window-and-scene','buffer_budget_scope':'conservative-owned-window-array-upper-bound-excludes-model-and-torch-temporaries',
            'input_alpha':'preserve','alpha_mode':'straight','alpha_min':alpha_min,'alpha_max':alpha_max,'alpha_mean':alpha_sum/pixels/255,
            'transparent_pixels':transparent,'opaque_pixels':opaque,'soft_alpha_pixels':pixels-transparent-opaque,
            'conditioning':'masked-rgb-127-and-previous-generated-context' if previous else 'masked-rgb-127-before-and-after-resize',
            'model_calls':calls,'empty_windows':empty_windows,'empty_mask_frames':empty_frames,'mask_pixels':masked,'resized_model_frames':resized_frames,
            'model_peak_pixels':model_peak,'outside_mask_changed_pixels':0,'clipped_model_values':clipped,'padded_frames':padded,
            'window_count':len(windows),'window_plan_sha256':plan_digest(windows),'overlap_frames_blended':blended,'window_samples':samples}
    if previous:
        result['temporal_context']={'protocol':PROTOCOL,'mode':'previous','source_kind':'previous-emitted-generated-rgba',
            'output_policy':'retain-emitted-prefix','generated_context_is_ground_truth':False,
            'windows_conditioned':context_windows,'frames_conditioned':context_frames,'pixels_conditioned':context_pixels,
            'peak_frames':context_peak,'peak_bytes':context_peak*width*height*4,
            'capacity_bytes':generation['window_overlap']*width*height*4,'scene_resets':scene_resets,
            'cross_scene_frames':0,'input_trace':trace.snapshot()}
    return result
