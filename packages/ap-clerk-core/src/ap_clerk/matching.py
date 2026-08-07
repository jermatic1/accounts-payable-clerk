from __future__ import annotations

import re
from collections.abc import Callable, Sequence

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


def _vendor_queries(extraction: InvoiceExtraction, normalizer: Normalizer) -> list[str]:
    return _unique_queries(
        [extraction.vendor_name_raw, *extraction.vendor_name_variants],
        normalizer,
    )


def _po_queries(extraction: InvoiceExtraction, normalizer: Normalizer) -> list[str]:
    return _unique_queries(
        [extraction.purchase_order_raw, *extraction.purchase_order_variants],
        normalizer,
    )


def _best_scores_by_key(
    queries: Sequence[str],
    labels: Sequence[str],
    keys: Sequence[str],
) -> dict[str, float]:
    best: dict[str, float] = {}
    if not queries or not labels:
        return best

    for query in queries:
        for label, key in zip(labels, keys, strict=True):
            if query == label:
                prev = best.get(key, 0.0)
                if prev < 100.0:
                    best[key] = 100.0

        extracted = process.extract(
            query,
            labels,
            scorer=fuzz.QRatio,
            limit=len(labels),
        )
        for _match_label, score, idx in extracted:
            key = keys[idx]
            score_f = float(score)
            prev = best.get(key, 0.0)
            if score_f > prev:
                best[key] = score_f
    return best


def _rank_scores(scores: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _margin(ranked: Sequence[tuple[str, float]]) -> float | None:
    if not ranked:
        return None
    if len(ranked) == 1:
        return None
    return float(ranked[0][1] - ranked[1][1])


def _is_confident(
    score: float | None,
    margin: float | None,
    *,
    threshold: float,
    match_margin: float,
) -> bool:
    if score is None or score < threshold:
        return False
    if margin is None:
        return True
    return margin >= match_margin


def match_vendor(
    extraction: InvoiceExtraction,
    vendors: Sequence[Vendor],
    *,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    margin: float = DEFAULT_MATCH_MARGIN,
    top_n: int = 3,
    normalizer: Normalizer = normalize,
) -> VendorMatch:
    queries = _vendor_queries(extraction, normalizer)
    if not queries or not vendors:
        return VendorMatch()

    labels = [normalizer(v.vendor_name) for v in vendors]
    keys = [v.vendor_id for v in vendors]
    by_id = {v.vendor_id: v for v in vendors}

    scores = _best_scores_by_key(queries, labels, keys)
    ranked = _rank_scores(scores)
    if not ranked:
        return VendorMatch()

    best_id, best_score = ranked[0]
    best = by_id[best_id]
    gap = _margin(ranked)
    candidates = [
        MatchCandidate(
            id=vid,
            name=by_id[vid].vendor_name,
            score=score,
        )
        for vid, score in ranked[:top_n]
    ]
    return VendorMatch(
        vendor_id=best.vendor_id,
        vendor_name=best.vendor_name,
        score=best_score,
        margin=gap,
        confident=_is_confident(
            best_score, gap, threshold=threshold, match_margin=margin
        ),
        candidates=candidates,
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
    queries = _po_queries(extraction, normalizer)
    if not queries:
        return PurchaseOrderMatch()

    if vendor_id is not None:
        pool = [po for po in purchase_orders if po.vendor_id == vendor_id]
    else:
        pool = list(purchase_orders)

    if not pool:
        return PurchaseOrderMatch()

    labels = [normalizer(po.purchase_order_id) for po in pool]
    keys = [po.purchase_order_id for po in pool]
    by_id = {po.purchase_order_id: po for po in pool}

    scores = _best_scores_by_key(queries, labels, keys)
    ranked = _rank_scores(scores)
    if not ranked:
        return PurchaseOrderMatch()

    best_id, best_score = ranked[0]
    best = by_id[best_id]
    gap = _margin(ranked)
    candidates = [
        MatchCandidate(
            id=pid,
            name=pid,
            score=score,
        )
        for pid, score in ranked[:top_n]
    ]
    return PurchaseOrderMatch(
        purchase_order_id=best.purchase_order_id,
        vendor_id=best.vendor_id,
        score=best_score,
        margin=gap,
        confident=_is_confident(
            best_score, gap, threshold=threshold, match_margin=margin
        ),
        candidates=candidates,
    )
