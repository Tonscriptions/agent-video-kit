"""Typed, bounded component fields over the existing offline HTML overrides.

Field discovery/reset follows OpenFilm's component-props design (MIT); this
host uses stable IDs, explicit errors, registered assets and native recipes.
No upstream UI, arbitrary style, URL, model or browser starts on import.
"""
from __future__ import annotations

import copy
import json
import math

from .errors import AppError
from .html_template import (MAX_CHANGES, MAX_JSON_BYTES, VARIABLE, _selector,
                            attach_resources, merge_overrides, read_patch)
from .project import asset_map
from .rights import check_project_rights, load_ledger
from .utils import assert_id

ENGINE = 'agent-html-components-v1'
UNITS = {'', 'px', '%', 'em', 'rem', 'vw', 'vh', 'vmin', 'vmax', 'deg', 'rad',
         'turn', 's', 'ms', 'ch', 'ex', 'cm', 'mm', 'in', 'pt', 'pc'}
SCHEMA_KEYS = {'type', 'minimum', 'maximum', 'minLength', 'maxLength', 'enum'}


def fail(message, path='component_fields'):
    raise AppError('HTML_COMPONENT_INVALID', message, exit_code=2, path=path)


def bounded(value, label):
    try:
        data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf8')
    except (ValueError, TypeError, UnicodeError) as exc:
        fail('要求有限、有效的 JSON: ' + str(exc), label)
    if len(data) > MAX_JSON_BYTES:
        fail('组件定义、取值或有效覆盖超过 64 KiB', label)
    return value


def value_schema(field):
    kind = field['type']
    schema = copy.deepcopy(field.get('schema', {}))
    default_type = {'text': 'string', 'image': 'object', 'boolean': 'boolean', 'var': 'string'}[kind]
    schema.setdefault('type', default_type)
    if schema['type'] == 'string':
        schema.setdefault('maxLength', 8000 if kind == 'text' else 2048)
    if kind == 'image':
        schema.update(required=['asset_id'], additionalProperties=False,
                      properties={'asset_id': {'type': 'string', 'minLength': 1, 'maxLength': 128}})
    return schema


def validate_value(field, value):
    schema = value_schema(field)
    kind = schema['type']
    valid = ((kind == 'string' and isinstance(value, str)) or
             (kind == 'boolean' and type(value) is bool) or
             (kind == 'integer' and type(value) is int) or
             (kind == 'number' and type(value) in {int, float}) or
             (kind == 'object' and isinstance(value, dict) and set(value) == {'asset_id'}))
    if not valid:
        fail('字段值类型不符: ' + field['id'], 'component_values')
    if kind in {'number', 'integer'}:
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite or ('minimum' in schema and value < schema['minimum']) or ('maximum' in schema and value > schema['maximum']):
            fail('数值非有限或超出字段范围: ' + field['id'], 'component_values')
    elif kind == 'string':
        if '\x00' in value or not schema.get('minLength', 0) <= len(value) <= schema['maxLength']:
            fail('文字长度超出字段范围: ' + field['id'], 'component_values')
        if field['type'] == 'var':
            merge_overrides(patch={'variables': {field['var']: value}})
    elif kind == 'object':
        assert_id(value['asset_id'], 'component_values.asset_id')
    if 'enum' in schema and not any(type(value) is type(choice) and value == choice for choice in schema['enum']):
        fail('字段值不在枚举选项内: ' + field['id'], 'component_values')
    return copy.deepcopy(value)


