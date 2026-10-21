"""Reuse the V81 bounded Git/index byte verifier for the index release."""
import hashlib
from pathlib import Path
import subprocess
MAIN=Path("E:/dev/sandbox/AI广告剪辑")

def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda: handle.read(65536), b''):
            value.update(part)
    return 'sha256:' + value.hexdigest()

def git(root, *args):
    return subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args],
                          cwd=root, capture_output=True, check=True).stdout

def staged_rows(expected):
    """Compare the index stream in bounded chunks, including unchanged frozen inputs."""
    process = subprocess.Popen(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', 'cat-file', '--batch'],
                               cwd=MAIN, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = []
    try:
        for name, digest in sorted(expected.items()):
            assert '\n' not in name and '\r' not in name
            process.stdin.write((':' + name + '\n').encode('utf8'))
            process.stdin.flush()
            header = process.stdout.readline().rstrip(b'\n').rsplit(b' ', 2)
            assert len(header) == 3 and header[1] == b'blob', (name, header)
            size = int(header[2]); path = MAIN / name
            assert path.stat().st_size == size, name
            remaining = size; value = hashlib.sha256()
            with path.open('rb') as handle:
                while remaining:
                    chunk = process.stdout.read(min(65536, remaining))
                    assert chunk and chunk == handle.read(len(chunk)), name
                    remaining -= len(chunk); value.update(chunk)
                assert not handle.read(1)
            assert process.stdout.read(1) == b'\n'
            assert 'sha256:' + value.hexdigest() == digest, name
            rows.append({'path': name, 'bytes': size, 'sha256': digest, 'git_blob': header[0].decode()})
        process.stdin.close()
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=10)
        for handle in (process.stdin, process.stdout, process.stderr):
            if handle and not handle.closed:
                handle.close()
    return rows
