from __future__ import annotations

import copy
import re
from typing import Any


PLACEHOLDER = re.compile(r"^\{\{([A-Za-z0-9_.:-]+)\}\}$")


def substitute(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = PLACEHOLDER.fullmatch(value)
        if match:
            key = match.group(1)
            if key not in variables:
                raise KeyError(key)
            return variables[key]
        return value
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, variables) for key, item in value.items()}
    return value


def validate_variables(template: dict[str, Any], variables: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for declaration in template.get("variables", []):
        name = declaration.get("name")
        if declaration.get("required", False) and name not in variables and "default" not in declaration:
            missing.append(str(name))
    return missing


def instantiate(template: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    missing = validate_variables(template, variables)
    if missing:
        raise ValueError(f"模板缺少必填变量: {', '.join(missing)}")
    resolved = {}
    for declaration in template.get("variables", []):
        name = declaration.get("name")
        if name not in variables and "default" in declaration:
            variables[name] = declaration["default"]
    resolved = substitute(copy.deepcopy(template), variables)
    resolved["template_snapshot"] = {"id": template.get("id"), "version": template.get("version"), "variables": copy.deepcopy(variables)}
    return resolved
