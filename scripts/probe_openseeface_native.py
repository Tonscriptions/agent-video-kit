"""Development-only local CPU probe; no downloads, installs or GUI."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import pathlib
import sys
import time
import types


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--upstream', type=pathlib.Path, required=True)
    parser.add_argument('--image', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'product/src'))
    blocked = []
    def offline(event, params):
        if event.startswith(('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'urllib.Request')):
            blocked.append(event)
            raise RuntimeError('OFFLINE_PROBE_NETWORK_REJECTED')
    sys.addaudithook(offline)
    from ai_ad_editor.face_landmarks import FaceModels, normalize_rgb, decode_landmarks, crop_for_landmarks
    import numpy as np
    import cv2
    import onnxruntime as ort
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('LOCAL_FIXTURE_REQUIRED')
    rgb = np.ascontiguousarray(image[..., ::-1])
    started = time.monotonic()
    models = FaceModels(args.upstream/'models', threads=2)
    faces = models.infer(rgb)
    elapsed = time.monotonic()-started
    if len(faces) != 1:
        raise ValueError('EXPECTED_ONE_REAL_FACE')

    # Run only the author's pure decoder/preprocessor methods from fixed source.
    tree = ast.parse((args.upstream/'tracker.py').read_text(encoding='utf-8'))
    tracker = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Tracker')
    methods = [n for n in tracker.body if isinstance(n, ast.FunctionDef) and n.name in ('landmarks', 'preprocess')]
    logit = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'logit_arr')
    namespace = {'np':np, 'cv2':cv2}
    exec(compile(ast.Module(body=[logit, *methods], type_ignores=[]), '<fixed-upstream-pure-functions>', 'exec'), namespace)
    std = np.array([.229,.224,.225],np.float32)
    config = types.SimpleNamespace(res=224.,res_i=224,out_res=27.,out_res_i=28,model_type=3,logit_factor=16.,
                                  std_res=np.tile(1/(std*255),[224,224,1]),
                                  mean_res=np.tile(-np.array([.485,.456,.406],np.float32)/std,[224,224,1]))
    crop = crop_for_landmarks(faces[0]['bbox'], image.shape[1], image.shape[0])
    x1,y1,x2,y2 = crop
    ours = normalize_rgb(rgb[y1:y2,x1:x2],np,cv2,before_resize=True)
    reference_input = namespace['preprocess'](config,image,crop)
    assert np.array_equal(ours,reference_input), 'UPSTREAM_PREPROCESS_MISMATCH'
    values = models.sessions[1].run(None, {models.sessions[1].get_inputs()[0].name:ours})[0]
    models.landmark_forwards += 1
    points, score = decode_landmarks(values,crop,np)
    ref_score, ref_points = namespace['landmarks'](config,values[0],(x1,y1,(x2-x1)/224,(y2-y1)/224,0))
    assert np.array_equal(points,ref_points[:,[1,0,2]]) and score == float(ref_score), 'UPSTREAM_DECODE_MISMATCH'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    overlay = image.copy()
    for x,y,c in points:
        cv2.circle(overlay,(round(float(x)),round(float(y))),1,(0,255,0),-1)
    ok,encoded = cv2.imencode('.png',overlay)
    assert ok, 'PNG_ENCODE_FAILED'
    args.output.with_suffix('.png').write_bytes(encoded.tobytes())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    result = {'status':'passed_native_probe','product_integrated':False,'quality_accepted':False,
              'upstream_commit':'50c09741897010faad721a218b2bbe14ecad6251',
              'python':sys.version,'device':'cpu','providers':['CPUExecutionProvider'],
              'versions':{'onnxruntime':ort.__version__,'numpy':np.__version__,'opencv':cv2.__version__},
              'blocked_python_network_events':blocked,'mediapipe_executed':False,
              'source':{'path':str(args.image),'sha256':sha(args.image),'width':image.shape[1],'height':image.shape[0],
                        'credit':'NASA / public-domain astronaut fixture distributed by scikit-image'},
              'models':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted((args.upstream/'models').glob('*.onnx'))],
              'detector_forwards':models.detector_forwards,'landmark_forwards':models.landmark_forwards,
              'first_inference_seconds_including_model_load':elapsed,
              'reference_checks':{'preprocessing_exact':True,'landmark_xy_and_confidence_exact':True},
              'faces':faces,'overlay_sha256':sha(args.output.with_suffix('.png'))}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','detector_forwards','landmark_forwards','first_inference_seconds_including_model_load','reference_checks','blocked_python_network_events')},ensure_ascii=False))


if __name__ == '__main__':
    main()
