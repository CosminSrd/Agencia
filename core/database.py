import os
import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

load_dotenv()

# Construimos la URL de conexión
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# --- MOTOR DE ALTO RENDIMIENTO (SQLAlchemy) ---
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=50,          # 50 Conexiones fijas
    max_overflow=50,       # 50 Conexiones extra (Total 100)
    pool_timeout=30,       # Tiempo de espera
    pool_recycle=1800      # Reciclaje cada 30 min
)

print(f"✅ Motor SQLAlchemy (Adapter Mode): 100 Conexiones listas.")

# --- CLASE ADAPTADORA (EL TRADUCTOR) ---
# Esta clase hace que PyMySQL se comporte igual que tu código antiguo.
class ConnectionAdapter:
    def __init__(self, connection):
        self._conn = connection

    def cursor(self, dictionary=False, buffered=None, **kwargs):
        # TRUCO: Si tu código pide 'dictionary=True', nosotros se lo damos
        # usando la forma que PyMySQL entiende (DictCursor)
        if dictionary:
            return self._conn.cursor(pymysql.cursors.DictCursor)
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def is_connected(self):
        # TRUCO: Traducimos la llamada antigua a la nueva propiedad .open
        # Así 'app.py' no se rompe al preguntar.
        return self._conn.open

    # Cualquier otra cosa que pidas, se la pasamos al motor real
    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db_connection():
    try:
        # 1. Pedimos conexión rápida a SQLAlchemy
        raw_conn = engine.raw_connection()
        # 2. La envolvemos en el Traductor antes de entregarla
        return ConnectionAdapter(raw_conn)
    except Exception as e:
        print(f"⚠️ CRÍTICO: Error obteniendo conexión: {e}")
        raise e