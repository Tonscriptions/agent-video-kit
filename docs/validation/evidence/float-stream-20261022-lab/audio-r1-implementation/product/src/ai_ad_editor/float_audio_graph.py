"""Reuse the existing authored audio engine beside a Float32 video producer.

The detached graph retains temporal/nested/audio controls, prunes visual
leaves and consumes its synthetic video output. It is not a second audio
engine or a completed default-renderer integration.
"""
from fractions import Fraction
import copy,math
from pathlib import Path
from .errors import AppError
from .native_audio_clock import cancel,verify_materialized
from .render import build_filter_graph

PROTOCOL='authored-audio-graph-for-float-video-v1'
VISUAL_FIELDS={'transform','mask','blend','crop','effects','tracking_binding','generator','subtitle'}

def prepare(root,project,sequence_id,*,cancel_file=None,persist_clock=True):
    root=Path(root).resolve();marker=Path(cancel_file) if cancel_file is not None else None;cancel(marker)
    detached=copy.deepcopy(project);detached['settings'].pop('adjustments',None);pruned=0
    for sequence in detached['sequences']:
        if sequence.get('source_transitions'):
            raise AppError('FLOAT_AUDIO_SOURCE_TRANSITION_UNCONNECTED','源转场计划尚未连接此独立音频适配器',exit_code=2)
        kept=[]
        for track in sequence['tracks']:
            if track['kind'] not in ('audio','video'):continue
            clips=[]
            for clip in track['clips']:
                if track['kind']!='audio' and not clip.get('sequence_id'):pruned+=1;continue
                for field in VISUAL_FIELDS:clip.pop(field,None)
                # Audio automation is defined by the existing audio namespace.
                clip['keyframes']=[row for row in clip.get('keyframes',[]) if str(row.get('property','')).startswith('audio.')]
                clips.append(clip)
            track['clips']=clips;kept.append(track)
        sequence['tracks']=kept
    sequence=next((s for s in detached['sequences'] if s['id']==sequence_id),None)
    if sequence is None:raise AppError('FLOAT_AUDIO_SEQUENCE','目标作者序列不存在',exit_code=2)
    inputs,graph,metadata,warnings=build_filter_graph(root,detached,sequence,_allow_audio_only=True,
        _persist_video_index=persist_clock,_cancel_file=marker)
    cancel(marker);ticks=project['settings']['timebase']['ticks_per_second']
    return {'protocol':PROTOCOL,'inputs':inputs,'filter_complex':graph+';[vout]nullsink','output_label':'aout',
        'metadata':metadata,'warnings':warnings,'expected_samples_48000':max(1,math.ceil(Fraction(sequence['duration_tick']*48000,ticks))),
        'pruned_visual_leaves':pruned,'original_project_rewritten':False,'synthetic_video_discarded':True,
        'real_video_decoded_by_adapter':False,'default_float_renderer_integrated':False,'network':False}

def verify(root,plan,*,cancel_file=None):
    if plan.get('protocol')!=PROTOCOL:raise AppError('FLOAT_AUDIO_PLAN','音频适配计划协议不一致',exit_code=2)
    verify_materialized(Path(root).resolve(),plan['metadata'],cancel_file=cancel_file)
