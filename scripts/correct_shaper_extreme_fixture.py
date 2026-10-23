"""Preserve r1 failure, then reach actual interpolation overflow with finite table values."""
from datetime import datetime,timezone
import ast
import json
from pathlib import Path
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/float-shaper-20261023-lab'

def main():
    proof=json.loads((REL/'native-r1/verification.json').read_bytes())
    assert proof['status']=='failed-preserved' and proof['methods']==118 and proof['failures']==2 and proof['errors']==0 and proof['skipped']==0
    assert proof['frozen_before']==proof['frozen_after']
    log=(REL/'native-r1/unittest.log').read_text(encoding='utf8')
    assert 'FLOAT_LUT_FORMAT' in log and 'FLOAT_LUT_VALUES' in log
    output=REL/'fixture-correction-r1';output.mkdir(exist_ok=False)
    path=ROOT/'product/tests/test_float_shaper.py';before=sha(path)
    (output/'test_float_shaper.before.py.txt').write_bytes(path.read_bytes())
    source=path.read_text(encoding='utf8')
    old="    def test_author_intensity_six_modes_and_Fraction_ticks(self):\n        for mode in"
    new="    def test_author_intensity_six_modes_and_Fraction_ticks(self):\n        from test_spatial_automation import declared_bezier_reference\n        for mode in"
    assert source.count(old)==1;source=source.replace(old,new)
    source=source.replace("controls=[.2,.8] if mode=='bezier' else None","controls=[1/3,0,2/3,1] if mode=='bezier' else None")
    anchor="                np.testing.assert_allclose(actual[...,:3],a[...,:3]*(1-strength)+full[...,:3]*strength,rtol=0,atol=6e-8)"
    replacement="""                if mode=='bezier':strength=declared_bezier_reference(.5)
                self.assertAlmostEqual(meta['intensity'],strength,places=14)
                expected=(a[...,:3].astype(np.float64)*(1-strength)+full[...,:3].astype(np.float64)*strength).astype(np.float32)
                np.testing.assert_allclose(actual[...,:3],expected,rtol=0,atol=6e-8)"""
    assert source.count(anchor)==1;source=source.replace(anchor,replacement)
    old='        large=np.float32(np.finfo(np.float32).max)\n'
    assert source.count(old)==1
    source=source.replace(old,'        large=np.float32(np.finfo(np.float32).max*.9)\n')
    old="        cube=write_cube(self.root/'cube.cube',2);write_shaper(self.root/'look.cube',values,cube=cube)\n        with self.assertRaises(AppError) as caught:self.apply(fixture.rgba((.5,.5,.5,1)),effect(interpolation_1d='cubic'))"
    new="        cube=write_cube(self.root/'cube.cube',2);write_shaper(self.root/'look.cube',values,cube=cube)\n        plan=self.plan(effect(interpolation_1d='cubic'));self.assertTrue(np.isfinite(plan.cube.table_1d).all())\n        with self.assertRaises(AppError) as caught:apply_lut(fixture.rgba((.5,.5,.5,1)),plan,0,working_signal=fixture.LINEAR)"
    assert source.count(old)==1;source=source.replace(old,new)
    old='    def test_combined_and_max_1D_budget_reject_before_table_allocation(self):'
    assert source.count(old)==1
    source=source.replace(old,'    def test_combined_budget_rejects_before_allocation_and_actual_65536_points_execute(self):')
    anchor="            self.assertEqual(caught.exception.code,'FLOAT_LUT_BUDGET')\n\n    def test_retained_tables_share_cache"
    replacement="""            self.assertEqual(caught.exception.code,'FLOAT_LUT_BUDGET')
        x=np.linspace(0,1,65536,dtype=np.float32)
        table=np.stack((x,1-x,2*x-.5),1);write_shaper(self.root/'look.cube',table)
        a=fixture.rgba((0,.5,1,1));actual,meta=self.apply(a)
        expected=one_d_oracle(table,a.reshape(-1,4)[:,:3]).reshape(a.shape[:2]+(3,))
        np.testing.assert_array_equal(actual[...,:3],expected);self.assertEqual(meta['table_1d_size'],65536)

    def test_retained_tables_share_cache"""
    assert source.count(anchor)==1;source=source.replace(anchor,replacement);ast.parse(source)
    path.write_text(source,encoding='utf8',newline='\n')
    receipt=dict(status='corrected-extreme-fixture-after-preserved-118-method-failure',at_utc=datetime.now(timezone.utc).isoformat(),
        previous_methods=118,previous_failures=2,previous_errors=0,previous_skipped=0,
        reason='Formatting exact Float32 maximum with nine significant decimal digits yields a decimal slightly above the accepted mathematical Float32 maximum. r1 therefore rejected the sample at parse time, before the intended cubic overflow. Use 90 percent of the maximum so parsing succeeds and cubic overshoot still exceeds the Float32 output range.',
        runtime_changed=False,tolerances_changed=False,source_before=before,source_after=sha(path),
        second_failure='The six-mode fixture used exact analytic Bezier midpoint .5; existing author animation explicitly uses a 33-knot, 20-step inverse and eight-decimal serialized lookup. Bind the established independent declared-Bezier oracle, assert the exact sampled intensity and retain the original pixel tolerance.',
        additional_coverage='Execute a complete 65,536-point per-channel table at the admitted upper size; retained as part of the same method.',
        new_actual_methods_executed_here=0,prior_failure_preserved=True)
    (output/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':receipt['status'],'runtime_changed':False}))

if __name__=='__main__':main()
