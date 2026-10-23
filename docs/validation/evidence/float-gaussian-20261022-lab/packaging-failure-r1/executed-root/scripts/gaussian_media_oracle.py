"""Original Gaussian recipe and independent boundary-system matrix reference.

No product color, effect, coefficient, automation or recurrence is imported.
"""
from functools import lru_cache
import math
import numpy as np

METHODS=('linked','horizontal','vertical','RGB_only','premult_headroom')
SIGNAL={'primaries':'bt709','transfer':'bt709-oetf'}


def key(prop,left,right,mode='linear',controls=None):
    first={'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None:first['control_points']=controls
    return {'property':prop,'keyframes':[first,{'at_tick':36000,'value':right,'interpolation':'linear'}]}


def effects(method):
    p={'input_signal':dict(SIGNAL),'output_signal':dict(SIGNAL),'intensity':.2,'steps':3}
    tracks=[key('intensity',.2,.85,'ease_in_out')]
    if method=='linked':
        p.update(radius=3);tracks.append(key('radius',3,10,'ease_in'))
    elif method=='horizontal':
        p.update(radius_x=4,radius_y=0);tracks.append(key('radius_x',4,16,'bezier',[.2,.05,.8,.95]))
    elif method=='vertical':
        p.update(radius_x=0,radius_y=3,steps=2);tracks.append(key('radius_y',3,12,'ease_out'))
    elif method=='RGB_only':
        p.update(radius=6,planes=7);tracks.append(key('radius',6,12,'hold'))
    else:p.update(radius=8,alpha_mode='premultiplied')
    blur={'type':'blur','parameters':p,'keyframes':tracks}
    left,right=(2.7,3.) if method=='premult_headroom' else (.15,.45)
    exposure={'type':'exposure','parameters':{'amount':left,'black':0},'keyframes':[key('amount',left,right,'ease_in')]}
    return [exposure,blur] if method=='premult_headroom' else [blur,exposure]


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


@lru_cache(maxsize=64)
def axis_matrix(length,radius,steps):
    if not radius:return np.eye(length)
    lam=radius**2/(2*steps)
    coefficient=4*lam/(math.sqrt(1+4*lam)+1)**2
    diagonal=np.ones(length);lower=diagonal*(1-coefficient);upper=lower.copy()
    lower[0]=1;upper[-1]=1
    forward=np.eye(length)-np.diag(np.full(length-1,coefficient),-1)
    backward=np.eye(length)-np.diag(np.full(length-1,coefficient),1)
    stage=np.linalg.solve(backward,np.diag(upper))@np.linalg.solve(forward,np.diag(lower))
    return np.linalg.matrix_power(stage,steps)


def grade(encoded,alpha,method,p):
    rx=3+7*p*p if method=='linked' else 4+12*timing(p) if method=='horizontal' else 0 if method=='vertical' else 6 if method=='RGB_only' else 8
    ry=rx if method not in ('horizontal','vertical') else 0 if method=='horizontal' else 3+9*(2*p-p*p)
    steps=2 if method=='vertical' else 3
    data=np.concatenate((encoded,alpha),axis=2).astype(np.float64)
    if method=='premult_headroom':data[...,:3]*=data[...,3:4]
    y=axis_matrix(data.shape[0],float(ry),steps);x=axis_matrix(data.shape[1],float(rx),steps)
    result=np.einsum('ij,jkc,lk->ilc',y,data,x,optimize=True)
    if method=='premult_headroom':
        positive=result[...,3]>0
        np.divide(result[...,:3],result[...,3:4],out=result[...,:3],where=positive[...,None])
        result[...,:3][~positive]=0
    if method=='RGB_only':result[...,3:4]=alpha
    return result.astype(np.float32)


def expected_rgb(planes,indices):
    results=[]
    q=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method=METHODS[index//4];p=(index%4)/4
        eased=2*p*p if p<.5 else 1-(-2*p+2)**2/2
        strength=.2+.65*eased
        left,right=(2.7,3.) if method=='premult_headroom' else (.15,.45)
        amount=np.float32(left+(right-left)*p*p)
        inverse=np.float32(2.**(-float(amount)));gain=np.float32(1/float(inverse))
        expose=lambda v:(v*gain).astype(np.float32)
        values=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        alpha=planes[index,3].astype(np.float32)[...,None]/np.float32(65535)
        linear=decode(values.astype(np.float64));before=expose(linear) if method=='premult_headroom' else linear
        encoded=encode(before.astype(np.float64));mapped=grade(encoded,alpha,method,p)
        recovered=decode(mapped[...,:3].astype(np.float64))
        mixed=(before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        coverage=(alpha.astype(np.float64)*(1-strength)+mapped[...,3:4].astype(np.float64)*strength).astype(np.float32).astype(np.float64)
        if method!='premult_headroom':mixed=expose(mixed)
        results.append((mixed.astype(np.float64)*coverage+background*(1-coverage)).astype(np.float32))
    return np.stack(results)
