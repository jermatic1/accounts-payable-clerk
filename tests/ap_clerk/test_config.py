from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ap_clerk.config import ConfigError, load_config


def _write_config(path: Path, body: str) -> Path:
    path.write_text(dedent(body).lstrip(), encoding="utf-8")
    return path


def test_load_valid_config_resolves_relative_paths(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "data/vendors.json"
        purchase_orders = "data/pos.json"

        [vlm]
        api_key = "secret-key"
        base_url = "http://127.0.0.1:8000/v1"
        model = "vision-model"

        [matching]
        threshold = 90.0
        margin = 3.0
        vendor_threshold = 88.0
        po_threshold = 92.0
        """,
    )
    config = load_config(cfg_path)
    assert config.api_key == "secret-key"
    assert config.base_url == "http://127.0.0.1:8000/v1"
    assert config.model == "vision-model"
    assert config.timeout_seconds == 120.0
    assert config.match_threshold == 90.0
    assert config.match_margin == 3.0
    assert config.vendor_threshold == 88.0
    assert config.po_threshold == 92.0
    assert config.vendors_path == (tmp_path / "data" / "vendors.json").resolve()
    assert config.purchase_orders_path == (tmp_path / "data" / "pos.json").resolve()
    assert config.config_path == cfg_path.resolve()


def test_matching_defaults_and_threshold_fallbacks(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "v.json"
        purchase_orders = "p.json"

        [vlm]
        api_key = "k"
        base_url = "http://example/v1"
        model = "m"
        """,
    )
    config = load_config(cfg_path)
    assert config.match_threshold == 85.0
    assert config.match_margin == 5.0
    assert config.vendor_threshold == 85.0
    assert config.po_threshold == 85.0


def test_missing_config_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="config.toml not found"):
        load_config()


def test_explicit_path_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(tmp_path / "missing.toml")


def test_missing_required_key(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "v.json"
        purchase_orders = "p.json"

        [vlm]
        api_key = "k"
        base_url = "http://example/v1"
        """,
    )
    with pytest.raises(ConfigError, match="vlm.model"):
        load_config(cfg_path)


def test_unknown_key(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "v.json"
        purchase_orders = "p.json"

        [vlm]
        api_key = "k"
        base_url = "http://example/v1"
        model = "m"
        extra = true
        """,
    )
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(cfg_path)


def test_empty_api_key(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "v.json"
        purchase_orders = "p.json"

        [vlm]
        api_key = ""
        base_url = "http://example/v1"
        model = "m"
        """,
    )
    with pytest.raises(ConfigError, match="api_key"):
        load_config(cfg_path)


def test_bad_type(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "v.json"
        purchase_orders = "p.json"

        [vlm]
        api_key = "k"
        base_url = "http://example/v1"
        model = "m"

        [matching]
        threshold = "high"
        """,
    )
    with pytest.raises(ConfigError, match="matching.threshold"):
        load_config(cfg_path)


def test_discover_cwd_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(
        tmp_path / "config.toml",
        """
        [masters]
        vendors = "v.json"
        purchase_orders = "p.json"

        [vlm]
        api_key = "from-cwd"
        base_url = "http://example/v1"
        model = "m"
        """,
    )
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.api_key == "from-cwd"
