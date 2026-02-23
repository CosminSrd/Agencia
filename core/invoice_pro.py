import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

def generar_factura_pdf(datos):
    folder = "facturas"
    if not os.path.exists(folder): os.makedirs(folder)
    
    ruta_pdf = f"{folder}/factura_{datos['numero_factura']}.pdf"
    doc = SimpleDocTemplate(ruta_pdf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    estilo_titulo = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.hexColor("#1e293b"), spaceAfter=10)
    estilo_subtitulo = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    estilo_label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.indigo)

    elements = []

    # --- CABECERA ESTILO AEROLÍNEA ---
    col1, col2 = [300, 230]
    header_data = [[
        Paragraph(f"<b>COSMIN</b><font color='#6366f1'>PRO</font>", estilo_titulo),
        Paragraph(f"FACTURA: {datos['numero_factura']}<br/>FECHA: {datos['fecha']}", ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT))
    ]]
    t_header = Table(header_data, colWidths=[col1, col2])
    elements.append(t_header)
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.hexColor("#e2e8f0"), spaceBefore=10, spaceAfter=20))

    # --- DATOS DEL CLIENTE Y AGENCIA ---
    info_data = [[
        Paragraph("<b>EMISOR:</b><br/>Cosmin Viajes S.L.<br/>CIF: B12345678<br/>Calle Gran Vía 1, Madrid", styles['Normal']),
        Paragraph(f"<b>CLIENTE:</b><br/>{datos['cliente']}<br/>Email: {datos['email_cliente']}", styles['Normal'])
    ]]
    t_info = Table(info_data, colWidths=[265, 265])
    elements.append(t_info)
    elements.append(Spacer(1, 30))

    # --- DETALLE DEL VIAJE ---
    elements.append(Paragraph("DETALLES DEL ITINERARIO", estilo_label))
    elements.append(Spacer(1, 5))
    viaje_data = [
        [Paragraph("<b>Descripción del Servicio</b>", styles['Normal']), Paragraph("<b>Monto</b>", styles['Normal'])],
        [Paragraph(f"{datos['viaje']}<br/><font size=8 color='grey'>Vuelo + Estancia Confirmada</font>", styles['Normal']), f"{datos['monto']} €"]
    ]
    t_viaje = Table(viaje_data, colWidths=[400, 130])
    t_viaje.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.hexColor("#f8fafc")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.hexColor("#64748b")),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 0.5, colors.hexColor("#e2e8f0"))
    ]))
    elements.append(t_viaje)
    elements.append(Spacer(1, 25))

    # --- MANIFIESTO DE PASAJEROS ---
    elements.append(Paragraph("PASAJEROS Y DOCUMENTACIÓN", estilo_label))
    elements.append(Spacer(1, 5))
    pax_rows = [["Nombre Completo", "Identificación (DNI/NIE)"]]
    for p in datos['pasajeros']:
        pax_rows.append([p['nombre'], p['dni']])
    
    t_pax = Table(pax_rows, colWidths=[265, 265])
    t_pax.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,0), (-1,0), colors.hexColor("#6366f1")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.hexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 8)
    ]))
    elements.append(t_pax)

    # --- TOTAL ---
    elements.append(Spacer(1, 40))
    total_data = [["", "TOTAL FACTURADO:", f"{datos['monto']} €"]]
    t_total = Table(total_data, colWidths=[300, 130, 100])
    t_total.setStyle(TableStyle([
        ('FONTNAME', (1,0), (1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (2,0), (2,0), 14),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('TEXTCOLOR', (2,0), (2,0), colors.indigo)
    ]))
    elements.append(t_total)

    doc.build(elements)
    return ruta_pdf