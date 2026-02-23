"""
Database package
Módulo de base de datos - Configuración centralizada
"""

from .connection import (
    engine,
    Session,
    get_db,
    get_db_session,
    close_session,
    test_connection,
    DATABASE_URL,
    get_db_connection  # ✅ AÑADIDO
)

from .models import (
    Base,
    Usuario,
    Tour,
    SalidaTour,
    Pedido,
    SolicitudTour,
    ReservaVuelo,
    DuffelSearch
)

__all__ = [
    # Connection
    'engine',
    'Session',
    'get_db',
    'get_db_session',
    'close_session',
    'test_connection',
    'DATABASE_URL',
    'get_db_connection',  # ✅ AÑADIDO
    # Models
    'Base',
    'Usuario',
    'Tour',
    'SalidaTour',
    'Pedido',
    'SolicitudTour',
    'ReservaVuelo',
    'DuffelSearch'
]


def init_db():
    """
    Inicializa todas las tablas en la base de datos
    """
    print("🔧 Creando tablas en PostgreSQL...")
    Base.metadata.create_all(engine)
    
    # Verificar tablas creadas
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tablas = inspector.get_table_names()
    
    print(f"✅ Tablas creadas: {', '.join(tablas)}")
    print(f"📊 Total: {len(tablas)} tablas")
    
    # Contar registros
    session = get_db_session()
    try:
        tour_count = session.query(Tour).count()
        user_count = session.query(Usuario).count()
        print(f"\n📈 Registros actuales:")
        print(f"   - Tours: {tour_count}")
        print(f"   - Usuarios: {user_count}")
    finally:
        session.close()
