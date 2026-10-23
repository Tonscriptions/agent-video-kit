"""Original five-scene keying recipe and independent dense color mathematics.

No production signal, keyer, automation, neighbourhood or padding helper is
imported. The explicit float32 boundaries model the shared source contract.
"""
from functools import lru_cache
import math
import numpy as np

METHODS = ('green', 'blue_chroma', 'feather', 'despill', 'headroom')
SIGNAL = {'primaries':'bt709', 'transfer':'bt709-oetf'}


def key(prop, left, right, mode='linear', controls=None):
    first = {'at_tick':0, 'value':left, 'interpolation':mode}
    if controls is not None:
        first['control_points'] = controls
    return {'property':prop, 'keyframes':[first, {'at_tick':36000, 'value':right, 'interpolation':'linear'}]}


def effects(method):
    p = {'input_signal':dict(SIGNAL), 'color':'#00ff00', 'similarity':.08, 'blend':.3}
    tracks = []
    if method == 'green':
        p.update(similarity=.05, blend=.2)
        tracks = [key('similarity',.05,.13), key('blend',.2,.55)]
    elif method == 'blue_chroma':
        p.update(color='#0000ff',metric='chroma',matrix='bt709',range='full',similarity=.02,blend=.25)
        tracks = [key('similarity',.02,.09,'ease_out'),key('key_blue',.9,1.,'ease_in')]
    elif method == 'feather':
        p.update(feather=1.25)
        tracks = [key('feather',1.25,6.75,'bezier',[.2,.05,.8,.95]),key('key_green',.9,1.)]
    elif method == 'despill':
        p.update(despill=.2,blend=.5,intensity=.75)
        tracks = [key('despill',.2,1.),key('intensity',.75,1.,'ease_in_out'),key('key_red',0.,.05,'ease_out')]
    elif method == 'headroom':
        p.update(similarity=.2,blend=.25,feather=.5,intensity=.8)
    else:
        raise ValueError(method)
    keyer = {'type':'chroma_key','parameters':p}
    if tracks:
        keyer['keyframes'] = tracks
    left, right = (2.7,3.) if method == 'headroom' else (.15,.45)
    exposure = {'type':'exposure','parameters':{'amount':left,'black':0},
                'keyframes':[key('amount',left,right,'ease_in')]}
    return [exposure,keyer] if method == 'headroom' else [keyer,exposure]


def decode(rgb):
    a = np.abs(rgb)
    return np.where(a < .081,rgb/4.5,np.sign(rgb)*((a+.099)/1.099)**(1/.45)).astype(np.float32)


def encode(rgb):
    a = np.abs(rgb)
    return np.where(a < .018,rgb*4.5,np.sign(rgb)*(1.099*a**.45-.099)).astype(np.float32)


def timing(p):
    roots = np.roots([-.8,1.2,.6,-p])
    u = next(float(v.real) for v in roots if abs(v.imag) < 1e-10 and -1e-12 <= v.real <= 1+1e-12)
    return .15*(1-u)**2*u+2.85*(1-u)*u*u+u**3


@lru_cache(maxsize=128)
def axis_matrix(length,radius):
    """Direct endpoint index matrices for the two integer means."""
    output = np.zeros((length,length),np.float64)
    n = math.floor(radius)
    for r, weight in ((n,1-(radius-n)),(n+1,radius-n)):
        if weight == 0:
            continue
        for offset in range(-r,r+1):
            columns = np.clip(np.arange(length)+offset,0,length-1)
            output[np.arange(length),columns] += weight/(2*r+1)
    return output


def parameters_at(method,p):
    values = {'key':np.array([0.,1.,0.]),'similarity':.08,'blend':.3,'feather':0.,'despill':0.,'intensity':1.}
    if method == 'green':
        values.update(similarity=.05+.08*p,blend=.2+.35*p)
    elif method == 'blue_chroma':
        values.update(key=np.array([0.,0.,.9+.1*p*p]),similarity=.02+.07*(2*p-p*p),blend=.25)
    elif method == 'feather':
        values.update(key=np.array([0.,.9+.1*p,0.]),feather=1.25+5.5*timing(p))
    elif method == 'despill':
        eased = 2*p*p if p < .5 else 1-(-2*p+2)**2/2
        values.update(key=np.array([.05*(2*p-p*p),1.,0.]),despill=.2+.8*p,blend=.5,intensity=.75+.25*eased)
    elif method == 'headroom':
        values.update(similarity=.2,blend=.25,feather=.5,intensity=.8)
    return values


def grade(before,alpha,method,progress):
    values = parameters_at(method,progress)
    encoded = encode(before.astype(np.float64))
    delta = encoded.astype(np.float64)-values['key']
    if method == 'blue_chroma':
        y = .2126*delta[...,0]+.7152*delta[...,1]+.0722*delta[...,2]
        cb, cr = (delta[...,2]-y)/(2*(1-.0722)), (delta[...,0]-y)/(2*(1-.2126))
        distance = np.sqrt((cb*cb+cr*cr)/2)
        distance = axis_matrix(len(distance),1.) @ distance @ axis_matrix(distance.shape[1],1.).T
    else:
        distance = np.sqrt(np.sum(delta*delta,axis=2)/3)
    matte = np.clip((distance-values['similarity'])/values['blend'],0,1)
    radius = values['feather']
    if radius:
        matte = axis_matrix(len(matte),float(radius)) @ matte @ axis_matrix(matte.shape[1],float(radius)).T
        matte = np.clip(matte,0,1)
    if values['despill']:
        recovered = encoded.copy()
        spill = np.maximum(encoded[...,1].astype(np.float64)-np.maximum(encoded[...,0],encoded[...,2]),0)
        recovered[...,1] = encoded[...,1].astype(np.float64)-values['despill']*spill
        graded = decode(recovered.astype(np.float64))
        strength = values['intensity']
        color = (before.astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength).astype(np.float32)
    else:
        color = before
    coverage = (alpha.astype(np.float64)*(1-values['intensity']+values['intensity']*matte[...,None])).astype(np.float32)
    return color,coverage


def expected_rgb(planes,indices):
    results = []
    q = (np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background = np.where(q <= .04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method, progress = METHODS[index//4], (index % 4)/4
        left, right = (2.7,3.) if method == 'headroom' else (.15,.45)
        amount = np.float32(left+(right-left)*progress**2)
        gain = np.float32(1/float(np.float32(2.**(-float(amount)))))
        expose = lambda value:(value*gain).astype(np.float32)
        rgb = np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        alpha = planes[index,3].astype(np.float32)[...,None]/np.float32(65535)
        linear = decode(rgb.astype(np.float64))
        before = expose(linear) if method == 'headroom' else linear
        color, coverage = grade(before,alpha,method,progress)
        if method != 'headroom':
            color = expose(color)
        coverage = coverage.astype(np.float64)
        results.append((color.astype(np.float64)*coverage+background*(1-coverage)).astype(np.float32))
    return np.stack(results)
