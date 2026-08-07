from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from ap_clerk.errors import APClerkError
from ap_clerk.vlm import FakeInvoiceExtractor
from ap_clerk_cli.cli import main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
VENDORS_PATH = FIXTURES / "vendors.json"
POS_PATH = FIXTURES / "purchase-orders.json"
INVOICE_PDF = FIXTURES / "invoices" / "V001_P0001001.pdf"


def _good_extraction(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "vendor_name_raw": "Summit Plumbing Supply",
        "purchase_order_raw": "P0001001",
        "subtotal": 1983.75,
        "tax_total": 0.0,
        "total_amount": 1983.75,
        "invoice_number": "INV-1",
    }
    base.update(overrides)
    return base


def _write_config(path: Path) -> Path:
    path.write_text(
        dedent(
            f"""
            [masters]
            vendors = "{VENDORS_PATH.as_posix()}"
            purchase_orders = "{POS_PATH.as_posix()}"

            [vlm]
            api_key = "test-key"
            base_url = "http://127.0.0.1:8000/v1"
            model = "test-model"
            """
        ).lstrip(),
        encoding="utf-8",
    )
    return path


def _patch_fake_extractor(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object] | None = None,
    *,
    error: BaseException | None = None,
) -> FakeInvoiceExtractor:
    fake = FakeInvoiceExtractor(
        payload if payload is not None else _good_extraction(),
        error=error,
    )
    monkeypatch.setattr(
        "ap_clerk_cli.cli.VisionInvoiceExtractor",
        lambda **_kwargs: fake,
    )
    return fake


def test_cli_extract_success_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write_config(tmp_path / "config.toml")
    fake = _patch_fake_extractor(monkeypatch)
    code = main(["--config", str(config), "extract", str(INVOICE_PDF)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "AUTO_APPROVED"
    assert payload["payload"]["vendor_match"]["vendor_id"] == "V001"
    assert payload["payload"]["po_match"]["purchase_order_id"] == "P0001001"
    assert len(fake.calls) == 1


def test_cli_extract_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write_config(tmp_path / "config.toml")
    _patch_fake_extractor(monkeypatch)
    output_path = tmp_path / "out.json"
    code = main(
        [
            "--config",
            str(config),
            "extract",
            str(INVOICE_PDF),
            "-o",
            str(output_path),
        ]
    )
    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "AUTO_APPROVED"


def test_cli_rejected_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_config(tmp_path / "config.toml")
    _patch_fake_extractor(monkeypatch, {"subtotal": "nope", "total_amount": 1})
    code = main(["--config", str(config), "extract", str(INVOICE_PDF)])
    assert code == 1


def test_cli_ap_clerk_error_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write_config(tmp_path / "config.toml")
    _patch_fake_extractor(monkeypatch, error=APClerkError("boom"))
    code = main(["--config", str(config), "extract", str(INVOICE_PDF)])
    assert code == 1
    assert "boom" in capsys.readouterr().err


def test_cli_missing_invoice_file_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write_config(tmp_path / "config.toml")
    _patch_fake_extractor(monkeypatch)
    missing = tmp_path / "missing.pdf"
    code = main(["--config", str(config), "extract", str(missing)])
    assert code == 1


def test_cli_missing_config_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["extract", str(INVOICE_PDF)])
    assert code == 1
    assert "config.toml not found" in capsys.readouterr().err


def test_cli_missing_config_path_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.toml"
    code = main(["--config", str(missing), "extract", str(INVOICE_PDF)])
    assert code == 1
    assert "config file not found" in capsys.readouterr().err


def test_cli_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "extract" in out
    assert "--config" in out


def test_cli_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    assert code == 0
    assert "extract" in capsys.readouterr().out


def test_cli_unknown_old_flags_rejected(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "config.toml")
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--config",
                str(config),
                "extract",
                str(INVOICE_PDF),
                "--vendors",
                str(VENDORS_PATH),
            ]
        )
    assert exc_info.value.code == 2


def test_cli_old_api_key_flag_rejected(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "config.toml")
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--config",
                str(config),
                "extract",
                str(INVOICE_PDF),
                "--api-key",
                "x",
            ]
        )
    assert exc_info.value.code == 2


def test_cli_verbose_flag_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write_config(tmp_path / "config.toml")
    _patch_fake_extractor(monkeypatch)
    code = main(
        [
            "-v",
            "--config",
            str(config),
            "extract",
            str(INVOICE_PDF),
            "-o",
            str(tmp_path / "o.json"),
        ]
    )
    assert code == 0
