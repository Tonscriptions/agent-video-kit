"""Bounded local template changes, preserving resource IDs and restore semantics.

OpenFilm's MIT DOM implementation is packaged separately, byte for byte.
Validation, asset closure and immutable native project recipes are our host.
"""
from __future__ import annotations

import copy
import json
import re

from .errors import AppError
from .policy import resolve_local_path
from .project import asset_map
from .utils import assert_id

MAX_CHANGES = 128
MAX_JSON_BYTES = 65536
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
VARIABLE = re.compile(r'^--[A-Za-z_][A-Za-z0-9_-]{0,127}$')


def fail(message, field='overrides'):
    raise AppError('HTML_OVERRIDE_INVALID', message, exit_code=2, path=field)


def _selector(item):
    at = item.get('at')
    if not isinstance(at, str) or not at.strip() or len(at) > 512 or any(ord(c) < 32 for c in at):
        fail('要求最多 512 字符的非空 CSS selector', 'at')
    n = item.get('n')
    if 'n' in item and (type(n) is not int or not 1 <= n <= 1024):
        fail('n 须为 1..1024 整数，省略代表所有匹配', 'n')
    return (at, n)


def merge_overrides(previous=None, patch=None):
    """A null removes a saved change; omitted keys inherit, empty text remains."""
    result = {'variables': {}, 'texts': [], 'images': []}
    for value in (previous, patch):
        if value is None:
            continue
        if not isinstance(value, dict) or set(value)-set(result):
            fail('覆盖只接受 variables/texts/images 对象字段')
        variables = value.get('variables', {})
        if not isinstance(variables, dict) or len(variables) > 64:
            fail('CSS 变量须为最多 64 项的对象', 'variables')
        for key, text in variables.items():
            if not isinstance(key, str) or not VARIABLE.fullmatch(key):
                fail('CSS 变量名无效', 'variables')
            if text is not None:
                if not isinstance(text, str) or not text.strip() or len(text) > 2048 or any(ord(c) < 32 for c in text):
                    fail('CSS 变量须为明确的非空字符串，数值必须带原单位', key)
                if re.search(r'url\s*\(|image-set\s*\(|@import|(?:https?|file|data|javascript)\s*:', text, re.I):
                    fail('变量不能携带 URL；图片须以资产 ID 显式替换', key)
                result['variables'][key] = text.strip()
            else:
                result['variables'].pop(key, None)
        for kind, field in [('texts', 'value'), ('images', 'asset_id')]:
            items = value.get(kind, [])
            if not isinstance(items, list) or len(items) > MAX_CHANGES:
                fail('文字/图片覆盖数组超预算', kind)
            indexed = {(_selector(x), x.get('kind')): x for x in result[kind]}
            seen = set()
            for item in items:
                fields = {'at', 'n', field} | ({'kind'} if kind == 'images' else set())
                if not isinstance(item, dict) or set(item)-fields or not {'at', field}.issubset(item):
                    fail('文字/图片覆盖字段无效', kind)
                key = (_selector(item), item.get('kind'))
                if key in seen:
                    fail('同一覆盖文件包含重复目标', kind)
                seen.add(key)
                text = item[field]
                if kind == 'texts':
                    if text is not None and (not isinstance(text, str) or len(text) > 8000 or '\x00' in text):
                        fail('文字必须为最多 8000 字符的字符串或 null', kind)
                else:
                    if item.get('kind') not in {'img', 'bg'}:
                        fail('图片须明确 kind=img 或 bg', kind)
                    if text is not None:
                        assert_id(text, 'asset_id')
                if text is None:
                    indexed.pop(key, None)
                else:
                    indexed[key] = copy.deepcopy(item)
            result[kind] = sorted(indexed.values(), key=lambda x: (x['at'], x.get('n', 0), x.get('kind', '')))
        if len(result['variables']) > 64 or sum(len(result[k]) for k in result) > MAX_CHANGES:
            fail('合并后的覆盖超过 128 项')
    if len(json.dumps(result,ensure_ascii=False).encode('utf-8')) > MAX_JSON_BYTES:
        fail('合并后的覆盖 JSON 超过 64 KiB')
    return result


def read_patch(root, value):
    if not value:
        return None
    path = resolve_local_path(root, value, field='overrides')
    if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        fail('覆盖文件必须是最多 64 KiB 的本地 JSON 文件')
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:fail('JSON 不允许重复字段',str(key))
            out[key]=value
        return out
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique)
    except (ValueError,UnicodeError) as exc:
        fail('覆盖 JSON 解析失败: '+str(exc))


def attach_resources(root, project, source, changes):
    """Copy verified image bytes into this render only; never edit source ZIP."""
    from .html_motion import MAX_BYTES, MAX_FILES, digest
    compiled, references = [], []
    assets = asset_map(project)
    data, files = source['data'], source['files']
    for item in changes['images']:
        asset = assets.get(item['asset_id'])
        if not asset or asset['kind'] != 'image':
            fail('替换图片必须为已登记的 image 资产', item['asset_id'])
        path = resolve_local_path(root, asset['uri'], field='image')
        if path.suffix.lower() not in IMAGE_EXTENSIONS or not path.is_file() or path.stat().st_size > MAX_BYTES:
            fail('替换图片类型或文件预算无效', item['asset_id'])
        # Resolving a directory junction is permitted for an ordinary project
        # URI; bytes and the asset hash are still checked before every job.
        content = path.read_bytes()
        if digest(content) != asset['sha256']:
            fail('替换图片已偏离登记 SHA-256', item['asset_id'])
        name = '__template_images/'+asset['sha256'][7:]+path.suffix.lower()
        if name in data and data[name] != content:
            fail('替换图片与源码路径冲突', name)
        if name not in data:
            data[name] = content
            files.append({'path': name, 'bytes': len(content), 'sha256': asset['sha256']})
        references.append({'asset_id': asset['id'], 'sha256': asset['sha256'], 'rights_ref': asset['rights_ref'], 'path': name})
        compiled.append({'at': item['at'], **({'n': item['n']} if 'n' in item else {}),
                         'style': {'content' if item['kind'] == 'img' else 'backgroundImage': 'url("/'+name+'")'},
                         '_image_kind': item['kind']})
    if len(data) > MAX_FILES or sum(len(v) for v in data.values()) > MAX_BYTES:
        fail('替换后资源闭包超过 256 文件或 64 MiB')
    compiled = ([{'at': ':root', 'style': changes['variables']}] if changes['variables'] else []) + [
        {'at': x['at'], **({'n': x['n']} if 'n' in x else {}), 'text': x['value']} for x in changes['texts']] + compiled
    return compiled, references
