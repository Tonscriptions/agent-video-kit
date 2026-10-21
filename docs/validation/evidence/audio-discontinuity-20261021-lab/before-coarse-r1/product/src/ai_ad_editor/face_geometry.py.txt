"""Explicit, compact-support face edits; no inference or identity decisions."""
from __future__ import annotations
import math

CONTROLS = ('skin_smooth', 'exposure_ev', 'face_slim', 'eye_enlarge')
TRANSFERS = ('srgb','bt709','gamma22','gamma28')


def exposed_rgb(rgb,ev,transfer,np):
    if transfer not in TRANSFERS:
        raise ValueError('FACE_TRANSFER_UNSUPPORTED')
    if transfer == 'srgb':
        linear = np.where(rgb <= .04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    elif transfer == 'bt709':
        linear = np.where(rgb < .081,rgb/4.5,((rgb+.099)/1.099)**(1/.45))
    else:
        linear = rgb**(2.2 if transfer == 'gamma22' else 2.8)
    linear = np.clip(linear*(2**ev),0,1)
    if transfer == 'srgb':
        return np.where(linear <= .0031308,linear*12.92,1.055*linear**(1/2.4)-.055)
    if transfer == 'bt709':
        return np.where(linear < .018,linear*4.5,1.099*linear**.45-.099)
    return linear**(1/(2.2 if transfer == 'gamma22' else 2.8))


def controls(**values):
    if set(values) - set(CONTROLS):
        raise ValueError('FACE_CONTROLS_UNKNOWN')
    result = {k: values.get(k, 0.) for k in CONTROLS}
    for key, value in result.items():
        low = -1 if key == 'exposure_ev' else 0
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= 1:
            raise ValueError('FACE_CONTROL_RANGE_INVALID')
    return {k:float(v) for k,v in result.items()}


def validate_face(face, width, height):
    if not isinstance(face, dict) or set(face) != {'face_id','detection_score','confidence','bbox','crop','landmarks'}:
        raise ValueError('FACE_ROW_INVALID')
    name = face['face_id']
    if not isinstance(name,str) or len(name) != 9 or not name.startswith('face_') or not name[5:].isdigit():
        raise ValueError('FACE_ID_INVALID')
    points = face['landmarks']
    if not isinstance(points, list) or len(points) != 66:
        raise ValueError('FACE_TOPOLOGY_INVALID')
    for point in points:
        if not isinstance(point,list) or len(point) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point):
            raise ValueError('FACE_POINT_INVALID')
        if not -2*width <= point[0] <= 3*width or not -2*height <= point[1] <= 3*height:
            raise ValueError('FACE_POINT_BOUNDS_INVALID')
    for key in ('detection_score','confidence'):
        if type(face[key]) not in (int,float) or not math.isfinite(face[key]):
            raise ValueError('FACE_SCORE_INVALID')
    box, crop = face['bbox'], face['crop']
    if not isinstance(box,list) or len(box) != 4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box) or min(box[2:]) <= 0:
        raise ValueError('FACE_BBOX_INVALID')
    if not isinstance(crop,list) or len(crop) != 4 or any(type(v) is not int for v in crop) or not 0 <= crop[0] < crop[2] <= width or not 0 <= crop[1] < crop[3] <= height:
        raise ValueError('FACE_CROP_INVALID')


