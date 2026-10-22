"""Author-clock Float32 sequence evaluation over explicitly supplied surfaces.

This frame host is a library boundary for the upcoming streaming renderer.
It does not invoke the legacy graph, decode files, render audio or silently
approximate unsupported effects. The authored project is never rewritten.
"""
from __future__ import annotations
from bisect import bisect_left,bisect_right
import copy,math,re
from fractions import Fraction
from typing import Callable
import numpy as np
from .animation import keyframe_value
from .clip_windows import validate_window
from .errors import AppError
from .float_color_signal import ColorSignal,convert_rgba
from .float_composite import composite_rgba
from .float_geometry import resample_rgba
from .float_mask import compile_mask, apply_mask
from .float_exposure import compile_effects,apply_exposure
from .float_raster import mode_name
from .sequence_canvas import sequence_canvas
from .speed_curves import compile_curve
from .time_mapping import make_map,unmap_time

PROTOCOL='author-clock-float32-frame-host-v1'
MAX_CLIPS=4096
MAX_DEPTH=16
MAX_LAYERS_PER_FRAME=128
MAX_SURFACE_BYTES=256*1024**2
TRANSFORM_PROPERTIES={'transform.scale','scale','transform.rotation','rotation','transform.opacity','opacity',
    'transform.position.x','position.x','position_x','transform.position.y','position.y','position_y',
    'transform.anchor.x','anchor.x','anchor_x','transform.anchor.y','anchor.y','anchor_y','blend.opacity','blend_opacity'}
MASK_PROPERTIES={'rectangle':{'mask.x','mask.position.x','mask.y','mask.position.y','mask.width','mask.w','mask.height','mask.h'},
    'circle':{'mask.cx','mask.center_x','mask.cy','mask.center_y','mask.radius'},
    'ellipse':{'mask.cx','mask.center_x','mask.cy','mask.center_y','mask.rx','mask.radius_x','mask.ry','mask.radius_y'}}

def error(code,message,**details):return AppError('FLOAT_TIMELINE_'+code,message,exit_code=2,diagnostics=details or None)

def integer(value,minimum=0):
    if type(value) is not int or value<minimum:raise error('CLOCK','作者时钟必须为范围内整数，不能使用布尔值或浮点数')
    return value

