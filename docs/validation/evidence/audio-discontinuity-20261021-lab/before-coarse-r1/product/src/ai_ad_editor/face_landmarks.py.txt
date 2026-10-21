# OpenSeeFace preprocessing/decoding adapted from tracker.py.
# Copyright (c) 2019, Emiliana. BSD-2-Clause; see OPENSEEFACE_LICENSE.txt.
# Modified for explicit local CPU sessions and validated source-pixel x/y.
"""Bounded 66-point inference; imports native dependencies only on demand."""
from __future__ import annotations

DETECTOR = 'mnv3_detection_opt.onnx'
LANDMARKS = 'lm_model3_opt.onnx'
TOPOLOGY = 'openseeface-66-v1'


def validate_onnx(message, onnx):
    """Permit ONNX and ORT's built-in FusedConv; never load external kernels."""
    if isinstance(message, onnx.ModelProto) and message.functions:
        raise ValueError('FACE_ONNX_LOCAL_FUNCTION_UNSUPPORTED')
    if isinstance(message, onnx.TensorProto) and (message.external_data or message.data_location == onnx.TensorProto.EXTERNAL):
        raise ValueError('FACE_ONNX_EXTERNAL_DATA_UNSUPPORTED')
    if isinstance(message, onnx.NodeProto) and message.domain not in ('', 'ai.onnx') and (message.domain, message.op_type) != ('com.microsoft', 'FusedConv'):
        raise ValueError('FACE_ONNX_CUSTOM_DOMAIN_UNSUPPORTED')
    for field, value in message.ListFields():
        if field.message_type is not None:
            for child in value if field.is_repeated else [value]:
                validate_onnx(child, onnx)


def normalize_rgb(image, np, cv2, *, before_resize=False):
    source = image.astype(np.float32) if before_resize else image
    resized = cv2.resize(source, (224, 224), interpolation=cv2.INTER_LINEAR)
    std = np.array([.229, .224, .225], dtype=np.float32)
    mean = np.array([.485, .456, .406], dtype=np.float32)
    values = resized * (1 / (std * 255)) - mean / std
    return np.ascontiguousarray(values.transpose(2, 0, 1)[None], dtype=np.float32)


def decode_detections(output, pooled, width, height, threshold, max_faces, np):
    if output.shape != (1, 2, 56, 56) or pooled.shape != (1, 2, 56, 56) or not np.isfinite(output).all() or not np.isfinite(pooled).all():
        raise ValueError('FACE_DETECTION_OUTPUT_INVALID')
    heat = np.where(output[0, 0] == pooled[0, 0], output[0, 0], 0)
    # Fixed secondary index makes tied peaks deterministic, without altering scores.
    order = np.lexsort((np.arange(56 * 56), -heat.reshape(-1)))
    rows = []
    for index in order[:max_faces]:
        y, x = divmod(int(index), 56)
        score = float(heat[y, x])
        if score < threshold:
            break
        radius = float(output[0, 1, y, x]) * 112
        if not 0 < radius <= 448:
            raise ValueError('FACE_DETECTION_VALUE_INVALID')
        rows.append({'bbox': [(x*4-radius)*width/224, (y*4-radius)*height/224,
                              2*radius*width/224, 2*radius*height/224], 'score': score})
    return rows


def crop_for_landmarks(box, width, height):
    x, y, w, h = box
    # Upstream clamp_to_im returns int(x), int(y+1); y2 is slice-exclusive.
    def clamp(a, b):
        return int(min(width-1, max(0, a))), int(min(height-1, max(0, b))+1)
    x1, y1 = clamp(x-int(w*.1), y-int(h*.125))
    x2, y2 = clamp(x+w+int(w*.1), y+h+int(h*.125))
    return (x1, y1, x2, y2) if x2-x1 >= 4 and y2-y1 >= 4 else None


