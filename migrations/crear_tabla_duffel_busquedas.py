"""
Migracion: Crear tabla duffel_searches para analitica de busquedas
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, DuffelSearch
from sqlalchemy import inspect


def migrar():
    inspector = inspect(engine)

    if 'duffel_searches' in inspector.get_table_names():
        print("✅ Tabla 'duffel_searches' ya existe")
        return

    print("📋 Creando tabla 'duffel_searches'...")
    DuffelSearch.__table__.create(engine)
    print("✅ Tabla 'duffel_searches' creada exitosamente")


if __name__ == '__main__':
    migrar()
