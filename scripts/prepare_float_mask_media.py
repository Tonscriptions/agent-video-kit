"""Adapt the previously executed public-CLI harness with explicit new oracles."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-exposure-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-mask-20261022-lab'


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()


def once(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)


def main():
    source=PARENT/'scripts/smoke_float_exposure_media.py'
    receipt=json.loads((PARENT/'docs/validation/evidence/float-exposure-20261022-lab/media-r1/verification.json').read_bytes())
    assert receipt['script_sha256']==sha(source)
    text=source.read_text('utf8').replace('float-exposure-20261022','float-mask-20261022')
    text=text.replace('float_exposure_media','float_mask_media').replace('linear Float32 exposure','floating alpha masks')
    text=once(text,'                frame[:, :, :3] *= .6','                frame[:, :, :3] *= .6\n                frame[:, :, 3] = .2+.8*x/(w-1)')
    text=once(text,"        base['effects'] = [{'type': 'exposure', 'parameters': {'amount': 1, 'black': .003}}]",'''        from mask_media_oracle import clip_mask,curve_mask,expected_rgb
        base.update(duration_tick=90000,source_out_tick=90000,mask=clip_mask())
        curve=copy.deepcopy(base)
        curve.update(id='curve_clip',timeline_start_tick=90000,source_in_tick=90000,source_out_tick=180000,mask=curve_mask())
        sequence['tracks'][0]['clips']=[base,curve]''')
    start=text.index('        # Independent encoded-source -> linear -> exposure calculation')
    end=text.index("        (assets/'author-project.json')",start)
    text=text[:start]+'''        source_planes = np.frombuffer(raw.read_bytes(), '<u2').reshape(count,4,h,w)
        expected=expected_rgb(source_planes,list(range(3,17)))
        actual_rgb=np.moveaxis(planes[:,[2,0,1]],1,-1)
        difference=float(np.max(np.abs(actual_rgb-expected)))
        check('all selected CLI RGB match independent source-alpha mask feather and composite oracle',difference<=3e-7,
            maximum_linear_absolute_error=difference,compared_RGB_values=int(actual_rgb.size))
        check('composited selected alpha remains opaque',np.all(planes[:,3]==1))
        record['mask_oracle']={'maximum_linear_absolute_error':difference,'RGB_values':int(actual_rgb.size),
            'static_polygon_frames':list(range(3,10)),'dynamic_cubic_frames':list(range(10,17)),
            'source_alpha_gradient':True,'oracle':'independent-direct-sums-polynomial-ray-crossing',
            'oracle_sha256':sha(ROOT/'scripts/mask_media_oracle.py'),'integer_intermediate':False}
'''+text[end:]
    text=text.replace('EXPOSURE +1 EV / CLI','MASKS + FEATHER / CLI').replace('EXPOSURE +1 EV / PREVIEW','MASKS + FEATHER / PREVIEW')
    text=text.replace('smoke_float_exposure_media.py','smoke_float_mask_media.py').replace('302','304')
    text=text.replace('passed-public-CLI-linear-exposure-and-native-float-previews','passed-public-CLI-floating-masks-and-native-float-previews')
    ast.parse(text)
    destination=ROOT/'scripts/smoke_float_mask_media.py'
    assert not destination.exists()
    destination.write_text(text,encoding='utf8',newline='\n')
    installer=PARENT/'scripts/verify_float_exposure_install.py'
    text=installer.read_text('utf8').replace('float-exposure-20261022','float-mask-20261022').replace('float_exposure_media','float_mask_media')
    text=text.replace('smoke_float_exposure_media.py','smoke_float_mask_media.py')
    text=text.replace('302','304').replace('181','182').replace('274','295')
    text=text.replace("'test_float_exposure']","'test_float_exposure', 'test_float_mask']")
    text=text.replace('passed-public-CLI-linear-exposure-and-native-float-previews','passed-public-CLI-floating-masks-and-native-float-previews')
    text=text.replace('native_float_exposure_integrated=True','native_float_exposure_integrated=True,native_float_mask_integrated=True')
    ast.parse(text)
    target=ROOT/'scripts/verify_float_mask_install.py'
    assert not target.exists()
    target.write_text(text,encoding='utf8',newline='\n')
    (REL/'media-install-drivers-r1.json').write_text(json.dumps({'status':'prepared-not-executed','parent_media_sha256':sha(source),
        'media_sha256':sha(destination),'oracle_sha256':sha(ROOT/'scripts/mask_media_oracle.py'),
        'installer_sha256':sha(target),'expected_methods':295,'expected_resources':182},indent=2)+'\n',encoding='utf8',newline='\n')
    print('prepared new mask media and fresh 8-wheel install verification')


if __name__=='__main__':main()