def decode_landmarks(tensor, crop, np):
    if tensor.shape != (1, 198, 28, 28) or not np.isfinite(tensor).all():
        raise ValueError('FACE_LANDMARK_OUTPUT_INVALID')
    values = tensor[0]
    heat = values[:66].reshape(66, -1)
    peaks = heat.argmax(1)
    indices = peaks[:, None]
    confidence = np.take_along_axis(heat, indices, 1).reshape(66)
    offsets = []
    for section in (values[66:132], values[132:198]):
        v = np.take_along_axis(section.reshape(66, -1), indices, 1).reshape(66)
        if (v < 0).any() or (v > 1).any():
            raise ValueError('FACE_LANDMARK_OFFSET_INVALID')
        v = np.clip(v, .0000001, .9999999)
        offsets.append(223 * np.log(v/(1-v))/16)
    # Heatmaps are regression values, not probabilities. Preserve values > 1.
    x1, y1, x2, y2 = crop
    # Upstream off_x is for the row/y axis; off_y is for column/x.
    ys = y1 + (y2-y1)/224 * (223*(peaks//28)/27 + offsets[0])
    xs = x1 + (x2-x1)/224 * (223*(peaks % 28)/27 + offsets[1])
    points = np.stack((xs, ys, confidence), 1)
    if not np.isfinite(points).all():
        raise ValueError('FACE_LANDMARK_VALUE_INVALID')
    return points, float(confidence.mean())


class FaceModels:
    """Two explicit standard-operator ONNX models; no camera or network APIs."""
    def __init__(self, model_dir, *, threads=4):
        if type(threads) is not int or not 1 <= threads <= 16:
            raise ValueError('FACE_THREADS_INVALID')
        from pathlib import Path
        import onnx
        import onnxruntime as ort
        ort.disable_telemetry_events()
        self.sessions = []
        for filename, shapes in ((DETECTOR, [[2, 56, 56], [2, 56, 56]]),
                                 (LANDMARKS, [[198, 28, 28]])):
            path = Path(model_dir)/filename
            graph = onnx.load(str(path), load_external_data=False)
            validate_onnx(graph, onnx)
            del graph
            options = ort.SessionOptions()
            options.intra_op_num_threads = threads
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
            inputs, outputs = session.get_inputs(), session.get_outputs()
            if len(inputs) != 1 or inputs[0].name != 'input' or inputs[0].shape[1:] != [3, 224, 224] or inputs[0].shape[0] not in (1, 'batch_size') or inputs[0].type != 'tensor(float)' or [o.shape[1:] for o in outputs] != shapes or any(o.type != 'tensor(float)' or o.shape[0] not in (1, 'batch_size') for o in outputs) or session.get_providers() != ['CPUExecutionProvider']:
                raise ValueError('FACE_MODEL_CONTRACT_UNSUPPORTED')
            self.sessions.append(session)
        self.detector_forwards = self.landmark_forwards = 0

    def infer(self, rgb, *, detection_threshold=.6, landmark_threshold=.6, max_faces=1):
        import numpy as np
        import cv2
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError('FACE_RGB_INPUT_INVALID')
        detector, landmarks = self.sessions
        values = detector.run(None, {detector.get_inputs()[0].name: normalize_rgb(rgb, np, cv2)})
        self.detector_forwards += 1
        found = decode_detections(*values, rgb.shape[1], rgb.shape[0], detection_threshold, max_faces, np)
        result = []
        for candidate in found:
            crop = crop_for_landmarks(candidate['bbox'], rgb.shape[1], rgb.shape[0])
            if crop is None:
                continue
            x1, y1, x2, y2 = crop
            values = landmarks.run(None, {landmarks.get_inputs()[0].name: normalize_rgb(rgb[y1:y2, x1:x2], np, cv2, before_resize=True)})
            self.landmark_forwards += 1
            points, score = decode_landmarks(values[0], crop, np)
            if score >= landmark_threshold:
                # Keep raw coordinates, including off-frame points, for review.
                result.append({'detection_score': candidate['score'], 'confidence': score,
                               'bbox': candidate['bbox'], 'crop': list(crop), 'landmarks': points.tolist()})
        return result
