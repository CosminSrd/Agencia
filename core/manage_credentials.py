import os
import mysql.connector
from dotenv import load_dotenv

# Cargar configuración
load_dotenv()
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME")
}
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

def agregar_credencial():
    print("--- 🔐 GESTOR DE CREDENCIALES SEGURAS ---")
    
    # 1. Pedir datos
    nombre = input("Nombre del Portal (ej: NipponTravel): ")
    url = input("URL de Login (ej: https://portal.proveedor.com/login): ")
    usuario = input("Usuario / Email de acceso: ")
    password = input("Contraseña: ")

    # 2. Conectar y Guardar
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Usamos AES_ENCRYPT para que la contraseña nunca sea legible en la DB
        sql = """
            INSERT INTO proveedores_credenciales 
            (nombre_portal, url_login, usuario_encriptado, password_encriptado) 
            VALUES (%s, %s, AES_ENCRYPT(%s, %s), AES_ENCRYPT(%s, %s))
        """
        
        cursor.execute(sql, (nombre, url, usuario, ENCRYPTION_KEY, password, ENCRYPTION_KEY))
        conn.commit()
        
        print(f"\n✅ ¡Éxito! Las credenciales de '{nombre}' han sido cifradas y guardadas.")
        
    except Exception as e:
        print(f"\n❌ Error al guardar: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    agregar_credencial()