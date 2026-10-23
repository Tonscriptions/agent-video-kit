"""Prepare independent sharpen owners; actual R17 publication is the main baseline gate."""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-spatial-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-sharpen-20261022-lab'


def transform(source):
    numbers = {'2774': '2836', '2715': '2774', '679': '741', '620': '679',
               '326': '328', '323': '326', '195': '196', '479': '121'}
    labels = {'full2774': 'full2836', 'full2715': 'full2774', 'installed679': 'installed741',
              'installed620': 'installed679', 'parent323': 'parent326', 'V108': 'V109',
              'V107': 'V108', 'r108': 'r109'}
    expression = re.compile('|'.join(map(re.escape, labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    source = expression.sub(lambda m: labels.get(m[0], numbers.get(m[0])), source)
    paths = {'float-spatial': 'float-sharpen', 'float-gaussian': 'float-spatial', 'float_spatial': 'float_sharpen'}
    source = re.sub('|'.join(map(re.escape, paths)), lambda m: paths[m[0]], source)
    source = source.replace('gaussian_parent_source', 'spatial_parent_source').replace('gaussian_published_parent', 'spatial_published_parent')
    source = source.replace('passed-public-CLI-floating-spatial-means-and-native-float-previews',
                            'passed-public-CLI-floating-unsharp-and-native-float-previews')
    source = source.replace('continuous Float32 average and box blur with adaptive4K workspace admission',
                            'continuous Float32 YCbCr unsharp with independent coverage and original author clocks')
    source = source.replace('new_methods=59', 'new_methods=62')
    source = source.replace('native-r2', 'native-r4').replace('4k-r2', '4k-r1').replace('media-r1', 'media-r2')
    source = source.replace('waiting-for-actual-published-V108-full2774', 'waiting-for-actual-R17-after-V108-full2774')
    return source


def main():
    rows = {}
    for stem in ('verify_float_spatial_install', 'run_float_spatial_complete', 'publish_float_spatial',
                 'release_float_spatial_after_complete', 'finish_float_spatial_chain'):
        parent = PARENT/'scripts'/(stem+'.py')
        source = transform(parent.read_text('utf-8-sig'))
        if stem == 'verify_float_spatial_install':
            source = source.replace("'test_float_tone','test_float_gaussian','test_float_sharpen']",
                "'test_float_tone','test_float_gaussian','test_float_spatial','test_float_sharpen']")
            source = source.replace('native_float_sharpen_means_integrated=True,',
                                    'native_float_spatial_means_integrated=True, native_float_sharpen_integrated=True,')
        if stem == 'run_float_spatial_complete':
            source = source.replace('Run the actual spatial full suite after the frozen Gaussian parent is published.',
                'Run the actual sharpen suite after V108 and the queued R17 research publication.')
            anchor = "        commit=publication['commit'];assert publication['remote_main']==commit"
            assert anchor in source
            source = source.replace(anchor, """        spatial_commit=publication['commit'];assert publication['remote_main']==spatial_commit
        research_path=MAIN/'product/.runtime/openfilm-reuse-lab-20261022-r17/product/.runtime/openfilm-r17-release/publication-owner-r1/run.json'
        while True:
            research=read(research_path)
            assert not research['status'].startswith('failed'),research.get('error',research['status'])
            if research['status']=='published-R17-research-after-V108':break
            time.sleep(5)
        assert research['published'] and research['main_clean'] and not research['force_push']
        assert research['parent_commit']==spatial_commit and research['publication_product_inputs']==326
        commit=research['commit'];assert research['remote_main']==commit
        state.update(actual_V108_product_commit=spatial_commit,actual_R17_baseline_commit=commit)
        checkpoint()""")
            source = source.replace("save(REL/'parent-full-r1.json',parent_full);save(REL/'parent-publication-r1.json',publication)",
                "save(REL/'parent-full-r1.json',parent_full);save(REL/'parent-publication-r1.json',publication)\n        save(REL/'parent-R17-publication-r1.json',research)")
            source = source.replace("'parent_publication_sha256':sha(parent_work/'publication-r1/run.json')}",
                "'parent_publication_sha256':sha(parent_work/'publication-r1/run.json'),\n            'V108_product_commit':spatial_commit,'R17_documentation_commit':commit,'R17_publication_sha256':sha(REL/'parent-R17-publication-r1.json')}")
            source = source.replace("'parent-publication-r1.json','parent-binding-r1.json'",
                "'parent-publication-r1.json','parent-R17-publication-r1.json','parent-binding-r1.json'")
        if stem == 'publish_float_spatial':
            source = source.replace("'date': '2026-10-22'", "'date': '2026-10-23'")
            source = source.replace('assert len(changed)==10', 'assert len(changed)==9')
            source = source.replace("audit.update(status='passed-native-installed-complete-gates'", "research=read(ROOT/REL/'parent-R17-publication-r1.json')\n        assert research['status']=='published-R17-research-after-V108' and research['commit']==lineage['published_parent_commit']\n        assert lineage['R17_publication_sha256']==sha(ROOT/REL/'parent-R17-publication-r1.json')\n        audit.update(status='passed-native-installed-complete-gates'")
        if stem == 'verify_float_spatial_install':
            source = source.replace('from float_sharpen_release_docs import fourk', 'from float_sharpen_release_docs import fourk, bound_media')
            source = source.replace("and media['frozen_after'] == before)", "and bound_media(media, before, 'media-r2/verification.json'))")
        if stem == 'run_float_spatial_complete':
            source = source.replace('for receipt in [native,media,installed]', 'for receipt in [native,installed]')
            source = source.replace('from float_sharpen_release_docs import fourk', 'from float_sharpen_release_docs import fourk, bound_media')
            source = source.replace('        fourk(before)\n', "        fourk(before)\n        assert bound_media(media, before, 'media-r2/verification.json')\n")
            source = source.replace("'external-fixtures-r1.json','4k-r1/verification.json']", "'external-fixtures-r1.json','4k-r1/verification.json','guard-only-input-binding-r1.json']")
        source = source.replace('installed-r1', 'installed-r2')
        if stem == 'verify_float_spatial_install':
            source = source.replace("proof4k['frozen_after']==before", "bound_media(proof4k, before, '4k-r1/verification.json')")
        if stem == 'finish_float_spatial_chain':
            source = source.replace('finish-chain-r1', 'finish-chain-r2')
        destination = ROOT/'scripts'/(stem.replace('float_spatial', 'float_sharpen')+'.py')
        ast.parse(source); assert not destination.exists()
        destination.write_text(source, encoding='utf8', newline='\n')
        rows[destination.name] = {'parent': str(parent), 'candidate': str(destination)}
    out = REL/'release-drivers-r1.json'; assert not out.exists()
    out.write_text(json.dumps({'status': 'prepared-not-executed', 'scripts': rows,
        'target_source_methods': 121, 'new_methods': 62, 'target_installed_methods': 741,
        'target_shipping_resources': 196, 'target_complete_methods': 2836,
        'required_main_baseline': 'actual published R17 documentation after V108 full2774/installed679; unchanged326 product inputs',
        'force_push': False, 'full_capcut_parity': False}, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print('prepared five owners; no owner executed; R17-after-V108 main baseline required')


if __name__ == '__main__':
    main()
