"""Independent synthetic demo geometry: direct polynomial and shifted sums."""
import numpy as np


def clip_mask():
    return {'type':'polygon', 'points':[[.12,.12],[.88,.12],[.66,.5],[.88,.88],[.12,.88],[.34,.5]], 'feather':.04}


def curve_mask():
    return {'type':'path', 'segments':[
        {'type':'cubic', 'from':[.12,.5], 'control1':[.12,.08], 'control2':[.88,.08], 'to':[.88,.5], 'samples':8},
        {'type':'cubic', 'from':[.88,.5], 'control1':[.88,.92], 'control2':[.12,.92], 'to':[.12,.5], 'samples':8}],
        'keyframes':[
            {'property':'segments.0.control1.y', 'keyframes':[{'at_tick':0,'value':.08,'interpolation':'linear'},{'at_tick':90000,'value':.3,'interpolation':'linear'}]},
            {'property':'feather', 'keyframes':[{'at_tick':0,'value':.02,'interpolation':'linear'},{'at_tick':90000,'value':.10,'interpolation':'linear'}]}]}


def expected_alpha(source_alpha, frame_index):
    height,width=source_alpha.shape
    y,x=np.indices((height,width),dtype=np.float64)
    if frame_index < 10:
        points=clip_mask()['points']
        feather=.04
    else:
        p=(frame_index-10)/10
        points=[]
        controls=[[(.12,.5),(.12,.08+.22*p),(.88,.08),(.88,.5)],
                  [(.88,.5),(.88,.92),(.12,.92),(.12,.5)]]
        for control in controls:
            for j in range(9):
                t=j/8
                point=tuple((1-t)**3*control[0][axis]+3*(1-t)**2*t*control[1][axis]+3*(1-t)*t*t*control[2][axis]+t**3*control[3][axis] for axis in (0,1))
                if not points or point != points[-1]:
                    points.append(point)
        feather=.02+.08*p
    vertices=[(a*width,b*height) for a,b in points]
    crossings=np.zeros((height,width),np.int32)
    distances=[]
    for i,(a,b) in enumerate(vertices):
        c,d=vertices[(i+1)%len(vertices)];dx,dy=c-a,d-b
        if dy:
            crossings+=(((b>=y)&(d<y))|((b<y)&(d>=y)))&(x<a+dx*(y-b)/dy)
        u=np.clip(((x-a)*dx+(y-b)*dy)/max(1e-6,dx*dx+dy*dy),0,1)
        distances.append(np.sqrt((x-a-u*dx)**2+(y-b-u*dy)**2))
    inside=crossings%2==1
    if frame_index>=10:
        coverage=np.where(inside,np.minimum.reduce(distances),-1)
        coverage=np.clip(coverage/(min(width,height)*feather),0,1)
        return (source_alpha.astype(np.float64)*coverage).astype(np.float32)
    alpha=source_alpha.astype(np.float64)*inside
    radius=int(min(width,height)*feather)
    for axis in (1,1,0,0):
        length=alpha.shape[axis]
        total=np.zeros_like(alpha)
        # Direct symmetric samples, independently of the product's prefix sum.
        for delta in range(-radius,radius+1):
            index=np.arange(length)+delta
            index=np.where(index<0,-index-1,index)
            index=np.where(index>=length,2*length-index-1,index)
            total+=np.take(alpha,index,axis=axis)
        alpha=total/(2*radius+1)
    return alpha.astype(np.float32)


def inverse_oetf(value):
    value=np.asarray(value,np.float64)
    return np.where(value<.081,value/4.5,((value+.099)/1.099)**(1/.45)).astype(np.float32)


def expected_rgb(planes, indices):
    results=[]
    # Author CSS-style hex backgrounds use the declared default sRGB signal;
    # registered camera-source RGB in this fixture uses BT.709 camera OETF.
    encoded_background=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(encoded_background<=.04045,encoded_background/12.92,
        ((encoded_background+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        rgb=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        source=inverse_oetf(rgb).astype(np.float64)
        alpha=expected_alpha(planes[index,3].astype(np.float32)/np.float32(65535),index).astype(np.float64)[...,None]
        results.append((source*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
