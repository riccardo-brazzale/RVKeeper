from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone

from .models import TimeEvent


def build_time_report(workshop, period_start, period_end, technician=None):
    now = timezone.now()
    report_end = min(period_end, now)
    events = TimeEvent.objects.filter(
        workshop=workshop,
        event_at__lt=period_end,
    ).exclude(
        mechanic__isnull=True,
    )
    if technician:
        events = events.filter(mechanic=technician)
    events = events.select_related(
        "mechanic",
        "job",
        "job__work_order",
        "job__work_order__customer",
        "job__work_order__vehicle",
    ).order_by("event_at", "pk")

    running = {}
    rows = []

    def add_interval(start_event, end_at):
        started_at = max(start_event.event_at, period_start)
        ended_at = min(end_at, report_end)
        if ended_at <= started_at:
            return

        seconds = int((ended_at - started_at).total_seconds())
        job = start_event.job
        order = job.work_order
        vehicle = order.vehicle
        vehicle_label = (
            " ".join(value for value in (vehicle.brand, vehicle.model) if value)
            if vehicle
            else " ".join(value for value in (order.make, order.model) if value)
        )
        rows.append({
            "technician": start_event.mechanic,
            "order": order,
            "order_number": order.ro_number,
            "order_date": order.created_at,
            "customer": order.customer_name or (str(order.customer) if order.customer else ""),
            "vehicle": vehicle_label,
            "job": job,
            "started_at": started_at,
            "ended_at": ended_at,
            "seconds": seconds,
            "minutes": seconds // 60,
            "hours": (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01")),
        })

    for event in events:
        key = (event.job_id, event.mechanic_id)
        if event.event_type in ("start", "resume"):
            running[key] = event
        elif event.event_type in ("pause", "finish", "waiting") and key in running:
            add_interval(running.pop(key), event.event_at)

    for start_event in running.values():
        add_interval(start_event, now)

    rows.sort(key=lambda row: (row["started_at"], row["order_number"], row["job"].job_number))

    order_totals = {}
    technician_totals = {}
    for row in rows:
        order_total = order_totals.setdefault(
            row["order"].pk,
            {"order": row["order"], "customer": row["customer"], "vehicle": row["vehicle"], "seconds": 0},
        )
        order_total["seconds"] += row["seconds"]
        technician_total = technician_totals.setdefault(
            row["technician"].pk,
            {"technician": row["technician"], "seconds": 0},
        )
        technician_total["seconds"] += row["seconds"]

    def finalize_totals(items):
        results = list(items)
        for item in results:
            item["minutes"] = item["seconds"] // 60
            item["hours"] = (Decimal(item["seconds"]) / Decimal(3600)).quantize(Decimal("0.01"))
        return results

    total_seconds = sum(row["seconds"] for row in rows)
    return {
        "rows": rows,
        "order_totals": finalize_totals(order_totals.values()),
        "technician_totals": finalize_totals(technician_totals.values()),
        "total_seconds": total_seconds,
        "total_minutes": total_seconds // 60,
        "total_hours": (Decimal(total_seconds) / Decimal(3600)).quantize(Decimal("0.01")),
    }


def export_time_report_pdf(report, period_start, period_end, technician):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TimeReportSmall",
        parent=styles["BodyText"],
        fontSize=7,
        leading=9,
    ))
    styles.add(ParagraphStyle(
        name="TimeReportRight",
        parent=styles["TimeReportSmall"],
        alignment=TA_RIGHT,
    ))

    def paragraph(value, style="TimeReportSmall"):
        return Paragraph(escape(str(value or "—")).replace("\n", "<br/>"), styles[style])

    def local_datetime(value):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Consuntivo tempi per tecnico",
    )
    technician_label = technician.get_full_name() or technician.username if technician else "Tutti i tecnici"
    story = [
        Paragraph("Consuntivo ordini e tempi", styles["Title"]),
        paragraph(f"Periodo: {period_start:%d/%m/%Y} – {period_end:%d/%m/%Y}"),
        paragraph(f"Tecnico: {technician_label}"),
        paragraph(f"Totale: {report['total_minutes']} minuti · {report['total_hours']} ore"),
        Spacer(1, 5 * mm),
        Paragraph("Dettaglio sessioni", styles["Heading2"]),
    ]

    detail_rows = [[
        paragraph("Ordine"),
        paragraph("Data ordine"),
        paragraph("Cliente"),
        paragraph("Veicolo"),
        paragraph("Lavorazione"),
        paragraph("Tecnico"),
        paragraph("Inizio"),
        paragraph("Fine"),
        paragraph("Minuti", "TimeReportRight"),
        paragraph("Ore", "TimeReportRight"),
    ]]
    for row in report["rows"]:
        detail_rows.append([
            paragraph(row["order_number"]),
            paragraph(timezone.localtime(row["order_date"]).strftime("%d/%m/%Y") if row["order_date"] else "—"),
            paragraph(row["customer"]),
            paragraph(row["vehicle"]),
            paragraph(row["job"].title),
            paragraph(row["technician"].get_full_name() or row["technician"].username),
            paragraph(local_datetime(row["started_at"])),
            paragraph(local_datetime(row["ended_at"])),
            paragraph(row["minutes"], "TimeReportRight"),
            paragraph(row["hours"], "TimeReportRight"),
        ])
    if not report["rows"]:
        detail_rows.append([paragraph("Nessuna sessione nel periodo selezionato"), *[paragraph("") for _ in range(9)]])
    detail_table = LongTable(
        detail_rows,
        colWidths=tuple(width * mm for width in (20, 17, 28, 29, 38, 24, 31, 31, 14, 14)),
        repeatRows=1,
    )
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8F2")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (8, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([detail_table, Spacer(1, 5 * mm), Paragraph("Totali per ordine", styles["Heading2"])])

    order_rows = [[paragraph("Ordine"), paragraph("Cliente"), paragraph("Veicolo"), paragraph("Minuti"), paragraph("Ore")]]
    for item in sorted(report["order_totals"], key=lambda total: total["order"].ro_number):
        order_rows.append([
            paragraph(item["order"].ro_number),
            paragraph(item["customer"]),
            paragraph(item["vehicle"]),
            paragraph(item["minutes"], "TimeReportRight"),
            paragraph(item["hours"], "TimeReportRight"),
        ])
    story.append(LongTable(order_rows, colWidths=tuple(width * mm for width in (35, 75, 70, 25, 25)), repeatRows=1))
    story.extend([Spacer(1, 5 * mm), Paragraph("Totali per tecnico", styles["Heading2"])])
    technician_rows = [[paragraph("Tecnico"), paragraph("Minuti"), paragraph("Ore")]]
    for item in sorted(
        report["technician_totals"],
        key=lambda total: total["technician"].get_full_name() or total["technician"].username,
    ):
        user = item["technician"]
        technician_rows.append([
            paragraph(user.get_full_name() or user.username),
            paragraph(item["minutes"], "TimeReportRight"),
            paragraph(item["hours"], "TimeReportRight"),
        ])
    story.append(LongTable(technician_rows, colWidths=tuple(width * mm for width in (100, 25, 25)), repeatRows=1))
    document.build(story)
    return buffer.getvalue()


