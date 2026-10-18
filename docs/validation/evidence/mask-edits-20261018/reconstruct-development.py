"""Reconstruct measured development snapshots and require every saved byte hash."""
from pathlib import Path
import hashlib,json,re,zipfile
ROOT=Path(__file__).resolve().parents[2]
runtime=ROOT/'product/.runtime'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
for tag,name in [('initial','mask-edit-development-20261018'),('policy','mask-edit-final-full-20261018')]:
    record=json.loads((runtime/(name+'.json')).read_text(encoding='utf-8'))
    contents={}
    for path,expected in record['frozen_before'].items():
        data=(ROOT/path).read_bytes()
        if sha(data)!=expected:
            text=data.decode('utf-8')
            if path.endswith('/cli.py'):
                text=text.replace("source_version='derived-local-mask-edit'", "source_version='derived:local-mask-edit'")
                if tag=='initial':
                    text=text.replace("        if (previous is None or previous.get('kind') not in {'image', 'video'} or authored.get('engine') != mask_edit.ENGINE\n                or not isinstance(embedded, dict) or mask_edit.plan_digest(embedded) != authored.get('plan_sha256')):",
                        "        if not isinstance(embedded, dict) or mask_edit.plan_digest(embedded) != authored.get('plan_sha256'):")
            elif path.endswith('/test_mask_edit.py'):
                text=text.replace("        code, audited = invoke('policy', 'audit', '--project', self.root)\n        self.assertEqual(code, 0, audited)\n",'')
                if tag=='initial':
                    text=re.sub(r'    def test_native_rational_overflow_rejects_before_decode.*?(?=    def test_preexecution_cancel)', '',text,flags=re.S)
                    text=text.replace("        self.assertEqual(code, 6, result)\n        self.assertEqual(result['errors'][0]['code'], 'PROJECT_WRITE_LOCKED')", "        self.assertEqual(code, 8, result)")
            elif path.endswith('/mask_edit.py') and tag=='initial':
                text=text.replace("    rate = Fraction(info['fps'])\n    if max(rate.numerator, rate.denominator) > 2**31-1:\n        raise argument_error('帧率分数必须能由原生编码器的有符号 32 位有理数表示', 'fps')\n",'')
            elif path.endswith('/mask_edit_geometry.py') and tag=='initial':
                text=text.replace("                if checkpoint and index % 8192 == 0:\n                    checkpoint()\n",'')
            data=text.encode('utf-8')
        assert sha(data)==expected,(tag,path,sha(data),expected)
        contents[path]=data
    target=runtime/f'mask-edit-{tag}-source-20261018.zip';assert not target.exists()
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path,data in contents.items():archive.writestr(path,data)
    print(json.dumps({'snapshot':tag,'files':len(contents),'every_saved_hash_matched':True,'zip_sha256':sha(target.read_bytes())}))
