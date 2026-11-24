from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _paragraph(value, style):
    return Paragraph(escape(str(value or "—")).replace("\n", "<br/>"), style)


def purchase_order_pdf(order):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="RightCell", parent=styles["SmallCell"], alignment=TA_RIGHT))
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Ordine fornitore {order.order_number}",
    )
    supplier = order.supplier
    supplier_name = supplier.company_name if supplier.is_company else str(supplier)
    story = [
        Paragraph("ORDINE DI ACQUISTO", styles["Title"]),
        Paragraph(
            f"<b>Ordine:</b> {escape(order.order_number)} · "
            f"<b>Data:</b> {order.order_date:%d/%m/%Y}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("<b>Fornitore</b>", styles["Heading3"]),
        _paragraph(supplier_name, styles["BodyText"]),
        _paragraph(supplier.address, styles["BodyText"]),
        _paragraph(" ".join(filter(None, (supplier.postal_code, supplier.city, supplier.country))), styles["BodyText"]),
        _paragraph(f"P. IVA: {supplier.vat_number}" if supplier.vat_number else "", styles["BodyText"]),
        _paragraph(supplier.email, styles["BodyText"]),
        Spacer(1, 6 * mm),
    ]
    rows = [[
        _paragraph("Codice fornitore", styles["SmallCell"]),
        _paragraph("Codice interno", styles["SmallCell"]),
        _paragraph("Articolo", styles["SmallCell"]),
        _paragraph("Quantità", styles["SmallCell"]),
        _paragraph("Prezzo", styles["SmallCell"]),
        _paragraph("Sconto", styles["SmallCell"]),
    ]]
    for line in order.lines.select_related("part").all():
        rows.append([
            _paragraph(line.supplier_article_code, styles["SmallCell"]),
            _paragraph(line.part.part_number, styles["SmallCell"]),
            _paragraph(line.part.name, styles["SmallCell"]),
            _paragraph(line.quantity_ordered, styles["RightCell"]),
            _paragraph(f"{line.unit_price:.2f}", styles["RightCell"]),
            _paragraph(f"{line.discount_percent:.2f}%", styles["RightCell"]),
        ])
    table = Table(rows, colWidths=(32 * mm, 28 * mm, 51 * mm, 20 * mm, 24 * mm, 22 * mm), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C4D0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    if order.notes:
        story.extend([Spacer(1, 5 * mm), Paragraph("<b>Note</b>", styles["Heading3"]), _paragraph(order.notes, styles["BodyText"])])
    document.build(story)
    return buffer.getvalue()


def goods_receipt_pdf(receipt):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=8, leading=10))
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Bolla entrata {receipt.receipt_number}",
    )
    order = receipt.purchase_order
    supplier = order.supplier.company_name if order.supplier.is_company else str(order.supplier)
    story = [
        Paragraph("BOLLA DI ENTRATA MERCE", styles["Title"]),
        Paragraph(
            f"<b>Bolla:</b> {escape(receipt.receipt_number)} · "
            f"<b>Ricevuta il:</b> {receipt.received_at:%d/%m/%Y %H:%M}",
            styles["Normal"],
        ),
        Paragraph(
            f"<b>Ordine fornitore:</b> {escape(order.order_number)} · "
            f"<b>Fornitore:</b> {escape(supplier)}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]
    rows = [[
        _paragraph("Codice interno", styles["SmallCell"]),
        _paragraph("Articolo", styles["SmallCell"]),
        _paragraph("Quantità ricevuta", styles["SmallCell"]),
    ]]
    for line in receipt.lines.select_related("purchase_order_line__part").all():
        order_line = line.purchase_order_line
        rows.append([
            _paragraph(order_line.part.part_number, styles["SmallCell"]),
            _paragraph(order_line.part.name, styles["SmallCell"]),
            _paragraph(line.quantity_received, styles["SmallCell"]),
        ])
    table = Table(rows, colWidths=(40 * mm, 95 * mm, 42 * mm), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C4D0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    if receipt.notes:
        story.extend([Spacer(1, 5 * mm), _paragraph(receipt.notes, styles["BodyText"])])
    story.extend([Spacer(1, 18 * mm), Paragraph("Firma ricezione: ______________________________", styles["Normal"])])
    document.build(story)
    return buffer.getvalue()
