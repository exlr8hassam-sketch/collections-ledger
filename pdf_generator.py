import os
import datetime
from pathlib import Path
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

INVOICE_DIR = Path(__file__).resolve().parent / "invoices"
INVOICE_DIR.mkdir(exist_ok=True)


def generate_invoice_pdf(client: Dict[str, Any], payment_details: Dict[str, Any], is_paid: bool = False) -> str:
    """
    Generates a high-quality, professional printable PDF invoice.
    If is_paid is True, stamps a green PAID watermark/badge and marks balance as zero.
    Returns the absolute path to the generated PDF file.
    """
    client_name = client.get("client_name", "Valued Client")
    client_id = client.get("client_id", "CLI-001")
    phone = client.get("phone", "N/A")
    inv_num = client.get("invoice_number", f"INV-{client_id}")
    currency = client.get("currency", "PKR")
    
    try:
        amount_val = float(client.get("amount_due", 0))
    except Exception:
        amount_val = 0.0
        
    formatted_amount = f"{currency} {amount_val:,.2f}"
    due_date = client.get("due_date", str(datetime.date.today()))
    issue_date = datetime.date.today().strftime("%d %b %Y")
    notes = client.get("notes") or "Professional Services & Account Settlement"

    bank_name = payment_details.get("bank_name", "Bank Transfer")
    account_title = payment_details.get("account_title", "Business Account")
    account_number = payment_details.get("account_number", "")
    iban = payment_details.get("iban", "")
    support_contact = payment_details.get("support_contact", "")

    prefix = "Receipt" if is_paid else "Invoice"
    filename = f"{prefix}-{inv_num}-{client_id}.pdf".replace(" ", "_").replace("/", "-")
    pdf_path = INVOICE_DIR / filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold"
    )
    
    inv_label_style = ParagraphStyle(
        'InvLabel',
        parent=styles['Normal'],
        fontSize=22,
        leading=26,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#10b981") if is_paid else colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold"
    )

    meta_right = ParagraphStyle(
        'MetaRight',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#475569")
    )

    meta_left = ParagraphStyle(
        'MetaLeft',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569")
    )

    section_header = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#64748b")
    )

    normal_bold = ParagraphStyle(
        'NormalBold',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a")
    )

    story = []

    # 1. HEADER TABLE (Company details on left, Invoice title & metadata on right)
    company_p = Paragraph(
        f"<b>{account_title}</b><br/>"
        f"<font color='#64748b'>Official Payment & Billing Voucher</font><br/>"
        f"<font color='#64748b'>Support: {support_contact}</font>",
        meta_left
    )

    status_tag = (
        "<font color='#16a34a'><b>[ ✓ SETTLED & PAID ]</b></font>"
        if is_paid else
        "<font color='#d97706'><b>[ ⏳ PAYMENT DUE ]</b></font>"
    )

    inv_meta_p = Paragraph(
        f"<b>{('RECEIPT' if is_paid else 'INVOICE')}</b><br/>"
        f"<b>Invoice #:</b> {inv_num}<br/>"
        f"<b>Date:</b> {issue_date}<br/>"
        f"<b>Due Date:</b> {due_date}<br/>"
        f"<b>Status:</b> {status_tag}",
        meta_right
    )

    header_table = Table(
        [[company_p, inv_meta_p]],
        colWidths=[270, 270]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#e2e8f0"), spaceAfter=14))

    # 2. BILL TO & PAYMENT SUMMARY SECTION
    bill_to_p = Paragraph(
        f"<b>BILLED TO</b><br/>"
        f"<font size='12'><b>{client_name}</b></font><br/>"
        f"Phone / WhatsApp: <b>{phone}</b><br/>"
        f"Client ID: {client_id}",
        meta_left
    )

    status_summary_p = Paragraph(
        f"<b>ACCOUNT SUMMARY</b><br/>"
        f"Invoice Amount: <b>{formatted_amount}</b><br/>"
        f"Payment Status: <b>{'Fully Paid' if is_paid else 'Pending Payment'}</b><br/>"
        f"Balance Due: <b>{currency} 0.00</b>" if is_paid else f"Balance Due: <font color='#dc2626'><b>{formatted_amount}</b></font>",
        meta_right
    )

    bill_table = Table(
        [[bill_to_p, status_summary_p]],
        colWidths=[270, 270]
    )
    bill_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
    ]))
    story.append(bill_table)

    # 3. LINE ITEMS TABLE
    items_data = [
        [
            Paragraph("<b>DESCRIPTION</b>", section_header),
            Paragraph("<b>QTY</b>", ParagraphStyle('HCenter', parent=section_header, alignment=TA_CENTER)),
            Paragraph("<b>UNIT PRICE</b>", ParagraphStyle('HRight', parent=section_header, alignment=TA_RIGHT)),
            Paragraph("<b>TOTAL</b>", ParagraphStyle('HRight2', parent=section_header, alignment=TA_RIGHT))
        ],
        [
            Paragraph(f"<b>{notes}</b><br/><font size='8' color='#64748b'>Invoice ref #{inv_num}</font>", meta_left),
            Paragraph("1", ParagraphStyle('QCenter', parent=meta_left, alignment=TA_CENTER)),
            Paragraph(formatted_amount, ParagraphStyle('QRight', parent=meta_left, alignment=TA_RIGHT)),
            Paragraph(formatted_amount, ParagraphStyle('QRight2', parent=normal_bold, alignment=TA_RIGHT))
        ]
    ]

    items_table = Table(items_data, colWidths=[280, 50, 105, 105])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 1), (-1, 1), 1, colors.HexColor("#f1f5f9")),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # 4. TOTALS TABLE
    totals_data = [
        ["", Paragraph("<b>Subtotal:</b>", meta_right), Paragraph(formatted_amount, meta_right)],
        ["", Paragraph("<b>Tax / Fees:</b>", meta_right), Paragraph(f"{currency} 0.00", meta_right)],
        [
            "",
            Paragraph("<b>TOTAL DUE:</b>" if not is_paid else "<b>TOTAL PAID:</b>", ParagraphStyle('TotLabel', parent=normal_bold, alignment=TA_RIGHT)),
            Paragraph(f"<font color='{'#10b981' if is_paid else '#059669'}'><b>{formatted_amount}</b></font>", ParagraphStyle('TotVal', parent=normal_bold, alignment=TA_RIGHT, fontSize=12))
        ]
    ]
    totals_table = Table(totals_data, colWidths=[280, 130, 130])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (1, 2), (2, 2), 1.5, colors.HexColor("#0f172a")),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 20))

    # 5. REMITTANCE / BANK DETAILS BOX
    if is_paid:
        payment_box_content = [
            [
                Paragraph(
                    "<b>PAYMENT CONFIRMATION RECEIPT</b><br/>"
                    f"This document certifies that payment of <b>{formatted_amount}</b> has been received and cleared.<br/>"
                    f"Settlement Date: <b>{issue_date}</b> • Status: <font color='#16a34a'><b>PAID IN FULL</b></font>",
                    meta_left
                )
            ]
        ]
        box_bg = colors.HexColor("#f0fdf4")
        box_border = colors.HexColor("#86efac")
    else:
        payment_box_content = [
            [
                Paragraph("<b>OFFICIAL BANK TRANSFER DETAILS</b>", section_header),
                Paragraph("<b>ACCOUNT TITLE & IBAN</b>", section_header)
            ],
            [
                Paragraph(f"Bank Name: <b>{bank_name}</b><br/>Account Number: <b>{account_number}</b>", meta_left),
                Paragraph(f"Account Title: <b>{account_title}</b><br/>IBAN: <b>{iban or 'N/A'}</b>", meta_left)
            ]
        ]
        box_bg = colors.HexColor("#f8fafc")
        box_border = colors.HexColor("#e2e8f0")

    pay_table = Table(payment_box_content, colWidths=[270, 270] if not is_paid else [540])
    pay_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), box_bg),
        ('BOX', (0, 0), (-1, -1), 1, box_border),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
    ]))
    story.append(pay_table)
    story.append(Spacer(1, 16))

    # 6. FOOTER
    footer_text = (
        f"Thank you for your business! For any questions, please contact {support_contact or account_title}."
        if is_paid else
        f"Please send a screenshot or transaction reference upon transfer. Thank you! Support: {support_contact}."
    )
    story.append(Paragraph(f"<font color='#94a3b8' size='8'>{footer_text}</font>", ParagraphStyle('Foot', parent=styles['Normal'], alignment=TA_CENTER)))

    doc.build(story)
    return str(pdf_path)
