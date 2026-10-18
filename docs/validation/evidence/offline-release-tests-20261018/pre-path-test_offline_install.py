from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import zipfile

SPEC=importlib.util.spec_from_file_location('offline_installer',Path(__file__).resolve().parents[1]/'offline/install.py')
installer=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(installer)


class OfflineInstallationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='offline-install-');self.addCleanup(temp.cleanup);self.folder=Path(temp.name)
        self.bundle=self.folder/'bundle';self.bundle.mkdir();(self.bundle/'wheels').mkdir();rows=[]
        for name in ('ai-ad-editor','jsonschema','attrs','jsonschema-specifications','referencing','rpds-py'):
            path='wheels/'+name.replace('-','_')+'-0.1-py3-none-any.whl';dist=name.replace('-','_')+'-0.1.dist-info/'
            with zipfile.ZipFile(self.bundle/path,'w') as archive:
                archive.writestr(dist+'METADATA',f'Metadata-Version: 2.1\nName: {name}\nVersion: 0.1\n')
                archive.writestr(dist+'WHEEL','Wheel-Version: 1.0\nTag: py3-none-any\n')
            rows.append({'name':name,'version':'0.1','path':path})
        (self.bundle/'requirements.lock').write_bytes(''.join('./'+x['path']+' --hash='+installer.sha(self.bundle/x['path'])+'\n' for x in rows).encode())
        self.manifest={'format':'agent-video-kit-offline-v1','target':'cp313-win_amd64','wheels':rows,'files':[]}
        self.reinventory();self.target=self.folder/'installed'

    def reinventory(self):
        self.manifest['files']=[{'path':p.relative_to(self.bundle).as_posix(),'bytes':p.stat().st_size,'sha256':installer.sha(p)} for p in sorted(self.bundle.rglob('*')) if p.is_file() and p.name!='manifest.json']
        self.save()

    def save(self):
        (self.bundle/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8');self.digest=installer.sha(self.bundle/'manifest.json')

    def test_native_bundle_dry_run_creates_no_target_or_staging(self):
        result=installer.install(self.bundle,self.target,self.digest,dry_run=True)
        self.assertEqual(result['status'],'planned');self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob('.agent-video-kit-install-*')),[])

    def test_wrong_manifest_digest_rejects(self):
        with self.assertRaises(installer.InstallError) as context:installer.validate_bundle(self.bundle,'sha256:'+'0'*64)
        self.assertEqual(context.exception.code,'MANIFEST_DIGEST_MISMATCH')

    def test_actual_wheel_byte_change_is_detected(self):
        path=self.bundle/self.manifest['wheels'][0]['path'];path.write_bytes(path.read_bytes()+b'x')
        with self.assertRaises(installer.InstallError) as context:installer.validate_bundle(self.bundle,self.digest)
        self.assertEqual(context.exception.code,'BUNDLE_DIGEST_MISMATCH')

    def test_extra_file_and_case_collisions_rejected(self):
        (self.bundle/'extra.txt').write_text('extra')
        with self.assertRaises(installer.InstallError):installer.validate_bundle(self.bundle,self.digest)
        (self.bundle/'extra.txt').unlink();row=dict(self.manifest['files'][0]);row['path']=row['path'].upper();self.manifest['files'].append(row);self.save()
        with self.assertRaises(installer.InstallError):installer.validate_bundle(self.bundle,self.digest)

    def test_unsafe_relative_paths_rejected(self):
        for path in ('../escape','/absolute','E:/absolute','wheels\\escape','wheels/../escape','wheels//double','wheels/CON.txt','wheels/file.','wheels/%TEMP%'):
            with self.assertRaises(installer.InstallError,msg=path):installer.safe_name(path)

    def test_existing_target_is_preserved(self):
        self.target.mkdir();sentinel=self.target/'keep';sentinel.write_bytes(b'keep')
        with self.assertRaises(installer.InstallError) as context:installer.install(self.bundle,self.target,self.digest)
        self.assertEqual(context.exception.code,'INSTALL_TARGET_EXISTS');self.assertEqual(sentinel.read_bytes(),b'keep')

    def test_pre_cancel_creates_no_installation(self):
        cancel=self.folder/'cancel';cancel.touch()
        with self.assertRaises(installer.InstallError) as context:installer.install(self.bundle,self.target,self.digest,cancel_file=cancel)
        self.assertEqual(context.exception.exit_code,8);self.assertFalse(self.target.exists())

    def test_failed_owned_process_rolls_back_staging(self):
        with mock.patch.object(installer,'run_owned',side_effect=installer.InstallError('CONTROLLED_FAILURE','controlled native-process failure')):
            with self.assertRaises(installer.InstallError):installer.install(self.bundle,self.target,self.digest)
        self.assertFalse(self.target.exists());self.assertEqual(list(self.folder.glob('.agent-video-kit-install-*')),[])

    def test_wheel_name_mismatch_rejected_before_pip(self):
        self.manifest['wheels'][0]['name']='wrong';self.save()
        with self.assertRaises(installer.InstallError) as context:installer.validate_bundle(self.bundle,self.digest)
        self.assertEqual(context.exception.code,'WHEEL_INVALID')

    def test_requirements_cannot_add_index_or_unhashed_requirements(self):
        with (self.bundle/'requirements.lock').open('ab') as stream:stream.write(b'--index-url https://example.invalid/\n')
        self.reinventory()
        with self.assertRaises(installer.InstallError) as context:installer.validate_bundle(self.bundle,self.digest)
        self.assertEqual(context.exception.code,'REQUIREMENTS_INVALID')

    def test_platform_mismatch_fails_before_any_files_created(self):
        with mock.patch.object(installer.sys,'platform','linux'):
            with self.assertRaises(installer.InstallError) as context:installer.install(self.bundle,self.target,self.digest)
        self.assertEqual(context.exception.code,'PYTHON_TARGET_MISMATCH');self.assertFalse(self.target.exists())

    def test_cleanup_guard_refuses_unowned_directory(self):
        keep=self.folder/'keep';keep.mkdir();(keep/'sentinel').write_bytes(b'keep')
        with self.assertRaises(installer.InstallError):installer.remove_owned(keep,self.folder)
        self.assertEqual((keep/'sentinel').read_bytes(),b'keep')

    def test_real_owned_process_cancel_is_reaped(self):
        ready=self.folder/'ready';cancel=self.folder/'cancel';log=self.folder/'process.log'
        command=[sys.executable,'-I','-B','-c','import pathlib,sys,time;pathlib.Path(sys.argv[1]).touch();time.sleep(20)',str(ready)]
        def trigger():
            deadline=time.monotonic()+5
            while not ready.exists() and time.monotonic()<deadline:time.sleep(0.02)
            cancel.touch()
        thread=threading.Thread(target=trigger);thread.start()
        try:
            with self.assertRaises(installer.InstallError) as context:installer.run_owned(command,cwd=self.folder,env=dict(os.environ),log=log,cancel_file=cancel,deadline=time.monotonic()+10)
            self.assertEqual(context.exception.code,'INSTALL_CANCELLED');self.assertTrue(ready.exists())
        finally:thread.join(timeout=6)

    def test_real_owned_process_timeout_is_reaped(self):
        command=[sys.executable,'-I','-B','-c','import time;time.sleep(20)']
        with self.assertRaises(installer.InstallError) as context:installer.run_owned(command,cwd=self.folder,env=dict(os.environ),log=self.folder/'timeout.log',cancel_file=None,deadline=time.monotonic()+0.15)
        self.assertEqual(context.exception.code,'INSTALL_TIMEOUT')
