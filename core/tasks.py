import hashlib
import threading
import os
import smtplib
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from email.message import EmailMessage
from core.database import get_db_connection

def generar_hash_dni(dni):
    """Crea una huella digital única (no reversible) para búsquedas ultra rápidas"""
    # Usamos una 'sal' (salt) para mayor seguridad. Cámbiala por algo secreto.
    salt = "COSMIN_SECRET_2026"
    return hashlib.sha256((dni + salt).encode()).hexdigest()

class FacturaPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "FACTURA DE VENTA - AGENCIA VIAJES", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(10)

def procesar_venta_background(email_cliente, nombre_pagador, lista_pasajeros, total, concepto, id_expediente, num_factura, fuente, email_prov):
    # 1. Generar PDF (Tarea pesada)
    pdf = FacturaPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Cliente: {nombre_pagador}")
    pdf.ln(10)
    pdf.cell(0, 10, f"Concepto: {concepto} | Total: {total} EUR")
    
    ruta_pdf = f"factura_{num_factura}.pdf"
    pdf.output(ruta_pdf)

    # 2. Actualizar DB (Operación atómica rápida)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE facturas SET url_archivo_pdf = %s WHERE numero_factura = %s", (ruta_pdf, num_factura))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error en worker: {e}")

    # 3. Notificaciones
    # Aquí iría el envío de SMTP (Mail)
    print(f"✅ Tarea finalizada para {num_factura}")

def lanzar_tarea_venta(email, pagador, pasajeros, total, concepto, id_exp, num_f, fuente, email_prov):
    threading.Thread(target=procesar_venta_background, args=(email, pagador, pasajeros, total, concepto, id_exp, num_f, fuente, email_prov)).start()