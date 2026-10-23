"""Original five-scene recipe and independent matrix-solve tone oracle.

No product color, matrix, coefficient, automation or effect module is imported.
"""
import math
import numpy as np

METHODS=('color','gamma','hsl','gray','native_clip')
SIGNAL={'primaries':'bt709','transfer':'bt709-oetf'}


def key(prop,left,right,mode='linear',controls=None):
    first={'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None:first['control_points']=controls
    return {'property':prop,'keyframes':[first,{'at_tick':36000,'value':right,'interpolation':'linear'}]}


def effects(method):
    p={'input_signal':dict(SIGNAL),'output_signal':dict(SIGNAL),'matrix':'bt709','range':'full','intensity':.2}
    tracks=[key('intensity',.2,.85,'ease_in_out')]
    if method=='color':
        kind='color';p.update(brightness=-.04,contrast=1.1,saturation=.7)
        tracks.append(key('brightness',-.04,.08,'ease_in'))
    elif method=='gamma':
        kind='gamma';p.update(gamma=.7)
        tracks.append(key('gamma',.7,1.8,'bezier',[.2,.05,.8,.95]))
    elif method=='hsl':
        kind='hsl';p.update(hue=-35,saturation=.8,lightness=.12,matrix='smpte170m',range='limited')
        tracks.append(key('hue',-35,40,'ease_out'))
    elif method=='gray':
        kind='grayscale';p.update(matrix='bt2020nc')
    else:
        kind='color';p.update(brightness=.1,contrast=1.8,saturation=1.7,arithmetic='native_coefficients')
        tracks.append(key('contrast',1.8,1.2,'hold'))
    colour={'type':kind,'parameters':p,'keyframes':tracks}
    left,right=(2.7,3.) if method=='native_clip' else (.15,.45)
    exposure={'type':'exposure','parameters':{'amount':left,'black':0},'keyframes':[key('amount',left,right,'ease_in')]}
    return [exposure,colour] if method=='native_clip' else [colour,exposure]


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


def grade(value,method,p):
    # Matrix rows derive normalized luma and centered chroma; an independent
    # matrix inverse reconstructs RGB, rather than product per-channel math.
    kr,kb=(.299,.114) if method=='hsl' else (.2627,.0593) if method=='gray' else (.2126,.0722)
    y=np.array([kr,1-kr-kb,kb],np.float64)
    matrix=np.array([y,(np.array([0,0,1])-y)/(2-2*kb),(np.array([1,0,0])-y)/(2-2*kr)])
    scales=np.array([219,224,224] if method=='hsl' else [255,255,255])
    offsets=np.array([16 if method=='hsl' else 0,128,128])
    q=value.astype(np.float64)@matrix.T*scales+offsets
    if method in ('hsl','gray'):
        angle=(-35+75*(2*p-p*p))*math.pi/180 if method=='hsl' else 0
        saturation=.8 if method=='hsl' else 0
        uv=(q[...,1:]-128)@np.array([[math.cos(angle),math.sin(angle)],[-math.sin(angle),math.cos(angle)]])*saturation+128
        q[...,1:]=np.clip(uv,0,255)
        if method=='hsl':q[...,0]=np.clip(q[...,0]+.12*25.5,0,255)
    else:
        brightness=-.04+.12*p*p if method=='color' else .1 if method=='native_clip' else 0.
        contrast=1.1 if method=='color' else 1.8 if method=='native_clip' else 1.
        saturation=.7 if method=='color' else 1.7 if method=='native_clip' else 1.
        gamma=.7+1.1*timing(p) if method=='gamma' else 1.
        for plane,c,b,g in ((0,contrast,brightness,gamma),(1,saturation,0.,1.),(2,saturation,0.,1.)):
            if c==1 and b==0 and g==1:continue
            if method=='native_clip':
                c,b=float(np.float32(c)),float(np.float32(b))
                coefficient=math.trunc(c*4096)
                shift=math.trunc(math.trunc(100*b+100)*511/200)-128-math.trunc(coefficient/32)
                q[...,plane]=np.clip(q[...,plane]*coefficient/4096+shift,0,255)
            else:q[...,plane]=np.clip(c*(q[...,plane]/255-.5)+.5+b,0,1)**(1/g)*255
    return (((q-offsets)/scales)@np.linalg.inv(matrix).T).astype(np.float32)


def expected_rgb(planes,indices):
    results=[]
    q=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method=METHODS[index//4];p=(index%4)/4
        eased=2*p*p if p<.5 else 1-(-2*p+2)**2/2
        strength=.2+.65*eased
        left,right=(2.7,3.) if method=='native_clip' else (.15,.45)
        amount=np.float32(left+(right-left)*p*p)
        inverse=np.float32(2.**(-float(amount)));gain=np.float32(1/float(inverse))
        expose=lambda v:(v*gain).astype(np.float32)
        values=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        alpha=(planes[index,3].astype(np.float32)/np.float32(65535)).astype(np.float64)[...,None]
        linear=decode(values.astype(np.float64));before=expose(linear) if method=='native_clip' else linear
        encoded=encode(before.astype(np.float64));mapped=grade(encoded,method,p)
        recovered=decode(mapped.astype(np.float64))
        mixed=(before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        if method!='native_clip':mixed=expose(mixed)
        results.append((mixed.astype(np.float64)*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
