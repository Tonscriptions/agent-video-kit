"""Original demo CUBEs and an independent linear-system pixel oracle.

No product LUT, colour conversion, effect, clock or interpolation helper is
imported. The table builder is the declared original CC0 creative input.
"""
import itertools
from pathlib import Path
import numpy as np

METHODS = ('nearest','trilinear','tetrahedral','pyramid','prism')


def table_values(size=5):
    values = []
    for b in np.linspace(0,1,size):
        for g in np.linspace(0,1,size):
            for r in np.linspace(0,1,size):
                values.append((.045+.91*r**.82+.08*g*b,.012+.85*g**1.12+.06*r*b,.018+.74*b**1.2+.06*r*g))
    return np.asarray(values,np.float32).reshape(size,size,size,3)


def write_original_cube(path):
    table = table_values()
    Path(path).write_text('TITLE "Original CC0 warm demonstration"\nLUT_3D_SIZE 5\n'+''.join(
        ' '.join(format(float(v),'.9g') for v in row)+'\n' for row in table.reshape(-1,3)),encoding='utf8',newline='\n')
    return table


def effects(method):
    signal = {'primaries':'bt709','transfer':'bt709-oetf'}
    lut = {'type':'lut3d','parameters':{'lut_id':'original_look','input_signal':signal,'output_signal':dict(signal),
        'interpolation':method,'intensity':.15},'keyframes':[{'property':'intensity','keyframes':[
            {'at_tick':0,'value':.15,'interpolation':'ease_in_out'},
            {'at_tick':36000,'value':.9,'interpolation':'linear'}]}]}
    exposure = {'type':'exposure','parameters':{'amount':.4,'black':.005}}
    return [exposure,lut] if method in ('nearest','tetrahedral','prism') else [lut,exposure]


def lookup(table, rgb, method):
    n = len(table)
    coordinates = (np.minimum(1,np.maximum(0,rgb)).astype(np.float32)*np.float32(n-1)).astype(np.float64)
    low = np.floor(coordinates).astype(int);f = coordinates-low
    def samples(vertices,where):
        points = np.minimum(low[where,None,:]+np.array(vertices,dtype=int)[None,:,:],n-1)
        return table[points[...,2],points[...,1],points[...,0]].astype(np.float64)
    if method=='nearest':
        nearest = np.floor(coordinates+.5).astype(int)
        return table[nearest[:,2],nearest[:,1],nearest[:,0]]
    out = np.zeros_like(rgb,dtype=np.float64)
    if method=='trilinear':
        vertices = list(itertools.product((0,1),repeat=3));where = np.ones(len(rgb),bool)
        weights = np.prod(np.where(np.array(vertices)[None,:,:],f[:,None,:],1-f[:,None,:]),axis=2)
        out = np.einsum('nv,nvc->nc',weights,samples(vertices,where))
    elif method=='tetrahedral':
        remaining = np.ones(len(rgb),bool)
        for permutation in itertools.permutations(range(3)):
            where = remaining.copy()
            for i in range(2):where &= f[:,permutation[i]]>=f[:,permutation[i+1]]
            remaining[where] = False
            if not np.any(where):continue
            vertices = [np.zeros(3,int)]
            for axis in permutation:
                point = vertices[-1].copy();point[axis] = 1;vertices.append(point)
            basis = np.column_stack((np.ones(4),vertices))
            weights = np.column_stack((np.ones(where.sum()),f[where]))@np.linalg.inv(basis)
            out[where] = np.einsum('nv,nvc->nc',weights,samples(vertices,where))
    elif method=='prism':
        for upper_triangle in (True,False):
            where = (f[:,2]>f[:,0]) if upper_triangle else (f[:,2]<=f[:,0])
            if not np.any(where):continue
            triangle = [(0,0),(0,1),(1,1)] if upper_triangle else [(0,0),(1,0),(1,1)]
            weights = np.column_stack((np.ones(where.sum()),f[where,0],f[where,2]))@np.linalg.inv(np.column_stack((np.ones(3),triangle)))
            bottom = np.einsum('nv,nvc->nc',weights,samples([(r,0,b) for r,b in triangle],where))
            top = np.einsum('nv,nvc->nc',weights,samples([(r,1,b) for r,b in triangle],where))
            out[where] = bottom*(1-f[where,1,None])+top*f[where,1,None]
    else:
        axis_r = (f[:,0]<f[:,1])&(f[:,0]<f[:,2])
        axis_g = ~axis_r&(f[:,1]<f[:,0])&(f[:,1]<f[:,2])
        for axis,where in enumerate((axis_r,axis_g,~(axis_r|axis_g))):
            if not np.any(where):continue
            others = [i for i in range(3) if i!=axis]
            vertices = []
            for u,v in ((0,0),(1,0),(0,1),(1,1)):
                point = np.zeros(3,int);point[others] = [u,v];vertices.append(point)
            vertices.append(np.ones(3,int));vertices = np.array(vertices)
            basis = np.column_stack((np.ones(5),vertices,vertices[:,others[0]]*vertices[:,others[1]]))
            weights = np.column_stack((np.ones(where.sum()),f[where],f[where,others[0]]*f[where,others[1]]))@np.linalg.inv(basis)
            out[where] = np.einsum('nv,nvc->nc',weights,samples(vertices,where))
    return out.astype(np.float32)


def decode_transfer(rgb):
    a = np.abs(rgb);sign = np.sign(rgb)
    return np.where(a<.081,rgb/4.5,sign*((a+.099)/1.099)**(1/.45)).astype(np.float32)


def encode_transfer(rgb):
    a = np.abs(rgb);sign = np.sign(rgb)
    return np.where(a<.018,rgb*4.5,sign*(1.099*a**.45-.099)).astype(np.float32)


def expected_rgb(planes, indices):
    results = []
    encoded_background = (np.array([16,32,64],np.float64)/255).astype(np.float32).astype(np.float64)
    background = np.where(encoded_background<=.04045,encoded_background/12.92,((encoded_background+.055)/1.055)**2.4).astype(np.float32).astype(np.float64)
    table = table_values();h,w = planes.shape[2:]
    amount = np.float32(.4);black = np.float32(.005)
    white = np.float32(2.**(-float(amount)));gain = np.float32(1/float(abs(np.float32(white-black))))
    def exposure(rgb):return ((rgb-black)*gain).astype(np.float32)
    for index in indices:
        values = np.moveaxis(planes[index,[2,0,1]],0,-1).astype(np.float32)/np.float32(65535)
        linear = decode_transfer(values.astype(np.float64))
        method = METHODS[index//4]
        before = exposure(linear) if method in ('nearest','tetrahedral','prism') else linear
        encoded = encode_transfer(before.astype(np.float64))
        mapped = lookup(table,encoded.reshape(-1,3).astype(np.float64),method).reshape(h,w,3)
        graded = decode_transfer(mapped.astype(np.float64))
        p = (index%4)/4
        eased = 2*p*p if p<.5 else 1-(-2*p+2)**2/2
        strength = .15+(.9-.15)*eased
        mixed = (before.astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength).astype(np.float32)
        if method not in ('nearest','tetrahedral','prism'):mixed = exposure(mixed)
        alpha = (planes[index,3].astype(np.float32)/np.float32(65535)).astype(np.float64)[...,None]
        results.append((mixed.astype(np.float64)*alpha+background*(1-alpha)).astype(np.float32))
    return np.stack(results)
