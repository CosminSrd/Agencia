#!/usr/bin/env python3
"""
Script de prueba para analizar PDFs de Saraya Tours
Descarga un PDF y muestra qué información se puede extraer
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import requests
from bs4 import BeautifulSoup
import pdfplumber
from dotenv import load_dotenv
from core.encriptacion import descifrar

load_dotenv()

# Configurar sesión con login
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

# Login
print("🔐 Iniciando sesión en Saraya Tours...")
user_enc = os.getenv('SARAYA_USER')
pass_enc = os.getenv('SARAYA_PASS')
username = descifrar(user_enc)
password = descifrar(pass_enc)

payload = {'par1': username, 'par2': password}
session.post("https://www.sarayatours.es/Inicio/Index", data=payload)
print("✅ Login completado\n")

# URL de prueba
test_url = "https://www.sarayatours.es/reservar/egipto-clasico-8-dias-charter_-3035?search_date="

print(f"📄 Analizando tour: {test_url}")
print("-" * 70)

response = session.get(test_url)
soup = BeautifulSoup(response.text, 'html.parser')

# Buscar enlace PDF
pdf_link = None
for a in soup.find_all('a', href=True):
    if '.pdf' in a['href'].lower():
        pdf_link = a['href']
        if not pdf_link.startswith('http'):
            pdf_link = "https://www.sarayatours.es" + pdf_link
        print(f"✅ PDF encontrado: {pdf_link}\n")
        break

if not pdf_link:
    print("❌ No se encontró PDF en la página")
    sys.exit(1)

# Descargar PDF
print("📥 Descargando PDF...")
pdf_response = session.get(pdf_link)

if pdf_response.status_code != 200:
    print(f"❌ Error descargando PDF: {pdf_response.status_code}")
    sys.exit(1)

print("✅ PDF descargado\n")

# Analizar PDF
print("=" * 70)
print("📖 CONTENIDO EXTRAÍDO DEL PDF")
print("=" * 70)

with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
    print(f"\n📄 Total de páginas: {len(pdf.pages)}\n")
    
    texto_completo = ""
    for i, page in enumerate(pdf.pages, 1):
        texto_pagina = page.extract_text()
        texto_completo += texto_pagina + "\n"
        print(f"--- PÁGINA {i} ---")
        print(texto_pagina)
        print("\n")

# Guardar texto completo para análisis
output_file = "pdf_analizado.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(texto_completo)

print("=" * 70)
print(f"💾 Texto completo guardado en: {output_file}")
print("=" * 70)

# Análisis básico de patrones
print("\n🔍 ANÁLISIS DE PATRONES DETECTADOS:")
print("-" * 70)

import re

# Detectar días del itinerario
dias = re.findall(r'DÍA\s+\d+[:\-]?.+', texto_completo, re.IGNORECASE)
print(f"\n📅 Días de itinerario detectados: {len(dias)}")
for dia in dias[:3]:  # Mostrar primeros 3
    print(f"   • {dia[:80]}...")

# Detectar precios
precios = re.findall(r'(\d+[.,]\d+)\s*€', texto_completo)
print(f"\n💰 Precios encontrados: {precios[:5]}")

# Detectar fechas
fechas = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', texto_completo)
print(f"\n📆 Fechas encontradas: {fechas[:5]}")

# Buscar sección "INCLUYE"
if 'INCLUYE' in texto_completo.upper() or 'INCLUIDO' in texto_completo.upper():
    print(f"\n✅ Sección 'INCLUYE' encontrada")
    
# Buscar sección "NO INCLUYE"
if 'NO INCLUYE' in texto_completo.upper():
    print(f"❌ Sección 'NO INCLUYE' encontrada")

print("\n" + "=" * 70)
print("✅ Análisis completado. Revisa pdf_analizado.txt para más detalles")
print("=" * 70)
