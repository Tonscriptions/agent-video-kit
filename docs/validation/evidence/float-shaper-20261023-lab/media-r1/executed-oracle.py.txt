"""Original 1D/combined LUT fixtures and independent Hermite/color oracle.

No production LUT, signal, automation or interpolation helper is imported.
"""
import numpy as np

METHODS=('1d_linear','1d_cubic','1d_spline','combined','headroom')
SIGNAL={'primaries':'bt709','transfer':'bt709-oetf'}
LOOKS={
    '1d_linear':('linear',None,((-.1,0.,-.2),(1.1,1.2,1.3)),None),
    '1d_cubic':('cubic',None,((0.,)*3,(1.,)*3),None),
    '1d_spline':('spline',None,((0.,)*3,(1.,)*3),None),
    'combined':('cosine','trilinear',((-.2,)*3,(1.2,)*3),((-.1,)*3,(1.3,)*3)),
    'headroom':('nearest','tetrahedral',((0.,)*3,(1.,)*3),((0.,)*3,(1.,)*3)),
}


def tables():
    x=np.linspace(0,1,9)
    one=np.stack((-.1+1.25*x*x,.05+.95*np.sqrt(x),.02+1.15*x+.03*np.sin(x*np.pi*2)),1).astype(np.float32)
    n=3
    three=np.array([(.04+.78*r+.14*g*b,.03+.8*g+.12*r*b,.06+.83*b+.07*r*g)
        for b in np.linspace(0,1,n) for g in np.linspace(0,1,n) for r in np.linspace(0,1,n)],np.float32).reshape(n,n,n,3)
    return one,three


def write_tables(directory):
    directory.mkdir(parents=True,exist_ok=True);one,three=tables();paths=[]
    for name,(method,cube_method,domain,cube_domain) in LOOKS.items():
        text='TITLE "Original Agent 1D and Resolve shaper '+name+'"\nLUT_1D_SIZE 9\n'
        if cube_method:
            text+='LUT_1D_INPUT_RANGE '+str(domain[0][0])+' '+str(domain[1][0])+'\nLUT_3D_SIZE 3\n'
            text+='LUT_3D_INPUT_RANGE '+str(cube_domain[0][0])+' '+str(cube_domain[1][0])+'\n'
        else:
            text+='DOMAIN_MIN '+' '.join(map(str,domain[0]))+'\nDOMAIN_MAX '+' '.join(map(str,domain[1]))+'\n'
        rows=list(one)
        if cube_method:rows.extend(three.reshape(-1,3))
        text+=''.join(' '.join(format(float(v),'.9g') for v in row)+'\n' for row in rows)
        path=directory/(name+'.cube');path.write_text(text,encoding='utf8',newline='\n');paths.append(path)
    return paths


def key(prop,left,right,mode='linear'):
    return {'property':prop,'keyframes':[{'at_tick':0,'value':left,'interpolation':mode},
        {'at_tick':36000,'value':right,'interpolation':'linear'}]}


def effects(method):
    first,second,_,_=LOOKS[method]
    p={'lut_id':method,'input_signal':dict(SIGNAL),'output_signal':dict(SIGNAL),'interpolation_1d':first,'intensity':.2}
    if second:p['interpolation']=second
    lut={'type':'lut','parameters':p,'keyframes':[key('intensity',.2,.9,'ease_in_out')]}
    left,right=(2.5,2.9) if method=='headroom' else (.1,.35)
    exposure={'type':'exposure','parameters':{'amount':left},'keyframes':[key('amount',left,right,'ease_in')]}
    return [exposure,lut] if method=='1d_cubic' else [lut,exposure]


def decode(rgb):
    a=np.abs(rgb)
    return np.where(a<.081,rgb/4.5,np.sign(rgb)*((a+.099)/1.099)**(1/.45)).astype(np.float32)


def encode(rgb):
    a=np.abs(rgb)
    return np.where(a<.018,rgb*4.5,np.sign(rgb)*(1.099*a**.45-.099)).astype(np.float32)


