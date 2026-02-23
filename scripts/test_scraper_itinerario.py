#!/usr/bin/env python3
"""
Debug para probar el parsing de itinerario del PDF
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper_saraya import ScraperSarayaB2B

# URL de prueba
url_test = "https://www.sarayatours.es/reservar/egipto-clasico-8-dias-charter_-3035?search_date="

scraper = ScraperSarayaB2B()

if scraper._login():
    print("\n🧪 Probando scrapear_tour...")
    tour_data = scraper.scrapear_tour(url_test)
    
    if tour_data:
        print("\n" + "="*70)
        print("DATOS EXTRAÍDOS:")
        print("="*70)
        print(f"Título: {tour_data.get('titulo')}")
        print(f"Precio: {tour_data.get('precio_desde')}€")
        print(f"Duración: {tour_data.get('duracion_dias')} días")
        print(f"\n📋 ITINERARIO:")
        itinerario = tour_data.get('itinerario', '')
        if itinerario:
            print(f"  Longitud: {len(itinerario)} caracteres")
            print(f"  Primeros 500 caracteres:")
            print(f"  {itinerario[:500]}...")
        else:
            print("  ❌ VACÍO")
            print("\n⚠️ El parser de PDF NO está extrayendo el itinerario!")
    else:
        print("❌ No se pudo scrapear el tour")
