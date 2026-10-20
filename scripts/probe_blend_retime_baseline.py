"""Capture the released planner's rejection without modifying its checkout."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve(strict=True)
    output = args.output.resolve()
    assert not output.exists()
    prior = json.loads(args.receipt.read_bytes())['frozen_after']
    def observed():
        return {p: 'sha256:'+hashlib.sha256((root/p).read_bytes()).hexdigest() for p in prior}
    before = observed()
    assert before == prior, 'baseline differs from the published full regression'
    sys.path[:0] = [str(root/'product/src'), str(root/'product/tests')]
    import ai_ad_editor.retime_edits as implementation
    from ai_ad_editor.edit_planner import build_edit_plan
    from ai_ad_editor.errors import AppError
    from test_retime_edits import state, request, at
    project = state()
    at(project, 'b').update(blend={'mode':'multiply', 'opacity':.5}, keyframes=[{
        'property':'blend.opacity', 'keyframes':[{'at_tick':0,'value':0}, {'at_tick':10,'value':1}]}])
    try:
        build_edit_plan(project, 'seq', request())
    except AppError as exc:
        rejection = exc.as_dict()
        assert exc.code == 'EDIT_RETIME_BLEND_CLOCK_UNSUPPORTED', rejection
    else:
        raise AssertionError('released rejection was not reproduced')
    after = observed()
    assert before == after
    record = {'kind':'released-planner-baseline', 'network':False, 'virtualization':False,
        'source_root':str(root), 'module_origin':implementation.__file__,
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'request':request(), 'input_clip':at(project,'b'), 'rejection':rejection,
        'frozen_before':before, 'frozen_after':after, 'frozen_equal':True,
        'published_inputs_equal':True, 'status':'reproduced'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'reproduced','code':rejection['code'],'frozen_inputs':len(before)}))


if __name__ == '__main__':
    main()
