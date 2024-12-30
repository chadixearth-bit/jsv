from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from django.conf import settings
import os
from datetime import datetime

def generate_sale_receipt(sale):
    # Create the directory if it doesn't exist
    receipt_dir = os.path.join(settings.MEDIA_ROOT, 'receipts')
    os.makedirs(receipt_dir, exist_ok=True)

    # Generate filename
    filename = f"receipt_{sale.transaction_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(receipt_dir, filename)

    # Create the PDF document
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Add title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph("Sales Receipt", title_style))
    story.append(Spacer(1, 12))

    # Add receipt details
    receipt_style = ParagraphStyle(
        'ReceiptStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6
    )
    
    story.append(Paragraph(f"Transaction ID: {sale.transaction_id}", receipt_style))
    story.append(Paragraph(f"Date: {sale.sale_date.strftime('%Y-%m-%d %H:%M:%S')}", receipt_style))
    story.append(Paragraph(f"Buyer: {sale.buyer.first_name}", receipt_style))
    story.append(Paragraph(f"Sold by: {sale.sold_by.username}", receipt_style))
    story.append(Spacer(1, 20))

    # Create items table
    table_data = [['Item', 'Quantity', 'Price/Unit', 'Total']]
    for sale_item in sale.items.all():
        table_data.append([
            sale_item.item.item_name if sale_item.item else 'Unknown Item',
            str(sale_item.quantity),
            f"${sale_item.price_per_unit:.2f}",
            f"${sale_item.total_price:.2f}"
        ])
    
    # Add total row
    table_data.append(['', '', 'Total:', f"${sale.total_price:.2f}"])

    # Create and style the table
    table = Table(table_data, colWidths=[4*inch, 1*inch, 1.25*inch, 1.25*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
    ]))
    story.append(table)

    # Add footer
    story.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey
    )
    story.append(Paragraph("Thank you for your purchase!", footer_style))

    # Build the PDF
    doc.build(story)
    return filename
