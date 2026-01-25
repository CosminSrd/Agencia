import mysql.connector
import os
from dotenv import load_dotenv

# 1. Cargar configuración
load_dotenv()
clave_secreta = os.getenv("ENCRYPTION_KEY")

DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME")
}

def prueba_blindaje():
    print("🛡️ INICIANDO PROTOCOLO DE SEGURIDAD...")
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # --- PARTE A: INSERTAR (ENCRIPTANDO) ---
    # Simulamos que el cliente 1 (que creaste antes) va a viajar
    # IMPORTANTE: Usamos AES_ENCRYPT(DATO, CLAVE)
    print("\n1️⃣  Guardando DNI '12345678Z' en la caja fuerte...")
    
    sql_insertar = """
        INSERT INTO pasajeros 
        (id_cliente_vinculado, nombre_completo, fecha_nacimiento, dni_pasaporte_encriptado, fecha_caducidad_doc) 
        VALUES (%s, %s, %s, AES_ENCRYPT(%s, %s), %s)
    """
    
    # Datos simulados del pasajero
    datos = (
        1,                         # ID del Cliente (Asumimos que el 1 existe por tu prueba anterior)
        "Cosmin Pasajero",         # Nombre
        "1990-05-20",              # Fecha Nacimiento
        "12345678Z",               # EL DNI REAL (Se encriptará al entrar)
        clave_secreta,             # LA LLAVE (Para cerrar el candado)
        "2030-01-01"               # Caducidad
    )

    try:
        cursor.execute(sql_insertar, datos)
        conn.commit()
        print("✅ DNI guardado bajo llave AES-256.")
    except mysql.connector.Error as err:
        print(f"❌ Error (¿Quizás no existe el cliente 1?): {err}")
        return

    # --- PARTE B: EL HACKER (INTENTO DE ROBO) ---
    # Vamos a ver qué pasa si alguien hace un SELECT normal sin la llave
    print("\n2️⃣  Simulando mirada de un Hacker (SELECT sin clave)...")
    cursor.execute("SELECT nombre_completo, dni_pasaporte_encriptado FROM pasajeros ORDER BY id_pasajero DESC LIMIT 1")
    resultado = cursor.fetchone()
    
    print(f"   Nombre: {resultado[0]}")
    print(f"   DNI Robado: {resultado[1]}") 
    print("   (¿Ves símbolos raros? ¡Eso es que está encriptado!)")

    # --- PARTE C: NOSOTROS (LECTURA AUTORIZADA) ---
    # Ahora usamos la llave para leerlo
    print("\n3️⃣  Lectura autorizada (SELECT con AES_DECRYPT)...")
    
    sql_leer = """
        SELECT nombre_completo, 
               CAST(AES_DECRYPT(dni_pasaporte_encriptado, %s) AS CHAR) 
        FROM pasajeros ORDER BY id_pasajero DESC LIMIT 1
    """
    cursor.execute(sql_leer, (clave_secreta,)) # Pasamos la llave
    resultado_limpio = cursor.fetchone()
    
    print(f"   Nombre: {resultado_limpio[0]}")
    print(f"   DNI Desencriptado: {resultado_limpio[1]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    prueba_blindaje()