def lookup_1d(rgb,table,method,domain):
    q=(np.minimum(1.,np.maximum(0.,(rgb.astype(np.float64)-domain[0])/(np.array(domain[1])-domain[0]))).astype(np.float32)*np.float32(len(table)-1)).astype(np.float64)
    k=np.floor(q).astype(int);j=np.minimum(k+1,len(table)-1);t=q-k;c=np.arange(3)
    if method=='nearest':return table[np.floor(q+.5).astype(int),c]
    y0=table[k,c].astype(np.float64);y1=table[j,c].astype(np.float64)
    if method in ('linear','cosine'):
        u=t if method=='linear' else .5-.5*np.cos(np.pi*t)
        return (y0+(y1-y0)*u).astype(np.float32)
    slope0=y1-table[np.maximum(k-1,0),c].astype(np.float64)
    slope1=table[np.minimum(j+1,len(table)-1),c].astype(np.float64)-y0
    if method=='spline':slope0*=.5;slope1*=.5
    return ((2*t**3-3*t**2+1)*y0+(t**3-2*t**2+t)*slope0+(-2*t**3+3*t**2)*y1+(t**3-t**2)*slope1).astype(np.float32)


def lookup_3d(rgb,table,method,domain):
    q=(np.clip((rgb.astype(np.float64)-domain[0])/(np.array(domain[1])-domain[0]),0,1).astype(np.float32)*np.float32(len(table)-1)).astype(np.float64)
    lo=np.floor(q).astype(int);hi=np.minimum(lo+1,len(table)-1);f=q-lo
    def fetch(bits):
        indexes=np.where(np.asarray(bits),hi,lo)
        return table[indexes[...,2],indexes[...,1],indexes[...,0]].astype(np.float64)
    out=np.zeros_like(rgb,dtype=np.float64)
    if method=='trilinear':
        for r in (0,1):
            for g in (0,1):
                for b in (0,1):
                    w=np.prod(np.where([r,g,b],f,1-f),axis=-1)
                    out+=fetch([r,g,b])*w[...,None]
    else:
        # The six simplex regions use cumulative sorted-axis vertices.
        order=np.argsort(-f,axis=-1,kind='stable');v=np.take_along_axis(f,order,axis=-1)
        weights=np.stack((1-v[...,0],v[...,0]-v[...,1],v[...,1]-v[...,2],v[...,2]),-1)
        bits=np.zeros_like(lo,dtype=bool)
        for level in range(4):
            out+=fetch(bits)*weights[...,level,None]
            if level<3:np.put_along_axis(bits,order[...,level,None],True,axis=-1)
    return out.astype(np.float32)


def expected_rgb(planes,indices):
    one,three=tables();results=[]
    q=(np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background=np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    for index in indices:
        method,p=METHODS[index//4],(index%4)/4
        left,right=(2.5,2.9) if method=='headroom' else (.1,.35)
        amount=np.float32(left+(right-left)*p*p);gain=np.float32(1/float(np.float32(2.**(-float(amount)))))
        rgb=np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        alpha=planes[index,3].astype(np.float32)[...,None]/np.float32(65535)
        before=decode(rgb.astype(np.float64))
        if method=='1d_cubic':before=(before*gain).astype(np.float32)
        encoded=encode(before.astype(np.float64));first,second,domain,cube_domain=LOOKS[method]
        mapped=lookup_1d(encoded,one,first,domain)
        if second:mapped=lookup_3d(mapped,three,second,cube_domain)
        graded=decode(mapped.astype(np.float64));eased=2*p*p if p<.5 else 1-(-2*p+2)**2/2
        strength=.2+.7*eased
        color=(before.astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength).astype(np.float32)
        if method!='1d_cubic':color=(color*gain).astype(np.float32)
        results.append((color.astype(np.float64)*alpha.astype(np.float64)+background*(1-alpha.astype(np.float64))).astype(np.float32))
    return np.stack(results)
