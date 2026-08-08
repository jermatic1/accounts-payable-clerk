from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Protocol, runtime_checkable

from openai import OpenAI
from pydantic import ValidationError

from ap_clerk.errors import ExtractionError
from ap_clerk.extraction import InvoiceExtraction

logger = logging.getLogger(__name__)

_RETRY_DELAYS_SECONDS = (0.5, 1.0)
DEFAULT_TIMEOUT_SECONDS = 120.0

EXTRACTION_INSTRUCTIONS = """\
Extract accounts-payable invoice fields from the provided page image(s).

Return a single JSON object matching this schema (omit unknown values as null or empty lists):
- vendor_name_raw: primary vendor/supplier name as printed
- vendor_name_variants: other vendor name strings visible on the page only
- vendor_address_raw: vendor address block as printed
- invoice_number, invoice_date, due_date, terms, currency: as printed (dates as strings)
- purchase_order_raw: primary PO / purchase order number as printed
- purchase_order_variants: other PO number strings visible on the page only
- line_items: list of {description, quantity, unit_price, amount}
- subtotal, tax_total, total_amount: numeric amounts when present
- unmapped_fields: list of {label, value} for every other labeled value printed on
  the page that fits none of the fields above (e.g. FEIN, account numbers, salesperson,
  ship-to, comments, tax-status notes)

Rules:
- Capture as much of the page as possible: anything labeled that does not fit a field
  above goes into unmapped_fields verbatim; do not silently drop printed information.
- Transcribe text as printed (OCR noise is acceptable). Do not correct or invent values.
- vendor_name_variants and purchase_order_variants must be verbatim strings that appear
  somewhere on the page (letterhead, remit-to, footer, stamps). Never invent abbreviations,
  expansions, or guessed alternate forms.
- Do not look up or assign vendor_id, internal ids, or master-data codes.
- Do not choose a vendor or PO from any external list; extract only what is on the page.
- Numbers should be plain JSON numbers without currency symbols.
"""


@runtime_checkable
class InvoiceExtractor(Protocol):
    def extract_invoice(self, image: bytes) -> dict[str, Any]: ...


class FakeInvoiceExtractor:
    def __init__(
        self,
        result: dict[str, Any] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self._result = dict(result) if result is not None else {}
        self._error = error
        self.calls: list[bytes] = []

    def extract_invoice(self, image: bytes) -> dict[str, Any]:
        self.calls.append(image)
        if self._error is not None:
            raise self._error
        return dict(self._result)


def build_extraction_messages(
    image: bytes,
    *,
    reinforce_json: bool = False,
) -> list[dict[str, Any]]:
    if not image:
        raise ValueError("extract_invoice requires a non-empty image")

    content: list[dict[str, Any]] = [
        {"type": "text", "text": EXTRACTION_INSTRUCTIONS},
    ]
    if reinforce_json:
        content.append(
            {
                "type": "text",
                "text": (
                    "Previous output was invalid. Reply with a single JSON object only. "
                    "No markdown fences, no commentary."
                ),
            }
        )
    b64 = base64.standard_b64encode(image).decode("ascii")
    content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        }
    )
    return [
        {
            "role": "system",
            "content": (
                "You are an invoice OCR extraction assistant. "
                "Output valid JSON only when asked for structured extraction."
            ),
        },
        {"role": "user", "content": content},
    ]


def parse_extraction_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ExtractionError("VLM response JSON must be an object")
    extraction = InvoiceExtraction.model_validate(data)
    return extraction.model_dump(mode="python")


class VisionInvoiceExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
            )

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def extract_invoice(self, image: bytes) -> dict[str, Any]:
        started = time.perf_counter()
        messages = build_extraction_messages(image)
        content = self._complete(messages)
        try:
            result = parse_extraction_response(content)
        except (json.JSONDecodeError, ValidationError, ExtractionError):
            logger.info(
                "vlm parse failed; retrying once with JSON-only reinforcement model=%s",
                self._model,
            )
            retry_messages = build_extraction_messages(image, reinforce_json=True)
            content = self._complete(retry_messages)
            try:
                result = parse_extraction_response(content)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ExtractionError(
                    "failed to parse VLM response as InvoiceExtraction"
                ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "vlm extract model=%s latency_ms=%.0f",
            self._model,
            elapsed_ms,
        )
        return result

    def _complete(self, messages: list[dict[str, Any]]) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        try:
            return self._create_with_retry(
                **kwargs, response_format={"type": "json_object"}
            )
        except Exception as exc:
            if not _is_response_format_error(exc):
                raise
            logger.info("vlm json_object response_format unsupported; plain completion")
            return self._create_with_retry(**kwargs)

    def _create_with_retry(self, **kwargs: Any) -> str:
        last_exc: BaseException | None = None
        attempts = len(_RETRY_DELAYS_SECONDS) + 1
        for attempt in range(attempts):
            try:
                response = self._client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                content = choice.message.content
                if not content:
                    raise ExtractionError("VLM returned empty content")
                return content
            except ExtractionError:
                raise
            except Exception as exc:
                if not _is_retryable(exc) or attempt >= attempts - 1:
                    raise
                last_exc = exc
                delay = _RETRY_DELAYS_SECONDS[attempt]
                logger.info(
                    "vlm transient error; retrying in %.1fs model=%s",
                    delay,
                    self._model,
                )
                time.sleep(delay)
        assert last_exc is not None
        raise last_exc


def _is_retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and (status == 429 or status >= 500):
        return True
    name = type(exc).__name__
    return name in {
        "RateLimitError",
        "APIConnectionError",
        "InternalServerError",
        "APITimeoutError",
    }


def _is_response_format_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status not in (400, 404, 422):
        name = type(exc).__name__
        if name not in {"BadRequestError", "NotFoundError", "UnprocessableEntityError"}:
            return False
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "response_format",
            "json_schema",
            "json_object",
            "structured output",
            "not supported",
        )
    )
