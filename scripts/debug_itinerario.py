#!/usr/bin/env python3
"""
Script para verificar el contenido del itinerario en la base de datos
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_session, Tour

db = get_db_session()

# Buscar tours de Saraya
tours_saraya = db.query(Tour).filter(Tour.proveedor == 'Saraya Tours').all()

print(f"🔍 Tours de Saraya encontrados: {len(tours_saraya)}\n")

for tour in tours_saraya:
    print("="*70)
    print(f"ID: {tour.id}")
    print(f"Título: {tour.titulo}")
    print(f"Proveedor: {tour.proveedor}")
    print(f"Precio: {tour.precio_desde}€")
    print(f"\n📋 ITINERARIO:")
    if tour.itinerario:
        print(f"  Longitud: {len(tour.itinerario)} caracteres")
        print(f"  Primeros 200 caracteres:")
        print(f"  {tour.itinerario[:200]}...")
    else:
        print("  ❌ VACÍO O NULL")
    print()

db.close()
