"""Actual native float surfaces compared with independent NumPy compositing."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_raster import FloatRasterGraph
from ai_ad_editor.media import ffmpeg_path

NATIVE_CALLS=[]

def reference_over(bottom,top,opacity=1.):
    bottom=bottom.astype(np.float64);top=top.astype(np.float64)
    ab=bottom[...,3:4];a=top[...,3:4]*opacity;alpha=a+ab*(1-a)
    rgb=np.divide(top[...,:3]*a+bottom[...,:3]*ab*(1-a),alpha,out=np.zeros_like(top[...,:3]),where=alpha>0)
    return np.concatenate((rgb,alpha),axis=-1)

def reference_nonseparable(mode,cb,cs):
    lum=lambda c:np.sum(c*np.array([.3,.59,.11]),axis=-1,keepdims=True)
    sat=lambda c:np.ptp(c,axis=-1,keepdims=True)
    def set_sat(c,s):
        order=np.argsort(c,axis=-1);sorted_values=np.take_along_axis(c,order,axis=-1)
        low=sorted_values[...,:1];high=sorted_values[...,2:3]
        result=np.divide(sorted_values-low,high-low,out=np.zeros_like(c),where=high>low)*s
        return np.take_along_axis(result,np.argsort(order,axis=-1),axis=-1)
    def set_lum(c,l):
        c=c+l-lum(c);minimum=np.min(c,axis=-1,keepdims=True)
        lower=l+np.divide((c-l)*l,l-minimum,out=np.zeros_like(c),where=l!=minimum)
        c=np.where(minimum<0,lower,c)
        maximum=np.max(c,axis=-1,keepdims=True)
        upper=l+np.divide((c-l)*(1-l),maximum-l,out=np.zeros_like(c),where=maximum!=l)
        return np.where(maximum>1,upper,c)
    if mode=='hue':return set_lum(set_sat(cs,sat(cb)),lum(cb))
    if mode=='saturation':return set_lum(set_sat(cb,sat(cs)),lum(cb))
    if mode=='color':return set_lum(cs,lum(cb))
    return set_lum(cb,lum(cs))

def reference_separable(mode,a,b):
    with np.errstate(divide='ignore',invalid='ignore'):
        if mode=='normal':return b
        if mode=='multiply':return a*b
        if mode=='screen':return 1-(1-a)*(1-b)
        if mode=='overlay':return np.where(a<=.5,2*a*b,1-2*(1-a)*(1-b))
        if mode=='darken':return np.minimum(a,b)
        if mode=='lighten':return np.maximum(a,b)
        if mode=='burn':return np.where(a==1,1,np.where(b==0,0,1-np.minimum(1,(1-a)/b)))
        if mode=='dodge':return np.where(a==0,0,np.where(b==1,1,np.minimum(1,a/(1-b))))
        if mode=='hardlight':return np.where(b<=.5,2*a*b,1-2*(1-a)*(1-b))
        if mode=='softlight':
            d=np.where(a<=.25,16*a**3-12*a*a+4*a,np.sqrt(a))
            return np.where(b<=.5,a-(1-2*b)*a*(1-a),a+(2*b-1)*(d-a))
        if mode=='difference':return np.abs(a-b)
        if mode=='exclusion':return a*(1-b)+b*(1-a)
        if mode=='addition':return np.minimum(1,a+b)
        if mode=='addition128':return np.clip(a+b-.5,0,1)
        if mode=='average':return (a+b)/2
        if mode=='subtract':return np.maximum(0,a-b)
        if mode=='divide':return np.where(b==0,1,np.minimum(1,a/b))
        if mode=='negation':return 1-np.abs(1-a-b)
        if mode=='phoenix':return np.minimum(a,b)-np.maximum(a,b)+1
        if mode=='pinlight':return np.where(b<=.5,np.minimum(a,2*b),np.maximum(a,2*b-1))
        if mode=='reflect':return np.where(b==1,1,np.minimum(1,a*a/(1-b)))
        if mode=='glow':return np.where(a==1,1,np.minimum(1,b*b/(1-a)))
        if mode=='freeze':return np.where(b==0,0,np.maximum(0,1-(1-a)**2/b))
        if mode=='vivid':return np.where(b<=.5,np.where(b==0,0,np.maximum(0,1-(1-a)/(2*b))),np.where(b==1,1,np.minimum(1,a/(2*(1-b)))))
        if mode=='hard_mix':return (a+b>=1).astype(np.float64)
        qa=np.floor(np.clip(a,0,1)*65535+.5).astype(np.uint16)
        qb=np.floor(np.clip(b,0,1)*65535+.5).astype(np.uint16)
        if mode=='and':return np.bitwise_and(qa,qb).astype(np.float64)/65535
        if mode=='or':return np.bitwise_or(qa,qb).astype(np.float64)/65535
        if mode=='xor':return np.bitwise_xor(qa,qb).astype(np.float64)/65535
    raise AssertionError(mode)

class FloatRasterTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='float-raster-',dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def samples(self):
        rng=np.random.default_rng(20261021)
        a=rng.random((2,16,32,4),dtype=np.float32);b=rng.random((2,16,32,4),dtype=np.float32)
        for v in (a,b):v[0,0,:,3]=0;v[0,1,:,3]=1;v[0,2,:,0]=0;v[0,3,:,0]=1
        return a,b

    def render(self,values,graph,target,*,fps=2):
        h,w=values[0].shape[1:3];command=[ffmpeg_path(),'-v','verbose','-filter_complex_threads','1']
        sources=[]
        for index,value in enumerate(values):
            path=self.root/(str(index)+'.gbrapf32le')
            raw=np.moveaxis(value[...,[1,2,0,3]],-1,1).astype('<f4').tobytes();path.write_bytes(raw)
            sources.append('sha256:'+hashlib.sha256(raw).hexdigest())
            command+=['-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{w}x{h}','-framerate',str(fps),'-i',str(path)]
        command+=['-filter_complex',graph.graph(),'-map','['+target+']','-pix_fmt','gbrapf32le','-fps_mode','passthrough','-f','rawvideo','pipe:1']
        p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        NATIVE_CALLS.append({'test':self.id(),'command':command,'exit_code':p.returncode,
            'source_float_RGBA_hashes':sources,'actual_output_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest(),'output_bytes':len(p.stdout),
            'automatic_conversions':[s for s in p.stderr.decode('utf8','replace').splitlines() if 'auto-inserting filter' in s]})
        self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace')[-5000:])
        self.assertEqual(len(p.stdout),values[0].size*4)
        self.assertFalse(NATIVE_CALLS[-1]['automatic_conversions'],NATIVE_CALLS[-1]['automatic_conversions'])
        planar=np.frombuffer(p.stdout,dtype='<f4').reshape(values[0].shape[0],4,h,w)
        return np.moveaxis(planar[:,[2,0,1,3]],1,-1)

    def close(self,actual,expected,tolerance=4e-7):
        self.assertTrue(np.isfinite(actual).all())
        error=float(np.abs(actual.astype(np.float64)-expected).max())
        self.assertLessEqual(error,tolerance)
        NATIVE_CALLS[-1].update(independent_expected_sha256='sha256:'+hashlib.sha256(expected.astype('<f8').tobytes()).hexdigest(),
            maximum_absolute_error=error,allowed_absolute_error=tolerance)

    def test_all_65536_original_gray_values_survive_float_source_over(self):
        gray=np.arange(65536,dtype=np.float32).reshape(1,64,1024)/65535
        foreground=np.stack((gray,gray,gray,np.ones_like(gray)),axis=-1)
        background=np.zeros_like(foreground);background[...,3]=1
        graph=FloatRasterGraph();target=graph.source_over('0:v','1:v')
        actual=self.render([background,foreground],graph,target)
        self.assertTrue(np.array_equal(actual,foreground))
        self.assertEqual(np.unique(actual[...,0]).size,65536)

    def test_full_mask_preserves_all_1024_native_gray_levels(self):
        gray=np.broadcast_to(np.arange(1024,dtype=np.float32)/1023,(1,16,1024)).copy()
        foreground=np.stack((gray,gray,gray,np.ones_like(gray)),axis=-1)
        background=np.zeros_like(foreground);background[...,3]=1
        graph=FloatRasterGraph();masked=graph.mask('1:v','1');target=graph.source_over('0:v',masked)
        actual=self.render([background,foreground],graph,target)
        self.assertTrue(np.array_equal(actual,foreground));self.assertEqual(np.unique(actual[...,0]).size,1024)

    def test_partial_transparent_layers_match_independent_porter_duff(self):
        a,b=self.samples();graph=FloatRasterGraph();target=graph.source_over('0:v','1:v',opacity='0.37123456789')
        self.close(self.render([a,b],graph,target),reference_over(a,b,.37123456789))

    def test_transparent_hidden_rgb_cannot_change_visible_result(self):
        a,b=self.samples();a[...,3]=0;b[...,3]=0
        graph=FloatRasterGraph();target=graph.source_over('0:v','1:v')
        self.close(self.render([a,b],graph,target),np.zeros_like(a,dtype=np.float64))

    def test_source_over_preserves_negative_and_high_dynamic_range_channels(self):
        a,b=self.samples();a[...,:3]=a[...,:3]*20-1;b[...,:3]=b[...,:3]*25-2
        graph=FloatRasterGraph();target=graph.source_over('0:v','1:v')
        self.close(self.render([a,b],graph,target),reference_over(a,b),tolerance=8e-6)

    def test_all_28_separable_modes_match_independent_float_references(self):
        modes=('normal','multiply','screen','overlay','darken','lighten','burn','dodge','hardlight','softlight',
            'difference','exclusion','addition','addition128','average','subtract','divide','negation','phoenix','pinlight',
            'reflect','glow','freeze','vivid','hard_mix','and','or','xor')
        a,b=self.samples()
        for mode in modes:
            with self.subTest(mode=mode):
                graph=FloatRasterGraph();target=graph.blend('0:v','1:v',mode=mode,opacity='0.813579')
                expected_top=b.astype(np.float64).copy()
                f=reference_separable(mode,a[...,:3].astype(np.float64),b[...,:3].astype(np.float64))
                expected_top[...,:3]=b[...,:3]*(1-a[...,3:4])+f*a[...,3:4]
                self.close(self.render([a,b],graph,target),reference_over(a,expected_top,.813579),tolerance=8e-7)

    def test_all_four_nonseparable_modes_match_sorted_colour_reference(self):
        a,b=self.samples()
        for mode in ('hue','saturation','color','luminosity'):
            with self.subTest(mode=mode):
                graph=FloatRasterGraph();target=graph.blend('0:v','1:v',mode=mode,opacity='0.712359')
                f=reference_nonseparable(mode,a[...,:3].astype(np.float64),b[...,:3].astype(np.float64))
                expected_top=b.astype(np.float64).copy();expected_top[...,:3]=b[...,:3]*(1-a[...,3:4])+f*a[...,3:4]
                self.close(self.render([a,b],graph,target),reference_over(a,expected_top,.712359),tolerance=8e-7)

    def test_opacity_uses_actual_surface_frame_pts(self):
        a,b=self.samples();graph=FloatRasterGraph();target=graph.source_over('0:v','1:v',opacity='T/2')
        opacity=np.array([0.,.25]).reshape(2,1,1,1)
        self.close(self.render([a,b],graph,target),reference_over(a,b,opacity))

    def test_mask_modifies_coverage_without_quantizing_or_multiplying_straight_rgb(self):
        a,_=self.samples();graph=FloatRasterGraph();target=graph.mask('0:v','if(lt(X,W/3),0.1234567,if(lt(X,2*W/3),0.6789123,1))')
        expected=a.astype(np.float64).copy();x=np.arange(32)
        expected[...,3]*=np.where(x<32/3,.1234567,np.where(x<64/3,.6789123,1))
        self.close(self.render([a],graph,target),expected)

    def test_nested_surface_outputs_remain_straight_until_parent_composition(self):
        a,b=self.samples();c=np.flip(b,axis=2).copy();graph=FloatRasterGraph()
        inner=graph.blend('1:v','2:v',mode='screen',opacity='.43');target=graph.source_over('0:v',inner,opacity='.61')
        blended=c.astype(np.float64).copy();blended[...,:3]=c[...,:3]*(1-b[...,3:4])+(1-(1-b[...,:3])*(1-c[...,:3]))*b[...,3:4]
        inner_expected=reference_over(b,blended,.43)
        self.close(self.render([a,b,c],graph,target),reference_over(a,inner_expected,.61),tolerance=8e-7)

    def test_invalid_labels_modes_and_graph_injection_are_rejected_before_execution(self):
        for bad in ('0:v];movie=x[steal','bad\nlabel','x'*100):
            with self.subTest(label=bad),self.assertRaises(AppError):FloatRasterGraph().prepare(bad)
        for bad in ('movie=x',"1';movie=x;[out",'0:v','x'*40000):
            with self.subTest(expression=bad),self.assertRaises(AppError):FloatRasterGraph().mask('0:v',bad)
        with self.assertRaises(AppError):FloatRasterGraph().blend('0:v','1:v',mode='unknown')

    def test_operation_budget_prevents_unbounded_surface_graph_growth(self):
        graph=FloatRasterGraph();surface='0:v'
        for _ in range(256):surface=graph.mask(surface,'1')
        with self.assertRaises(AppError):graph.mask(surface,'1')
