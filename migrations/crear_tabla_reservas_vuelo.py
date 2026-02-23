"""
Migración: Crear tabla reservas_vuelo para checkout de vuelos con Duffel
"""

import sys
import os

# Añadir el directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base, ReservaVuelo
from sqlalchemy import inspect

def migrar():
    """Crea la tabla reservas_vuelo si no existe"""
    
    inspector = inspect(engine)
    
    if 'reservas_vuelo' in inspector.get_table_names():
        print("✅ Tabla 'reservas_vuelo' ya existe")
        return
    
    print("📋 Creando tabla 'reservas_vuelo'...")
    
    # Crear solo la tabla ReservaVuelo
    ReservaVuelo.__table__.create(engine)
    
    print("✅ Tabla 'reservas_vuelo' creada exitosamente")
    print("\nColumnas creadas:")
    print("  - id (PK)")
    print("  - codigo_reserva (UNIQUE)")
    print("  - offer_id_duffel")
    print("  - order_id_duffel")
    print("  - datos_vuelo (JSON)")
    print("  - pasajeros (JSON)")
    print("  - precio_vuelos, precio_extras, precio_total")
    print("  - stripe_payment_intent_id, stripe_session_id")
    print("  - estado (PENDIENTE/PAGADO/CONFIRMADO/ERROR)")
    print("  - email_cliente, telefono_cliente")
    print("  - es_viaje_redondo")
    print("  - notas, error_mensaje")
    print("  - fecha_creacion, fecha_pago, fecha_confirmacion")

if __name__ == '__main__':
    migrar()
