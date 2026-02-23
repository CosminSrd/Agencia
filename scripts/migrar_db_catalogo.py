#!/usr/bin/env python3
"""
Migración: Añadir campos para catálogo avanzado
Fecha: 2026-02-03
Descripción: Añade 13 campos nuevos a la tabla tours y crea la tabla salidas_tour
"""

import sqlite3
import os
from pathlib import Path

# Ruta a la base de datos
DB_PATH = Path(__file__).parent.parent / 'viatges.db'

def ejecutar_migracion():
    print("🔧 Iniciando migración de base de datos...")
    print(f"📁 Base de datos: {DB_PATH}")
    
    if not DB_PATH.exists():
        print(f"❌ Error: No se encontró la base de datos en {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Verificar si las columnas ya existen
        cursor.execute("PRAGMA table_info(tours)")
        columnas_existentes = [col[1] for col in cursor.fetchall()]
        
        print(f"📊 Columnas existentes en 'tours': {len(columnas_existentes)}")
        
        # 2. Añadir columnas nuevas a la tabla tours
        columnas_nuevas = [
            ("continente", "VARCHAR(50)"),
            ("pais", "VARCHAR(100)"),
            ("ciudad_salida", "VARCHAR(100)"),
            ("precio_hasta", "FLOAT"),
            ("tipo_viaje", "VARCHAR(50)"),
            ("nivel_confort", "VARCHAR(20)"),
            ("temporada_inicio", "DATE"),
            ("temporada_fin", "DATE"),
            ("num_visitas", "INTEGER DEFAULT 0"),
            ("num_solicitudes", "INTEGER DEFAULT 0"),
            ("destacado", "BOOLEAN DEFAULT 0"),
            ("slug", "VARCHAR(255) UNIQUE"),
            ("keywords", "TEXT")
        ]
        
        columnas_añadidas = 0
        for col_name, col_type in columnas_nuevas:
            if col_name not in columnas_existentes:
                try:
                    sql = f"ALTER TABLE tours ADD COLUMN {col_name} {col_type}"
                    cursor.execute(sql)
                    print(f"  ✅ Añadida columna: {col_name} ({col_type})")
                    columnas_añadidas += 1
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        print(f"  ⚠️  Columna ya existe: {col_name}")
                    else:
                        raise
            else:
                print(f"  ⏭️  Columna ya existe: {col_name}")
        
        # 3. Crear tabla salidas_tour si no existe
        print("\n📅 Creando tabla salidas_tour...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS salidas_tour (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tour_id INTEGER NOT NULL,
                fecha_salida DATE NOT NULL,
                plazas_totales INTEGER DEFAULT 0,
                plazas_vendidas INTEGER DEFAULT 0,
                precio_especial FLOAT,
                estado VARCHAR(20) DEFAULT 'abierta',
                fecha_confirmacion_proveedor DATETIME,
                notas TEXT,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tour_id) REFERENCES tours (id) ON DELETE CASCADE
            )
        """)
        print("  ✅ Tabla salidas_tour creada/verificada")
        
        # 4. Crear índices para optimización
        print("\n🔍 Creando índices de optimización...")
        indices = [
            ("idx_continente_precio", "tours", "continente, precio_desde"),
            ("idx_destino_active", "tours", "destino, activo"),
            ("idx_proveedor_categoria", "tours", "proveedor, categoria"),
            ("idx_destacado", "tours", "destacado, activo"),
            ("idx_slug", "tours", "slug"),
            ("idx_salidas_tour_fecha", "salidas_tour", "fecha_salida"),
            ("idx_salidas_tour_estado", "salidas_tour", "estado")
        ]
        
        for idx_name, tabla, columnas in indices:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tabla} ({columnas})")
                print(f"  ✅ Índice creado: {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  Error creando índice {idx_name}: {e}")
        
        # 5. Commit y cerrar
        conn.commit()
        conn.close()
        
        print(f"\n✅ Migración completada exitosamente!")
        print(f"   - Columnas añadidas: {columnas_añadidas}")
        print(f"   - Tabla salidas_tour: OK")
        print(f"   - Índices: {len(indices)} creados/verificados")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    exito = ejecutar_migracion()
    
    if exito:
        print("\n🎉 ¡Base de datos migrada! Ahora puedes ejecutar:")
        print("   python3 scripts/categorizar_tours.py")
    else:
        print("\n⚠️  La migración falló. Revisa los errores anteriores.")
        exit(1)
