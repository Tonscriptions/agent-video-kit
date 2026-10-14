from __future__ import annotations

import copy
import re
from typing import Any


PLACEHOLDER = re.compile(r"^\{\{([A-Za-z0-9_.:-]+)\}\}$")
INLINE_PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_.:-]+)\}\}")
COLOR_VALUE = re.compile(r"^(?:#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?|rgba?\([^()]+\)|[A-Za-z][A-Za-z0-9_-]*)$")
VARIABLE_TYPES = {"any", "string", "number", "integer", "boolean", "asset", "color", "enum"}


def substitute(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = PLACEHOLDER.fullmatch(value)
        if match:
            key = match.group(1)
            if key not in variables:
                raise KeyError(key)
            return copy.deepcopy(variables[key])

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise KeyError(key)
            replacement = variables[key]
            if isinstance(replacement, (dict, list, tuple, set)):
                raise ValueError(f"变量 {key} 不能作为字符串内嵌值")
            return str(replacement)

        return INLINE_PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, variables) for key, item in value.items()}
    return value


def validate_variables(template: dict[str, Any], variables: dict[str, Any]) -> list[str]:
    declarations = template.get("variables", [])
    if declarations is None:
        declarations = []
    if not isinstance(declarations, list):
        raise ValueError("模板 variables 必须是数组")
    missing: list[str] = []
    seen: set[str] = set()
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise ValueError("模板变量声明必须是对象")
        name = declaration.get("name")
        if not isinstance(name, str) or not name or not re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
            raise ValueError("模板变量 name 必须匹配 [A-Za-z0-9_.:-]+")
        if name in seen:
            raise ValueError(f"模板变量重复声明: {name}")
        seen.add(name)
        declared_type = str(declaration.get("type", "any")).lower()
        if declared_type not in VARIABLE_TYPES:
            raise ValueError(f"模板变量 {name} 的 type 不支持: {declared_type}")
        if declaration.get("required", False) and name not in variables and "default" not in declaration:
            missing.append(str(name))
        if name not in variables and "default" in declaration:
            candidate = declaration["default"]
        elif name in variables:
            candidate = variables[name]
        else:
            continue
        if not _value_matches(candidate, declaration):
            raise ValueError(f"模板变量 {name} 不符合 type={declared_type} 的约束")
    return missing


def _value_matches(value: Any, declaration: dict[str, Any]) -> bool:
    declared_type = str(declaration.get("type", "any")).lower()
    if declared_type == "any":
        return True
    if declared_type in {"string", "asset", "color", "enum"} and not isinstance(value, str):
        return False
    if declared_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return False
    if declared_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return False
    if declared_type == "boolean" and not isinstance(value, bool):
        return False
    if declared_type == "color" and not COLOR_VALUE.fullmatch(value):
        return False
    if declared_type == "enum":
        allowed = declaration.get("values", declaration.get("choices", declaration.get("enum")))
        if not isinstance(allowed, list) or value not in allowed:
            return False
    if declared_type in {"number", "integer"}:
        if "min" in declaration and value < declaration["min"]:
            return False
        if "max" in declaration and value > declaration["max"]:
            return False
    if declared_type in {"string", "asset", "color", "enum"}:
        if "min_length" in declaration and len(value) < int(declaration["min_length"]):
            return False
        if "max_length" in declaration and len(value) > int(declaration["max_length"]):
            return False
    return True


def instantiate(template: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(variables, dict):
        raise ValueError("模板变量必须是对象")
    resolved_variables = copy.deepcopy(variables)
    missing = validate_variables(template, resolved_variables)
    if missing:
        raise ValueError(f"模板缺少必填变量: {', '.join(missing)}")
    for declaration in template.get("variables", []) or []:
        name = declaration.get("name")
        if name not in resolved_variables and "default" in declaration:
            resolved_variables[name] = copy.deepcopy(declaration["default"])
    resolved = substitute(copy.deepcopy(template), resolved_variables)
    resolved["template_snapshot"] = {"id": template.get("id"), "version": template.get("version"), "variables": copy.deepcopy(resolved_variables)}
    return resolved