def export_time_report_excel(report, period_start, period_end, technician):
    from openpyxl import Workbook

    workbook = Workbook()
    details = workbook.active
    details.title = "Dettaglio"
    technician_label = technician.get_full_name() or technician.username if technician else "Tutti i tecnici"
    details.append(["Consuntivo ordini e tempi"])
    details.append(["Periodo", f"{period_start:%d/%m/%Y} - {period_end:%d/%m/%Y}"])
    details.append(["Tecnico", technician_label])
    details.append(["Totale", report["total_minutes"], "minuti", float(report["total_hours"]), "ore"])
    details.append([])
    details.append([
        "Ordine", "Data ordine", "Cliente", "Veicolo", "Lavorazione", "Tecnico",
        "Inizio", "Fine", "Minuti", "Ore",
    ])
    for row in report["rows"]:
        details.append([
            row["order_number"],
            timezone.localtime(row["order_date"]).replace(tzinfo=None) if row["order_date"] else None,
            row["customer"],
            row["vehicle"],
            row["job"].title,
            row["technician"].get_full_name() or row["technician"].username,
            timezone.localtime(row["started_at"]).replace(tzinfo=None),
            timezone.localtime(row["ended_at"]).replace(tzinfo=None),
            row["minutes"],
            float(row["hours"]),
        ])
    _style_report_sheet(details, header_row=6)
    for row_index in range(7, details.max_row + 1):
        for column in (2, 7, 8):
            details.cell(row_index, column).number_format = "dd/mm/yyyy hh:mm"
        details.cell(row_index, 10).number_format = "0.00"

    orders = workbook.create_sheet("Totali ordine")
    orders.append(["Ordine", "Cliente", "Veicolo", "Minuti", "Ore"])
    for item in sorted(report["order_totals"], key=lambda total: total["order"].ro_number):
        orders.append([
            item["order"].ro_number,
            item["customer"],
            item["vehicle"],
            item["minutes"],
            float(item["hours"]),
        ])
    _style_report_sheet(orders, header_row=1)
    for row_index in range(2, orders.max_row + 1):
        orders.cell(row_index, 5).number_format = "0.00"

    technicians = workbook.create_sheet("Totali tecnico")
    technicians.append(["Tecnico", "Minuti", "Ore"])
    for item in sorted(
        report["technician_totals"],
        key=lambda total: total["technician"].get_full_name() or total["technician"].username,
    ):
        user = item["technician"]
        technicians.append([
            user.get_full_name() or user.username,
            item["minutes"],
            float(item["hours"]),
        ])
    _style_report_sheet(technicians, header_row=1)
    for row_index in range(2, technicians.max_row + 1):
        technicians.cell(row_index, 3).number_format = "0.00"

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _style_report_sheet(sheet, header_row):
    from openpyxl.styles import Font, PatternFill

    header_fill = PatternFill(fill_type="solid", fgColor="DCE8F2")
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color="12263D")
        cell.fill = header_fill
    sheet.freeze_panes = f"A{header_row + 1}"
    if sheet.max_column and sheet.max_row >= header_row:
        sheet.auto_filter.ref = f"A{header_row}:{sheet.cell(sheet.max_row, sheet.max_column).coordinate}"
    for column in sheet.columns:
        max_width = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max_width + 2, 42)
