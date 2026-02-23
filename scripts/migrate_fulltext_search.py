"""
Script de migración para añadir Full-Text Search a Tours
Ejecutar: python scripts/migrate_fulltext_search.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import engine, get_db_session
from sqlalchemy import text

def crear_fulltext_search():
    """
    Añade soporte de Full-Text Search a la tabla tours
    """
    print("🔧 Iniciando migración de Full-Text Search...")
    
    with engine.connect() as conn:
        try:
            # 1. Añadir columna search_vector si no existe
            print("1️⃣ Verificando columna search_vector...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tours' AND column_name='search_vector'
            """))
            
            if result.fetchone() is None:
                print("   ➕ Añadiendo columna search_vector...")
                conn.execute(text("""
                    ALTER TABLE tours 
                    ADD COLUMN search_vector tsvector
                """))
                conn.commit()
                print("   ✅ Columna añadida")
            else:
                print("   ℹ️ Columna ya existe")
            
            # 2. Generar contenido de búsqueda para tours existentes
            print("2️⃣ Generando vectores de búsqueda...")
            conn.execute(text("""
                UPDATE tours 
                SET search_vector = to_tsvector('spanish', 
                    coalesce(titulo, '') || ' ' || 
                    coalesce(destino, '') || ' ' || 
                    coalesce(descripcion, '') || ' ' || 
                    coalesce(pais, '') || ' ' ||
                    coalesce(keywords, '')
                )
                WHERE search_vector IS NULL OR search_vector = ''::tsvector
            """))
            conn.commit()
            print("   ✅ Vectores generados")
            
            # 3. Crear índice GIN (si no existe)
            print("3️⃣ Creando índice GIN...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_tours_search_vector 
                    ON tours USING GIN(search_vector)
                """))
                conn.commit()
                print("   ✅ Índice GIN creado")
            except Exception as e:
                print(f"   ⚠️ Índice puede existir ya: {e}")
            
            # 4. Crear trigger para auto-actualización
            print("4️⃣ Creando trigger de actualización automática...")
            
            # Crear función del trigger
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION tours_search_vector_update() 
                RETURNS trigger AS $$
                BEGIN
                    NEW.search_vector := to_tsvector('spanish',
                        coalesce(NEW.titulo, '') || ' ' ||
                        coalesce(NEW.destino, '') || ' ' ||
                        coalesce(NEW.descripcion, '') || ' ' ||
                        coalesce(NEW.pais, '') || ' ' ||
                        coalesce(NEW.keywords, '')
                    );
                    RETURN NEW;
                END
                $$ LANGUAGE plpgsql
            """))
            conn.commit()
            
            # Crear trigger
            try:
                conn.execute(text("""
                    DROP TRIGGER IF EXISTS tsvector_update ON tours
                """))
                conn.execute(text("""
                    CREATE TRIGGER tsvector_update 
                    BEFORE INSERT OR UPDATE ON tours 
                    FOR EACH ROW 
                    EXECUTE FUNCTION tours_search_vector_update()
                """))
                conn.commit()
                print("   ✅ Trigger creado")
            except Exception as e:
                print(f"   ⚠️ Error creando trigger: {e}")
            
            # 5. Verificar
            print("5️⃣ Verificando instalación...")
            result = conn.execute(text("""
                SELECT COUNT(*) as total, 
                       COUNT(search_vector) as con_vector
                FROM tours
            """))
            stats = result.fetchone()
            print(f"   📊 Total tours: {stats[0]}")
            print(f"   📊 Con search_vector: {stats[1]}")
            
            if stats[0] == stats[1]:
                print("\n✅ ¡Migración completada exitosamente!")
            else:
                print(f"\n⚠️ Advertencia: {stats[0] - stats[1]} tours sin search_vector")
                
        except Exception as e:
            print(f"\n❌ Error en migración: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    crear_fulltext_search()
