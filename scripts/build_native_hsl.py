"""Build the original frei0r HSL DLL with an existing native MSVC toolchain."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--vcvars',type=Path,required=True);p.add_argument('--compiler',type=Path,required=True)
    a=p.parse_args();work=a.work.resolve();evidence=a.evidence.resolve()
    assert platform.system()=='Windows' and platform.machine().lower() in ('amd64','x86_64')
    assert not work.exists() and not evidence.exists() and work.is_relative_to(ROOT/'product/.runtime')
    assert evidence.is_relative_to(ROOT/'docs') and a.vcvars.is_file() and a.compiler.is_file()
    work.mkdir(parents=True);evidence.mkdir(parents=True)
    source=ROOT/'product/src/ai_ad_editor/native_hsl.c';dll=work/'avk_hsl.dll'
    (evidence/'executed-source.c').write_bytes(source.read_bytes())
    command=[str(a.compiler.resolve()),'/nologo','/O2','/W4','/WX','/std:c11','/LD','/MT','/fp:precise','/Brepro',
             '/Fo'+str(work/'native_hsl.obj'),'/Fe'+str(dll),str(source),'/link','/INCREMENTAL:NO','/Brepro']
    # Both paths and flags are authored here, still reject cmd metacharacters.
    assert not any(any(c in arg for c in '%&|<>!\r\n') for arg in [str(a.vcvars),*command])
    shell='call '+subprocess.list2cmdline([str(a.vcvars.resolve())])+' >nul && '+subprocess.list2cmdline(command)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'generator_sha256':sha(__file__),'source_sha256':sha(source),'compiler_sha256':sha(a.compiler),
            'vcvars_sha256':sha(a.vcvars),'command':command,'shell_command':shell,
            'network':False,'virtualization':False,'runtime_compilation':False}
    env={**os.environ,'TEMP':str(work),'TMP':str(work),'TMPDIR':str(work),'VSCMD_SKIP_SENDTELEMETRY':'1'}
    # Supply a raw Windows command line: list2cmdline on the complete /c body
    # would insert literal backslash-quotes, which cmd.exe does not unescape.
    result=subprocess.run('cmd.exe /d /s /c "'+shell+'"',cwd=work,env=env,capture_output=True,timeout=180)
    for stream in ('stdout','stderr'):(evidence/(stream+'.log')).write_bytes(getattr(result,stream))
    record.update(exit_code=result.returncode,finished_at_utc=datetime.now(timezone.utc).isoformat())
    if result.returncode==0:
        name='avk_hsl_'+sha(dll)[7:23]+'.dll';target=source.with_name(name)
        assert not target.exists();shutil.copyfile(dll,target)
        manifest={'format':'avk-selective-hsl-native-v1','platform':'win32-amd64','program_format':'AVKHSL01',
            'binary_filename':name,'binary_sha256':sha(target),'source_sha256':sha(source),'license':'NATIVE_HSL_LICENSE.txt',
            'compiler':'MSVC 19.29 x64 /O2 /MT /fp:precise /Brepro','runtime_compilation':False}
        source.with_name('native_hsl_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8',newline='\n')
        record.update(status='passed-build',manifest=manifest,binary_bytes=target.stat().st_size)
    else:record['status']='failed'
    (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    assert result.returncode==0,'native build failed; original logs retained'
    print(json.dumps({'status':record['status'],'manifest':manifest,'binary_bytes':record['binary_bytes']}))


if __name__=='__main__':main()
