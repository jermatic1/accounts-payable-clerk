from __future__ import annotations


class APClerkError(Exception):
    """Base for failures whose message is safe to show an operator.

    Wrap external causes with `raise ... from exc`; never wrap unexpected
    bugs — let those traceback.
    """


class ExtractionError(APClerkError):
    """Vision/model extraction failure."""
