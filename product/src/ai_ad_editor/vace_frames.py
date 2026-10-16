"""Bounded joint-video windows, explicit padding and masked overlap composition."""
from __future__ import annotations

import hashlib
import time
import numpy as np
from PIL import Image, ImageFilter

from .local_vace import buffer_budget, window_plan, plan_digest
from .matting_frames import read_frame
from .repair_blend import harmonize_region, required_blend_bytes, joint_blend_overhead, new_blend_report, record_blend


def _selected(mask, channel, options):
    if channel not in {'alpha', 'luma'}: raise ValueError('VACE_MASK_CHANNEL_INVALID')
    values=mask[:,:,3] if channel=='alpha' else np.einsum('...k,k->...',mask[:,:,:3],np.array([.2126,.7152,.0722],np.float32))
    selected=values>options['threshold']*255
    if options['grow']:
        selected=np.asarray(Image.fromarray(selected.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(options['grow']*2+1)))!=0
    return selected


def _predict_window(entries, spec, *, options, generation, infer):
    start,end=spec['start'],spec['end']; items=[entries[i] for i in range(start,end)]
    union=np.zeros(items[0][1].shape,dtype=bool)
    for _, selected in items:union|=selected
    stats={'start':start,'end':end,'model_frames':spec['model_frames'],'seed':spec['seed'],
           'model_calls':0,'roi':None,'resized':False,'model_pixels':0,'padded_frames':0,'clipped_model_values':0}
    if not union.any():return None,stats
    ys,xs=np.flatnonzero(union.any(axis=1)),np.flatnonzero(union.any(axis=0));h,w=union.shape;context=options['context']
    x1,y1=max(0,int(xs.min())-context),max(0,int(ys.min())-context)
    x2,y2=min(w,int(xs.max())+1+context),min(h,int(ys.max())+1+context)
    rw,rh=x2-x1,y2-y1;scale=min(1.,options['model_max_edge']/max(rw,rh))
    mw,mh=max(1,round(rw*scale)),max(1,round(rh*scale));pw,ph=max(64,(mw+15)//16*16),max(64,(mh+15)//16*16)
    images=[];masks=[]
    for source, selected in items:
        # VACE inpainting expects absent content at 127, not the object to remove.
        # Erase before resizing so interpolation cannot leak selected source RGB.
        conditioning=source[y1:y2,x1:x2,:3].copy()
        conditioning[selected[y1:y2,x1:x2]]=127
        rgb=np.asarray(Image.fromarray(conditioning).resize((mw,mh),Image.Resampling.BILINEAR)).copy()
        mask=np.asarray(Image.fromarray(selected[y1:y2,x1:x2].astype(np.uint8)*255).resize((mw,mh),Image.Resampling.NEAREST))
        if selected.any() and not mask.any():raise ValueError('VACE_MASK_LOST_DURING_RESIZE_INCREASE_MODEL_MAX_EDGE_OR_REDUCE_CONTEXT')
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
    predicted=infer(np.stack(images),np.stack(masks),{**generation,'seed':spec['seed']})
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
    blend_report=new_blend_report(options);blend_peak=0
    entries={};accum={};weights={};read=emitted=0
    hashes={k:hashlib.sha256() for k in ('rgba','source','mask','input_alpha','output_alpha')}
    transparent=opaque=alpha_sum=masked=empty_frames=blended=0;alpha_min=255;alpha_max=0
    calls=empty_windows=padded=clipped=model_peak=resized_frames=0;samples=[]
    for wi,spec in enumerate(windows):
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
        projections,stats=_predict_window(entries,spec,options=options,generation=generation,infer=infer)
        calls+=stats['model_calls'];empty_windows+=not stats['model_calls'];padded+=stats['padded_frames']
        clipped+=stats['clipped_model_values'];model_peak=max(model_peak,stats['model_pixels'])
        resized_frames+=(spec['end']-spec['start']) if stats['resized'] else 0
        if len(samples)<16:samples.append(stats)
        for i in range(spec['start'],spec['end']):
            original,selected=entries[i]
            if not selected.any():continue
            if projections is None:raise ValueError('VACE_NONEMPTY_MASK_WITHOUT_PREDICTION')
            local=i-spec['start'];overlap=generation['window_overlap'];weight=1.
            if spec['start']>spec['scene_start'] and local<overlap:weight=min(weight,(local+1)/(overlap+1))
            if spec['end']<spec['scene_end'] and spec['end']-i<=overlap:weight=min(weight,(spec['end']-i)/(overlap+1))
            if i not in accum:accum[i]=np.zeros((height,width,3),np.float32);weights[i]=0.;
            x1,y1,x2,y2=stats['roi']
            accum[i][y1:y2,x1:x2]+=projections[local]*weight
            weights[i]+=weight
        stop=windows[wi+1]['start'] if wi+1<len(windows) else frames
        for i in range(emitted,stop):
            original,selected=entries.pop(i);output=original.copy();count=int(np.count_nonzero(selected))
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
                blended+=sum(s['start']<=i<s['end'] for s in windows[max(0,wi-generation['window_frames']):wi+1])>1
            if not np.array_equal(original[:,:,3],output[:,:,3]) or np.any((output[:,:,:3]!=original[:,:,:3])&(~selected[:,:,None])):raise ValueError('VACE_UNMASKED_OR_ALPHA_CHANGED')
            raw=output.tobytes();hashes['rgba'].update(raw);hashes['output_alpha'].update(output[:,:,3].tobytes())
            a=output[:,:,3];transparent+=int(np.count_nonzero(a==0));opaque+=int(np.count_nonzero(a==255));alpha_sum+=int(a.sum(dtype=np.uint64))
            alpha_min=min(alpha_min,int(a.min()));alpha_max=max(alpha_max,int(a.max()))
            destination.write(raw);emitted=i+1
            if progress:progress(emitted)
        # The model output and projections need not survive into the next window.
        del projections
    if read!=frames or emitted!=frames or entries or accum or weights:raise ValueError('VACE_WINDOW_STREAM_INCOMPLETE')
    if source.read(1):raise ValueError('VACE_INPUT_EXTRA_FRAMES')
    destination.flush();pixels=width*height*frames
    return {'frames':frames,'width':width,'height':height,'rgba_sha256':'sha256:'+hashes['rgba'].hexdigest(),'rgba_bytes':pixels*4,
            'source_rgba_sha256':'sha256:'+hashes['source'].hexdigest(),'decoded_mask_rgba_sha256':'sha256:'+hashes['mask'].hexdigest(),
            'input_alpha_sha256':'sha256:'+hashes['input_alpha'].hexdigest(),'output_alpha_sha256':'sha256:'+hashes['output_alpha'].hexdigest(),
            'state_updates':frames,'state_peak_bytes':owned+blend_peak,'base_state_peak_bytes':owned,'blend':blend_report,'state_reset':'per-joint-window-and-scene','buffer_budget_scope':'conservative-owned-window-array-upper-bound-excludes-model-and-torch-temporaries',
            'input_alpha':'preserve','alpha_mode':'straight','alpha_min':alpha_min,'alpha_max':alpha_max,'alpha_mean':alpha_sum/pixels/255,
            'transparent_pixels':transparent,'opaque_pixels':opaque,'soft_alpha_pixels':pixels-transparent-opaque,
            'conditioning':'masked-rgb-127-before-and-after-resize',
            'model_calls':calls,'empty_windows':empty_windows,'empty_mask_frames':empty_frames,'mask_pixels':masked,'resized_model_frames':resized_frames,
            'model_peak_pixels':model_peak,'outside_mask_changed_pixels':0,'clipped_model_values':clipped,'padded_frames':padded,
            'window_count':len(windows),'window_plan_sha256':plan_digest(windows),'overlap_frames_blended':blended,'window_samples':samples}
