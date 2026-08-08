"""Load and validate config.toml into a resolved Config."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ap_clerk.errors import APClerkError
from ap_clerk.extractors import DEFAULT_TIMEOUT_SECONDS
from ap_clerk.matching import DEFAULT_MATCH_MARGIN, DEFAULT_MATCH_THRESHOLD


class ConfigError(APClerkError):
    """Invalid or missing configuration."""


class _MastersSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendors: Path
    purchase_orders: Path


class _VlmSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=1)
    base_url: str
    model: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


class _MatchingSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float = DEFAULT_MATCH_THRESHOLD
    margin: float = DEFAULT_MATCH_MARGIN
    vendor_threshold: float | None = None
    po_threshold: float | None = None


class _ConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    masters: _MastersSection
    vlm: _VlmSection
    matching: _MatchingSection = _MatchingSection()


@dataclass(frozen=True)
class Config:
    """Fully resolved settings: paths absolute, thresholds defaulted, nothing optional."""

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
    """Load an explicit path, or ./config.toml when none is given.

    Relative paths inside the file resolve against the config file's own
    directory. There is no environment-variable fallback.
    """
    if path is None:
        path = Path.cwd() / "config.toml"
        if not path.is_file():
            raise ConfigError(
                "config.toml not found; copy config.example.toml to config.toml and edit"
            )
    elif not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"could not read config file: {path}") from exc
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in config file: {path}: {exc}") from exc

    try:
        parsed = _ConfigFile.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid config in {path}: {_format_errors(exc)}") from exc

    base_dir = path.parent.resolve()
    matching = parsed.matching
    return Config(
        vendors_path=_resolve(parsed.masters.vendors, base_dir),
        purchase_orders_path=_resolve(parsed.masters.purchase_orders, base_dir),
        api_key=parsed.vlm.api_key,
        base_url=parsed.vlm.base_url,
        model=parsed.vlm.model,
        timeout_seconds=parsed.vlm.timeout_seconds,
        match_threshold=matching.threshold,
        match_margin=matching.margin,
        vendor_threshold=(
            matching.vendor_threshold
            if matching.vendor_threshold is not None
            else matching.threshold
        ),
        po_threshold=(
            matching.po_threshold
            if matching.po_threshold is not None
            else matching.threshold
        ),
        config_path=path.resolve(),
    )


def _format_errors(exc: ValidationError) -> str:
    return "; ".join(
        ".".join(str(part) for part in err["loc"]) + ": " + err["msg"]
        for err in exc.errors()
    )


def _resolve(value: Path, base_dir: Path) -> Path:
    if value.is_absolute():
        return value
    return (base_dir / value).resolve()
