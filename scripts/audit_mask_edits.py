"""Verify final mask-edit delivery against real frozen runs, native media and wheel."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_fragments import frozen,save,sha


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def run(output):
    assert not output.exists();evidence=output.parent;evidence.mkdir(parents=True,exist_ok=True)
    runtime=ROOT/'product/.runtime';public=ROOT/'docs/assets/mask-edits-20261018'
    regression=load(runtime/'mask-edit-full-final-host-20261018.json')
    specific=load(runtime/'mask-edit-specific-final-v2-20261018.json')
    for record in (regression,specific):
        assert record['exit_code']==0 and record['terminal_ok'] and record['skipped']==0 and record['frozen_equal']
        assert record['frozen_before']==record['frozen_after']==frozen()
    assert regression['methods']==1005 and specific['methods']==30
    media=load(public/'verification.json');natural=load(runtime/'mask-edit-natural-20261018.json')
    wheelroot=runtime/'mask-edit-wheel-20261018';wheel=load(wheelroot/'verification.json')
    assert media['product_frozen']==natural['frozen_product']==wheel['frozen_product']==frozen()
    assert media['actual_cli_calls']==12 and media['expected_rejections']==2 and media['after_checked_points']==24
    assert media['all_pixels_exact_to_independent_truth'] and media['every_pts_exact'] and media['network_guard_events']==[]
    assert natural['actual_cli_calls']==11 and natural['actual_model_calls']==32 and natural['new_scene_count']==0
    assert natural['changed_final_frame_alpha_pixels']==261 and natural['independent_alpha_exact']
    assert natural['first_31_alpha_frames_unchanged'] and natural['outside_grown_mask_changed_rgb_pixels']==0
    assert natural['model_received_exact_edited_rgba'] and natural['source_alpha_exact'] and natural['pcm_exact'] and natural['pcm_bytes']==768000
    assert len(natural['before']['failed_points'])==1 and natural['after']['checked_points']==5 and not natural['after']['failed_points']
    assert natural['rights_expected_exit_code']==7 and not natural['natural_pixels_published'] and not natural['natural_quality_accepted']
    assert natural['worker']['blocked_network_events']==[]
    assert wheel['package_file_count']==96 and wheel['actual_fresh_process_clis']==11 and wheel['imported_plan_rebuild_exact']
    assert sha(Path(wheel['wheel']))==wheel['wheel_sha256']
    for name,item in media['files'].items():
        assert sha(public/name)==item['sha256'] and (public/name).stat().st_size==item['bytes'],name
    # Independent native full-array checks once more; no product rasterizer.
    def native(argv):
        result=subprocess.run(argv,capture_output=True,timeout=120);assert result.returncode==0,result.stderr
        return result.stdout
    def decode(path):return native(['ffmpeg','-v','error','-i',str(path),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1'])
    expected=decode(public/'independent-truth.mov');assert expected==decode(public/'mask-edited.mov')
    assert len(expected)==1228800
    assert 'sha256:'+hashlib.sha256(expected).hexdigest()==media['independent_rgba_sha256']==wheel['decoded_rgba_sha256']
    # Raw unsuccessful evidence stays immutable and is not counted as acceptance.
    names=['mask-edit-development-20261018','mask-edit-final-specific-20261018',
           'mask-edit-final-full-20261018','mask-edit-specific-final-v2-20261018','mask-edit-full-final-v2-20261018',
           'mask-edit-full-final-host-20261018']
    for name in names:
        source=runtime/(name+'.json');record=load(source)
        assert record['log_sha256']==sha(source.with_suffix('.log'))
        for suffix in ('.json','.log'):shutil.copyfile(source.with_suffix(suffix),evidence/(name+suffix))
    failed=load(runtime/'mask-edit-development-20261018.json');assert failed['exit_code']==1 and failed['methods']==28
    interrupted=load(runtime/'mask-edit-final-full-20261018.json');assert not interrupted['terminal_ok'] and interrupted['methods'] is None
    assert interrupted['frozen_equal']
    embedded=load(runtime/'mask-edit-full-final-v2-20261018.json')
    assert embedded['frozen_equal'] and not embedded['terminal_ok'] and embedded['frozen_before']==frozen()
    shutil.copyfile(runtime/'mask-edit-host-unicode-diagnostic-20261018.log',evidence/'host-unicode-diagnostic.log')
    for tag,record_name in [('initial','mask-edit-development-20261018'),('policy','mask-edit-final-full-20261018')]:
        archive_path=runtime/f'mask-edit-{tag}-source-20261018.zip'
        measured=load(runtime/(record_name+'.json'))['frozen_before']
        with zipfile.ZipFile(archive_path) as archive:
            assert set(archive.namelist())==set(measured)
            for name,expected_hash in measured.items():
                assert 'sha256:'+hashlib.sha256(archive.read(name)).hexdigest()==expected_hash
        shutil.copyfile(archive_path,evidence/archive_path.name)
    shutil.copyfile(runtime/'reconstruct_mask_edit_development.py',evidence/'reconstruct-development.py')
    save(evidence/'natural.json',natural);save(evidence/'wheel.json',wheel)
    shutil.copyfile(Path(wheel['wheel']),evidence/Path(wheel['wheel']).name)
    for name in wheel['logs']:shutil.copyfile(wheelroot/name,evidence/('wheel-'+name))
    shutil.copyfile(Path(wheel['revised_package']['path']),evidence/'wheel-revised-project.zip')
    failedroot=runtime/'mask-edits-public-policy-failed-20261018'
    failure_logs=sorted(failedroot.glob('cli-*.log'))
    assert len(failure_logs)==10 and load(failure_logs[-1])['errors'][0]['code']=='POLICY_REMOTE_REFERENCE'
    with zipfile.ZipFile(evidence/'policy-failure-logs.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in failure_logs:archive.write(path,path.name)
    snapshots=frozen()
    with zipfile.ZipFile(evidence/'final-source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,expected_hash in snapshots.items():
            data=(ROOT/name).read_bytes();assert 'sha256:'+hashlib.sha256(data).hexdigest()==expected_hash
            archive.writestr(name,data)
    scripts=['scripts/smoke_mask_edits.py','scripts/smoke_mask_edit_natural.py','scripts/audit_mask_edit_wheel.py',
             'scripts/audit_mask_edits.py','scripts/run_frozen_regression.py','scripts/smoke_fragments.py']
    # Actual NUT duration diagnostic supporting the explicit MOV mask choice.
    nut=ROOT/'docs/assets/coherent-reference-20261018/elastic_exposure-candidate.nut'
    nut_clock=json.loads(native(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(nut)]))
    stream=next(s for s in nut_clock['streams'] if s['codec_type']=='video')
    assert int(stream['nb_read_frames'])==12 and stream['avg_frame_rate']=='12/1'
    assert float(nut_clock['format']['duration'])<1
    save(evidence/'nut-clock-observation.json',{'file':nut.relative_to(ROOT).as_posix(),'sha256':sha(nut),'probe':nut_clock,
        'actual_frames':12,'fps':'12','full_interval_seconds':1,'duration_stops_at_last_pts':True,
        'limitation':'diagnostic of this fixture, not a universal container duration implementation or new format fix'})
    sources={name:sha(ROOT/name) for name in scripts}
    record={'status':'product_execution_passed_natural_quality_unaccepted','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'engine':'agent-local-mask-edit-v1','full':regression,'specific':specific,'specific_is_subset_of_full':True,
        'frozen_product':snapshots,'product_file_count':len(snapshots),'python_file_count':sum(n.endswith('.py') for n in snapshots),
        'public_media':{'directory':public.relative_to(ROOT).as_posix(),'verification_sha256':sha(public/'verification.json'),
            'files':len(media['files'])+1,'cli_calls':12,'expected_rejections':2,'frames':16,'checkpoint_passed':24,
            'independent_rgba_bytes':1228800,'all_pixels_exact':True},
        'natural':{'record':'natural.json','sha256':sha(evidence/'natural.json'),'cli_calls':11,'repair_worker_runs':1,
            'model_calls':32,'same_existing_scene':True,'sparse_points_before_passed':4,'sparse_points_after_passed':5,
            'changed_final_alpha_pixels':261,'first_31_alpha_frames_exact':True,'outside_changed':0,'pcm_exact':True,
            'natural_pixels_published':False,'complete_object_selection_accepted':False,'repair_quality_accepted':False},
        'wheel':{'record':'wheel.json','sha256':sha(evidence/'wheel.json'),'package_files':96,'fresh_process_clis':11,
            'optional_imports_blocked':['numpy','PIL','torch'],'schema_standalone_packaging_accepted':False,'clean_machine_accepted':False},
        'failures_preserved':{'initial_subset_methods':28,'initial_subset_failed_methods':1,
            'initial_reason':'test expected cancellation exit8 instead of documented project-lock exit6; product rejection was correct',
            'successful_development_30_not_additive':True,'stopped_full_methods':None,'stopped_full_terminal_ok':False,
            'development_source_snapshots':'both reconstructed from current bytes with explicit reverse edits; every file matches the recorded before SHA; not rerun',
            'stopped_full_reason':'explicitly stopped its native child tree after independent real policy failure, before editing product',
            'actual_policy_failure':'derived:local-mask-edit was interpreted as a URI; replaced with derived-local-mask-edit and regression added',
            'generator_import_failure':'initial isolated script missed scripts sys.path; failed before creating media; corrected',
            'embedded_python_regression_failure':'embedded model Python ignores PYTHONPATH in a subprocess module test; stopped and reran the complete suite with C:/Python313 used by V41; no product changes for this harness issue',
            'nut_duration_diagnostic':'recorded; mask output uses QTRLE MOV with exact video track time scale'},
        'manual_static_review':{'public_frames':[8],'private_frames':[31],
            'private_contact_sha256':natural['private_contact']['sha256'],'findings':[
                'Public frame8 shows missing arm/leg and false disk/corner removed; independent all-frame coverage also passed.',
                'Natural wrist is included, girl forearm remains clear. Real LaMa still smears background; dense anatomy and temporal quality unaccepted.']},
        'continuous_playback_reviewed':False,'sound_reviewed':False,'broad_natural_quality_accepted':False,
        'complete_capcut_parity_accepted':False,'goal_still_active':True,'browser_started_by_new_feature':False,'virtualization':False,
        'generator_sources':sources,'support_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(evidence.iterdir()) if p.is_file()}}
    save(output,record)
    print(json.dumps({k:record[k] for k in ('status','product_file_count','python_file_count','public_media','natural','wheel')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();run(args.output.resolve())
