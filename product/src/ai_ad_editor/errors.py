from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AppError(Exception):
    code: str
    message: str
    exit_code: int = 9
    path: str | None = None
    retryable: bool = False
    cause: str | None = None
    hint: str | None = None
    operation_id: str | None = None

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "retryable": self.retryable,
        }
        if self.cause:
            value["cause"] = self.cause
        if self.hint:
            value["hint"] = self.hint
        if self.operation_id:
            value["operation_id"] = self.operation_id
        return value


def argument_error(message: str, path: str | None = None) -> AppError:
    return AppError("ARGUMENT_INVALID", message, exit_code=2, path=path)


def missing_asset(message: str, path: str | None = None) -> AppError:
    return AppError("ASSET_MISSING", message, exit_code=3, path=path)


def dependency_error(message: str, hint: str | None = None) -> AppError:
    return AppError("DEPENDENCY_UNAVAILABLE", message, exit_code=10, hint=hint)


def rights_error(message: str, path: str | None = None, hint: str | None = None) -> AppError:
    return AppError("RIGHTS_BLOCKED", message, exit_code=7, path=path, hint=hint)
