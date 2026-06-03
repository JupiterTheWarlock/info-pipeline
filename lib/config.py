"""Configuration loader."""

import os
from pathlib import Path
from typing import Any

import yaml


_config: dict[str, Any] | None = None
_project_root = Path(__file__).parent.parent


def load() -> dict[str, Any]:
    """Load config from config.yaml. Raises if not found."""
    global _config
    if _config is not None:
        return _config

    config_path = _project_root / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            "config.yaml not found. Copy config.yaml.example to config.yaml first."
        )

    with open(config_path, encoding="utf-8") as f:
        _config = yaml.safe_load(f)

    # Resolve relative paths against project root
    if "storage" in _config:
        db_path = _config["storage"].get("db_path", "./data/pipeline.db")
        _config["storage"]["db_path"] = str(
            (Path(db_path) if Path(db_path).is_absolute() else _project_root / db_path)
        )
        output_dir = _config["storage"].get("output_dir", "./output")
        _config["storage"]["output_dir"] = str(
            (Path(output_dir) if Path(output_dir).is_absolute() else _project_root / output_dir)
        )

    return _config


def get(keys: str, default: Any = None) -> Any:
    """Dot-notation accessor, e.g. get('llm.model')."""
    cfg = load()
    for key in keys.split("."):
        if isinstance(cfg, dict):
            cfg = cfg.get(key)
        else:
            return default
        if cfg is None:
            return default
    return cfg


def reload() -> dict[str, Any]:
    """Force reload config from disk."""
    global _config
    _config = None
    return load()
