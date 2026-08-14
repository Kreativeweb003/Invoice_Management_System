"""
Generates a downloadable PDF invoice using ReportLab. Called from
invoices.views.InvoicePDFView. Mirrors the layout of invoice_print.html
so the printed browser view and the downloaded PDF look consistent.
"""

from io import BytesIO
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT

# Business info — move to settings.py or a Company model later if you want
# this to be configurable per-tenant instead of hardcoded.
COMPANY_NAME = "Cresent Gadget Store"
COMPANY_ADDRESS = "23 Oke-odo, Iwo, Osun state, Nige"
COMPANY_CONTACT = "Phone: +234 704 1253  |  Email: abdulrafiuqudus90@gmail.com"

# Plain "#rrggbb" strings — used inside Paragraph HTML markup (<font color="...">).
# NOTE: do NOT use colors.HexColor(...).hexval() here — hexval() returns a
# "0xrrggbbaa" style string with no leading "#" and a trailing alpha byte,
# which ReportLab's mini-HTML parser rejects (ValueError: Invalid color value).
STATUS_COLORS = {
    'PENDING': '#d97706',
    'PARTIALLY_PAID': '#0891b2',
    'PAID': '#16a34a',
    'OVERDUE': '#dc2626',
    'CANCELLED': '#6b7280',
}


def render_invoice_pdf(invoice):
    """
    Builds the PDF in-memory and returns it as an HttpResponse with the
    correct content-disposition so the browser downloads it as a file
    named after the invoice number.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Invoice {invoice.invoice_number}",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CompanyName', fontSize=16, leading=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SmallGray', fontSize=9, textColor=colors.HexColor('#6b7280')))
    styles.add(ParagraphStyle(name='InvoiceTitle', fontSize=18, alignment=TA_RIGHT, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='RightSmall', fontSize=9, alignment=TA_RIGHT, textColor=colors.HexColor('#374151')))
    styles.add(ParagraphStyle(name='SectionLabel', fontSize=8, textColor=colors.HexColor('#6b7280'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='BodyBold', fontSize=10, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Body', fontSize=10))

    elements = []

    # --- Header: company info (left) + invoice meta (right) ---
    status_color = STATUS_COLORS.get(invoice.status, '#6b7280')
    header_table = Table(
        [[
            [
                Paragraph(COMPANY_NAME, styles['CompanyName']),
                Paragraph(COMPANY_ADDRESS, styles['SmallGray']),
                Paragraph(COMPANY_CONTACT, styles['SmallGray']),
            ],
            [
                Paragraph("INVOICE", styles['InvoiceTitle']),
                Paragraph(f"<b>{invoice.invoice_number}</b>", styles['RightSmall']),
                Paragraph(f"Issue Date: {invoice.issue_date.strftime('%b %d, %Y')}", styles['RightSmall']),
                Paragraph(
                    f"Due Date: {invoice.due_date.strftime('%b %d, %Y')}" if invoice.due_date else "Due Date: —",
                    styles['RightSmall']
                ),
                Paragraph(
                    f'<font color="{status_color}"><b>{invoice.get_status_display().upper()}</b></font>',
                    styles['RightSmall']
                ),
            ],
        ]],
        colWidths=[95 * mm, 75 * mm],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4 * mm))

    # Divider line
    divider = Table([['']], colWidths=[170 * mm], rowHeights=[1])
    divider.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor('#1f2937'))]))
    elements.append(divider)
    elements.append(Spacer(1, 6 * mm))

    # --- Bill To ---
    bill_to_lines = [Paragraph("BILLED TO", styles['SectionLabel'])]
    bill_to_lines.append(Paragraph(invoice.customer_display_name, styles['BodyBold']))
    if invoice.customer_display_phone:
        bill_to_lines.append(Paragraph(invoice.customer_display_phone, styles['Body']))
    if invoice.customer_display_address:
        bill_to_lines.append(Paragraph(invoice.customer_display_address, styles['Body']))
    for p in bill_to_lines:
        elements.append(p)
    elements.append(Spacer(1, 6 * mm))

    # --- Line items table ---
    table_data = [["Item", "Unit Price", "Qty", "Total"]]
    for item in invoice.items.all():
        table_data.append([
            item.product_name,
            f"{item.unit_price:.2f}",
            f"{item.quantity:g}",
            f"{item.line_total:.2f}",
        ])

    items_table = Table(table_data, colWidths=[85 * mm, 30 * mm, 25 * mm, 30 * mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 6 * mm))

    # --- Totals block (right-aligned) ---
    totals_data = [
        ["Subtotal", f"{invoice.subtotal:.2f}"],
        ["Discount", f"-{invoice.discount_amount:.2f}"],
        [f"Tax ({invoice.tax_percentage:g}%)", f"{invoice.tax_amount:.2f}"],
        ["Total", f"{invoice.total_amount:.2f}"],
        ["Amount Paid", f"{invoice.amount_paid:.2f}"],
        ["Balance Due", f"{invoice.balance_due:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[40 * mm, 35 * mm], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEABOVE', (0, 3), (-1, 3), 1, colors.HexColor('#1f2937')),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 3), (-1, 3), 11),
        ('LINEABOVE', (0, 5), (-1, 5), 1, colors.HexColor('#1f2937')),
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 5), (-1, 5), 11),
        ('TEXTCOLOR', (0, 5), (-1, 5), colors.HexColor('#dc2626') if invoice.balance_due > 0 else colors.HexColor('#16a34a')),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 8 * mm))

    # --- Notes ---
    if invoice.notes:
        elements.append(Paragraph("NOTES", styles['SectionLabel']))
        elements.append(Paragraph(invoice.notes.replace('\n', '<br/>'), styles['Body']))
        elements.append(Spacer(1, 8 * mm))

    # --- Signature lines ---
    sig_table = Table(
        [["_________________________", "_________________________"],
         ["Authorized Signature", "Customer Signature"]],
        colWidths=[75 * mm, 75 * mm],
    )
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#6b7280')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
    ]))
    elements.append(Spacer(1, 15 * mm))
    elements.append(sig_table)

    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{invoice.invoice_number}.pdf"'
    return response