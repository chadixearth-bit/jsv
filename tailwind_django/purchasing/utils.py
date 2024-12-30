from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from django.conf import settings
import os
from datetime import datetime

def generate_purchase_order_pdf(order):
    # Create the directory if it doesn't exist
    po_dir = os.path.join(settings.MEDIA_ROOT, 'purchase_orders')
    os.makedirs(po_dir, exist_ok=True)

    # Generate filename
    filename = f"PO_{order.po_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(po_dir, filename)

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
    story.append(Paragraph("Purchase Order", title_style))
    story.append(Spacer(1, 12))

    # Add PO details
    detail_style = ParagraphStyle(
        'DetailStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6
    )
    
    story.append(Paragraph(f"PO Number: {order.po_number}", detail_style))
    story.append(Paragraph(f"Date: {order.order_date.strftime('%Y-%m-%d')}", detail_style))
    story.append(Paragraph(f"Status: {order.status.title()}", detail_style))
    story.append(Spacer(1, 20))

    # Add supplier information
    story.append(Paragraph("Supplier Information", styles['Heading2']))
    story.append(Paragraph(f"Name: {order.supplier.name}", detail_style))
    story.append(Paragraph(f"Contact Person: {order.supplier.contact_person}", detail_style))
    story.append(Paragraph(f"Email: {order.supplier.email}", detail_style))
    story.append(Paragraph(f"Phone: {order.supplier.phone}", detail_style))
    story.append(Paragraph(f"Address: {order.supplier.address}", detail_style))
    if order.supplier.tax_id:
        story.append(Paragraph(f"Tax ID: {order.supplier.tax_id}", detail_style))
    if order.supplier.website:
        story.append(Paragraph(f"Website: {order.supplier.website}", detail_style))
    if order.supplier.payment_terms:
        story.append(Paragraph(f"Payment Terms: {order.supplier.payment_terms}", detail_style))
    story.append(Spacer(1, 20))

    # Add order details
    story.append(Paragraph("Order Details", styles['Heading2']))
    story.append(Paragraph(f"Warehouse: {order.warehouse.name}", detail_style))
    story.append(Paragraph(f"Expected Delivery: {order.expected_delivery_date.strftime('%Y-%m-%d')}", detail_style))
    story.append(Paragraph(f"Created By: {order.created_by.username}", detail_style))
    if order.notes:
        story.append(Paragraph(f"Notes: {order.notes}", detail_style))
    story.append(Spacer(1, 20))

    # Create items table
    table_data = [['Brand', 'Item Name', 'Model', 'SKU', 'Category', 'Quantity', 'Unit Price', 'Subtotal']]
    for item in order.items.all():
        table_data.append([
            item.item.brand.name if item.item.brand else '',
            item.item.item_name,
            item.item.model or '',
            item.item.sku or '',
            item.item.category.name if item.item.category else '',
            str(item.quantity),
            f"${item.unit_price:.2f}",
            f"${item.subtotal:.2f}"
        ])
    
    # Add total row
    table_data.append(['', '', '', '', '', '', 'Total:', f"${order.total_amount:.2f}"])

    # Create and style the table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (-2, -1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
    ]))
    story.append(table)

    # Add signature section
    story.append(Spacer(1, 40))
    signature_data = [['_________________', '_________________', '_________________'],
                     ['Prepared By', 'Approved By', 'Received By']]
    signature_table = Table(signature_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 10),
        ('TOPPADDING', (0, 1), (-1, 1), 5),
    ]))
    story.append(signature_table)

    # Build the PDF
    doc.build(story)
    return filename
