from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]

from ap_clerk.errors import APClerkError

RENDER_DPI = 150


@dataclass(frozen=True)
class LoadedInvoice:
    image: bytes
    page_count: int
    source_path: Path


def load_invoice(path: Path) -> LoadedInvoice:
    if not path.exists():
        raise APClerkError(f"file not found: {path}")
    if not path.is_file():
        raise APClerkError(f"not a file: {path}")
    if path.suffix.lower() != ".pdf":
        raise APClerkError(f"unsupported invoice format {path.suffix!r}; expected .pdf")

    image, page_count = _render_pdf_first_page(path)
    return LoadedInvoice(image=image, page_count=page_count, source_path=path)


def _render_pdf_first_page(path: Path) -> tuple[bytes, int]:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise APClerkError(f"unreadable PDF: {path}: {exc}") from exc

    try:
        page_count = doc.page_count
        if page_count < 1:
            raise APClerkError(f"PDF has no pages: {path}")
        page = doc.load_page(0)
        zoom = RENDER_DPI / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        png_bytes = pix.tobytes("png")
    except APClerkError:
        raise
    except Exception as exc:
        raise APClerkError(f"failed to render PDF: {path}: {exc}") from exc
    finally:
        doc.close()

    if not png_bytes:
        raise APClerkError(f"PDF render produced empty image: {path}")
    return png_bytes, page_count
