"""Distribution controls: declared NumPy must arrive from a complete offline bundle."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


installer=load('media_profile_installer',ROOT/'offline/install.py')
builder=load('media_profile_builder',ROOT/'offline/build.py')


class OfflineMediaProfileTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='offline-media-profile-');self.addCleanup(temporary.cleanup)
        self.folder=Path(temporary.name);self.bundle=self.folder/'bundle';self.bundle.mkdir();(self.bundle/'wheels').mkdir()
        self.rows=[]
        for name in ('ai-ad-editor','jsonschema','attrs','jsonschema-specifications','referencing','rpds-py','pillow','numpy'):
            self.wheel(name)
        self.manifest={'format':'agent-video-kit-offline-v1','target':'cp313-win_amd64','runtime_profile':'media-analysis-v1','wheels':self.rows}
        self.inventory();self.target=self.folder/'installed'

    def wheel(self,name,*,version='0.1',tag='py3-none-any',requires=()):
        old=next((r for r in self.rows if r['name']==name),None)
        if old:(self.bundle/old['path']).unlink();self.rows.remove(old)
        path='wheels/'+name.replace('-','_')+'-'+version+'-'+tag+'.whl'
        dist=name.replace('-','_')+'-'+version+'.dist-info/'
        with zipfile.ZipFile(self.bundle/path,'w') as archive:
            metadata=f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n'
            metadata+=''.join('Requires-Dist: '+r+'\n' for r in requires)
            archive.writestr(dist+'METADATA',metadata)
            archive.writestr(dist+'WHEEL','Wheel-Version: 1.0\nTag: '+tag+'\n')
            archive.writestr(dist+'licenses/LICENSE.txt','Synthetic test data; no third-party code.\n')
        self.rows.append({'name':name,'version':version,'path':path})

    def drop(self,name):
        row=next(r for r in self.rows if r['name']==name);(self.bundle/row['path']).unlink();self.rows.remove(row)

    def inventory(self):
        (self.bundle/'requirements.lock').write_text(''.join('./'+r['path']+' --hash='+installer.sha(self.bundle/r['path'])+'\n' for r in self.rows),encoding='utf8',newline='\n')
        self.manifest['files']=[{'path':p.relative_to(self.bundle).as_posix(),'bytes':p.stat().st_size,'sha256':installer.sha(p)} for p in sorted(self.bundle.rglob('*')) if p.is_file() and p.name!='manifest.json']
        (self.bundle/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf8',newline='\n')
        self.digest=installer.sha(self.bundle/'manifest.json')

    def rejected(self,code):
        with self.assertRaises(installer.InstallError) as caught:
            installer.install(self.bundle,self.target,self.digest,dry_run=True)
        self.assertEqual(caught.exception.code,code)
        self.assertFalse(self.target.exists());self.assertEqual(list(self.folder.glob('.agent-video-kit-install-*')),[])

    def wheelhouse(self):
        folder=self.folder/'wheelhouse';folder.mkdir();entries=[]
        for row in self.rows:
            if row['name']=='ai-ad-editor':continue
            source=self.bundle/row['path'];target=folder/source.name;target.write_bytes(source.read_bytes())
            entries.append({'name':row['name'],'version':row['version'],'filename':target.name,'bytes':target.stat().st_size,'sha256':installer.sha(target),'runtime_dependency':True})
        (folder/'lock.json').write_text(json.dumps({'target':'cp313-win_amd64','runtime_profile':'media-analysis-v1','artifacts':entries}),encoding='utf8')
        return folder,entries

    def test_complete_media_profile_plans_eight_wheels_without_writes(self):
        self.wheel('ai-ad-editor',requires=('Pillow>=12.1,<13','numpy>=2.4.2,<3'));self.inventory()
        result=installer.install(self.bundle,self.target,self.digest,dry_run=True)
        self.assertEqual(result['status'],'planned');self.assertEqual(result['wheels'],8)
        self.assertFalse(self.target.exists());self.assertEqual(list(self.folder.glob('.agent-video-kit-install-*')),[])

    def test_media_profile_without_numpy_rejects_before_install(self):
        self.drop('numpy');self.inventory();self.rejected('WHEEL_SET_INVALID')

    def test_media_profile_without_pillow_rejects_before_install(self):
        self.drop('pillow');self.inventory();self.rejected('WHEEL_SET_INVALID')

    def test_font_text_product_requiring_numpy_cannot_fall_back_to_host(self):
        self.drop('numpy');self.manifest['runtime_profile']='font-text-v1'
        self.wheel('ai-ad-editor',requires=('numpy>=2.4.2,<3',));self.inventory();self.rejected('WHEEL_SET_INVALID')

    def test_legacy_core_product_requiring_numpy_cannot_fall_back_to_host(self):
        self.drop('numpy');self.drop('pillow');self.manifest['runtime_profile']='core-v1'
        self.wheel('ai-ad-editor',requires=('numpy>=2.4.2,<3',));self.inventory();self.rejected('WHEEL_SET_INVALID')

    def test_extra_numpy_cannot_silently_change_font_text_profile(self):
        self.manifest['runtime_profile']='font-text-v1';self.inventory();self.rejected('WHEEL_SET_INVALID')

    def test_media_numpy_wrong_native_abi_rejects_before_install(self):
        self.wheel('numpy',tag='cp312-cp312-win_amd64');self.inventory();self.rejected('WHEEL_INVALID')

    def test_media_numpy_version_mismatch_rejects_before_install(self):
        next(r for r in self.rows if r['name']=='numpy')['version']='9.9'
        self.inventory();self.rejected('WHEEL_INVALID')

    def test_media_numpy_payload_change_is_detected_before_install(self):
        row=next(r for r in self.rows if r['name']=='numpy')
        with (self.bundle/row['path']).open('ab') as stream:stream.write(b'changed')
        self.rejected('BUNDLE_DIGEST_MISMATCH')

    def test_cancelled_media_install_preserves_target_parent(self):
        cancel=self.folder/'cancel';cancel.touch();keep=self.folder/'keep';keep.write_bytes(b'keep')
        with self.assertRaises(installer.InstallError) as caught:
            installer.install(self.bundle,self.target,self.digest,cancel_file=cancel)
        self.assertEqual(caught.exception.code,'INSTALL_CANCELLED');self.assertFalse(self.target.exists())
        self.assertEqual(keep.read_bytes(),b'keep');self.assertEqual(list(self.folder.glob('.agent-video-kit-install-*')),[])

    def test_builder_missing_numpy_rejects_before_product_build_or_output(self):
        self.drop('numpy');house,entries=self.wheelhouse();output=self.folder/'release'
        with mock.patch.object(builder.subprocess,'run',side_effect=AssertionError('must not build before dependency preflight')):
            with self.assertRaisesRegex(ValueError,'[Nn]um[Pp]y|media-analysis'):
                builder.build(output,house)
        self.assertFalse(output.exists())

    def test_builder_changed_numpy_rejects_before_product_build_or_output(self):
        house,entries=self.wheelhouse();row=next(r for r in entries if r['name']=='numpy')
        with (house/row['filename']).open('ab') as stream:stream.write(b'changed')
        output=self.folder/'release'
        with mock.patch.object(builder.subprocess,'run',side_effect=AssertionError('must not build before dependency preflight')):
            with self.assertRaisesRegex(ValueError,'Dependency source changed'):
                builder.build(output,house)
        self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
