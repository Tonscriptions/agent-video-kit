"""Original five-scene recipe; independent binary64/coloursys source oracle.

No product colour, coefficient, animation or effect module is imported.
"""
import colorsys
import numpy as np

METHODS=('balance','wheel','midrange','native_hsl','temperature')
SIGNAL={'primaries':'bt709','transfer':'bt709-oetf'}
BASE={'shadows_red':.12,'shadows_green':-.08,'shadows_blue':.04,
      'midtones_red':-.08,'midtones_green':.05,'midtones_blue':-.06,
      'highlights_red':.05,'highlights_green':-.08,'highlights_blue':.18}

def key(prop,left,right,mode='linear',controls=None):
    first={'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None:first['control_points']=controls
    return {'property':prop,'keyframes':[first,{'at_tick':36000,'value':right,'interpolation':'linear'}]}

def effects(method):
    p={'input_signal':dict(SIGNAL),'output_signal':dict(SIGNAL),'intensity':.2}
    tracks=[key('intensity',.2,.85,'ease_in_out')]
    if method=='balance':
        kind='color_balance';p.update(red=-.1,green=-.05,blue=-.12)
        tracks.append(key('red',-.1,.3,'ease_in'))
    elif method=='temperature':
        kind='color_temperature';p['kelvin']=3500
        tracks.append(key('kelvin',3500,11000,'bezier',[.2,.05,.8,.95]))
    else:
        kind='color_wheel';p.update(BASE)
        tracks.extend([key('shadows_red',.12,.28,'ease_in'),key('midtones_green',.05,.25,'ease_out')])
        if method=='native_hsl':p.update(preserve_lightness='native_hsl',output_gamut='clip')
        elif method=='midrange':p['preserve_lightness']='midrange'
    colour={'type':kind,'parameters':p,'keyframes':tracks}
    left,right=(2.3,3.) if method=='midrange' else (.15,.45)
    exposure={'type':'exposure','parameters':{'amount':left,'black':0},'keyframes':[key('amount',left,right,'ease_in')]}
    return [exposure,colour] if method=='midrange' else [colour,exposure]

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
    if method=='balance':return {'shadows_red':-.1+.4*p*p,'shadows_green':-.05,'shadows_blue':-.12}
    if method=='temperature':
        kelvin=3500+7500*timing(p);delta=max(-1.,min(1.,(kelvin-6500)/6500))
        return {'shadows_red':-delta*.30,'shadows_green':-delta*.05,'shadows_blue':delta*.30}
    return {**BASE,'shadows_red':.12+.16*p*p,'midtones_green':.05+.2*(2*p-p*p)}

def grade(value,method,p):
    """Evaluate analytic real-valued weights, then one Float32 materialisation."""
    original=value.astype(np.float64);level=original.max(axis=2)+original.min(axis=2)
    unit=lambda x:np.minimum(1.,np.maximum(0.,x))
    weights=(unit((.333-level)*4+.5)*.7,
             unit((level-.333)*4+.5)*unit((1-level-.333)*4+.5)*.7,
             unit((level+.333-1)*4+.5)*.7)
    controls=sampled(method,p);out=original.copy()
    for i,c in enumerate(('red','green','blue')):
        for j,t in enumerate(('shadows','midtones','highlights')):out[...,i]+=controls.get(t+'_'+c,0.)*weights[j]
    if method=='midrange':
        delta=(original.max(axis=2)+original.min(axis=2)-out.max(axis=2)-out.min(axis=2))*.5
        out+=delta[...,None]
    elif method=='native_hsl':
        clipped=unit(out);flat=clipped.reshape(-1,3);source_level=level.reshape(-1)*.5
        reconstructed=np.empty_like(flat)
        # Python's independent scalar coloursys implementation supplies hue and
        # HLS reconstruction. Native's preserved level and boundary rule are
        # applied explicitly, rather than borrowing the product's vectors.
        for i,(r,g,b) in enumerate(flat):
            h,_,_=colorsys.rgb_to_hls(float(r),float(g),float(b))
            light=float(source_level[i]);denominator=1-abs(2*light-1)
            saturation=0. if max(r,g,b)==1 or min(r,g,b)==0 or denominator==0 else (max(r,g,b)-min(r,g,b))/denominator
            reconstructed[i]=colorsys.hls_to_rgb(h,light,saturation)
        out=unit(reconstructed.reshape(out.shape))
    return out.astype(np.float32)

def expected_rgb(planes,indices):
    results=[]
    q=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method=METHODS[index//4];p=(index%4)/4
        eased=2*p*p if p<.5 else 1-(-2*p+2)**2/2
        strength=.2+.65*eased
        left,right=(2.3,3.) if method=='midrange' else (.15,.45)
        amount=np.float32(left+(right-left)*p*p)
        inverse=np.float32(2.**(-float(amount)));gain=np.float32(1/float(inverse))
        expose=lambda v:(v*gain).astype(np.float32)
        values=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        alpha=(planes[index,3].astype(np.float32)/np.float32(65535)).astype(np.float64)[...,None]
        linear=decode(values.astype(np.float64));before=expose(linear) if method=='midrange' else linear
        encoded=encode(before.astype(np.float64));mapped=grade(encoded,method,p)
        recovered=decode(mapped.astype(np.float64))
        mixed=(before.astype(np.float64)*(1-strength)+recovered.astype(np.float64)*strength).astype(np.float32)
        if method!='midrange':mixed=expose(mixed)
        results.append((mixed.astype(np.float64)*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
