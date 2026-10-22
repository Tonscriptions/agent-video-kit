"""CAS checkpoint existing native owners without changing their frozen inputs."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
FINAL = ROOT.parent/'float-preview-lab-20261022'
STREAM = ROOT.parent/'float-stream-lab-20261022'


def read(path):
    return json.loads(path.read_bytes())


def main():
    now = datetime.now(timezone.utc).isoformat()
    work = ROOT/'product/.runtime/checkpoint-r1'
    work.mkdir(parents=True, exist_ok=False)
    full_owner = FINAL/'product/.runtime/float-delivery-20261022/complete-r1/run.json'
    release_owner = FINAL/'product/.runtime/float-delivery-20261022/release-chain-r1/run.json'
    stream_owner = STREAM/'product/.runtime/float-stream-20261022/complete-r2/run.json'
    f, r, s = read(full_owner), read(release_owner), read(stream_owner)
    preflight = read(FINAL/'docs/validation/evidence/float-delivery-20261022/staging-preflight-r1.json')
    assert preflight['status'] == 'passed-private-cumulative-staging-and-document-preflight'
    assert preflight['main_mutated'] is False
    npath = ROOT/'docs/validation/evidence/float-exposure-20261022-lab/native-r2/verification.json'
    n = read(npath)
    bundle = dict(root=str(FINAL), status=f['status'], published=False,
        main_integrated=False, frozen_inputs=300, expected_full_methods=2355,
        source_installed_methods=260, source_installed_resources=180,
        full_suite_started=f['suite_launched'], full_suite_passed=False,
        full_owner=str(full_owner), full_owner_pid=f['pid'], full_tool_session_id=31351,
        release_owner=str(release_owner), release_owner_pid=r['pid'], release_tool_session_id=95911,
        release_status=r['status'], source_preflight=str(FINAL/'docs/validation/evidence/float-delivery-20261022/staging-preflight-r1.json'),
        source_preflight_status=preflight['status'], staged_blobs_compared=1226, local_links_checked=3109,
        prior_full2299_owner=str(stream_owner), prior_full2299_pid=s['pid'], prior_full2299_tool_session_id=43752,
        individual_V95_full2320_executed=False, individual_V96_full2337_executed=False,
        preserved_failures='four original pre-suite owner failures and first live-log staging failure retained',
        full_capcut_parity=False, default_backend_migrated=False, updated_at_utc=now)
    exposure = dict(root=str(ROOT), status=n['status'], frozen_inputs=302,
        parent_inputs=300, new_product_files=2, changed_parent_files=3,
        native_owner_pid=n['pid'], native_tool_session_id=94672,
        native_planned_methods=n['planned_methods'], native_receipt=str(npath),
        prior_failure=dict(methods=14, failures=2, receipt=str(npath.parent.parent/'native-r1/verification.json')),
        correction='positive gain from absolute binary32 white-minus-black; native edge cases rerun in related suite',
        installed_suite_passed=False, full_suite_started=False, full_suite_passed=False,
        published=False, main_integrated=False, full_capcut_parity=False, updated_at_utc=now)
    paths = [MAIN/'product/.runtime/agent-video-kit-progress-20261021.json',
             MAIN/'product/.runtime/release-recovery-20261022/current.json']
    originals = {p:p.read_bytes() for p in paths}
    progress = json.loads(originals[paths[0]])
    progress.update(updated_at_utc=now, float_delivery_bundle=bundle, float_exposure_lab=exposure)
    progress['openfilm_r16'].update(published=True, main_integrated=True,
        owner_record=progress['openfilm_r16']['publication_record'],
        future_parent='published R16 commit 4053cf6 over V93; final300 cumulative publication waits for actual full2355')
    for key in ['float_native_source_lab','float_standard_render_lab','float_preview_lab']:
        progress[key]['individual_full_owner_preserved']=progress[key].get('full_suite_owner',progress[key].get('full_owner'))
        progress[key].update(cumulative_delivery_owner=str(full_owner), cumulative_full_expected_methods=2355,
            cumulative_delivery_status=f['status'], cumulative_release_owner=str(release_owner))
    recovery = json.loads(originals[paths[1]])
    recovery.update(updated_at_utc=now, publication_owners_live=True, float_delivery_bundle=bundle,
        float_exposure_lab=exposure, next_required=[
            'Wait for actual native R94 full2299 terminal without changing its 292 product and 15 script inputs',
            'Final300 owner then executes actual full2355 with all four candidate changes; no separate V95/V96 full runs claimed',
            'Reviewed cumulative publisher ordinary commits and pushes only after that actual zero-skip full2355 pass',
            'R98 exposure independent candidate: preserve native-r1 failures, finish native-r2 related tests then real CLI media and isolated installation'])
    for p, data in zip(paths, [progress,recovery]):
        (work/(p.name+'.before')).write_bytes(originals[p])
        assert p.read_bytes() == originals[p], 'concurrent progress update'
        temp=p.with_name(p.name+'.float-work-'+str(os.getpid()))
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        assert p.read_bytes() == originals[p], 'concurrent progress update'
        os.replace(temp,p)
    handles = dict(updated_at_utc=now, stream_full=dict(session=43752,pid=s['pid'],status=s['status']),
        final_full=dict(session=31351,pid=f['pid'],status=f['status']),
        final_release=dict(session=95911,pid=r['pid'],status=r['status']),
        exposure_native=dict(session=94672,pid=n['pid'],status=n['status']),
        closed_preflight_failure=52983, closed_preflight_pass=49557)
    (work/'handles.json').write_text(json.dumps(handles,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(handles,ensure_ascii=False))


if __name__=='__main__':main()
