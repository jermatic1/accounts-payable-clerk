from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ap_clerk.errors import APClerkError

RENDER_DPI = 150

SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
SUPPORTED_PDF_SUFFIXES = frozenset({".pdf"})
SUPPORTED_SUFFIXES = SUPPORTED_IMAGE_SUFFIXES | SUPPORTED_PDF_SUFFIXES

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "image/png",
}


@dataclass(frozen=True)
class LoadedInvoice:
    image: bytes
    mime: str
    page_count: int
    source_path: Path


def load_invoice(path: Path) -> LoadedInvoice:
    if not path.exists():
        raise APClerkError(f"file not found: {path}")
    if not path.is_file():
        raise APClerkError(f"not a file: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise APClerkError(
            f"unsupported invoice format {suffix!r}; "
            f"expected one of {sorted(SUPPORTED_SUFFIXES)}"
        )

    mime = _MIME_BY_SUFFIX[suffix]

    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise APClerkError(f"could not read image: {exc}") from exc
        if not data:
            raise APClerkError(f"empty image file: {path}")
        return LoadedInvoice(
            image=data,
            mime=mime,
            page_count=1,
            source_path=path,
        )

    image, page_count = _render_pdf_first_page(path)
    return LoadedInvoice(
        image=image,
        mime=mime,
        page_count=page_count,
        source_path=path,
    )


def _render_pdf_first_page(path: Path) -> tuple[bytes, int]:
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:
        raise APClerkError("pymupdf is required to render PDF invoices") from exc

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise APClerkError(f"unreadable PDF: {path}: {exc}") from exc

    try:
        page_count = doc.page_count
        if page_count < 1:
            raise APClerkError(f"PDF has no pages: {path}")
        page = doc.load_page(0)
        zoom = RENDER_DPI / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
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