def _overlap(a, b):
    x = max(0., min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))
    y = max(0., min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    area = x*y
    return area/max(1e-12,a[2]*a[3]+b[2]*b[3]-area)


class FaceAssociation:
    """Adjacent-frame IoU association; absence/cuts clear, IDs never recycle."""
    def __init__(self):
        self.previous = []
        self.next_id = 1

    def update(self, faces, *, cut=False):
        if cut:
            self.previous = []
        candidates = sorted(((-_overlap(a['bbox'],b['bbox']),a['face_id'],i,j)
                             for i,a in enumerate(self.previous) for j,b in enumerate(faces)))
        used_before, used_now, identifiers = set(), set(), {}
        for negative, name, i, j in candidates:
            if negative <= -.2 and i not in used_before and j not in used_now:
                used_before.add(i); used_now.add(j); identifiers[j] = name
        result = []
        for i, face in enumerate(faces):
            name = identifiers.get(i)
            if name is None:
                name = f'face_{self.next_id:04d}'
                self.next_id += 1
            result.append({'face_id':name, **face})
        self.previous = result
        return sorted(result,key=lambda f:f['face_id'])


def _skin_mask(points, shape, np, cv2):
    height,width = shape
    hard = np.zeros((height,width),np.uint8)
    polygon = points[list(range(17))+list(range(26,16,-1))]
    cv2.fillPoly(hard,[np.rint(polygon).astype(np.int32)],255)
    protected = np.zeros_like(hard)
    for indices in (list(range(36,42)),list(range(42,48)),list(range(48,66))):
        cv2.fillPoly(protected,[np.rint(points[indices]).astype(np.int32)],255)
    for indices in (list(range(17,22)),list(range(22,27)),list(range(31,36))):
        cv2.polylines(protected,[np.rint(points[indices]).astype(np.int32)],False,255,2)
    protect = cv2.dilate(protected,np.ones((5,5),np.uint8))
    hard[protect != 0] = 0
    # Feather strictly inside the proposed skin area, never across exclusions.
    soft = cv2.GaussianBlur(hard.astype(np.float32)/255,(7,7),1.5)
    soft[hard == 0] = 0
    return soft


def retouch_frame(rgba, faces, settings, *, selected_ids=None,transfer='srgb'):
    import numpy as np
    import cv2
    settings = controls(**settings)
    if transfer not in TRANSFERS:
        raise ValueError('FACE_TRANSFER_UNSUPPORTED')
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('FACE_RGBA_INPUT_INVALID')
    height,width = rgba.shape[:2]
    if len(faces) > 4 or len({f['face_id'] for f in faces}) != len(faces):
        raise ValueError('FACE_FRAME_COUNT_INVALID')
    for face in faces:
        validate_face(face,width,height)
    output = rgba.copy()
    affected = np.zeros((height,width),bool)
    if not any(settings.values()):
        return output,affected
    grid_y,grid_x = np.mgrid[:height,:width].astype(np.float32)
    for face in sorted(faces,key=lambda f:f['face_id']):
        if selected_ids is not None and face['face_id'] not in selected_ids:
            continue
        points = np.asarray(face['landmarks'],np.float32)[:,:2]
        current = output[:,:,:3].copy()
        map_x,map_y = grid_x.copy(),grid_y.copy()
        warped = np.zeros((height,width),bool)
        face_width = max(4.,float(np.linalg.norm(points[0]-points[16])))
        if settings['face_slim']:
            for index in (3,13):
                shift = (points[30]-points[index]) * (.12*settings['face_slim'])
                target = points[index]+shift
                radius = face_width*.45
                r2 = ((grid_x-target[0])**2+(grid_y-target[1])**2)/(radius*radius)
                weight = np.maximum(0,1-r2)**2
                map_x -= shift[0]*weight; map_y -= shift[1]*weight
                warped |= weight > 0
        if settings['eye_enlarge']:
            for indices in (list(range(36,42)),list(range(42,48))):
                eye = points[indices]
                center = eye.mean(axis=0)
                radius = max(2.,float(np.linalg.norm(eye[0]-eye[3]))*.9)
                r2 = ((grid_x-center[0])**2+(grid_y-center[1])**2)/(radius*radius)
                weight = np.maximum(0,1-r2)**2
                amount = (1-1/(1+.2*settings['eye_enlarge']))*weight
                map_x -= (grid_x-center[0])*amount; map_y -= (grid_y-center[1])*amount
                warped |= weight > 0
        if warped.any():
            values = cv2.remap(current,map_x,map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            current[warped] = values[warped]
            affected |= warped
        if settings['skin_smooth'] or settings['exposure_ev']:
            skin = _skin_mask(points,(height,width),np,cv2)
            if warped.any():
                skin = cv2.remap(skin,map_x,map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
            skin[rgba[:,:,3] == 0] = 0
            rgb = current.astype(np.float32)/255
            if settings['skin_smooth']:
                smooth = cv2.bilateralFilter(current,7,30,4).astype(np.float32)/255
                weight = skin[:,:,None]*settings['skin_smooth']
                rgb += (smooth-rgb)*weight
            if settings['exposure_ev']:
                corrected = exposed_rgb(rgb,settings['exposure_ev'],transfer,np)
                rgb += (corrected-rgb)*skin[:,:,None]
            changed = skin > 0
            current[changed] = np.clip(np.rint(rgb[changed]*255),0,255).astype(np.uint8)
            affected |= changed
        output[:,:,:3] = current
    # Alpha is copied directly; never remapped or used to premultiply RGB.
    if not np.array_equal(output[:,:,3],rgba[:,:,3]) or not np.array_equal(output[~affected],rgba[~affected]):
        raise ValueError('FACE_PROTECTED_PIXELS_CHANGED')
    return output,affected
