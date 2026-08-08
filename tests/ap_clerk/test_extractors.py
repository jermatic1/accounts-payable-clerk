from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ap_clerk.documents import LoadedInvoice
from ap_clerk.errors import ExtractionError
from ap_clerk.extraction import InvoiceExtraction
from ap_clerk.extractors import (
    EXTRACTION_INSTRUCTIONS,
    FakeInvoiceExtractor,
    VisionInvoiceExtractor,
    build_extraction_messages,
    parse_extraction_response,
)
from ap_clerk.pipeline import (
    STATUS_AUTO_APPROVED,
    STATUS_HUMAN_REVIEW,
    process_invoice,
)
from ap_clerk.purchase_orders import load_purchase_orders
from ap_clerk.vendors import load_vendors

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
VENDORS_PATH = FIXTURES / "vendors.json"
POS_PATH = FIXTURES / "purchase-orders.json"


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


def _loaded(
    image: bytes = b"fake-png-bytes", source: str = "page.pdf"
) -> LoadedInvoice:
    return LoadedInvoice(
        image=image,
        page_count=1,
        source_path=Path(source),
    )


def test_fake_extractor_process_invoice_auto_approve() -> None:
    vendors = load_vendors(VENDORS_PATH)
    pos = load_purchase_orders(POS_PATH)
    extractor = FakeInvoiceExtractor(_good_extraction())
    result = process_invoice(
        _loaded(),
        extractor=extractor,
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_AUTO_APPROVED
    assert result.source_file == "page.pdf"
    assert extractor.calls == [b"fake-png-bytes"]
    assert isinstance(result.payload.extraction, InvoiceExtraction)


def test_fake_extractor_process_invoice_human_review() -> None:
    vendors = load_vendors(VENDORS_PATH)
    pos = load_purchase_orders(POS_PATH)
    extractor = FakeInvoiceExtractor(
        _good_extraction(purchase_order_raw=None, purchase_order_variants=[])
    )
    result = process_invoice(
        _loaded(b"img"),
        extractor=extractor,
        vendors=vendors,
        purchase_orders=pos,
    )
    assert result.status == STATUS_HUMAN_REVIEW


def test_fake_extractor_propagates_error() -> None:
    vendors = load_vendors(VENDORS_PATH)
    pos = load_purchase_orders(POS_PATH)
    extractor = FakeInvoiceExtractor(error=ExtractionError("boom"))
    with pytest.raises(ExtractionError, match="boom"):
        process_invoice(
            _loaded(b"img"),
            extractor=extractor,
            vendors=vendors,
            purchase_orders=pos,
        )


def test_extraction_instructions_require_verbatim_variants() -> None:
    lower = EXTRACTION_INSTRUCTIONS.lower()
    assert "verbatim" in lower
    assert "never invent" in lower
    assert "vendor_id" in lower
    assert "master" in lower or "external list" in lower


def test_build_extraction_messages_embeds_data_url() -> None:
    messages = build_extraction_messages(b"\x89PNG")
    assert messages[0]["role"] == "system"
    user = messages[1]
    assert user["role"] == "user"
    content = user["content"]
    assert isinstance(content, list)
    image_parts = [p for p in content if p.get("type") == "image_url"]
    assert len(image_parts) == 1
    url = image_parts[0]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")


def test_build_extraction_messages_requires_image() -> None:
    with pytest.raises(ValueError, match="non-empty image"):
        build_extraction_messages(b"")


def test_parse_extraction_response_plain_and_fenced() -> None:
    payload = _good_extraction()
    plain = parse_extraction_response(json.dumps(payload))
    assert plain["vendor_name_raw"] == "Summit Plumbing Supply"
    fenced = parse_extraction_response("```json\n" + json.dumps(payload) + "\n```")
    assert fenced["total_amount"] == 1983.75


def test_parse_extraction_response_invalid() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_extraction_response("not-json")


class _FakeChoiceMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeChoiceMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self.contents = list(contents)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self.contents:
            raise AssertionError("no more fake responses")
        return _FakeResponse(self.contents.pop(0))


class _FakeChat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _FakeCompletions(contents)


class _FakeOpenAI:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _FakeChat(contents)


def test_vision_extractor_parses_with_injected_client() -> None:
    payload = _good_extraction()
    fake = _FakeOpenAI([json.dumps(payload)])
    client = VisionInvoiceExtractor(
        api_key="test-key-not-for-logging",
        base_url="http://example.test/v1",
        model="test-model",
        client=fake,
    )
    result = client.extract_invoice(b"img-bytes")
    assert result["vendor_name_raw"] == "Summit Plumbing Supply"
    assert result["purchase_order_raw"] == "P0001001"
    assert fake.chat.completions.calls
    call = fake.chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["response_format"] == {"type": "json_object"}


def test_vision_extractor_retries_on_parse_failure() -> None:
    payload = _good_extraction()
    fake = _FakeOpenAI(["not-json{{{", json.dumps(payload)])
    client = VisionInvoiceExtractor(
        api_key="k",
        base_url="http://example.test/v1",
        model="m",
        client=fake,
    )
    result = client.extract_invoice(b"x")
    assert result["total_amount"] == 1983.75
    assert len(fake.chat.completions.calls) == 2