class TimedSurfaceSource:
    """Native clock plus a supplied bounded random-access frame callback.

    Points are absolute native PTS; source selection is demux-relative. Holds
    run to the next PTS, and the final duration establishes known video EOF.
    A missing final duration is not inferred from average FPS. Right-edge
    sampling implements reversed half-open display intervals exactly.
    """
    def __init__(self,pts,durations,time_base,demux_origin,fetch:Callable,*,signal:ColorSignal,
                 source_sha256:str,verify=None,still=False,source_frame_start=0):
        if not callable(fetch) or not isinstance(signal,ColorSignal):raise error('SOURCE','帧源须提供明确取帧函数和RGB信号')
        if not isinstance(source_sha256,str) or not re.fullmatch('sha256:[0-9a-f]{64}',source_sha256):raise error('SOURCE','帧源须绑定原始资产SHA')
        if type(still) is not bool or type(source_frame_start) is not int or source_frame_start<0:raise error('SOURCE','图片标记或原始帧偏移无效')
        self.still=still;self.source_frame_start=source_frame_start
        self.pts=tuple(pts);self.durations=tuple(durations)
        if not self.pts or len(self.pts)!=len(self.durations) or len(self.pts)>1000000:raise error('CLOCK','原生时钟数组无效或超限')
        if any(type(v) is not int or not -(2**63)<=v<2**63 for v in (*self.pts,*self.durations)):
            raise error('CLOCK','原生PTS/时长须为signed int64')
        if any(v<0 for v in self.durations) or any(a>=b for a,b in zip(self.pts,self.pts[1:])):raise error('CLOCK','原生PTS须严格递增且时长非负')
        if still and len(self.pts)!=1:raise error('SOURCE','静态图片必须只有一个原始表面')
        try:self.time_base=Fraction(time_base);self.origin=Fraction(demux_origin)
        except (ValueError,TypeError,ZeroDivisionError) as caught:raise error('CLOCK','须提供明确有理数时间基和容器起点') from caught
        if self.time_base<=0:raise error('CLOCK','原生时间基必须为正')
        if verify is not None and not callable(verify):raise error('SOURCE','源验证回调无效')
        self.fetch=fetch;self.signal=signal;self.sha256=source_sha256;self.verify_callback=verify

    def index_at(self,source_time,*,right_edge=False):
        try:point=(Fraction(source_time)+self.origin)/self.time_base
        except (ValueError,TypeError,ZeroDivisionError) as caught:raise error('CLOCK','取帧时间必须是有理数') from caught
        if self.still:return 0
        index=(bisect_left(self.pts,point) if right_edge else bisect_right(self.pts,point))-1
        if index<0:return None
        last=self.pts[-1];duration=self.durations[-1]
        if index==len(self.pts)-1:
            if duration==0:raise error('EOF_UNKNOWN','末帧原生duration未知，不能推测EOF或补帧')
            end=last+duration
            if point>end or (point==end and not right_edge):return None
        return index

    def sample(self,source_time,*,right_edge=False):
        index=self.index_at(source_time,right_edge=right_edge)
        if index is None:return None,None
        value=self.fetch(index)
        if not isinstance(value,np.ndarray) or value.dtype!=np.float32 or value.ndim!=3 or value.shape[-1]!=4 or not value.flags.c_contiguous:
            raise error('SURFACE','取帧函数必须返回连续H×W×4 Float32')
        if value.nbytes>MAX_SURFACE_BYTES:raise error('BUDGET','单帧RGBA超过256MiB')
        if not min(value.shape[:2]):raise error('SURFACE','帧表面不能为空')
        return value,index+self.source_frame_start

    def verify(self):
        if self.verify_callback is not None:self.verify_callback()

