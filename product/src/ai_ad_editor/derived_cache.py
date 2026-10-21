"""Bounded inventories and explicit pruning of fixed-layout derived caches."""
from itertools import islice
import os
from pathlib import Path
import re

from .errors import AppError


def fail(prefix,suffix,message,**details):
    return AppError(prefix+'_'+suffix,message,exit_code=6,diagnostics=details or None)


def owned(root,path,prefix):
    root=root.resolve();path=Path(os.path.abspath(path))
    if not path.is_relative_to(root):
        raise fail(prefix,'PATH_INVALID','派生缓存路径必须位于当前工程内',path=str(path))
    current=root
    for part in path.relative_to(root).parts:
        current/=part
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():
            raise fail(prefix,'PATH_INVALID','派生缓存路径不能包含符号链接或目录联接',path=str(current))
    return path


def entry(root,directory,*,file_names,prefix):
    directory=owned(root,directory,prefix)
    if not re.fullmatch('[0-9a-f]{64}',directory.name) or not directory.is_dir():
        raise fail(prefix,'LAYOUT_INVALID','派生缓存包含未知目录条目',path=str(directory))
    files=list(islice(directory.iterdir(),len(file_names)+1))
    if len(files)>len(file_names) or any(path.name not in file_names for path in files):
        raise fail(prefix,'LAYOUT_INVALID','派生缓存包含未知文件，拒绝清理',path=str(directory))
    for path in files:
        owned(root,path,prefix)
        if not path.is_file():
            raise fail(prefix,'LAYOUT_INVALID','派生缓存包含目录或特殊文件',path=str(path))
    return {'key':directory.name,'path':str(directory),'bytes':sum(path.stat().st_size for path in files),
            'mtime_ns':directory.stat().st_mtime_ns,'complete_file_set':{p.name for p in files}==set(file_names),
            'media_integrity_checked':False,'byte_integrity_checked':False}


def inventory(root,*,kind,file_names,protocol,maximum_entries,prefix):
    assert re.fullmatch('[a-z0-9-]+',kind)
    base=owned(root,root/'cache'/kind,prefix)
    directories=sorted(islice(base.iterdir(),maximum_entries+1)) if base.exists() else []
    if len(directories)>maximum_entries:
        raise fail(prefix,'ENTRY_BUDGET','派生缓存条目超过目录预算')
    entries=[entry(root,directory,file_names=file_names,prefix=prefix) for directory in directories]
    return {'protocol':protocol,'kind':kind,'entries':entries,
            'bytes':sum(item['bytes'] for item in entries),'max_entries':maximum_entries}


def prune(root,*,kind,file_names,protocol,maximum_entries,prefix,keep_bytes=0,dry_run=False,key=None):
    """Caller holds the project write lock; unlink known files without recursion."""
    if type(keep_bytes) is not int or keep_bytes<0 or (key is not None and
        (not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key) or keep_bytes)):
        raise fail(prefix,'ARGUMENT_INVALID','保留配额必须非负；指定 key 时配额必须为 0')
    listing=inventory(root,kind=kind,file_names=file_names,protocol=protocol,
                      maximum_entries=maximum_entries,prefix=prefix)
    from .preview import _paths_from_objects
    from .project import project_file
    from .utils import load_json
    base=owned(root,root/'cache'/kind,prefix);protected=set()
    for path in _paths_from_objects(root,load_json(project_file(root))):
        if path.is_relative_to(base) and (parts:=path.relative_to(base).parts):protected.add(parts[0])
    remaining=listing['bytes'];removed=[]
    for item in sorted(listing['entries'],key=lambda value:(value['mtime_ns'],value['key'])):
        if keep_bytes and remaining<=keep_bytes:break
        if item['key'] in protected or (key is not None and item['key']!=key):continue
        directory=owned(root,Path(item['path']),prefix)
        fresh=entry(root,directory,file_names=file_names,prefix=prefix)
        if not dry_run:
            try:
                for name in file_names:
                    path=owned(root,directory/name,prefix)
                    if path.exists():path.unlink()
                directory.rmdir()
            except OSError as caught:
                raise AppError(prefix+'_PRUNE_FAILED','无法完整清理派生缓存',exit_code=6,
                               path=str(directory),cause=str(caught)) from caught
        remaining-=fresh['bytes'];removed.append(item['key'])
    return {'protocol':protocol,'kind':kind,'removed':removed,'before_bytes':listing['bytes'],
            'remaining_bytes':remaining,'protected_reference_keys':sorted(protected),
            'dry_run':dry_run,'selected_key':key}
