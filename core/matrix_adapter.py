import os
from database import get_db_session, Tour

class MatrixOrchestrator:
    def __init__(self):
        # Mantenemos las variables por compatibilidad
        self.cache_vuelos = [] 
        print("🚀 Orquestador iniciado en modo UNIFICADO (SQLAlchemy)")

    def obtener_catalogo_unificado(self):
        """Obtiene los viajes directamente de la base de datos principal (agencia.db) vía SQLAlchemy."""
        print("🏠 Cargando catálogo desde base de datos unificada...")
        return self._obtener_datos_locales()

    def _obtener_datos_locales(self):
        """Consulta a la tabla de tours usando ORM."""
        db = get_db_session()
        try:
            tours = db.query(Tour).filter_by(activo=True).all()
            # Mapeamos los objetos Tour al formato de diccionario que espera el frontend
            catalogo = []
            for t in tours:
                catalogo.append({
                    'id_viaje': t.id, # Mapeamos id a id_viaje para compatibilidad
                    'nombre': t.titulo,
                    'descripcion': t.descripcion,
                    'destino': t.destino,
                    'precio_venta': t.precio_desde,
                    'url_imagen': t.imagen_url,
                    'duracion': f"{t.duracion_dias} Días" if t.duracion_dias else "",
                    'proveedor': t.proveedor
                })
            return catalogo
        except Exception as e:
            print(f"❌ Error al leer la base de datos: {e}")
            return []
        finally:
            db.close()

    def obtener_detalle_viaje(self, id_viaje):
        """Busca un viaje específico por su ID."""
        db = get_db_session()
        try:
            t = db.query(Tour).get(int(id_viaje))
            if t:
                return {
                    'id_viaje': t.id,
                    'nombre': t.titulo,
                    'descripcion': t.descripcion,
                    'destino': t.destino,
                    'precio_venta': t.precio_desde,
                    'url_imagen': t.imagen_url
                }
            return None
        except Exception as e:
            print(f"❌ Error al obtener detalle: {e}")
            return None
        finally:
            db.close()