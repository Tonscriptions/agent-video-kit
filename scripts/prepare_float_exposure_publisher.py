"""Prepare a scoped publisher from the reviewed local exact-byte procedure."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-preview-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-exposure-20261022-lab'


def main():
    path=PARENT/'scripts/publish_float_preview.py'
    raw=path.read_bytes()
    text=raw.decode('utf8')
    for old,new in [('float_preview_release_docs','float_exposure_release_docs'),
        ('float-preview-20261022','float-exposure-20261022'),('r97_','r98_'),('V97','V98'),
        ('2355','2369'),('260','274'),('180','181'),('300','302'),('298','300')]:
        assert old in text,old
        text=text.replace(old,new)
    start=text.index('def source_gate(complete):')
    end=text.index('\ndef publication_files(audit):',start)
    gate='''def source_gate(complete):
    current,native,media,installed=docs.current()
    foundation=read(ROOT/REL/'foundation-r1.json')
    parent=foundation['parent_frozen_inputs'];assert len(parent)==300
    assert not set(parent)-set(current) and len(current)==302
    changed={n for n in current if parent.get(n)!=current[n]};assert len(changed)==5
    review=read(ROOT/REL/'static-review-r1.json')
    assert review['status']=='passed-static-contact-and-GIF-clock-review'
    assert review['GIF_frames']==14 and review['viewed_panels']==6 and not review['continuous_playback_review']
    assert review['contact_sha256']==sha(ROOT/docs.ASSETS/'contact.png')
    assert review['GIF_sha256']==sha(ROOT/docs.ASSETS/'comparison.gif')
    verify(ROOT,foundation['dependency_artifact_inputs'])
    assert installed['status']=='passed-fresh-eight-wheel-181-resources-real-previews-and-274-methods'
    assert installed['frozen_before']==installed['frozen_after']==current
    assert installed['isolated_methods']['methods']==274 and installed['isolated_methods']['skipped']==0
    assert len(installed['resource_hashes'])==181 and len(installed['numpy_distribution']['files'])==931
    replay=read(ROOT/REL/'media-installed-r1/verification.json')
    assert replay['status']==media['status'] and replay['isolated']
    assert replay['frozen_before']==replay['frozen_after']==current
    assert media['actual_public_preview_CLI_processes']==replay['actual_public_preview_CLI_processes']==3
    for name in media['decoded']:
        for key in ['native_yuv10_sha256','PCM_sha256']:
            assert replay['decoded'][name][key]==media['decoded'][name][key]
    for key in ['Float32_sha256','PCM_sha256','PNG16_sha256']:
        assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    for rel in [media,replay]:
        for name,row in rel['assets'].items():assert sha(ROOT/name)==row['sha256']
    owner_path=WORK/'complete-r1/run.json'
    owner=read(owner_path) if owner_path.exists() else None
    if owner:
        verify(ROOT,owner['frozen_inputs']);verify(ROOT,owner['verification_scripts'])
    audit={'status':'passed-source-and-installed-preflight-not-full-acceptance','frozen_inputs':current,
        'parent_frozen_inputs':parent,'changed_product_files':sorted(changed),'native_methods':74,
        'native_receipt_sha256':sha(ROOT/REL/'native-r2/verification.json'),
        'installed_receipt_sha256':sha(ROOT/REL/'installed-r1/verification.json'),
        'source_media_receipt_sha256':sha(ROOT/REL/'media-r1/verification.json'),
        'installed_status':installed['status'],'complete_terminal_checked':False,
        'startup_frozen_scripts':len(owner['verification_scripts']) if owner else 0}
    full=None
    if complete:
        assert owner['status']=='passed-complete-native-suite-not-published' and owner['methods']==2369
        full=read(ROOT/REL/'full-r1.json')
        assert owner['full_receipt_sha256']==sha(ROOT/REL/'full-r1.json')
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2369 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==current and full['external_fixture_count']==8
        assert full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        verify(ROOT,owner['dependency_artifact_inputs']);verify(ROOT,owner['bound_evidence'])
        lineage=read(ROOT/REL/'parent-binding-r1.json')
        assert lineage['status']=='passed-actual-published-parent300-full2355' and lineage['parent_inputs']==parent
        audit.update(status='passed-native-installed-complete-gates',complete_terminal_checked=True,
            published_parent=lineage['published_parent_commit'],full_receipt_sha256=sha(ROOT/REL/'full-r1.json'))
    return audit,full

'''
    text=text[:start]+gate+text[end:]
    text=text.replace("ROOT.parent/'float-standard-render-lab-20261022'", "ROOT.parent/'float-preview-lab-20261022'")
    text=text.replace('docs.links(stage)',"docs.links(stage, [*docs.LATEST_DOCS, docs.REPORT, docs.CONTRACT])")
    text=text.replace('docs.links(MAIN)',"docs.links(MAIN, [*docs.LATEST_DOCS, docs.REPORT, docs.CONTRACT])")
    text=text.replace("[*docs.LATEST_DOCS, '.gitattributes']", "[*docs.LATEST_DOCS, docs.REPORT, docs.CONTRACT, '.gitattributes']")
    start=text.index('        docs.report(full)')
    end=text.index('        reviewed = publication_files(audit);',start)
    text=text[:start]+"        docs.write(ROOT/docs.REPORT,docs.report(full,published=True))\n"+text[end:]
    text=text.replace("'feat: connect native Float32 timeline previews and content cache'", "'feat: add linear Float32 exposure to shared render and preview host'")
    text=text.replace('V98 explicit native Float32 timeline previews and content cache; actual full2369/installed274, 181 resources;',
        'V98 static linear Float32 exposure in the common render/preview host; actual full2369/installed274, 181 resources;')
    text=text.replace("    return (text.rstrip()", "    return (text.rstrip()")
    # Preserve original product/script bytes, including native CRLF sources.
    text=text.replace("name+' -text\\n'", "name+' -text whitespace=cr-at-eol\\n'")
    # Full logs are mutable until the whole suite has actually ended.
    old="names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/REL).rglob('*') if p.is_file())"
    assert old in text
    text=text.replace(old,"names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/REL).rglob('*') if p.is_file() and (audit['complete_terminal_checked'] or not p.name.startswith('full-r1')))")
    # Bind the accepted private preview to the exact publisher and docs code.
    text=text.replace("'source_audit': audit, 'generator_sha256': sha(Path(__file__))}",
        "'source_audit': audit, 'generator_sha256': sha(Path(__file__)), 'documentation_generator_sha256': sha(Path(docs.__file__))}")
    anchor="        audit, full = source_gate(True); parent = audit['published_parent']; current = audit['frozen_inputs']"
    assert text.count(anchor)==1
    text=text.replace(anchor,anchor+"\n        preflight_record=read(ROOT/REL/'staging-preflight-r1.json')\n        assert preflight_record['status']=='passed-private-native-staging-and-document-preflight'\n        assert preflight_record['generator_sha256']==sha(Path(__file__))\n        assert preflight_record['documentation_generator_sha256']==sha(Path(docs.__file__))")
    ast.parse(text)
    target=ROOT/'scripts/publish_float_exposure.py';assert not target.exists()
    target.write_text(text,encoding='utf8',newline='\n')
    out=REL/'publisher-preparation-r1.json';assert not out.exists()
    out.write_text(json.dumps({'status':'prepared-not-preflighted','parent_driver_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),
        'driver_sha256':'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest(),'preflight_executed':False,
        'full_suite_passed':False,'published':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(out)


if __name__=='__main__':main()
