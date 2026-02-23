import hashlib
import os
from cryptography.fernet import Fernet
from database import get_db_connection

# Inicializar Fernet
FERNET_KEY = os.getenv("ENCRYPTION_KEY").encode()
cipher_suite = Fernet(FERNET_KEY)

def generar_hash_dni(dni):
    """Búsqueda rápida (No reversible)"""
    salt = "COSMIN_SECRET_2026"
    return hashlib.sha256((dni + salt).encode()).hexdigest()

def cifrar_dato(dato):
    """Cifrado reversible para recuperación de datos"""
    if not dato: return None
    return cipher_suite.encrypt(dato.encode())

def descifrar_dato(dato_cifrado):
    """Descifrado para mostrar en el Panel de Admin"""
    if not dato_cifrado: return None
    return cipher_suite.decrypt(dato_cifrado).decode()

# Ejemplo de cómo usarlo al guardar un pasajero:
def guardar_pasajero_seguro(id_expediente, nombre, dni):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    dni_cifrado = cifrar_dato(dni)       # Para recuperar (Fernet)
    dni_hash = generar_hash_dni(dni)    # Para buscar (SHA256)
    
    sql = """
        INSERT INTO pasajeros (id_expediente, nombre_completo, dni_pasaporte_encriptado, dni_blind_index)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(sql, (id_expediente, nombre, dni_cifrado, dni_hash))
    conn.commit()
    conn.close()