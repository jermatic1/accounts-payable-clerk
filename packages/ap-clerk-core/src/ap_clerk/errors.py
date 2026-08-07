from __future__ import annotations


class APClerkError(Exception):
    """Operator-visible library failure with a clear message."""


class ExtractionError(APClerkError):
    """Vision/model extraction failure."""
