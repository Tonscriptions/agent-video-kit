"""Closed five-scene creative recipe and an independent source-pixel oracle.

This file imports no product math, coefficient, signal or animation modules.
"""
import numpy as np

METHODS = ('shared','channels','auto','preserve','bezier')
SIGNAL = {'primaries':'bt709','transfer':'bt709-oetf'}


def key(prop,left,right,mode='linear',controls=None):
    first = {'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None:first['control_points'] = controls
    return {'property':prop,'keyframes':[first,{'at_tick':36000,'value':right,'interpolation':'linear'}]}


def effects(method):
    p = {'input_signal':dict(SIGNAL),'output_signal':dict(SIGNAL),'output_black':.03125,'output_white':.9375}
    tracks = [key('output_black',.03125,.09375,'ease_in'),
        key('intensity',.2,.85,'bezier' if method=='bezier' else 'ease_in_out',
            [.2,.05,.8,.95] if method=='bezier' else None)]
    if method=='channels':
        p.update(red_output_white=.75,green_output_black=.0625,blue_output_white=.8125,alpha_output_white=.875)
        tracks.append(key('red_output_white',.75,.9375,'ease_out'))
    if method=='auto':p.update(input_black=-1,input_white=-1)
    if method=='preserve':p.update(red_output_white=.875,blue_output_white=.8125,preserve='lum')
    levels = {'type':'color_levels','parameters':p,'keyframes':tracks}
    exposure = {'type':'exposure','parameters':{'amount':.2,'black':0},'keyframes':[
        key('amount',.2,.6,'ease_in'),key('black',0,.0078125,'ease_out')]}
    return [exposure,levels] if method in ('shared','channels','bezier') else [levels,exposure]


def decode(rgb):
    a = np.abs(rgb)
    return np.where(a<.081,rgb/4.5,np.sign(rgb)*((a+.099)/1.099)**(1/.45)).astype(np.float32)


def encode(rgb):
    a = np.abs(rgb)
    return np.where(a<.018,rgb*4.5,np.sign(rgb)*(1.099*a**.45-.099)).astype(np.float32)


def expected_rgb(planes,indices):
    results = []
    q = (np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background = np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        phase = METHODS[index//4];p = (index%4)/4
        eased = 2*p*p if p<.5 else 1-(-2*p+2)**2/2
        if phase=='bezier':
            roots = np.roots([-.8,1.2,.6,-p])
            u = next(float(v.real) for v in roots if abs(v.imag)<1e-10 and -1e-12<=v.real<=1+1e-12)
            strength = .2+.65*(.15*(1-u)**2*u+2.85*(1-u)*u*u+u**3)
        else:strength = .2+.65*eased
        amount = np.float32(.2+.4*p*p);black = np.float32(.0078125*(2*p-p*p))
        inverse_white = np.float32(2.**(-float(amount)))
        gain = np.float32(1/float(abs(np.float32(inverse_white-black))))
        def expose(value):return ((value-black)*gain).astype(np.float32)
        values = np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        original_alpha = planes[index,3].astype(np.float32)/np.float32(65535)
        linear = decode(values.astype(np.float64));before = expose(linear) if phase in ('shared','channels','bezier') else linear
        encoded = encode(before.astype(np.float64));graded = np.empty_like(encoded)
        shared_black = np.float32(.03125+.0625*p*p)
        for c in range(3):
            low,high = np.float32(0),np.float32(1)
            if phase=='auto':low = min(np.float32(1),encoded[...,c].min());high = max(np.float32(0),encoded[...,c].max())
            out_low,out_high = shared_black,np.float32(.9375)
            if phase=='channels':
                if c==0:out_high = np.float32(.75+.1875*(2*p-p*p))
                elif c==1:out_low = np.float32(.0625)
                else:out_high = np.float32(.8125)
            if phase=='preserve':
                if c==0:out_high = np.float32(.875)
                elif c==2:out_high = np.float32(.8125)
            slope = np.float32(float(np.float32(out_high-out_low))/float(np.float32(high-low)))
            graded[...,c] = ((encoded[...,c]-low)*slope+out_low).astype(np.float32)
        if phase=='preserve':
            # Binary64 extrema equations form an independent reference. The
            # tolerance includes native binary32 metric/ratio rounding.
            src = encoded.astype(np.float64);dst = graded.astype(np.float64)
            ratio = (src.max(axis=2)+src.min(axis=2))/(dst.max(axis=2)+dst.min(axis=2))
            graded = (dst*ratio[...,None]).astype(np.float32)
        recovered = decode(graded.astype(np.float64))
        mixed = (before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        alpha = original_alpha
        if phase=='channels':
            mapped_alpha = (original_alpha*np.float32(.875)).astype(np.float32)
            alpha = (original_alpha.astype(np.float64)*(1-strength)+mapped_alpha.astype(np.float64)*strength).astype(np.float32)
        if phase not in ('shared','channels','bezier'):mixed = expose(mixed)
        alpha = alpha.astype(np.float64)[...,None]
        results.append((mixed.astype(np.float64)*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
