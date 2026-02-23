import requests
import xml.etree.ElementTree as ET
import sqlite3
import html
import os
import time
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ==========================================
# 🔐 CREDENCIALES SEGURAS DESDE .ENV
# ==========================================
NEGO_USER = os.getenv("NEGOPLANET_USER")
NEGO_PASS = os.getenv("NEGOPLANET_PASS")

# Validación crítica
if not NEGO_USER or not NEGO_PASS:
    print("❌ ERROR: Credenciales de NegoPlanet no configuradas en .env")
    sys.exit(1)

print(f"✅ Credenciales NegoPlanet cargadas para usuario: {NEGO_USER}")
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'viatges.db')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def limpiar_texto(texto):
    if not texto: return ""
    # Decodificamos y limpiamos HTML básico
    txt = html.unescape(texto)
    tags = ['<h2>', '</h2>', '<p>', '</p>', '<strong>', '</strong>', '<br>', '<br />']
    for tag in tags:
        txt = txt.replace(tag, '\n')
    return txt.strip()

def request_segura(url):
    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200: 
            print(f"⚠️ Error HTTP {response.status_code} en: {url}")
            return None
        
        content = response.text.strip()
        if content.startswith('\ufeff'): content = content[1:]
        content = content.replace('& ', '&amp; ')
        
        try:
            return ET.fromstring(content)
        except:
            return ET.fromstring(content.encode('utf-8'))
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout al conectar con: {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de red: {e}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def sincronizar_todo():
    print(f"🚀 INICIANDO SINCRONIZACIÓN TOTAL DE NEGOPLANET")
    print(f"📂 Base de datos: {DB_FILE}")

    viajes_totales = []

    # --- FASE 1: OBTENER LISTA DE PAÍSES ---
    print("\n🌍 1. Obteniendo catálogo de países...")
    url_paises = f"https://www.negoplanet.com/nego-xml/destinos/?tipo=destino&usuario={NEGO_USER}&pass={NEGO_PASS}"
    root_paises = request_segura(url_paises)
    
    lista_paises = []
    if root_paises is not None:
        for dest in root_paises.findall('.//destino'):
            nombre = dest.find('post_title')
            if nombre is not None and nombre.text:
                lista_paises.append(nombre.text.strip())
    
    # Eliminamos duplicados y vacíos
    lista_paises = sorted(list(set(filter(None, lista_paises))))
    print(f"📋 Catálogo encontrado: {len(lista_paises)} países.")

    if len(lista_paises) == 0:
        print("❌ No se encontraron países. Verifica tus credenciales.")
        return

    # --- FASE 2: BARRIDO MUNDIAL ---
    print("\n✈️ 2. Descargando viajes por país (Esto tardará unos minutos)...")
    
    # Barra de progreso visual simple
    total = len(lista_paises)
    
    for i, pais in enumerate(lista_paises):
        # Feedback visual de progreso
        porcentaje = int((i / total) * 100)
        sys.stdout.write(f"\r⏳ Progreso: [{porcentaje}%] Escaneando: {pais:<20}")
        sys.stdout.flush()

        url = f"https://www.negoplanet.com/nego-xml/buscar-programas/?pais={pais}&usuario={NEGO_USER}&pass={NEGO_PASS}"
        root = request_segura(url)
        
        if root is not None:
            programas = root.findall('.//programa')
            if not programas: programas = root.findall('.//item') # Soporte legacy

            for prog in programas:
                try:
                    titulo = prog.find('post_title').text
                    if not titulo: continue

                    # Descripción
                    desc_node = prog.find('post_excerpt')
                    if desc_node is None or not desc_node.text:
                        desc_node = prog.find('itinerario')
                    descripcion = limpiar_texto(desc_node.text if desc_node is not None else "")

                    # Precio
                    precio = 0.0
                    precio_node = prog.find('preciosimple')
                    if precio_node is not None and precio_node.text:
                        try:
                            nums = ''.join(c for c in precio_node.text if c.isdigit() or c == '.')
                            if nums: precio = float(nums)
                        except: pass

                    # Imagen
                    img_url = "https://via.placeholder.com/800x600?text=Viatges+Carcaixent"
                    imagenes = prog.find('imagenes')
                    if imagenes is not None and len(imagenes) > 0:
                        for child in imagenes[0]:
                            if child.tag in ['large', 'url'] and child.text:
                                img_url = child.text
                                break
                    
                    # Duración
                    dias = "Consultar"
                    dias_node = prog.find('dias')
                    if dias_node is not None and dias_node.text: dias = dias_node.text

                    # Evitar duplicados por título
                    if not any(v[0] == titulo for v in viajes_totales):
                        viajes_totales.append((
                            titulo, pais, precio, img_url, dias, descripcion, 'negoplanet', 1, 0
                        ))
                except Exception as e:
                    print(f"\n⚠️ Error procesando un viaje: {e}")
                    continue
        
        # Pausa muy pequeña para no saturar
        time.sleep(0.1)

    print(f"\n\n📦 3. Procesamiento finalizado. Total viajes encontrados: {len(viajes_totales)}")

    # --- FASE 3: GUARDADO ---
    if viajes_totales:
        print("💾 Guardando en base de datos...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Borramos SOLO los de NegoPlanet anteriores
        cursor.execute("DELETE FROM destinos WHERE proveedor = 'negoplanet'")
        print(f"🗑️ Eliminados {cursor.rowcount} viajes antiguos de NegoPlanet")
        
        sql = """INSERT INTO destinos 
                 (nombre, destino_pais, precio, imagen_url, duracion, descripcion, proveedor, destacado, oferta_flash) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        
        cursor.executemany(sql, viajes_totales)
        conn.commit()
        
        print(f"✅ {len(viajes_totales)} viajes insertados correctamente")
        conn.close()
        print("✅ ¡TODO LISTO! Base de datos actualizada con éxito.")
    else:
        print("⚠️ No se encontraron viajes. Revisa tus credenciales o la disponibilidad de la API.")

if __name__ == "__main__":
    try:
        sincronizar_todo()
    except KeyboardInterrupt:
        print("\n\n⚠️ Sincronización interrumpida por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)