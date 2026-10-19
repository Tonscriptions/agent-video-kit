"""Unintegrated native safetensors reader candidate; no Torch import at startup."""
from pathlib import Path
import threading

WEIGHT_FILES = {
    'text_encoder': [f'model-{i:05d}-of-00003.safetensors' for i in range(1, 4)],
    'transformer': [f'diffusion_pytorch_model-{i:05d}-of-00002.safetensors' for i in range(1, 3)],
    'vae': ['diffusion_pytorch_model.safetensors'],
}


def load_local_weights(loader, directory, *, read_report, **options):
    """Select the public pread backend in this isolated worker's load call only.

    Transformers holds a local safe_open alias, while Diffusers uses the alias
    in safetensors.torch. Restore both even on loader or reader failure. Existing
    artifact locks and hashes remain responsible for the complete weight bytes.
    """
    import safetensors
    import safetensors.torch as tensor_io
    import transformers.modeling_utils as transformer_io
    directory = Path(directory).resolve(strict=True)
    expected = WEIGHT_FILES.get(directory.name)
    if not expected or options.get('local_files_only') is not True or options.get('use_safetensors') is not True:
        raise ValueError('VACE_LOCAL_SAFETENSORS_LOAD_REQUIRED')
    native = safetensors.safe_open
    targets = ((transformer_io, 'safe_open'), (tensor_io, 'safe_open'))
    if any(getattr(module, name) is not native for module, name in targets):
        raise ValueError('VACE_UNEXPECTED_SAFETENSORS_READER')
    allowed = {directory/name for name in expected}
    if any(not path.is_file() or path.is_symlink() for path in allowed):
        raise ValueError('VACE_LOCAL_SAFETENSORS_FILE_MISSING')
    opened = {}; lock = threading.Lock()

    def local_open(filename, framework, device='cpu', *, backend='mmap'):
        path = Path(filename).resolve(strict=True)
        if path not in allowed or framework != 'pt' or backend not in {'mmap', 'pread'}:
            raise ValueError('VACE_SAFETENSORS_READ_OUTSIDE_COMPONENT')
        # An old native library rejecting this keyword fails closed; never retry
        # with mmap or deserialize pickle as a fallback.
        pointer = native(str(path), framework=framework, device=device, backend='pread')
        with lock:
            opened[path.name] = opened.get(path.name, 0) + 1
        return pointer

    try:
        for module, name in targets:
            setattr(module, name, local_open)
        result = loader(str(directory), **options)
        if set(opened) != set(expected):
            raise ValueError('VACE_SAFETENSORS_READER_NOT_USED_FOR_ALL_SHARDS')
    finally:
        for module, name in targets:
            setattr(module, name, native)
    read_report.append({'component': directory.name, 'backend': 'pread',
        'files': [{'path': directory.name+'/'+name, 'opens': opened[name]} for name in sorted(opened)]})
    return result


def validate_weight_reads(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('VACE_SAFETENSORS_READ_REPORT_MISSING')
    components = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {'component', 'backend', 'files'}:
            raise ValueError('VACE_SAFETENSORS_READ_REPORT_INVALID')
        component = row['component']
        if component not in WEIGHT_FILES or component in components or row['backend'] != 'pread':
            raise ValueError('VACE_SAFETENSORS_READ_BACKEND_OR_COMPONENT_INVALID')
        components.add(component)
        expected = [component+'/'+name for name in sorted(WEIGHT_FILES[component])]
        files = row['files']
        if not isinstance(files, list) or len(files) != len(expected):
            raise ValueError('VACE_SAFETENSORS_READ_INVENTORY_INVALID')
        for item, name in zip(files, expected, strict=True):
            if (not isinstance(item, dict) or set(item) != {'path', 'opens'} or item['path'] != name
                    or type(item['opens']) is not int or not 1 <= item['opens'] <= 1024):
                raise ValueError('VACE_SAFETENSORS_READ_INVENTORY_INVALID')