def validate_fields(value):
    bounded(value, 'component_fields')
    if not isinstance(value, list) or len(value) > MAX_CHANGES:
        fail('字段定义须为最多 128 项的数组')
    ids, names, targets, out = set(), set(), set(), []
    for raw in value:
        if not isinstance(raw, dict) or not {'id', 'name', 'type'} <= set(raw):
            fail('字段须有 id/name/type')
        field = copy.deepcopy(raw)
        assert_id(field['id'], 'component_fields.id')
        name, kind = field['name'], field['type']
        if not isinstance(name, str) or not name.strip() or name != name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
            fail('字段名称须为最多 80 字符的明确非空名称')
        if not isinstance(kind, str) or kind not in {'text', 'image', 'boolean', 'var'}:
            fail('字段 type 仅支持 text/image/boolean/var')
        allowed = {'id', 'name', 'type', 'schema', 'default'} | ({'var', 'unit'} if kind == 'var' else {'at', 'n'}) | ({'kind'} if kind == 'image' else set())
        if set(field) - allowed:
            fail('字段定义包含未知属性')
        if kind == 'var':
            if not isinstance(field.get('var'), str) or not VARIABLE.fullmatch(field['var']):
                fail('CSS 变量名无效，不能仅为 --')
            target = (kind, field['var'])
        else:
            target = (kind, *_selector(field))
            if kind == 'image' and field.get('kind') not in {'img', 'bg'}:
                fail('图片字段要求 kind=img 或 bg')
        if field['id'] in ids or name in names or target in targets:
            fail('字段 ID、名称或同类型目标重复')
        ids.add(field['id']); names.add(name); targets.add(target)
        schema = field.get('schema', {})
        if not isinstance(schema, dict) or set(schema) - SCHEMA_KEYS:
            fail('字段 schema 含不支持的校验关键字')
        expected = {'text': {'string'}, 'image': {'object'}, 'boolean': {'boolean'}, 'var': {'string', 'number', 'integer'}}[kind]
        actual = value_schema(field)['type']
        if not isinstance(actual, str) or actual not in expected:
            fail('字段 schema.type 与组件类型不一致')
        if set(schema) & {'minimum', 'maximum'} and actual not in {'number', 'integer'}:
            fail('范围只适用于数值变量')
        if set(schema) & {'minLength', 'maxLength'} and actual != 'string':
            fail('长度只适用于字符串')
        for key in ('minimum', 'maximum'):
            if key in schema:
                n = schema[key]
                try:
                    finite = type(n) in {int, float} and math.isfinite(n)
                except OverflowError:
                    finite = False
                if not finite:
                    fail('数值范围须为有限数字')
        if schema.get('minimum', -math.inf) > schema.get('maximum', math.inf):
            fail('minimum 不能大于 maximum')
        maximum = 8000 if kind == 'text' else 2048
        for key in ('minLength', 'maxLength'):
            if key in schema and (type(schema[key]) is not int or not 0 <= schema[key] <= maximum):
                fail('字符串长度约束超出预算')
        if schema.get('minLength', 0) > schema.get('maxLength', maximum):
            fail('minLength 不能大于 maxLength')
        if 'enum' in schema:
            choices = schema['enum']
            if not isinstance(choices, list) or not 1 <= len(choices) <= 64:
                fail('enum 须为 1..64 项数组')
            without_enum = copy.deepcopy(field)
            without_enum['schema'] = {k: v for k, v in schema.items() if k != 'enum'}
            seen = set()
            for choice in choices:
                validate_value(without_enum, choice)
                key = json.dumps(choice, sort_keys=True, ensure_ascii=False, allow_nan=False)
                if key in seen:
                    fail('enum 含重复选项')
                seen.add(key)
        if 'unit' in field and (actual not in {'number', 'integer'} or not isinstance(field['unit'], str) or field['unit'] not in UNITS):
            fail('unit 只支持数值变量和明确的 CSS 单位')
        if field.get('default') is not None:
            if kind == 'boolean':
                fail('显隐默认须为 null/原页面；true/false 使用逐片段值')
            validate_value(field, field['default'])
        out.append(field)
    return out


def read_values(fields, stored):
    bounded(stored, 'component_values')
    if not isinstance(stored, list) or len(stored) > MAX_CHANGES:
        fail('保存的组件值须为最多 128 项数组', 'component_values')
    by_id, result = {f['id']: f for f in fields}, {}
    for item in stored:
        if not isinstance(item, dict) or set(item) != {'field_id', 'value'}:
            fail('保存值只接受 field_id/value', 'component_values')
        key = item['field_id']
        if not isinstance(key, str) or key not in by_id or key in result or item['value'] is None:
            fail('保存值含未知、重复或 null 字段', 'component_values')
        result[key] = validate_value(by_id[key], item['value'])
    return result


def configure(root, source, previous, args):
    """Resolve definitions and patch values; preserve old snapshots unless explicit."""
    previous = previous or {}
    original = validate_fields(previous.get('component_fields', source['asset']['html_source'].get('component_fields', [])))
    values = read_values(original, previous.get('component_values', []))
    fields_path = getattr(args, 'component_fields', None)
    fields = validate_fields(read_patch(root, fields_path)) if fields_path else original
    if getattr(args, 'reset_components', False):
        values = {}
    patch_path = getattr(args, 'component_values', None)
    patch = read_patch(root, patch_path) if patch_path else {}
    if not isinstance(patch, dict) or len(patch) > MAX_CHANGES:
        fail('组件取值补丁须为最多 128 项的对象', 'component_values')
    known = {f['id'] for f in fields}
    old_ids = {f['id'] for f in original}
    for key, value in patch.items():
        if key not in known and not (key in old_ids and value is None):
            fail('未知组件字段: ' + str(key), 'component_values')
        if value is None:
            values.pop(key, None)
        else:
            values[key] = copy.deepcopy(value)
    stored = [{'field_id': key, 'value': value} for key, value in sorted(values.items())]
    read_values(fields, stored)
    enabled = bool(fields_path or patch_path or getattr(args, 'reset_components', False) or
                   'component_fields' in previous or 'component_fields' in source['asset']['html_source'])
    return fields, stored, enabled


def _image_closure(source, project):
    assets = asset_map(project)
    return {entry['asset_id']: entry for entry in source['asset']['html_source'].get('resources', [])
            if assets.get(entry.get('asset_id'), {}).get('kind') == 'image'}


