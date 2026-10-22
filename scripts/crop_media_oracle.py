"""Synthetic crop demo oracle built from a forward homogeneous transform.

Does not import the product sampler, plan resolver or keyframe evaluator.
Geometry and alpha are compared before the display/delivery integer edge.
"""
import math
import numpy as np


def key(name, left, right):
    return {'property':name,'keyframes':[{'at_tick':0,'value':left,'interpolation':'linear'},
        {'at_tick':90000,'value':right,'interpolation':'linear'}]}


def clip_crop():
    return {'unit':'normalized','x':.12,'y':.13,'width':.65,'height':.62,'fit':'fit',
        'keyframes':[key('x',.12,.31)]}


def curve_crop():
    return {'unit':'normalized','x':.1,'y':.04,'width':.8,'height':.9,'fit':'fill',
        'keyframes':[key('x',.1,.3),key('y',.04,.15),key('width',.8,.45),key('height',.9,.6)]}


def clip_motion():
    return [key('transform.rotation',-5,5),key('transform.scale',.9,1.05)]


def curve_motion():
    return [key('transform.rotation',-10,14),key('transform.scale',.82,1.12)]


def forward_projection(a, window, size, fit, *, rotation, scale, anchor=(.5,.5), position=(.5,.5)):
    # Independently assemble source -> parent and invert it with LAPACK. The
    # product instead directly expands the inverse transform into coefficients.
    w,h=size;cx,cy,cw,ch=window
    fitx,fity=w/cw,h/ch
    if fit != 'stretch':
        fitx=fity=(max if fit=='fill' else min)(fitx,fity)
    def translate(x,y):return np.array([[1,0,x],[0,1,y],[0,0,1]],np.float64)
    angle=math.radians(rotation);c,s=math.cos(angle),math.sin(angle)
    rotate=np.array([[c,-s,0],[s,c,0],[0,0,1]],np.float64)
    zoom=np.diag([scale*fitx,scale*fity,1.])
    forward=translate(position[0]*w-.5,position[1]*h-.5)@rotate@zoom@translate(.5-cx-anchor[0]*cw,.5-cy-anchor[1]*ch)
    y,x=np.indices((h,w),dtype=np.float64)
    coordinates=np.linalg.solve(forward,np.stack((x.ravel(),y.ravel(),np.ones(w*h)),axis=0))
    sx,sy=coordinates[:2].reshape(2,h,w)
    coverage=(sx>=cx-.5)&(sx<cx+cw-.5)&(sy>=cy-.5)&(sy<cy+ch-.5)
    sx,sy=np.clip(sx,cx,cx+cw-1),np.clip(sy,cy,cy+ch-1)
    left,top=np.floor(sx).astype(np.int64),np.floor(sy).astype(np.int64)
    right,bottom=left+1,top+1
    dx,dy=(sx-left)[...,None],(sy-top)[...,None]
    premult=a.astype(np.float64).copy();premult[...,:3]*=premult[...,3:4]
    def take(yy,xx):return premult[np.clip(yy,0,len(a)-1),np.clip(xx,0,a.shape[1]-1)]
    top_row=take(top,left)*(1-dx)+take(top,right)*dx
    bottom_row=take(bottom,left)*(1-dx)+take(bottom,right)*dx
    result=(top_row*(1-dy)+bottom_row*dy)*coverage[...,None]
    np.divide(result[...,:3],result[...,3:4],out=result[...,:3],where=result[...,3:4]>0)
    return result.astype(np.float32)


def expected_rgb(planes, indices):
    results=[]
    encoded_background=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(encoded_background<=.04045,encoded_background/12.92,
        ((encoded_background+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    h,w=planes.shape[2:]
    for index in indices:
        rgb=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        rgb=rgb.astype(np.float64)
        a=np.empty((h,w,4),np.float32)
        a[...,:3]=np.where(rgb<.081,rgb/4.5,((rgb+.099)/1.099)**(1/.45)).astype(np.float32)
        a[...,3]=planes[index,3].astype(np.float32)/np.float32(65535)
        p=(index%10)/10
        if index<10:
            # Fixed leaf size and moving origin retain native integer crop
            # rounding. Sizes/origins here are independently written constants.
            window=(round((.12+(.31-.12)*p)*w),round(.13*h),round(.65*w),round(.62*h))
            transformed=forward_projection(a,window,(w,h),'fit',rotation=-5+10*p,scale=.9+(1.05-.9)*p)
        else:
            cw=(.8+(.45-.8)*p)*w;ch=(.9+(.6-.9)*p)*h
            window=(min((.1+(.3-.1)*p)*w,w-cw),min((.04+(.15-.04)*p)*h,h-ch),cw,ch)
            transformed=forward_projection(a,window,(w,h),'fill',rotation=-10+24*p,scale=.82+(1.12-.82)*p,
                anchor=(.45,.55),position=(.53,.49))
        alpha=transformed[...,3:4].astype(np.float64)
        results.append((transformed[...,:3].astype(np.float64)*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
