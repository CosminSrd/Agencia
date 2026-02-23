import os
import sys
import psycopg2
from dotenv import load_dotenv

# Add parent dir to path to import core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.security import cifrar

load_dotenv()

DB_CONFIG = {
    'host': os.getenv("DB_HOST", "localhost"),
    'port': int(os.getenv("DB_PORT", "5432")),
    'user': os.getenv("DB_USER", "agencia_user"),
    'password': os.getenv("DB_PASSWORD", "agencia_password"),
    'dbname': os.getenv("DB_NAME", "agencia_viajes")
}

def agregar_credencial():
    print("--- 🔐 GESTOR DE CREDENCIALES (UNIFICADO) ---")
    
    nombre = input("Nombre del Portal: ")
    url = input("URL de Login: ")
    usuario = input("Usuario / Email: ")
    password = input("Contraseña: ")

    # Cifrado usando el módulo unificado (Bytes)
    usuario_cifrado = cifrar(usuario)
    password_cifrada = cifrar(password)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        sql = """
            INSERT INTO proveedores_credenciales 
            (nombre_portal, url_login, usuario_encriptado, password_encriptado) 
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (nombre, url, usuario_cifrado, password_cifrada))
        conn.commit()
        print(f"\n✅ Credenciales de '{nombre}' cifradas y guardadas con éxito.")
        
    except Exception as e:
        print(f"\n❌ Error al guardar: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    agregar_credencial()
