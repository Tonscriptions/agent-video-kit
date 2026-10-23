"""Reuse the retained default-budget 4K admission harness with new LUT stages."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-keyer-lab-20261023'
source=(PARENT/'scripts/smoke_float_keyer_4k.py').read_text(encoding='utf8')
source=source.replace('keyer','shaper').replace('330','331')
start=source.index('def shaper_row(');end=source.index('\n\ndef main():',start)
source=source[:start]+'''def shaper_row(value,parameters):
    from shaper_media_oracle import tables,LOOKS,lookup_1d,lookup_3d
    name=Path(parameters['path']).stem
    first,second,domain,cube_domain=LOOKS[name];one,three=tables()
    result=value.copy();mapped=lookup_1d(value[:,:3],one,first,domain)
    if second:mapped=lookup_3d(mapped,three,second,cube_domain)
    strength=parameters.get('intensity',1.)
    result[:,:3]=value[:,:3].astype('float64')*(1-strength)+mapped.astype('float64')*strength
    return result
'''+source[end:]

def replace(old,new):
    global source
    assert source.count(old)==1,(old,source.count(old))
    source=source.replace(old,new)

replace('Original 4K default-budget color key and despill admission fixture',
    'Original 4K default-budget standalone 1D and combined shaper LUT admission fixture')
replace("        save_ledger(project_root, ledger)",'''        from shaper_media_oracle import write_tables
        for table in write_tables(project_root/'assets/looks'):
            add_record(ledger,{'asset_id':table.stem,'kind':'lut','verification_status':'verified','source_type':'generated',
                'source_url':str(table),'license_spdx':'CC0-1.0','evidence':str(ROOT/'scripts/shaper_media_oracle.py'),
                'permitted_uses':['all'],'sha256':sha(table),'verified_by':'original-shaper-table-generator'})
        shutil.copytree(project_root/'assets/looks',assets/'original-luts')
        save_ledger(project_root, ledger)''')
start=source.index("        cases = [");end=source.index('        contacts = []',start)
source=source[:start]+'''        from shaper_media_oracle import LOOKS
        cases=[(name,'lut',{'path':'assets/looks/'+name+'.cube','output_signal':dict(linear),
            'interpolation_1d':LOOKS[name][0],'interpolation':LOOKS[name][1] or 'tetrahedral','intensity':.85})
            for name in ('1d_spline','combined','headroom')]
'''+source[end:]
replace("            if label == 'rgb':","            if label == '1d_spline':")
replace("'continuous_key_distance_and_matte': True","'continuous_1D_and_combined_shaper': True")
source=source.replace('Original synthetic4K color key stripes','Original synthetic4K LUT grading stripes')
source=source.replace('p in assets.iterdir()','p in assets.rglob(\'*\')')
replace("        check('all331 source inputs unchanged', before == frozen())", "        check('all331 source inputs unchanged', before == frozen() and len(before)==331)")
replace("        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes()); save()", "        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())\n        (rel/'executed-oracle.py.txt').write_bytes((ROOT/'scripts/shaper_media_oracle.py').read_bytes()); save()")
ast.parse(source)
destination=ROOT/'scripts/smoke_float_shaper_4k.py';assert not destination.exists()
destination.write_text(source,encoding='utf8',newline='\n')
print('created three actual 4K standalone/combined LUT admission cases')
