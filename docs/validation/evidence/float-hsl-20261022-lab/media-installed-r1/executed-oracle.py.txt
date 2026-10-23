"""Original five-scene recipe and independent scalar colorsys/neighbor oracle.

No product color, band, coefficient, automation or effect module is imported.
"""
import bisect
import colorsys
import numpy as np

METHODS=('warm','cool','mixed','input_clip','residual')
SIGNAL={'primaries':'bt709','transfer':'bt709-oetf'}
NAMES=('red','orange','yellow','green','cyan','blue','purple','magenta')
CENTERS=(0,30,60,120,180,240,270,300)
MIXED={band+'_'+axis:(1 if i%2==0 else -1)*value
       for i,band in enumerate(NAMES) for axis,value in (('hue',25),('saturation',.25),('lightness',.1))}

def key(prop,left,right,mode='linear',controls=None):
    first={'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None:first['control_points']=controls
    return {'property':prop,'keyframes':[first,{'at_tick':36000,'value':right,'interpolation':'linear'}]}

def effects(method):
    p={'input_signal':dict(SIGNAL),'output_signal':dict(SIGNAL),'intensity':.2}
    tracks=[key('intensity',.2,.85,'ease_in_out')]
    if method=='warm':
        p.update(red_hue=-45,orange_saturation=.3,yellow_lightness=.12)
        tracks.extend([key('red_hue',-45,45,'ease_in'),key('orange_saturation',.3,-.3,'ease_out')])
    elif method=='cool':
        p.update(blue_hue=-70,cyan_saturation=.4,purple_lightness=.2)
        tracks.append(key('blue_hue',-70,20,'bezier',[.2,.05,.8,.95]))
    elif method=='mixed':
        p.update(MIXED)
        tracks.append(key('green_hue',-40,40,'hold'))
    else:
        p.update(red_hue=20,blue_hue=-30,green_saturation=-.25,
                 input_gamut='clip' if method=='input_clip' else 'preserve_residual')
    colour={'type':'selective_hsl','parameters':p,'keyframes':tracks}
    left,right=(2.3,3.) if method=='input_clip' else (2.7,3.) if method=='residual' else (.15,.45)
    exposure={'type':'exposure','parameters':{'amount':left,'black':0},'keyframes':[key('amount',left,right,'ease_in')]}
    return [exposure,colour] if method in ('input_clip','residual') else [colour,exposure]

def decode(rgb):
    a=np.abs(rgb)
    return np.where(a<.081,rgb/4.5,np.sign(rgb)*((a+.099)/1.099)**(1/.45)).astype(np.float32)

def encode(rgb):
    a=np.abs(rgb)
    return np.where(a<.018,rgb*4.5,np.sign(rgb)*(1.099*a**.45-.099)).astype(np.float32)

def timing(p):
    roots=np.roots([-.8,1.2,.6,-p])
    u=next(float(v.real) for v in roots if abs(v.imag)<1e-10 and -1e-12<=v.real<=1+1e-12)
    return .15*(1-u)**2*u+2.85*(1-u)*u*u+u**3

def sampled(method,p):
    if method=='warm':return {'red_hue':-45+90*p*p,'orange_saturation':.3-.6*(2*p-p*p),'yellow_lightness':.12}
    if method=='cool':return {'blue_hue':-70+90*timing(p),'cyan_saturation':.4,'purple_lightness':.2}
    if method=='mixed':return {**MIXED,'green_hue':-40}
    return {'red_hue':20,'blue_hue':-30,'green_saturation':-.25}

def grade(value,method,p):
    controls=sampled(method,p)
    original=value.astype(np.float64);bounded=np.clip(original,0,1)
    flat=bounded.reshape(-1,3);result=np.empty_like(flat)
    for index,(r,g,b) in enumerate(flat):
        hue,level,saturation=colorsys.rgb_to_hls(float(r),float(g),float(b))
        if saturation:
            degrees=hue*360;left=bisect.bisect_right(CENTERS,degrees)-1;right=(left+1)%8
            span=(CENTERS[right] if right else 360)-CENTERS[left]
            fraction=(degrees-CENTERS[left])/span
            changes=[(1-fraction)*controls.get(NAMES[left]+'_'+axis,0)+fraction*controls.get(NAMES[right]+'_'+axis,0)
                     for axis in ('hue','saturation','lightness')]
            hue=(hue+changes[0]/360)%1
            saturation=saturation+(1-saturation)*changes[1] if changes[1]>=0 else saturation*(1+changes[1])
            level=level+(1-level)*changes[2] if changes[2]>=0 else level*(1+changes[2])
            result[index]=colorsys.hls_to_rgb(hue,max(0,min(1,level)),max(0,min(1,saturation)))
        else:result[index]=[r,g,b]
    out=result.reshape(original.shape)
    if method=='residual':out+=original-bounded
    return out.astype(np.float32)

def expected_rgb(planes,indices):
    results=[]
    q=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method=METHODS[index//4];p=(index%4)/4
        eased=2*p*p if p<.5 else 1-(-2*p+2)**2/2
        strength=.2+.65*eased
        left,right=(2.3,3.) if method=='input_clip' else (2.7,3.) if method=='residual' else (.15,.45)
        amount=np.float32(left+(right-left)*p*p)
        inverse=np.float32(2.**(-float(amount)));gain=np.float32(1/float(inverse))
        expose=lambda v:(v*gain).astype(np.float32)
        values=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        alpha=(planes[index,3].astype(np.float32)/np.float32(65535)).astype(np.float64)[...,None]
        linear=decode(values.astype(np.float64));before=expose(linear) if method in ('input_clip','residual') else linear
        encoded=encode(before.astype(np.float64));mapped=grade(encoded,method,p)
        recovered=decode(mapped.astype(np.float64))
        mixed=(before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        if method not in ('input_clip','residual'):mixed=expose(mixed)
        results.append((mixed.astype(np.float64)*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