class FloatTimeline:
    def __init__(self,project,sequence_id,sources,*,working_signal,background_signal=ColorSignal('bt709','srgb'),cancel=None,
                 max_working_bytes=768*1024*1024):
        if not isinstance(working_signal,ColorSignal) or not isinstance(background_signal,ColorSignal):raise error('SIGNAL','工作与背景RGB信号须明确')
        if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调无效')
        self.project=copy.deepcopy(project);self.sources=dict(sources);self.working=working_signal;self.background_signal=background_signal
        if type(max_working_bytes) is not int or not 1<=max_working_bytes<=768*1024*1024:
            raise error('BUDGET','浮点投影/合成的单次工作区配额须在1字节到768MiB')
        self.max_working_bytes=max_working_bytes
        self.poll=cancel if cancel is not None else lambda:None;self.poll()
        self.settings=self.project['settings'];base=self.settings['timebase'];fps=base['display_fps']
        self.tps=integer(base['ticks_per_second'],1);self.fps=Fraction(integer(fps['num'],1),integer(fps['den'],1))
        if self.tps<1 or self.fps<=0 or self.fps>1000:raise error('CLOCK','作者时间基或帧率无效')
        self.sequences={s['id']:s for s in self.project['sequences']};self.sequence_id=sequence_id
        if len(self.sequences)!=len(self.project['sequences']):raise error('SEQUENCE','序列ID重复')
        if sequence_id not in self.sequences:raise error('SEQUENCE','目标作者序列不存在')
        self.assets={a['id']:a for a in self.project['assets']};self.maps={};self.effect_plans={};self.mask_plans={};self.clip_count=0
        if len(self.assets)!=len(self.project['assets']):raise error('SOURCE','资产ID重复')
        self._validate(sequence_id,());sequence=self.sequences[sequence_id]
        self.frame_count=math.ceil(Fraction(int(sequence['duration_tick']),self.tps)*self.fps)
        self.metadata={'protocol':PROTOCOL,'sequence_id':sequence_id,'display_fps':str(self.fps),'frames':self.frame_count,
            'working_signal':{'primaries':working_signal.primaries,'transfer':working_signal.transfer},
            'scalar_clock':'exact rational source/display intervals','curve_clock':'existing adaptive Float64 author clock;see compilation certificate',
            'native_holds':'original PTS to next PTS;last native duration establishes EOF',
            'nested_clock':'continuous author time;exact left/right limits propagated through reversal',
            'input_contract':'validated Agent Project IR;registered SHA and explicit common working RGB signal',
            'audio_rendered':False,'legacy_render_preview_cache_integrated':False,'HDR_accepted':False,'network':False}

    def _validate(self,sequence_id,stack):
        if sequence_id in stack or len(stack)>=MAX_DEPTH:raise error('NESTING','嵌套循环或超过16层')
        sequence=self.sequences[sequence_id];canvas=sequence_canvas(self.project,sequence)
        integer(sequence['duration_tick'],1)
        if sequence.get('source_transitions'):raise error('UNSUPPORTED','源转场计划尚未连接浮点宿主')
        if canvas['width']*canvas['height']*16>MAX_SURFACE_BYTES:raise error('BUDGET','作者画布超过256MiB表面')
        ids=set()
        for track in sequence['tracks']:
            if track.get('muted') or track['kind']=='audio':continue
            if track['kind']!='video' and track.get('clips'):raise error('UNSUPPORTED','该帧宿主尚未接入此轨道类型',track=track['id'],kind=track['kind'])
            for clip in track['clips']:
                self.clip_count+=1
                if self.clip_count>MAX_CLIPS:raise error('BUDGET','展开作者片段数超过4096')
                path=sequence_id+'/'+str(clip['id'])
                if clip['id'] in ids:raise error('SEQUENCE','轨道内片段ID重复',clip=path)
                ids.add(clip['id'])
                for field in ('transition_in','transition_out','crop','generator','subtitle','tracking_binding'):
                    if clip.get(field):raise error('UNSUPPORTED','该作者操作尚未连接浮点宿主，不进行旧路径回落',clip=path,operation=field)
                self.effect_plans[path]=compile_effects(clip.get('effects',[]))
                if self.effect_plans[path] and self.working.transfer!='linear':raise error('SIGNAL','浮点曝光要求线性光工作域',clip=path)
                integer(clip['timeline_start_tick']);integer(clip['duration_tick'],1);integer(clip['source_in_tick']);integer(clip['source_out_tick'],1)
                if clip['source_out_tick']<=clip['source_in_tick']:
                    raise error('CLOCK','作者片段范围无效',clip=path)
                authored=validate_window(clip);freeze=clip.get('freeze') or {};freeze_duration=integer(freeze.get('duration_tick',0));freeze_at=integer(freeze.get('at_tick',0))
                if freeze_duration>=authored or freeze_at>authored-freeze_duration:
                    raise error('FREEZE','冻结区间无效',clip=path)
                mode_name((clip.get('blend') or {}).get('mode','normal'))
                self.mask_plans[path]=compile_mask(clip)
                allowed=TRANSFORM_PROPERTIES|(self.mask_plans[path].properties if self.mask_plans[path] else set())
                properties=[frame.get('property') for frame in clip.get('keyframes',[])]
                if any(p not in allowed for p in properties) or len(set(properties))!=len(properties):raise error('UNSUPPORTED','关键帧属性尚未接入或重复',clip=path)
                if (clip.get('transform') or {}).get('opacity_keyframes'):raise error('UNSUPPORTED','独立透明度轨道尚未接入',clip=path)
                try:speed=Fraction(str(clip.get('speed',1)))
                except (ValueError,ZeroDivisionError) as caught:raise error('CLOCK','速度必须为正有限数字') from caught
                if speed<=0:raise error('CLOCK','速度必须为正有限数字')
                if clip.get('sequence_id'):
                    child=clip['sequence_id']
                    if child not in self.sequences:raise error('SEQUENCE','子序列不存在',clip=path)
                    self._validate(child,(*stack,sequence_id))
                else:
                    asset_id=clip.get('asset_id');asset=self.assets.get(asset_id);source=self.sources.get(asset_id)
                    if not asset or asset.get('kind') not in ('video','image') or not isinstance(source,TimedSurfaceSource):raise error('SOURCE','片段需要已登记本地视频/图片及对应浮点源',clip=path)
                    if source.sha256!=asset.get('sha256') or source.signal!=self.working:raise error('SOURCE','源SHA或共同工作RGB信号不一致',clip=path)
                    if (asset['kind']=='image')!=source.still:raise error('SOURCE','静态图片/视频源类型不一致',clip=path)
                raw=copy.deepcopy(clip);raw['timeline_start_tick']=0;raw['duration_tick']=authored-freeze_duration
                if clip.get('speed_curve'):
                    span=int(clip['source_out_tick'])-int(clip['source_in_tick']);segments=compile_curve(raw,span,self.tps)
                    self.maps[path]=make_map(raw,segments,self.tps)

    def _source_time(self,clip,local_tick,path,*,left_limit=False):
        window=clip.get('presentation_window') or {};elapsed=local_tick+int(window.get('offset_tick',0))
        animation_tick=elapsed
        freeze=clip.get('freeze') or {};at=int(freeze.get('at_tick',0));duration=int(freeze.get('duration_tick',0))
        held=duration and ((at<elapsed<=at+duration) if left_limit else (at<=elapsed<at+duration))
        if held:elapsed=Fraction(at)
        elif duration and elapsed>=at+duration:elapsed-=duration
        start,end=Fraction(int(clip['source_in_tick']),self.tps),Fraction(int(clip['source_out_tick']),self.tps)
        reverse=bool(clip.get('reverse'))
        if path in self.maps:
            if elapsed==0:result=end if reverse else start
            elif elapsed==validate_window(clip)-duration:result=start if reverse else end
            else:result=Fraction.from_float(unmap_time(self.maps[path],float(elapsed/self.tps)))
        else:
            speed=Fraction(str(clip.get('speed',1)))
            if speed<=0:raise error('CLOCK','速度必须为正',clip=path)
            result=(end-elapsed/self.tps*speed) if reverse else (start+elapsed/self.tps*speed)
        right_edge=reverse if held else reverse!=left_limit
        if held and result==start:right_edge=False
        if held and result==end:right_edge=True
        if left_limit:animation_tick=math.nextafter(float(animation_tick),-math.inf)
        return result,animation_tick,right_edge

    def _project(self,clip,surface,canvas,tick,path):
        transform=clip.get('transform') or {};position=transform.get('position') or {};anchor=transform.get('anchor') or {}
        def value(names,default):return keyframe_value(clip,names,float(default),float(tick))
        scale=value(('transform.scale','scale'),transform.get('scale',1));angle=value(('transform.rotation','rotation'),transform.get('rotation',0))
        opacity=value(('transform.opacity','opacity'),transform.get('opacity',1))
        px=value(('transform.position.x','position.x','position_x'),position.get('x',transform.get('position_x',.5)));py=value(('transform.position.y','position.y','position_y'),position.get('y',transform.get('position_y',.5)))
        ax=value(('transform.anchor.x','anchor.x','anchor_x'),anchor.get('x',transform.get('anchor_x',.5)))
        ay=value(('transform.anchor.y','anchor.y','anchor_y'),anchor.get('y',transform.get('anchor_y',.5)))
        if not all(math.isfinite(v) for v in (scale,angle,opacity,px,py,ax,ay)) or scale<=0 or not 0<=opacity<=1:raise error('GEOMETRY','变换包含无效值')
        height,width=surface.shape[:2];cw,ch=canvas['width'],canvas['height']
        zoom=min(cw/width,ch/height)*scale;c,s=math.cos(math.radians(angle))/zoom,math.sin(math.radians(angle))/zoom
        anchor_x,anchor_y=width*ax-.5,height*ay-.5;dest_x,dest_y=cw*px-.5,ch*py-.5
        inverse=[[c,s,anchor_x-c*dest_x-s*dest_y],[-s,c,anchor_y+s*dest_x-c*dest_y]]
        mask_metadata=None
        if self.mask_plans[path] is not None:
            surface,mask_metadata=apply_mask(surface,self.mask_plans[path],tick,max_working_bytes=self.max_working_bytes,cancel=self.poll)
        result,_=resample_rgba(surface,(cw,ch),inverse,max_working_bytes=self.max_working_bytes,cancel=self.poll)
        return result,opacity,inverse,mask_metadata

    def _sequence(self,sequence_id,at,rows,*,root=False,depth=0,left_limit=False):
        self.poll();sequence=self.sequences[sequence_id];canvas=sequence_canvas(self.project,sequence);w,h=canvas['width'],canvas['height']
        result=np.zeros((h,w,4),dtype=np.float32)
        if root:
            text=str(self.settings['canvas'].get('background','#000000'))
            if text=='transparent':text='#00000000'
            if not re.fullmatch('#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?',text):raise error('BACKGROUND','背景当前要求明确RGB/RGBA十六进制')
            channels=[int(text[i:i+2],16)/255 for i in range(1,len(text),2)]
            if len(channels)==3:channels.append(1.)
            colour,_=convert_rgba(np.array([[channels]],np.float32),self.background_signal,self.working,max_working_bytes=self.max_working_bytes,cancel=self.poll)
            result[:]=colour[0,0]
        duration=Fraction(int(sequence['duration_tick']),self.tps)
        if not ((0<at<=duration) if left_limit else (0<=at<duration)):return result
        for _,track in sorted(enumerate(sequence['tracks']),key=lambda pair:(pair[1].get('order',pair[0]),pair[0])):
            if track.get('muted') or track['kind']!='video':continue
            for clip in track['clips']:
                local_tick=at*self.tps-int(clip['timeline_start_tick'])
                if not ((0<local_tick<=clip['duration_tick']) if left_limit else (0<=local_tick<clip['duration_tick'])):continue
                self.poll()
                if len(rows)>=MAX_LAYERS_PER_FRAME:raise error('BUDGET','同帧片段数超过128')
                path=sequence_id+'/'+str(clip['id']);source_time,tick,right=self._source_time(clip,local_tick,path,left_limit=left_limit)
                if (source_time<Fraction(int(clip['source_in_tick']),self.tps) or source_time>Fraction(int(clip['source_out_tick']),self.tps)
                    or (source_time==Fraction(int(clip['source_out_tick']),self.tps) and not right)):continue
                frame_index=None
                if clip.get('sequence_id'):
                    source=self._sequence(clip['sequence_id'],source_time,rows,depth=depth+1,left_limit=right)
                else:
                    source,frame_index=self.sources[clip['asset_id']].sample(source_time,right_edge=right)
                    if source is None:
                        rows.append({'clip':path,'source_time':str(source_time),'empty_native_coverage':True});continue
                if len(rows)>=MAX_LAYERS_PER_FRAME:raise error('BUDGET','同帧片段数超过128')
                effect_metadata=None
                if self.effect_plans[path]:
                    source,effect_metadata=apply_exposure(source,self.effect_plans[path],max_working_bytes=self.max_working_bytes,cancel=self.poll)
                layer,opacity,inverse,mask_metadata=self._project(clip,source,canvas,tick,path)
                blend=clip.get('blend') or {};opacity*=keyframe_value(clip,('blend.opacity','blend_opacity'),float(blend.get('opacity',1)),float(tick))
                result,_=composite_rgba(result,layer,mode=blend.get('mode','normal'),opacity=opacity,max_working_bytes=self.max_working_bytes,cancel=self.poll)
                rows.append({'clip':path,'source_time':str(source_time),'native_frame_index':frame_index,'right_edge':right,
                    'author_animation_tick':str(tick),'inverse_affine':inverse,'opacity':opacity,'effects':effect_metadata,'mask':mask_metadata})
        return result

    def render_frame(self,index):
        if type(index) is not int or not 0<=index<self.frame_count:raise error('RANGE','输出帧索引越界')
        rows=[];at=Fraction(index,1)/self.fps;result=self._sequence(self.sequence_id,at,rows,root=True)
        return result,{'protocol':PROTOCOL,'frame':index,'author_time':str(at),'layers':rows,'encoded_movie':False,'legacy_render_integrated':False}

    def verify_sources(self):
        for source in self.sources.values():self.poll();source.verify()