def check_images(root, project, source, fields, values, *, strict=True):
    closure = _image_closure(source, project)
    assets = asset_map(project)
    selected = []
    for field in fields:
        if field['type'] != 'image':
            continue
        candidates = list(field.get('schema', {}).get('enum', []))
        if field.get('default') is not None:
            candidates.append(field['default'])
        actual = values.get(field['id'], field.get('default'))
        if actual is not None:
            candidates.append(actual)
            selected.append(actual['asset_id'])
        for value in candidates:
            aid = value['asset_id']
            if aid not in closure or aid not in assets or closure[aid]['sha256'] != assets[aid]['sha256']:
                fail('图片必须属于已登记的源资源闭包: ' + aid, 'component_values')
        if not closure:
            fail('图片字段需要至少一个已登记的源图片资源')
    if strict and selected:
        candidate = {'assets': [assets[key] for key in sorted(set(selected))]}
        gate = check_project_rights(candidate, load_ledger(root), 'commercial_ad', strict=True)
        if not gate['ok']:
            raise AppError('HTML_COMPONENT_RIGHTS_BLOCKED', '组件图片权利不满足本地使用门槛', exit_code=2,
                           path='component_values', cause=json.dumps(gate, ensure_ascii=False))
    return closure


def compile_overrides(root, project, source, ordinary, fields, stored):
    values = read_values(fields, stored)
    check_images(root, project, source, fields, values)
    patch, visibility = {'variables': {}, 'texts': [], 'images': []}, []
    for field in fields:
        value = values.get(field['id'], field.get('default'))
        if value is None:
            continue
        target = {k: field[k] for k in ('at', 'n') if k in field}
        if field['type'] == 'text':
            patch['texts'].append({**target, 'value': value})
        elif field['type'] == 'image':
            patch['images'].append({**target, 'kind': field['kind'], 'asset_id': value['asset_id']})
        elif field['type'] == 'boolean':
            visibility.append({**target, '_visible': value})
        else:
            text = value if isinstance(value, str) else str(value) + field.get('unit', '')
            patch['variables'][field['var']] = text
    combined = merge_overrides(ordinary, patch)
    if sum(len(v) for v in combined.values()) + len(visibility) > MAX_CHANGES:
        fail('普通与组件覆盖合计超过 128 项')
    bounded({'overrides': combined, 'visibility': visibility}, 'component_overrides')
    compiled, references = attach_resources(root, project, source, combined)
    return compiled + visibility, references


def discover(root, project, source, fields, stored, ordinary):
    values = read_values(fields, stored)
    closure = check_images(root, project, source, fields, values)
    # Identical compilation budgets to the write path, with no browser/runtime.
    compile_overrides(root, project, source, ordinary, fields, stored)
    properties = {}
    for field in fields:
        schema = value_schema(field)
        if field['type'] == 'image':
            schema['properties']['asset_id']['enum'] = sorted(closure)
        properties[field['id']] = {'title': field['name'], 'anyOf': [schema, {'type': 'null'}],
            'default': copy.deepcopy(field.get('default')), 'x-component-type': field['type'],
            'x-target': {k: field[k] for k in ('at', 'n', 'var', 'kind') if k in field},
            'x-default-source': 'field' if field.get('default') is not None else 'page',
            **({'x-unit': field['unit']} if 'unit' in field else {})}
    return {'engine': ENGINE, 'fields': fields, 'values': stored,
            'effective_values': [{'field_id': f['id'],
                'source': 'value' if f['id'] in values else 'field' if f.get('default') is not None else 'page',
                'value': copy.deepcopy(values.get(f['id'], f.get('default')))} for f in fields],
            'schema': {'type': 'object', 'additionalProperties': False, 'maxProperties': MAX_CHANGES, 'properties': properties},
            'limits': {'fields': MAX_CHANGES, 'json_bytes': MAX_JSON_BYTES, 'selector_characters': 512,
                       'match_index_max': 1024, 'images': 'registered_source_closure_and_strict_commercial_ad_rights'},
            'drawing_executed': False, 'component_overrides_follow_ordinary_overrides': True}


def validate_project_metadata(project):
    """Semantic part of the packaged schema; no runtime or generated writes."""
    assets = asset_map(project)
    for asset in project.get('assets', []):
        source = asset.get('html_source', {})
        if 'component_fields' in source:
            validate_fields(source['component_fields'])
        recipe = asset.get('html_motion', {})
        if 'component_fields' not in recipe and 'component_values' not in recipe:
            continue
        fields = validate_fields(recipe.get('component_fields', []))
        values = read_values(fields, recipe.get('component_values', []))
        source_asset = assets.get(recipe.get('source_asset_id'))
        if not source_asset or 'html_source' not in source_asset:
            fail('组件配方缺少可编辑源码资产')
        check_images(None, project, {'asset': source_asset}, fields, values, strict=False)
