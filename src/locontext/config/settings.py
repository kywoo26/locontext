from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(slots=True)
class Settings:
    project_root: Path
    data_dir: Path


def load_settings(project_root: Path) -> Settings:
    config_path = project_root / "locontext.toml"
    if not config_path.exists():
        return Settings(project_root=project_root, data_dir=project_root / ".locontext")

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    data_dir_value = cast(object, data.get("data_dir", ".locontext"))
    if not isinstance(data_dir_value, str):
        msg = "locontext.toml data_dir must be a string"
        raise TypeError(msg)
    data_dir = Path(data_dir_value)
    if not data_dir.is_absolute():
        data_dir = project_root / data_dir
    return Settings(project_root=project_root, data_dir=data_dir)
