"""SQLite schema migrations for locontext."""

from __future__ import annotations

import sqlite3
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Final, Protocol, cast

_RUNNER_MODULE_NAME: Final = "locontext.store._migrations_runner"


class _MigrationRunner(Protocol):
    def apply_migrations(self, connection: sqlite3.Connection) -> None: ...


def _load_runner_module() -> ModuleType:
    existing_module = sys.modules.get(_RUNNER_MODULE_NAME)
    if existing_module is not None:
        return existing_module
    runner_path = Path(__file__).resolve().parent.parent / "migrations.py"
    spec = spec_from_file_location(_RUNNER_MODULE_NAME, runner_path)
    if spec is None or spec.loader is None:
        msg = f"unable to load migration runner from {runner_path}"
        raise ImportError(msg)
    module = module_from_spec(spec)
    sys.modules[_RUNNER_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def apply_migrations(connection: sqlite3.Connection) -> None:
    runner = cast(_MigrationRunner, cast(object, _load_runner_module()))
    runner.apply_migrations(connection)


__all__ = ["apply_migrations"]
