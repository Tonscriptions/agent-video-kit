"""Native frame identities on rational CFR grids, without renderer-clock oracles."""
from __future__ import annotations
from bisect import bisect_right
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor.project import create_project,load_project,save_project
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.video_clock import working_clock
from test_magnetic_reorder import invoke

TPS,W,H=90000,32,18


class CFRBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name);self.root=self.work/'project'
        create_project(self.root)

    def run_native(self,arguments,*,data=None,cwd=None):
        result=subprocess.run(list(map(str,arguments)),input=data,capture_output=True,cwd=cwd,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        return result.stdout

    def source(self,*,rate='25',container='nut',count=55,vfr=None,audio_tail=False):
        colors=[(30+i*3,50+i*2,220-i*3,255) for i in range(count)]
        raw=b''.join(bytes(color)*(W*H) for color in colors)
        path=self.work/('source.'+container)
        command=[ffmpeg_path(),'-hide_banner','-v','error','-filter_threads','1',
            '-f','rawvideo','-pixel_format','rgba','-video_size',f'{W}x{H}','-framerate',rate,'-i','pipe:0']
        if audio_tail:command+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','2','-c:a','pcm_s16le']
        if vfr is not None:
            expression=str(vfr[-1])
            for i in range(len(vfr)-2,-1,-1):expression=f'if(eq(N,{i}),{vfr[i]},{expression})'
            command+=['-vf',"settb=1/1000,setpts='"+expression+"'",'-fps_mode','passthrough','-enc_time_base','filter']
        command+=['-c:v','ffv1','-pix_fmt','bgra',path]
        self.run_native(command,data=raw)
        probe=json.loads(self.run_native([ffprobe_path(),'-v','error','-select_streams','v:0',
            '-show_frames','-show_streams','-show_entries','frame=pts,duration:stream=time_base','-of','json',path]))
        tb=Fraction(probe['streams'][0]['time_base'])
        timestamps=[int(f['pts'])*tb for f in probe['frames']]
        self.assertEqual(len(timestamps),len(colors))
        if vfr is not None:self.assertEqual(timestamps,[Fraction(t,1000) for t in vfr])
        return path,colors,timestamps

    def project(self,path,*,rate='30000/1001',start=9900,duration=90000,source_in=0,source_out=90000,patch=None):
        code,value=invoke('media','ingest','--project',self.root,'--input',path)
        self.assertEqual(code,0,value)
        p=load_project(self.root)[1];fps=Fraction(rate)
        p['settings']['canvas']={'width':W,'height':H,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':fps.numerator,'den':fps.denominator}}
        seq=p['sequences'][0];seq['duration_tick']=135000
        clip={'id':'clip','asset_id':value['data']['asset']['id'],'timeline_start_tick':start,
              'duration_tick':duration,'source_in_tick':source_in,'source_out_tick':source_out,**(patch or {})}
        seq['tracks'][0]['clips']=[clip]
        save_project(self.root,p)
        return p,seq,clip

    def render(self,p,seq):
        inputs,graph,metadata,warnings=build_filter_graph(self.root,p,seq)
        raw=self.run_native([ffmpeg_path(),'-hide_banner','-v','error','-filter_threads','1','-filter_complex_threads','1',
            *inputs,'-filter_complex',graph,'-map','[vout]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1',
            '-map','[aout]','-f','null','NUL'],cwd=self.root)
        fps=p['settings']['timebase']['display_fps'];rate=Fraction(fps['num'],fps['den'])
        count=math.ceil(Fraction(seq['duration_tick'],TPS)*rate);size=W*H*4
        self.assertEqual(len(raw),count*size)
        frames=[raw[i*size:(i+1)*size] for i in range(count)]
        self.assertTrue(all(frame[3::4]==bytes([255])*(W*H) for frame in frames))
        return frames,metadata,warnings

    def compare(self,frames,colors,timestamps,*,rate='30000/1001',start=9900,span=Fraction(1),speed=Fraction(1),reverse=False):
        rate=Fraction(rate);origin=Fraction(start,TPS)
        selected=[i for i,t in enumerate(timestamps) if t<span*speed]
        values=[colors[i] for i in selected]
        times=[(timestamps[i]-timestamps[selected[0]])/speed for i in selected]
        if reverse:values=values[::-1]
        for i,frame in enumerate(frames):
            display=Fraction(i)/rate
            if origin<=display<origin+span:
                index=bisect_right(times,display-origin)-1
                expected=values[index]
            else:expected=(0,0,0,255)
            self.assertEqual(frame,bytes(expected)*(W*H),(i,str(display),list(frame[:4]),expected))

    def compare_requested_source(self,frames,colors,timestamps,*,start,source_in,source_out,speed=Fraction(1),rate='30000/1001'):
        origin=Fraction(start,TPS);left=Fraction(source_in,TPS);right=Fraction(source_out,TPS)
        span=(right-left)/speed
        for index,frame in enumerate(frames):
            output_time=Fraction(index)/Fraction(rate)
            if origin<=output_time<origin+span:
                source_time=left+(output_time-origin)*speed
                source_index=bisect_right(timestamps,source_time)-1
                expected=colors[source_index] if source_index>=0 else (0,0,0,255)
            else:expected=(0,0,0,255)
            self.assertEqual(frame,bytes(expected)*(W*H),(index,str(output_time),list(frame[:4]),expected))

    def test_moving_cfr_nut_same_rate_keeps_every_source_identity(self):
        path,colors,times=self.source(rate='30000/1001')
        p,s,_=self.project(path);frames,metadata,_=self.render(p,s)
        self.compare(frames,colors,times)
        self.assertNotEqual(frames[33][:3],bytes(3))
        clock=next(x['video_frame_clock'] for x in metadata if x.get('kind')=='video')
        self.assertTrue(clock['input_pts_and_author_offsets_exact'])

    def test_moving_matroska_pts_are_preserved_across_different_fps(self):
        path,colors,times=self.source(container='mkv')
        p,s,_=self.project(path);frames,_,_=self.render(p,s)
        self.compare(frames,colors,times)

    def test_variable_frame_rate_is_not_replaced_by_an_average_rate(self):
        pts=[0,33,101,188,195,441,499,800,1002,1221,1600,1800]
        path,colors,times=self.source(container='nut',count=len(pts),vfr=pts)
        p,s,_=self.project(path,duration=85500,source_out=85500)
        frames,metadata,_=self.render(p,s)
        self.compare(frames,colors,times,span=Fraction(95,100))
        clock=next(x['video_frame_clock'] for x in metadata if x.get('kind')=='video')
        self.assertFalse(clock['input_VFR_normalized'])
        self.assertEqual(frames[32][:3],bytes(3))

    def test_reverse_and_constant_speed_use_the_same_exact_global_grid(self):
        path,colors,times=self.source()
        p,s,_=self.project(path,duration=60000,patch={'reverse':True,'speed':1.5})
        frames,_,_=self.render(p,s)
        self.compare(frames,colors,times,span=Fraction(2,3),speed=Fraction(3,2),reverse=True)

    def test_one_tick_origin_does_not_round_to_zero_on_the_image_clock(self):
        path=self.work/'plate.png';color=(32,96,192,255);Image.new('RGBA',(W,H),color).save(path)
        p,s,_=self.project(path,rate='30',start=1)
        frames,_,_=self.render(p,s)
        self.compare(frames,[color],[Fraction(0)],rate='30',start=1)
        self.assertEqual(frames[0][:3],bytes(3));self.assertEqual(frames[30][:4],bytes(color))

    def test_genuinely_short_video_with_a_long_audio_tail_is_not_cloned(self):
        path,_,_=self.source(count=8,container='mkv',audio_tail=True)
        p,s,_=self.project(path);frames,metadata,_=self.render(p,s)
        self.assertTrue(all(frame[:3]==bytes(3) for frame in frames[13:]))
        self.assertTrue(any(frame[:3]!=bytes(3) for frame in frames[4:13]))
        clock=next(x['video_frame_clock'] for x in metadata if x.get('kind')=='video')
        self.assertFalse(clock['short_input_padded'])

    def test_old_project_can_reprobe_missing_timebase_without_changing_recipe(self):
        path,colors,times=self.source()
        p,s,_=self.project(path);p['assets'][0]['probe'].pop('streams')
        before=json.dumps(p,sort_keys=True);frames,metadata,_=self.render(p,s)
        self.compare(frames,colors,times)
        self.assertEqual(json.dumps(p,sort_keys=True),before)
        clock=next(x['video_frame_clock'] for x in metadata if x.get('kind')=='video')
        self.assertEqual(clock['input_time_base_source'],'local-native-probe')
        with self.assertRaises(AppError) as caught:working_clock(Fraction(1,2147483647),'30000/1001',TPS)
        self.assertEqual(caught.exception.code,'VIDEO_CLOCK_TIMEBASE_UNREPRESENTABLE')

    def test_fractional_presentation_surface_does_not_lose_its_last_visible_frame(self):
        path=self.work/'plate.png';color=(32,96,192,255);Image.new('RGBA',(W,H),color).save(path)
        p,s,_=self.project(path,start=2970,duration=87300,source_out=180000,
            patch={'presentation_window':{'version':1,'authored_start_tick':0,'authored_duration_tick':180000,'offset_tick':9900}})
        frames,_,_=self.render(p,s)
        self.compare(frames,[color],[Fraction(0)],start=2970,span=Fraction(97,100))

    def test_fractional_source_in_keeps_requested_CFR_phase(self):
        path,colors,times=self.source()
        p,s,_=self.project(path,start=2970,source_in=10170,source_out=100170)
        frames,_,_=self.render(p,s)
        self.compare_requested_source(frames,colors,times,start=2970,source_in=10170,source_out=100170)

    def test_VFR_source_in_keeps_covering_source_frame_and_native_holds(self):
        pts=[0,33,101,188,195,441,499,800,1002,1221,1600,1800]
        path,colors,times=self.source(container='nut',count=len(pts),vfr=pts)
        p,s,_=self.project(path,start=2970,source_in=10170,source_out=100170)
        frames,_,_=self.render(p,s)
        self.compare_requested_source(frames,colors,times,start=2970,source_in=10170,source_out=100170)

    def test_fractional_source_in_with_constant_speed_uses_requested_origin(self):
        path,colors,times=self.source()
        p,s,_=self.project(path,start=1,duration=60000,source_in=10170,source_out=100170,patch={'speed':1.5})
        frames,_,_=self.render(p,s)
        self.compare_requested_source(frames,colors,times,start=1,source_in=10170,source_out=100170,speed=Fraction(3,2))

    def test_single_tick_source_in_does_not_advance_a_whole_source_frame(self):
        path,colors,times=self.source()
        p,s,_=self.project(path,start=9900,source_in=1,source_out=90001)
        frames,_,_=self.render(p,s)
        self.compare_requested_source(frames,colors,times,start=9900,source_in=1,source_out=90001)

    def test_NTSC_source_in_on_and_around_a_native_frame_boundary(self):
        path,colors,times=self.source(rate='30000/1001')
        for source_in in [3002,3003,3004]:
            with self.subTest(source_in_tick=source_in):
                p,s,_=self.project(path,start=1,source_in=source_in,source_out=source_in+90000)
                frames,_,_=self.render(p,s)
                self.compare_requested_source(frames,colors,times,start=1,source_in=source_in,source_out=source_in+90000)

    def test_nonlinear_speed_and_fractional_source_in_keep_CFR_and_VFR_identity(self):
        irregular=[0,33,101,188,195,441,499,800,1002,1221,1600,1800]
        for label,container,pts in [('cfr','nut',None),('vfr','mkv',irregular)]:
            with self.subTest(source=label):
                path,colors,times=self.source(container=container,count=len(pts) if pts else 55,vfr=pts)
                curve={'keyframes':[{'at_tick':0,'speed':.5,'interpolation':'linear'},
                                     {'at_tick':TPS,'speed':1.5}]}
                p,s,_=self.project(path,start=2970,duration=round(math.log(3)*TPS),
                    source_in=10170,source_out=100170,patch={'speed_curve':curve})
                frames,metadata,_=self.render(p,s)
                with localcontext() as context:
                    context.prec=50
                    origin=Decimal(2970)/TPS;left=Decimal(10170)/TPS;span=Decimal(3).ln()
                    native_pts=[Decimal(t.numerator)/t.denominator for t in times]
                    for index,frame in enumerate(frames):
                        now=Decimal(index)*1001/30000
                        if origin<=now<origin+span:
                            # du/dt=.5+u, u(0)=0: independent inverse of the
                            # source-time speed ramp, without renderer helpers.
                            source_time=left+Decimal('.5')*((now-origin).exp()-1)
                            source_index=bisect_right(native_pts,source_time)-1
                            expected=colors[source_index]
                        else:expected=(0,0,0,255)
                        self.assertEqual(frame,bytes(expected)*(W*H),(label,index,list(frame[:4]),expected))
                clock=next(x['video_frame_clock'] for x in metadata if x.get('kind')=='video')
                self.assertEqual(clock['source_clock_anchor'],'requested-author-source-in-tick')


if __name__=='__main__':unittest.main()
