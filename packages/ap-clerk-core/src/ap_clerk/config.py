from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ap_clerk.errors import APClerkError
from ap_clerk.matching import DEFAULT_MATCH_MARGIN, DEFAULT_MATCH_THRESHOLD
from ap_clerk.vlm import DEFAULT_TIMEOUT_SECONDS

_ALLOWED_TOP_LEVEL = frozenset({"masters", "vlm", "matching"})
_ALLOWED_MASTERS = frozenset({"vendors", "purchase_orders"})
_ALLOWED_VLM = frozenset({"api_key", "base_url", "model", "timeout_seconds"})
_ALLOWED_MATCHING = frozenset(
    {"threshold", "margin", "vendor_threshold", "po_threshold"}
)


class ConfigError(APClerkError):
    """Invalid or missing configuration."""


@dataclass(frozen=True)
class Config:
    vendors_path: Path
    purchase_orders_path: Path
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    match_threshold: float
    match_margin: float
    vendor_threshold: float
    po_threshold: float
    config_path: Path


def load_config(path: Path | None = None) -> Config:
    if path is None:
        candidate = Path.cwd() / "config.toml"
        if not candidate.is_file():
            raise ConfigError(
                "config.toml not found; copy config.example.toml to config.toml and edit"
            )
        path = candidate
    else:
        if not path.is_file():
            raise ConfigError(f"config file not found: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"could not read config file: {path}") from exc

    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in config file: {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a table: {path}")

    _reject_unknown_keys(data, _ALLOWED_TOP_LEVEL, "config")

    masters = _require_table(data, "masters")
    _reject_unknown_keys(masters, _ALLOWED_MASTERS, "masters")
    vendors_raw = _require_str(masters, "vendors", "masters.vendors")
    pos_raw = _require_str(masters, "purchase_orders", "masters.purchase_orders")

    vlm = _require_table(data, "vlm")
    _reject_unknown_keys(vlm, _ALLOWED_VLM, "vlm")
    api_key = _require_str(vlm, "api_key", "vlm.api_key")
    if not api_key.strip():
        raise ConfigError("vlm.api_key must not be empty")
    base_url = _require_str(vlm, "base_url", "vlm.base_url")
    model = _require_str(vlm, "model", "vlm.model")
    timeout_seconds = _optional_float(
        vlm, "timeout_seconds", "vlm.timeout_seconds", DEFAULT_TIMEOUT_SECONDS
    )

    matching = data.get("matching", {})
    if matching is None:
        matching = {}
    if not isinstance(matching, dict):
        raise ConfigError("matching must be a table")
    _reject_unknown_keys(matching, _ALLOWED_MATCHING, "matching")

    match_threshold = _optional_float(
        matching, "threshold", "matching.threshold", DEFAULT_MATCH_THRESHOLD
    )
    match_margin = _optional_float(
        matching, "margin", "matching.margin", DEFAULT_MATCH_MARGIN
    )
    vendor_threshold = _optional_float(
        matching, "vendor_threshold", "matching.vendor_threshold", match_threshold
    )
    po_threshold = _optional_float(
        matching, "po_threshold", "matching.po_threshold", match_threshold
    )

    base_dir = path.parent.resolve()
    vendors_path = _resolve_path(vendors_raw, base_dir)
    purchase_orders_path = _resolve_path(pos_raw, base_dir)

    return Config(
        vendors_path=vendors_path,
        purchase_orders_path=purchase_orders_path,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        match_threshold=match_threshold,
        match_margin=match_margin,
        vendor_threshold=vendor_threshold,
        po_threshold=po_threshold,
        config_path=path.resolve(),
    )


def _reject_unknown_keys(
    table: dict[str, Any], allowed: frozenset[str], where: str
) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"unknown key(s) in {where}: {', '.join(unknown)}")


def _require_table(data: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in data:
        raise ConfigError(f"missing required table: {key}")
    value = data[key]
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a table")
    return value


def _require_str(table: dict[str, Any], key: str, path: str) -> str:
    if key not in table:
        raise ConfigError(f"missing required key: {path}")
    value = table[key]
    if not isinstance(value, str):
        raise ConfigError(f"{path} must be a string")
    return value


def _optional_float(
    table: dict[str, Any], key: str, path: str, default: float
) -> float:
    if key not in table:
        return default
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{path} must be a number")
    return float(value)


def _resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()
