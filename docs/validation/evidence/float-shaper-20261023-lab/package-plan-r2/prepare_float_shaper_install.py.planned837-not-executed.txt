"""Reuse the pinned native offline audit and add the actual 1D/shaper suite."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'pipeline-recovery-lab-20261023'
source=(PARENT/'scripts/verify_pipeline_recovery_install.py').read_text(encoding='utf8')
source=source.replace('pipeline_recovery','float_shaper').replace('pipeline-recovery','float-shaper')
source=source.replace("REL = ROOT/'docs/validation/evidence/float-shaper-20261023'", "REL = ROOT/'docs/validation/evidence/float-shaper-20261023-lab'")
source=source.replace('804','837').replace('== 330','== 331').replace('330 product','331 product')
start=source.index("        standard=json.loads(");end=source.index("        bundle, installed =",start)
source=source[:start]+'''        standard=json.loads((REL/'native-r2/verification.json').read_bytes())
        check('actual 1D shaper source118 accepted', standard['status']=='passed' and standard['methods']==118 and standard['skipped']==0 and standard['frozen_before']==standard['frozen_after']==before)
        proof4k=json.loads((REL/'4k-r1/verification.json').read_bytes())
        check('actual default budget4K shaper proof bound', proof4k['status']=='passed-actual-default-budget-4K-formal-preview-and-independent-pixels' and proof4k['public_CLI_processes']==8 and proof4k['frozen_before']==proof4k['frozen_after']==before)
        reference=REL/'media-r1/verification.json'
        media=json.loads(reference.read_bytes())
        check('actual source public CLI shaper media accepted', media['status']=='passed-public-CLI-floating-shaper-and-native-float-previews' and media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3 and media['frozen_before']==media['frozen_after']==before)
        record['accepted_source_evidence']={'source':sha(REL/'native-r2/verification.json'),'4K':sha(REL/'4k-r1/verification.json'),'media':sha(reference)}
'''+source[end:]
source=source.replace('smoke_float_keyer_media.py','smoke_float_shaper_media.py').replace('installed-recovery-r1','installed-r1')
source=source.replace("ROOT/'docs/validation/evidence/float-keyer-20261023-lab/media-installed-r1/verification.json'", "REL/'media-installed-r1/verification.json'")
source=source.replace('passed-public-CLI-floating-keyer-and-native-float-previews','passed-public-CLI-floating-shaper-and-native-float-previews')
assert source.count("'test_float_keyer','test_html_motion.")==1
source=source.replace("'test_float_keyer','test_html_motion.","'test_float_keyer','test_float_shaper','test_html_motion.")
source=source.replace('HTML_preparation_diagnostics_integrated=True','HTML_preparation_diagnostics_integrated=True,native_float_1D_shaper_integrated=True')
ast.parse(source)
runner=(PARENT/'scripts/run_pipeline_installed_suite.py').read_text(encoding='utf8').replace('len(names)==39','len(names)==40').replace('804','837')
ast.parse(runner)
for name,text in [('verify_float_shaper_install.py',source),('run_float_shaper_installed_suite.py',runner)]:
    path=ROOT/'scripts'/name;assert not path.exists();path.write_text(text,encoding='utf8',newline='\n')
print('created offline eight-wheel isolated 837-method shaper audit; not executed')
