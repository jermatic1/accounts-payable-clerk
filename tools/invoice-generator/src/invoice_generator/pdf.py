"""ReportLab invoice layout."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

Alignment = Literal[0, 1, 2, 4]

BILL_TO = {
    "name": "Northstar Manufacturing Inc.",
    "department": "Accounts Payable Department",
    "street": "4800 Industrial Parkway",
    "city_state_zip": "Columbus, OH 43228",
    "email": "ap@northstarmfg.example",
}

PAGE_WIDTH, _PAGE_HEIGHT = letter
MARGIN = 0.6 * inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
AMOUNT_WIDTH = 1.35 * inch
DESC_WIDTH = CONTENT_WIDTH - AMOUNT_WIDTH
TOTALS_LABEL_WIDTH = 1.35 * inch
META_WIDTH = 2.9 * inch
LINE_ROW_COUNT = 12
LINE_ROW_HEIGHT = 22

DARK = colors.HexColor("#4a4a4a")
LIGHT_GRAY = colors.HexColor("#f7f7f7")
ROW_ALT = colors.HexColor("#f0f0f0")
GRID = colors.HexColor("#888888")
ZERO_PAD = [
    ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ("TOPPADDING", (0, 0), (-1, -1), 0),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
]


def _style(
    name: str,
    *,
    font: str = "Helvetica",
    size: int = 10,
    leading: int | None = None,
    align: Alignment = TA_LEFT,
    text_color=colors.black,
    **kwargs,
) -> ParagraphStyle:
    base = getSampleStyleSheet()["Normal"]
    return ParagraphStyle(
        name,
        parent=base,
        fontName=font,
        fontSize=size,
        leading=leading if leading is not None else size + 2,
        alignment=align,
        textColor=text_color,
        spaceBefore=0,
        spaceAfter=0,
        **kwargs,
    )


def build_styles() -> dict[str, ParagraphStyle]:
    return {
        "company": _style("company", font="Helvetica-Bold", size=16, leading=18),
        "body": _style("body", size=10, leading=12),
        "right": _style("right", size=9, leading=11, align=TA_RIGHT),
        "right_bold": _style(
            "right_bold", font="Helvetica-Bold", size=11, leading=13, align=TA_RIGHT
        ),
        "title": _style(
            "title",
            font="Helvetica-Bold",
            size=26,
            leading=30,
            align=TA_RIGHT,
            text_color=colors.HexColor("#333333"),
        ),
        "section": _style(
            "section",
            font="Helvetica-Bold",
            size=10,
            leading=12,
            text_color=colors.white,
        ),
        "header": _style(
            "header",
            font="Helvetica-Bold",
            size=10,
            leading=12,
            align=TA_CENTER,
            text_color=colors.white,
        ),
        "line": _style("line", size=9, leading=11),
        "line_amount": _style("line_amount", size=9, leading=11, align=TA_RIGHT),
        "comment": _style("comment", size=9, leading=12),
    }


def _table(data, col_widths, style_commands, **kwargs) -> Table:
    table = Table(data, colWidths=col_widths, **kwargs)
    table.setStyle(TableStyle(style_commands))
    return table


def _section_box(title: str, body: str, width: float, styles: dict) -> Table:
    return _table(
        [
            [Paragraph(title, styles["section"])],
            [
                Paragraph(
                    body, styles["body"] if title != "COMMENTS" else styles["comment"]
                )
            ],
        ],
        [width],
        [
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                ROW_ALT if title == "BILL TO:" else colors.white,
            ),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (0, 0), 5),
            ("BOTTOMPADDING", (0, 0), (0, 0), 5),
            ("TOPPADDING", (0, 1), (0, 1), 8),
            ("BOTTOMPADDING", (0, 1), (0, 1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ],
    )


def _boxed_value_column_style(*, highlight_last: bool = False) -> list:
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 8 if highlight_last else 6),
        ("LEFTPADDING", (1, 0), (1, -1), 6),
        ("RIGHTPADDING", (1, 0), (1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5 if highlight_last else 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 if highlight_last else 3),
        ("BOX", (1, 0), (1, -1), 0.6, colors.black),
        ("LINEBELOW", (1, 0), (1, -2), 0.5, colors.black),
        ("BACKGROUND", (1, 0), (1, -1), LIGHT_GRAY),
    ]
    if highlight_last:
        commands.extend(
            [
                ("BACKGROUND", (1, 0), (1, -2), LIGHT_GRAY),
                ("BACKGROUND", (1, -1), (1, -1), colors.HexColor("#e8e8e8")),
                ("LINEABOVE", (0, -1), (-1, -1), 1.0, colors.black),
            ]
        )
    return commands


def format_money(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}"


def header_block(invoice: dict, styles: dict) -> Table:
    left_width = CONTENT_WIDTH - META_WIDTH
    details = "<br/>".join(
        [
            invoice.get("street") or "&nbsp;",
            invoice.get("city_state_zip") or "&nbsp;",
            f"Phone: {invoice['phone']}" if invoice.get("phone") else "Phone:",
            f"FEIN# {invoice['fein']}" if invoice.get("fein") else "FEIN#",
            f"Website: {invoice['website']}" if invoice.get("website") else "Website:",
        ]
    )
    vendor = _table(
        [
            [Paragraph(invoice.get("vendor_name") or "&nbsp;", styles["company"])],
            [Spacer(1, 6)],
            [Paragraph(details, styles["body"])],
        ],
        [left_width],
        ZERO_PAD,
    )

    meta_rows = [
        (label, invoice.get(key) or "&nbsp;")
        for label, key in [
            ("INVOICE #", "invoice_number"),
            ("INVOICE DATE", "invoice_date"),
            ("TERMS", "terms"),
            ("DUE DATE", "due_date"),
            ("PURCHASE ORDER#", "purchase_order"),
        ]
    ]
    meta = _table(
        [
            [Paragraph(label, styles["right"]), Paragraph(value, styles["right"])]
            for label, value in meta_rows
        ],
        [META_WIDTH - AMOUNT_WIDTH, AMOUNT_WIDTH],
        _boxed_value_column_style(),
    )
    right = _table(
        [
            [Paragraph("INVOICE", styles["title"])],
            [Spacer(1, 6)],
            [meta],
        ],
        [META_WIDTH],
        [("ALIGN", (0, 0), (-1, -1), "RIGHT"), *ZERO_PAD],
    )
    return _table(
        [[vendor, right]],
        [left_width, META_WIDTH],
        [("VALIGN", (0, 0), (-1, -1), "TOP"), *ZERO_PAD],
    )


def bill_to_block(styles: dict) -> Table:
    body = "<br/>".join(
        [
            BILL_TO["name"],
            BILL_TO["department"],
            BILL_TO["street"],
            BILL_TO["city_state_zip"],
            f"Email address: {BILL_TO['email']}",
        ]
    )
    return _section_box("BILL TO:", body, CONTENT_WIDTH, styles)


def line_items_table(invoice: dict, styles: dict) -> Table:
    lines = list(invoice.get("lines") or [])
    while len(lines) < LINE_ROW_COUNT:
        lines.append({"description": "", "amount": None})

    data = [
        [
            Paragraph("DESCRIPTION", styles["header"]),
            Paragraph("AMOUNT", styles["header"]),
        ]
    ]
    row_heights = [18]
    for line in lines:
        data.append(
            [
                Paragraph(line.get("description") or "&nbsp;", styles["line"]),
                Paragraph(format_money(line.get("amount")), styles["line_amount"]),
            ]
        )
        row_heights.append(LINE_ROW_HEIGHT)

    return _table(
        data,
        [DESC_WIDTH, AMOUNT_WIDTH],
        [
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ],
        rowHeights=row_heights,
        repeatRows=1,
    )


def comments_and_totals(invoice: dict, styles: dict) -> Table:
    comments_width = CONTENT_WIDTH - TOTALS_LABEL_WIDTH - AMOUNT_WIDTH - 0.15 * inch
    comments = _section_box(
        "COMMENTS",
        "Please include the invoice number on your check",
        comments_width,
        styles,
    )

    total = invoice.get("total")
    subtotal = format_money(invoice.get("subtotal"))
    total_text = format_money(total)
    rows = [
        ("SUBTOTAL", subtotal, styles["right"]),
        ("TAX EXEMPT", "0.000%" if total is not None else "", styles["right"]),
        ("OTHER", "-" if total is not None else "", styles["right"]),
        ("TOTAL", f"$  {total_text}" if total_text else "", styles["right_bold"]),
    ]
    totals = _table(
        [
            [
                Paragraph(label, style if label != "TOTAL" else styles["right_bold"]),
                Paragraph(value, style if label != "TOTAL" else styles["right_bold"]),
            ]
            for label, value, style in rows
        ],
        [TOTALS_LABEL_WIDTH, AMOUNT_WIDTH],
        _boxed_value_column_style(highlight_last=True),
    )

    gap = CONTENT_WIDTH - comments_width - TOTALS_LABEL_WIDTH - AMOUNT_WIDTH
    return _table(
        [[comments, "", totals]],
        [comments_width, gap, TOTALS_LABEL_WIDTH + AMOUNT_WIDTH],
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            *ZERO_PAD,
        ],
    )


def render_invoice(path: Path, invoice: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.45 * inch,
        bottomMargin=0.4 * inch,
    )
    doc.build(
        [
            header_block(invoice, styles),
            Spacer(1, 14),
            bill_to_block(styles),
            Spacer(1, 14),
            line_items_table(invoice, styles),
            Spacer(1, 10),
            comments_and_totals(invoice, styles),
        ]
    )
