from __future__ import annotations
from typing import Dict, List
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import logging

logger = logging.getLogger(__name__)


def generate_fiche_pdf(title: str, date_label: str, service_label: str, reservations: List[Dict], totals: Dict[str, int]) -> bytes:
    logger.info(f"PDF: generating fiche - title='{title}', date='{date_label}', service='{service_label}'")
    logger.debug(f"PDF: totals count={len(totals)} reservations count={len(reservations)}")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{title}</b>", styles['Title']))
    story.append(Paragraph(f"{date_label} - {service_label}", styles['Heading2']))
    story.append(Spacer(1, 12))

    # Totals table
    data = [["Plat", "Quantité"]]
    for name, qty in sorted(totals.items(), key=lambda x: (-x[1], x[0])):
        data.append([name, str(qty)])

    tbl = Table(data, colWidths=[350, 100])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story.append(Paragraph("<b>Totaux</b>", styles['Heading3']))
    story.append(tbl)
    story.append(Spacer(1, 16))

    # Reservations detail
    story.append(Paragraph("<b>Détail par réservation</b>", styles['Heading3']))
    for res in reservations:
        logger.debug(f"PDF: reservation name='{res.get('name','')}', time='{res.get('time','')}', pax='{res.get('pax','')}', items={len(res.get('items', []))}")
        story.append(Paragraph(f"<b>{res.get('time','')} - {res.get('name','')}</b> ({res.get('pax','')} pax)", styles['Heading4']))
        lines = []
        for it in res.get('items', []):
            lines.append(f"- {it['name']} x{it['qty']}")
        if not lines:
            lines.append("- (aucun plat détecté)")
        story.append(Paragraph("<br/>".join(lines), styles['BodyText']))
        if res.get('note'):
            story.append(Paragraph(f"<i>Note:</i> {res['note']}", styles['BodyText']))
        story.append(Spacer(1, 8))

    doc.build(story)
    return buffer.getvalue()
