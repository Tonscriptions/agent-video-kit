"""Physical/Torch admission policy tests; fake driver rows are not GPU evidence."""
import copy
import json
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_ad_editor.cuda_admission import (CudaAdmissionError, HEADROOM_BYTES, POLICY, admit_cuda,
                                        record_window, validate_execution, window_summary)

UUID = 'GPU-01234567-89ab-cdef-0123-456789abcdef'
MiB = 1024**2


class CudaAdmissionTests(unittest.TestCase):
    def torch(self, free=10000*MiB, uuid=UUID):
        state = {'allocated':128*MiB, 'reserved':256*MiB}
        def empty_cache():state['reserved']=state['allocated']
        return SimpleNamespace(cuda=SimpleNamespace(current_device=lambda: 0,
            get_device_properties=lambda index: SimpleNamespace(uuid=uuid),
            synchronize=lambda index:None, memory_allocated=lambda index:state['allocated'],
            memory_reserved=lambda index:state['reserved'], empty_cache=empty_cache, _allocator_state=state,
            mem_get_info=lambda index: (free, 12288*MiB)))

    def check(self, *, required=HEADROOM_BYTES, free=10000*MiB, physical=9000,
              identity=UUID, stage='text-weights', stdout=None, **kwargs):
        result = SimpleNamespace(returncode=0, stdout=stdout if stdout is not None else
                                 f'{identity}, 12288, {physical}\r\n'.encode(), stderr=b'')
        with patch('ai_ad_editor.cuda_admission.shutil.which', return_value='C:/Windows/System32/nvidia-smi.exe'), \
                patch('ai_ad_editor.cuda_admission.subprocess.run', return_value=result) as run:
            value = admit_cuda(self.torch(free=free), required, stage, **kwargs)
        return value, run

    def test_same_uuid_is_queried_without_guessing_physical_index(self):
        check, run = self.check()
        args, options = run.call_args
        self.assertIn('--id='+UUID, args[0]);self.assertEqual(options['timeout'], 5)
        self.assertNotIn('shell', options);self.assertEqual(check['effective_free_bytes'], 9000*MiB)
        self.assertFalse(check['reservation']);self.assertFalse(check['oom_guarantee'])

    def test_installed_torch_uuid_object_with_no_gpu_prefix_is_supported(self):
        class TorchUuid:
            def __str__(self): return UUID[4:]
        with patch('ai_ad_editor.cuda_admission.shutil.which', return_value='nvidia-smi.exe'), \
                patch('ai_ad_editor.cuda_admission.subprocess.run', return_value=SimpleNamespace(
                    returncode=0, stdout=f'{UUID},12288,9000'.encode())):
            result = admit_cuda(self.torch(uuid=TorchUuid()), HEADROOM_BYTES, 'text-weights')
        self.assertEqual(result['device_uuid'], UUID)

    def test_physical_free_rejects_even_when_torch_reports_sufficient_space(self):
        with self.assertRaises(CudaAdmissionError) as failed:
            self.check(required=7936*MiB, physical=7935)
        self.assertEqual(str(failed.exception), 'CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE')
        self.assertEqual(failed.exception.report['effective_free_bytes'], 7935*MiB)
        self.assertEqual(failed.exception.report['status'], 'rejected')

    def test_torch_free_rejects_even_when_physical_free_is_sufficient(self):
        with self.assertRaisesRegex(CudaAdmissionError, 'INSUFFICIENT_TORCH_FREE'):
            self.check(required=7936*MiB, free=7936*MiB-1)

    def test_exact_budget_boundary_is_admitted(self):
        value, _ = self.check(required=7936*MiB, free=7936*MiB, physical=7936)
        self.assertEqual(value['status'], 'admitted')

    def test_wrong_identity_mig_missing_uuid_and_nonzero_logical_device_fail_closed(self):
        for identity in ('GPU-ffffffff-ffff-ffff-ffff-ffffffffffff', 'MIG-'+UUID, 'GPU-short'):
            with self.subTest(identity=identity), self.assertRaises(CudaAdmissionError):
                self.check(identity=identity)
        for uuid in (None, 'MIG-'+UUID):
            with self.subTest(uuid=uuid), self.assertRaises(CudaAdmissionError):
                admit_cuda(self.torch(uuid=uuid), HEADROOM_BYTES, 'text-weights')
        torch = self.torch();torch.cuda.current_device=lambda: 1
        with self.assertRaisesRegex(CudaAdmissionError, 'LOGICAL_DEVICE_MUST_BE_ZERO'):
            admit_cuda(torch, HEADROOM_BYTES, 'text-weights')
        with self.assertRaisesRegex(CudaAdmissionError, 'DEVICE_IDENTITY_CHANGED'):
            self.check(expected_uuid='GPU-ffffffff-ffff-ffff-ffff-ffffffffffff')

    def test_invalid_csv_units_extra_rows_negative_and_impossible_free_fail_closed(self):
        for raw in (b'', f'{UUID},12288,N/A'.encode(), f'{UUID},12.5,10'.encode(),
                    f'{UUID},12288,-1'.encode(), f'{UUID},12288,12289'.encode(),
                    (f'{UUID},12288,9000\n'*2).encode(), b'x'*4097, b'\xff'):
            with self.subTest(raw=raw[:40]), self.assertRaises(CudaAdmissionError):
                self.check(stdout=raw)
        for free in (True, -1, 12289*MiB):
            with self.subTest(free=free), self.assertRaises(CudaAdmissionError):self.check(free=free)

    def test_missing_failed_and_timed_out_driver_tool_never_admit(self):
        with patch('ai_ad_editor.cuda_admission.shutil.which', return_value=None), \
                self.assertRaisesRegex(CudaAdmissionError, 'PHYSICAL_QUERY_UNAVAILABLE'):
            admit_cuda(self.torch(), HEADROOM_BYTES, 'text-weights')
        for failure in (subprocess.TimeoutExpired('nvidia-smi', 5), OSError('missing local driver')):
            with patch('ai_ad_editor.cuda_admission.shutil.which', return_value='nvidia-smi.exe'), \
                    patch('ai_ad_editor.cuda_admission.subprocess.run', side_effect=failure), \
                    self.assertRaises(CudaAdmissionError):
                admit_cuda(self.torch(), HEADROOM_BYTES, 'text-weights')
        with patch('ai_ad_editor.cuda_admission.shutil.which', return_value='nvidia-smi.exe'), \
                patch('ai_ad_editor.cuda_admission.subprocess.run', return_value=SimpleNamespace(returncode=9)), \
                self.assertRaisesRegex(CudaAdmissionError, 'PHYSICAL_QUERY_FAILED'):
            admit_cuda(self.torch(), HEADROOM_BYTES, 'text-weights')

    def test_invalid_required_budget_and_stage_are_rejected_before_query(self):
        with patch('ai_ad_editor.cuda_admission.subprocess.run') as run:
            for required in (True, 0, -1, 1.5):
                with self.subTest(required=required), self.assertRaises(ValueError):
                    admit_cuda(self.torch(), required, 'text-weights')
            for stage in ('', 'text\nweights', 'x'*65, None):
                with self.subTest(stage=stage), self.assertRaises(ValueError):
                    admit_cuda(self.torch(), HEADROOM_BYTES, stage)
        run.assert_not_called()

    def test_idle_cache_is_released_before_sampling_while_live_allocation_is_preserved(self):
        torch=self.torch();state=torch.cuda._allocator_state;state['reserved']=640*MiB;events=[]
        torch.cuda.synchronize=lambda index:events.append('synchronize')
        original_empty=torch.cuda.empty_cache
        def empty():
            events.append('empty-cache');original_empty()
        torch.cuda.empty_cache=empty
        torch.cuda.mem_get_info=lambda index:(600*MiB+640*MiB-state['reserved'],12288*MiB)
        def physical(*args,**kwargs):
            events.append('physical-query')
            return SimpleNamespace(returncode=0,stdout=f"{UUID},12288,{500+640-state['reserved']//MiB}".encode())
        with patch('ai_ad_editor.cuda_admission.shutil.which',return_value='nvidia-smi.exe'), \
                patch('ai_ad_editor.cuda_admission.subprocess.run',side_effect=physical):
            result=admit_cuda(torch,HEADROOM_BYTES,'video-window-1')
        self.assertEqual(events,['synchronize','empty-cache','physical-query'])
        self.assertEqual(result['effective_free_bytes'],1012*MiB)
        cache=result['idle_cache_release']
        self.assertEqual(cache['released_reserved_bytes'],512*MiB)
        self.assertEqual(cache['allocated_before_bytes'],128*MiB)
        self.assertEqual(cache['allocated_after_bytes'],128*MiB)
        self.assertTrue(cache['active_allocation_preserved'])

    def test_invalid_allocator_counters_fail_before_driver_query_or_empty_cache(self):
        for update in ({'allocated':True},{'allocated':-1},{'allocated':257*MiB}):
            torch=self.torch();torch.cuda._allocator_state.update(update)
            with self.subTest(update=update), \
                    patch('ai_ad_editor.cuda_admission.shutil.which',return_value='nvidia-smi.exe'), \
                    patch('ai_ad_editor.cuda_admission.subprocess.run') as query, \
                    patch.object(torch.cuda,'empty_cache') as empty, \
                    self.assertRaises(CudaAdmissionError):
                admit_cuda(torch,HEADROOM_BYTES,'text-weights')
            query.assert_not_called();empty.assert_not_called()

    def test_allocator_release_failure_preserves_partial_evidence_and_never_queries(self):
        torch=self.torch()
        with patch('ai_ad_editor.cuda_admission.shutil.which',return_value='nvidia-smi.exe'), \
                patch('ai_ad_editor.cuda_admission.subprocess.run') as query, \
                patch.object(torch.cuda,'empty_cache',side_effect=RuntimeError('native allocator failed')), \
                self.assertRaises(CudaAdmissionError) as failed:
            admit_cuda(torch,HEADROOM_BYTES,'text-weights')
        query.assert_not_called();cache=failed.exception.report['idle_cache_release']
        self.assertTrue(cache['synchronized']);self.assertTrue(cache['empty_cache_called'])
        self.assertFalse(cache['completed']);self.assertEqual(cache['allocated_before_bytes'],128*MiB)

    def test_parent_rejects_missing_or_inconsistent_idle_cache_accounting(self):
        original=self.execution()
        mutations=[lambda c:c.pop('idle_cache_release'),
            lambda c:c['idle_cache_release'].update(completed=False),
            lambda c:c['idle_cache_release'].update(allocated_after_bytes=1),
            lambda c:c['idle_cache_release'].update(released_reserved_bytes=1),
            lambda c:c['idle_cache_release'].update(reserved_after_bytes=257*MiB)]
        for mutate in mutations:
            value=copy.deepcopy(original);mutate(value['gpu_admission']['text'])
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_execution(value,text_gpu_budget_mib=7168,model_calls=3)

    def execution(self, count=3):
        summary = window_summary()
        for i in range(count):
            value, _ = self.check(stage='video-window-'+str(i+1), physical=9000-i)
            record_window(summary, value)
        text, _ = self.check(required=7936*MiB)
        video, _ = self.check(stage='video-weights', required=1024+4096+HEADROOM_BYTES)
        return {'gpu_admission': {'policy':POLICY,'reservation':False,'oom_guarantee':False,
            'headroom_bytes':HEADROOM_BYTES,'text':text,'video':video,'video_weight_bytes':1024,
            'prompt_embedding_bytes':4096,'windows':summary}}

    def test_window_summary_retains_count_minimum_and_only_first_last_snapshots(self):
        value = self.execution()
        validate_execution(value, text_gpu_budget_mib=7168, model_calls=3)
        summary = value['gpu_admission']['windows']
        self.assertEqual(summary['minimum_physical_free_bytes'], 8998*MiB)
        self.assertEqual(summary['count'], 3);self.assertEqual(len(summary), 5)
        self.assertEqual(summary['first']['stage'], 'video-window-1')
        self.assertEqual(summary['last']['stage'], 'video-window-3')

    def test_execution_validation_rejects_missing_budget_device_count_and_guarantees(self):
        original = self.execution()
        mutations = [lambda x:x.pop('gpu_admission'),
            lambda x:x['gpu_admission'].update(reservation=True),
            lambda x:x['gpu_admission'].update(oom_guarantee=True),
            lambda x:x['gpu_admission']['video'].update(device_uuid='GPU-ffffffff-ffff-ffff-ffff-ffffffffffff'),
            lambda x:x['gpu_admission']['text'].update(required_free_bytes=True),
            lambda x:x['gpu_admission']['text'].update(effective_free_bytes=1),
            lambda x:x['gpu_admission']['windows'].update(count=4),
            lambda x:x['gpu_admission']['windows'].update(minimum_physical_free_bytes=1),
            lambda x:x['gpu_admission']['windows']['last'].update(stage='video-window-2')]
        for mutate in mutations:
            value=copy.deepcopy(original);mutate(value)
            with self.subTest(value=json.dumps(value)), self.assertRaises(ValueError):
                validate_execution(value, text_gpu_budget_mib=7168, model_calls=3)

    def test_rejection_precedes_component_imports_tokenizer_and_any_checkpoint_access(self):
        from ai_ad_editor.vace_model import load_predictor
        failure=CudaAdmissionError('CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE', {'stage':'text-weights'})
        phases=[]
        with patch.dict(sys.modules, {'torch':self.torch()}), \
                patch('ai_ad_editor.cuda_admission.admit_cuda', side_effect=failure) as admission, \
                self.assertRaises(CudaAdmissionError):
            load_predictor('no-model-files-exist', {'text_gpu_budget_mib':7168}, {}, progress=phases.append)
        self.assertEqual(phases, ['admitting-text-gpu-memory'])
        self.assertEqual(admission.call_args.args[1:], (7936*MiB, 'text-weights'))
