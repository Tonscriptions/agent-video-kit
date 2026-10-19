"""Reader routing/rollback contracts; fake APIs are not native loading evidence."""
import copy
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
from weight_reader import WEIGHT_FILES, load_local_weights, validate_weight_reads


class LocalWeightReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.calls = []; self.report = []
        self.modules = {name: ModuleType(name) for name in (
            'safetensors', 'safetensors.torch', 'transformers', 'transformers.modeling_utils')}
        def native(filename, framework, device='cpu', *, backend='mmap'):
            self.calls.append((Path(filename), framework, device, backend)); return object()
        self.native = native
        self.modules['safetensors'].safe_open = native
        self.modules['safetensors'].torch = self.modules['safetensors.torch']
        self.modules['transformers'].modeling_utils = self.modules['transformers.modeling_utils']
        for name in ('safetensors.torch', 'transformers.modeling_utils'):
            self.modules[name].safe_open = native
        self.scope = patch.dict(sys.modules, self.modules); self.scope.start(); self.addCleanup(self.scope.stop)
        for component, names in WEIGHT_FILES.items():
            directory = self.root/component; directory.mkdir()
            for name in names: (directory/name).write_bytes(b'fake fixture, never a model')

    def options(self):
        return {'local_files_only': True, 'use_safetensors': True, 'dtype': 'sentinel-dtype',
                'device_map': {'layer': 0}, 'max_memory': {0: 7168, 'cpu': 8192}, 'output_loading_info': True}

    def loader(self, directory, **options):
        self.assertEqual(options, self.options())
        directory = Path(directory)
        for i, path in enumerate(sorted(directory.glob('*.safetensors'))):
            module = self.modules['transformers.modeling_utils' if i%2 else 'safetensors.torch']
            module.safe_open(path, framework='pt', device='cpu', backend='mmap')
        return 'same-model', {'missing_keys': [], 'unexpected_keys': []}

    def restored(self):
        for name in ('safetensors', 'safetensors.torch', 'transformers.modeling_utils'):
            self.assertIs(self.modules[name].safe_open, self.native)

    def test_each_component_routes_both_aliases_to_pread_and_preserves_model_options(self):
        for component in WEIGHT_FILES:
            result = load_local_weights(self.loader, self.root/component, read_report=self.report, **self.options())
            self.assertEqual(result, ('same-model', {'missing_keys': [], 'unexpected_keys': []})); self.restored()
        self.assertEqual(len(self.calls), 6); self.assertTrue(all(row[3]=='pread' for row in self.calls))
        validate_weight_reads(self.report)

    def test_native_failure_does_not_retry_mmap_and_restores_aliases(self):
        def failed(filename, framework, device='cpu', *, backend='mmap'):
            self.calls.append(backend); raise TypeError('backend unsupported')
        self.native = failed
        for module in ('safetensors', 'safetensors.torch', 'transformers.modeling_utils'):
            self.modules[module].safe_open = failed
        with self.assertRaisesRegex(TypeError, 'backend unsupported'):
            load_local_weights(self.loader, self.root/'vae', read_report=self.report, **self.options())
        self.assertEqual(self.calls, ['pread']); self.assertFalse(self.report); self.restored()

    def test_loader_exception_after_partial_reads_restores_aliases_without_success_report(self):
        def failed(directory, **options):
            self.modules['transformers.modeling_utils'].safe_open(Path(directory)/WEIGHT_FILES['text_encoder'][0], 'pt')
            raise RuntimeError('controlled loader failure')
        with self.assertRaisesRegex(RuntimeError, 'controlled loader failure'):
            load_local_weights(failed, self.root/'text_encoder', read_report=self.report, **self.options())
        self.assertFalse(self.report); self.restored()

    def test_unregistered_file_and_other_component_are_rejected_before_native_read(self):
        outside = self.root/'outside.safetensors'; outside.write_bytes(b'not allowed')
        for path in (outside, self.root/'text_encoder'/WEIGHT_FILES['text_encoder'][0]):
            def failed(directory, **options): self.modules['safetensors.torch'].safe_open(path, 'pt')
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'OUTSIDE_COMPONENT'):
                load_local_weights(failed, self.root/'vae', read_report=self.report, **self.options())
            self.restored()
        self.assertFalse(self.calls); self.assertFalse(self.report)

    def test_partial_or_bypassed_load_cannot_claim_complete_weight_reads(self):
        def partial(directory, **options):
            self.modules['safetensors.torch'].safe_open(Path(directory)/WEIGHT_FILES['text_encoder'][0], 'pt')
        for loader in (partial, lambda *_a, **_k: 'bypass'):
            with self.assertRaisesRegex(ValueError, 'NOT_USED_FOR_ALL_SHARDS'):
                load_local_weights(loader, self.root/'text_encoder', read_report=self.report, **self.options())
            self.restored()
        self.assertFalse(self.report)

    def test_preexisting_alias_replacement_and_nonlocal_modes_fail_closed(self):
        for field in ('local_files_only', 'use_safetensors'):
            options=self.options(); options[field]=False
            with self.assertRaisesRegex(ValueError, 'LOCAL_SAFETENSORS_LOAD_REQUIRED'):
                load_local_weights(self.loader, self.root/'vae', read_report=self.report, **options)
        self.modules['transformers.modeling_utils'].safe_open=lambda *_a, **_k: None
        with self.assertRaisesRegex(ValueError, 'UNEXPECTED_SAFETENSORS_READER'):
            load_local_weights(self.loader, self.root/'vae', read_report=self.report, **self.options())
        self.assertFalse(self.calls)

    def test_missing_weights_and_unsupported_framework_fail_before_native_read(self):
        path=self.root/'vae'/WEIGHT_FILES['vae'][0];path.unlink()
        with self.assertRaisesRegex(ValueError, 'FILE_MISSING'):
            load_local_weights(self.loader, self.root/'vae', read_report=self.report, **self.options())
        path.write_bytes(b'fixture')
        for framework, backend in [('np', 'mmap'), ('pt', 'unknown')]:
            def failed(directory, **options): self.modules['safetensors.torch'].safe_open(path, framework, backend=backend)
            with self.assertRaisesRegex(ValueError, 'OUTSIDE_COMPONENT'):
                load_local_weights(failed, self.root/'vae', read_report=self.report, **self.options())
            self.restored()
        self.assertFalse(self.calls)

    def test_report_rejects_wrong_backend_missing_shards_duplicates_and_invalid_counts(self):
        for component in WEIGHT_FILES:
            load_local_weights(self.loader, self.root/component, read_report=self.report, **self.options())
        cases=[None, [], self.report[:2]]
        for mutate in (
            lambda v:v[0].update(backend='mmap'), lambda v:v[0]['files'].pop(),
            lambda v:v.__setitem__(1, copy.deepcopy(v[0])), lambda v:v[0]['files'][0].update(opens=True),
            lambda v:v[0]['files'][0].update(path='../escape'), lambda v:v[0].update(extra=True),
            lambda v:v[0]['files'][0].update(opens=1025)):
            value=copy.deepcopy(self.report);mutate(value);cases.append(value)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError): validate_weight_reads(value)


if __name__=='__main__':unittest.main()
