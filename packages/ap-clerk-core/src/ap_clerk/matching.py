from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import NamedTuple

from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from ap_clerk.extraction import InvoiceExtraction
from ap_clerk.purchase_orders import PurchaseOrder
from ap_clerk.vendors import Vendor

DEFAULT_MATCH_THRESHOLD = 85.0
DEFAULT_MATCH_MARGIN = 5.0

Normalizer = Callable[[str], str]

# After casefold: map digit/pipe OCR confusables onto letter forms.
# Do not remap i/l globally — that corrupts ordinary words.
# 0→o (with o unchanged), 1→i (with i unchanged), |→i.
_OCR_CONFUSABLES = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "|": "i",
    }
)


class MatchCandidate(BaseModel):
    id: str | None = None
    name: str | None = None
    score: float | None = None


class VendorMatch(BaseModel):
    vendor_id: str | None = None
    vendor_name: str | None = None
    score: float | None = None
    margin: float | None = None
    confident: bool = False
    candidates: list[MatchCandidate] = Field(default_factory=list)


class PurchaseOrderMatch(BaseModel):
    purchase_order_id: str | None = None
    vendor_id: str | None = None
    score: float | None = None
    margin: float | None = None
    confident: bool = False
    candidates: list[MatchCandidate] = Field(default_factory=list)


def normalize(text: str) -> str:
    s = text.strip().casefold().translate(_OCR_CONFUSABLES)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


class _Ranked(NamedTuple):
    key: str
    score: float
    gap: float | None
    candidates: list[tuple[str, float]]
    confident: bool


def _match(
    queries: Sequence[str],
    labels: Sequence[str],
    keys: Sequence[str],
    *,
    threshold: float,
    margin: float,
    top_n: int,
) -> _Ranked | None:
    """Best fuzzy match of any query against labels; keys[i] identifies labels[i].

    Confident means the best score reached the threshold and, when more than one
    key scored, the top-1 vs top-2 gap reached the margin.
    """
    best: dict[str, float] = {}
    for query in queries:
        matches = process.extract(query, labels, scorer=fuzz.QRatio, limit=len(labels))
        for _label, score, idx in matches:
            key = keys[idx]
            if float(score) > best.get(key, 0.0):
                best[key] = float(score)
    if not best:
        return None

    ranked = sorted(best.items(), key=lambda item: (-item[1], item[0]))
    top_key, top_score = ranked[0]
    gap = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else None
    confident = top_score >= threshold and (gap is None or gap >= margin)
    return _Ranked(top_key, top_score, gap, ranked[:top_n], confident)


def _unique_queries(
    raw_values: Sequence[str | None], normalizer: Normalizer
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in raw_values:
        if value is None:
            continue
        normalized = normalizer(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def match_vendor(
    extraction: InvoiceExtraction,
    vendors: Sequence[Vendor],
    *,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    margin: float = DEFAULT_MATCH_MARGIN,
    top_n: int = 3,
    normalizer: Normalizer = normalize,
) -> VendorMatch:
    queries = _unique_queries(
        [extraction.vendor_name_raw, *extraction.vendor_name_variants], normalizer
    )
    if not queries or not vendors:
        return VendorMatch()

    by_id = {v.vendor_id: v for v in vendors}
    ranked = _match(
        queries,
        labels=[normalizer(v.vendor_name) for v in vendors],
        keys=[v.vendor_id for v in vendors],
        threshold=threshold,
        margin=margin,
        top_n=top_n,
    )
    if ranked is None:
        return VendorMatch()

    best = by_id[ranked.key]
    return VendorMatch(
        vendor_id=best.vendor_id,
        vendor_name=best.vendor_name,
        score=ranked.score,
        margin=ranked.gap,
        confident=ranked.confident,
        candidates=[
            MatchCandidate(id=key, name=by_id[key].vendor_name, score=score)
            for key, score in ranked.candidates
        ],
    )


def match_purchase_order(
    extraction: InvoiceExtraction,
    purchase_orders: Sequence[PurchaseOrder],
    *,
    vendor_id: str | None = None,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    margin: float = DEFAULT_MATCH_MARGIN,
    top_n: int = 3,
    normalizer: Normalizer = normalize,
) -> PurchaseOrderMatch:
    queries = _unique_queries(
        [extraction.purchase_order_raw, *extraction.purchase_order_variants], normalizer
    )
    if not queries:
        return PurchaseOrderMatch()

    if vendor_id is not None:
        pool = [po for po in purchase_orders if po.vendor_id == vendor_id]
    else:
        pool = list(purchase_orders)
    if not pool:
        return PurchaseOrderMatch()

    by_id = {po.purchase_order_id: po for po in pool}
    ranked = _match(
        queries,
        labels=[normalizer(po.purchase_order_id) for po in pool],
        keys=[po.purchase_order_id for po in pool],
        threshold=threshold,
        margin=margin,
        top_n=top_n,
    )
    if ranked is None:
        return PurchaseOrderMatch()

    best = by_id[ranked.key]
    return PurchaseOrderMatch(
        purchase_order_id=best.purchase_order_id,
        vendor_id=best.vendor_id,
        score=ranked.score,
        margin=ranked.gap,
        confident=ranked.confident,
        candidates=[
            MatchCandidate(id=key, name=key, score=score)
            for key, score in ranked.candidates
        ],
    )
