"""Prepare spatial install/full/publication owners; no owner is executed here."""
import ast
import json
from pathlib import Path
import re
from run_frozen_regression import sha

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-gaussian-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-spatial-20261022-lab'


def transform(source):
    numbers = {'2715': '2774', '2667': '2715', '620': '679', '572': '620',
               '323': '326', '320': '323', '193': '195', '420': '479'}
    labels = {'full2715': 'full2774', 'full2667': 'full2715', 'installed620': 'installed679',
              'installed572': 'installed620', 'parent320': 'parent323', 'V107': 'V108', 'V106': 'V107', 'r107': 'r108'}
    expression = re.compile('|'.join(map(re.escape, labels))+r'|\b(?:'+'|'.join(numbers)+r')\b')
    source = expression.sub(lambda m: labels.get(m[0], numbers.get(m[0])), source)
    paths = {'float-gaussian': 'float-spatial', 'float-tone': 'float-gaussian', 'float_gaussian': 'float_spatial'}
    source = re.sub('|'.join(map(re.escape, paths)), lambda m: paths[m[0]], source)
    source = source.replace('tone_parent_source', 'gaussian_parent_source').replace('tone_published_parent', 'gaussian_published_parent')
    source = source.replace('passed-public-CLI-floating-Gaussian-and-native-float-previews',
                            'passed-public-CLI-floating-spatial-means-and-native-float-previews')
    source = source.replace('normalized continuous Float32 Gaussian blur with explicit coverage and axis semantics',
                            'continuous Float32 average and box blur with adaptive4K workspace admission')
    source = source.replace('Run the actual Gaussian full suite after the frozen basic-tone parent is published.',
                            'Run the actual spatial full suite after the frozen Gaussian parent is published.')
    source = source.replace('new_methods=48', 'new_methods=59')
    for old, new in [('native-r3', 'native-r2'), ('media-installed-r2', 'media-installed-r1'),
                     ('media-r2', 'media-r1'), ('installed-r2', 'installed-r1'),
                     ('static-review-r2', 'static-review-r1'), ('finish-chain-r2', 'finish-chain-r1')]:
        source = source.replace(old, new)
    return source


def main():
    rows = {}
    for stem in ('verify_float_gaussian_install', 'run_float_gaussian_complete', 'publish_float_gaussian',
                 'release_float_gaussian_after_complete', 'finish_float_gaussian_chain'):
        parent = PARENT/'scripts'/(stem+'.py'); source = transform(parent.read_text('utf8'))
        if stem == 'verify_float_gaussian_install':
            source = source.replace("'test_float_tone','test_float_spatial']", "'test_float_tone','test_float_gaussian','test_float_spatial']")
            source = source.replace('native_float_spatial_integrated=True',
                                    'native_float_gaussian_integrated=True, native_float_spatial_means_integrated=True')
            anchor = "        check('nine pinned wheelhouse inputs unchanged',"
            assert anchor in source
            source = source.replace(anchor,
                "        from float_spatial_release_docs import fourk\n"
                "        proof4k=fourk(before)\n"
                "        check('actual default-budget4K source proof bound', proof4k['frozen_after']==before, public_CLI_processes=proof4k['public_CLI_processes'])\n"+anchor)
        if stem == 'run_float_gaussian_complete':
            anchor = "        verify(ROOT,before);verify(ROOT,deps)"
            assert anchor in source
            source = source.replace(anchor, "        from float_spatial_release_docs import fourk\n        fourk(before)\n"+anchor, 1)
            source = source.replace("'parent-publication-r1.json','parent-binding-r1.json','external-fixtures-r1.json']",
                "'parent-publication-r1.json','parent-binding-r1.json','external-fixtures-r1.json','4k-r2/verification.json']")
        if stem == 'publish_float_gaussian':
            source = source.replace('float-spatial-20261022-*/**', 'float-spatial*-20261022-*/**')
            anchor = "'source_media_receipt_sha256':sha(ROOT/REL/'media-r1/verification.json'),"
            assert anchor in source
            source = source.replace(anchor, anchor+"\n        'actual4K_receipt_sha256':sha(ROOT/REL/'4k-r2/verification.json'),")
        if stem == 'finish_float_gaussian_chain':
            source = source.replace("'actual-readme-preview-r3'", "'actual-readme-preview-r2'")
            source = source.replace("'--revision','r3'", "'--revision','r2'")
        destination = ROOT/'scripts'/(stem.replace('float_gaussian', 'float_spatial')+'.py')
        assert not destination.exists(); ast.parse(source)
        destination.write_text(source, encoding='utf8', newline='\n')
        rows[destination.name] = {'source_sha256': sha(parent), 'candidate_sha256': sha(destination)}
    path = REL/'release-drivers-r1.json'; assert not path.exists()
    path.write_text(json.dumps({'status': 'prepared-not-executed', 'scripts': rows, 'target_full_methods': 2774,
        'source_methods_gate': 479, 'installed_methods_target': 679, 'shipping_resource_target': 195,
        'changed_product_paths': 10, 'required_parent': 'actual published V107/full2715/installed620',
        'required_actual4K_proof': '4k-r2/verification.json', 'force_push': False, 'full_capcut_parity': False}, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print('prepared five owners: actual source479, actual4K, installed679 and full2774 are independent execution gates')


if __name__ == '__main__': main()
