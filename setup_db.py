import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}
DB_NAME = os.getenv("DB_NAME")

print("🔌 Conectando al servidor MySQL...")
conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

print(f"🧹 Reiniciando base de datos: {DB_NAME}...")
cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
cursor.execute(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4")
cursor.execute(f"USE {DB_NAME}")

# 1. TABLAS DE GESTIÓN DE VENTAS
print("👥 Creando tablas de clientes y pasajeros...")
cursor.execute("""
CREATE TABLE clientes (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    tipo VARCHAR(50), 
    nombre_razon_social VARCHAR(150), 
    nif_cif VARCHAR(20), 
    email VARCHAR(100)
)
""")

# OPTIMIZACIÓN: Añadimos dni_blind_index para búsquedas ultra rápidas
cursor.execute("""
CREATE TABLE pasajeros (
    id_pasajero INT AUTO_INCREMENT PRIMARY KEY,
    id_cliente_vinculado INT,
    nombre_completo VARCHAR(150),
    dni_pasaporte_encriptado BLOB,
    dni_blind_index VARCHAR(64),
    fecha_nacimiento DATE,
    fecha_caducidad_doc DATE
)
""")

# Creamos el índice para que MySQL encuentre el DNI sin procesar toda la tabla
cursor.execute("CREATE INDEX idx_dni_hash ON pasajeros(dni_blind_index)")

cursor.execute("""
CREATE TABLE expedientes (
    id_expediente INT AUTO_INCREMENT PRIMARY KEY,
    codigo_expediente VARCHAR(50), 
    id_cliente_titular INT, 
    estado VARCHAR(50), 
    total_venta DECIMAL(10,2)
)
""")

cursor.execute("""
CREATE TABLE facturas (
    id_factura INT AUTO_INCREMENT PRIMARY KEY,
    id_expediente INT, 
    numero_factura VARCHAR(50), 
    url_archivo_pdf VARCHAR(255),
    total_factura DECIMAL(10,2), 
    base_imponible DECIMAL(10,2), 
    impuestos DECIMAL(10,2),
    fecha_emision DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# 2. TABLA DE VIAJES
print("🌍 Creando catálogo de viajes...")
cursor.execute("""
CREATE TABLE viajes (
    id_viaje INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100),
    descripcion TEXT,
    precio DECIMAL(10,2),
    url_imagen VARCHAR(255),
    fuente_datos ENUM('LOCAL', 'API_PRINCIPAL', 'API_AUX', 'PORTAL_WEB') DEFAULT 'LOCAL',
    proveedor_id VARCHAR(50),
    email_confirmacion_proveedor VARCHAR(100)
)
""")

# 3. TABLA DE CREDENCIALES
print("🔐 Creando caja fuerte para proveedores...")
cursor.execute("""
CREATE TABLE proveedores_credenciales (
    id_credencial INT AUTO_INCREMENT PRIMARY KEY,
    nombre_portal VARCHAR(100),
    url_login VARCHAR(255),
    usuario_encriptado BLOB,
    password_encriptado BLOB
)
""")

# 4. INSERTAR DATOS DE EJEMPLO
viajes_ejemplo = [
    ('Escapada a París', 'Vuelo + Hotel 4*', 30.00, 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=400', 'API_PRINCIPAL', 'MATRIZ-001', 'reservas@matriz.com'),
    ('Aventura en Tokio', '10 días en Japón', 50.00, 'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400', 'PORTAL_WEB', 'NIPON-TRAVEL', 'booking@nippon.jp'),
    ('Relax en Roma', 'Ruta gastronómica', 45.00, 'https://images.unsplash.com/photo-1552832230-c0197dd311b5?w=400', 'LOCAL', 'INTERNO', 'cosmin@agencia.com')
]

sql = """INSERT INTO viajes 
         (nombre, descripcion, precio, url_imagen, fuente_datos, proveedor_id, email_confirmacion_proveedor) 
         VALUES (%s, %s, %s, %s, %s, %s, %s)"""
         
cursor.executemany(sql, viajes_ejemplo)

print("🚀 ¡Base de datos reconstruida y optimizada!")
conn.commit()
cursor.close()
conn.close()