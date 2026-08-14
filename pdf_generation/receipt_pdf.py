"""
Generates a compact PDF payment receipt using ReportLab. Called from
payments.views (wire up PaymentReceiptPDFView similarly to InvoicePDFView
if you want a downloadable receipt alongside the printable HTML one).
"""

from io import BytesIO
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

COMPANY_NAME = "Your Business Name"
COMPANY_ADDRESS = "123 Business Street, City, Country"


def render_receipt_pdf(payment):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A6,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        title=f"Receipt {payment.payment_number}",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER, fontSize=10))
    styles.add(ParagraphStyle(name='CenterBold', alignment=TA_CENTER, fontSize=13, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CenterGray', alignment=TA_CENTER, fontSize=8, textColor=colors.HexColor('#6b7280')))

    elements = [
        Paragraph(COMPANY_NAME, styles['CenterBold']),
        Paragraph(COMPANY_ADDRESS, styles['CenterGray']),
        Spacer(1, 4 * mm),
        Paragraph("PAYMENT RECEIPT", styles['Center']),
        Spacer(1, 4 * mm),
    ]

    invoice = payment.invoice
    rows = [
        ["Receipt #", payment.payment_number],
        ["Invoice #", invoice.invoice_number],
        ["Customer", invoice.customer_display_name],
        ["Date", payment.payment_date.strftime('%b %d, %Y')],
        ["Method", payment.get_method_display()],
    ]
    if payment.reference_number:
        rows.append(["Reference", payment.reference_number])

    info_table = Table(rows, colWidths=[35 * mm, 55 * mm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 5 * mm))

    amount_table = Table(
        [["Amount Paid", f"{payment.amount:.2f}"]],
        colWidths=[45 * mm, 45 * mm],
    )
    amount_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#1f2937')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#1f2937')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(amount_table)
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(f"Invoice balance after payment: {invoice.balance_due:.2f}", styles['CenterGray']))
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("Thank you for your payment!", styles['CenterGray']))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{payment.payment_number}.pdf"'
    return response




