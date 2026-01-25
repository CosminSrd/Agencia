import os
import stripe
import json
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, Response, send_from_directory
from dotenv import load_dotenv

# IMPORTACIONES DE TU ARQUITECTURA
try:
    from core.database import get_db_connection
    from core.matrix_adapter import MatrixOrchestrator
    from core.tasks import lanzar_tarea_venta, generar_hash_dni
    print("✅ Módulos core cargados y Blind Index listo")
except ImportError as e:
    print(f"❌ ERROR: No se encuentran los módulos en /core: {e}")
    exit()

load_dotenv()
app = Flask(__name__)

# Configuración de Stripe y Seguridad
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
encryption_key = os.getenv("ENCRYPTION_KEY")
orchestrator = MatrixOrchestrator()

# --- SEGURIDAD ADMIN ---
def check_auth(username, password):
    return username == 'admin' and password == 'cosmin'

def authenticate():
    return Response('Acceso denegado', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password): return authenticate()
        return f(*args, **kwargs)
    return decorated

# ==========================================
# RUTAS PÚBLICAS
# ==========================================

@app.route('/')
def home():
    # Obtenemos el catálogo unificado (Local + APIs)
    viajes_dict = orchestrator.obtener_catalogo_unificado()
    # Convertimos a lista para el index.html
    viajes_lista = [[v['id_viaje'], v['nombre'], v['descripcion'], v['precio'], v['url_imagen']] for v in viajes_dict]
    return render_template('index.html', viajes=viajes_lista)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    id_viaje = request.form.get('id_viaje')
    nombres = request.form.getlist('nombres[]')
    dnis = request.form.getlist('dnis[]')
    
    # Buscamos el viaje en el orquestador
    viaje = orchestrator.obtener_detalle_viaje(id_viaje)
    if not viaje: 
        print(f"⚠️ Error: Viaje ID {id_viaje} no encontrado.")
        return "Error: El viaje no existe."

    pasajeros = [{'nombre': n, 'dni': d} for n, d in zip(nombres, dnis)]
    
    try:
        s = stripe.checkout.Session.create(
            line_items=[{
                'price_data': {
                    'currency': 'eur', 
                    'product_data': {'name': viaje['nombre']}, 
                    'unit_amount': int(float(viaje['precio'])*100)
                }, 
                'quantity': len(pasajeros)
            }],
            mode='payment',
            success_url='http://localhost:4242/success',
            cancel_url='http://localhost:4242/cancel',
            metadata={
                'concepto': viaje['nombre'],
                'json_pasajeros': json.dumps(pasajeros),
                'fuente': viaje.get('fuente_datos', 'LOCAL'),
                'email_prov': viaje.get('email_confirmacion_proveedor', '')
            }
        )
        return redirect(s.url, code=303)
    except Exception as e:
        print(f"❌ Error Stripe: {e}")
        return str(e)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig = request.headers.get('STRIPE_SIGNATURE')
    try:
        event = stripe.Webhook.construct_event(payload, sig, endpoint_secret)
    except Exception as e: return str(e), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        meta = session.get('metadata', {})
        pasajeros = json.loads(meta.get('json_pasajeros', '[]'))
        
        email = session['customer_details']['email']
        pagador = session['customer_details']['name']
        total = session['amount_total'] / 100

        conn = None  # Inicializamos la variable
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 1. Guardar Cliente
            cursor.execute("INSERT INTO clientes (nombre_razon_social, email) VALUES (%s, %s)", (pagador, email))
            id_c = cursor.lastrowid
            
            # 2. Guardar Pasajeros con BLIND INDEX
            for p in pasajeros:
                hash_dni = generar_hash_dni(p['dni'])
                cursor.execute("""
                    INSERT INTO pasajeros (id_cliente_vinculado, nombre_completo, dni_pasaporte_encriptado, dni_blind_index) 
                    VALUES (%s, %s, AES_ENCRYPT(%s, %s), %s)
                """, (id_c, p['nombre'], p['dni'], encryption_key, hash_dni))

            # 3. Crear Expediente
            id_exp_cod = f"EXP-{datetime.now().strftime('%Y%m%d')}-{id_c}"
            cursor.execute("INSERT INTO expedientes (codigo_expediente, id_cliente_titular, estado, total_venta) VALUES (%s, %s, 'CONFIRMADO', %s)", (id_exp_cod, id_c, total))
            id_e = cursor.lastrowid
            
            # 4. Crear Factura
            num_f = f"F-{datetime.now().strftime('%Y')}-{id_e}"
            cursor.execute("INSERT INTO facturas (id_expediente, numero_factura, url_archivo_pdf, total_factura) VALUES (%s, %s, 'PENDIENTE', %s)", (id_e, num_f, total))
            
            conn.commit()
            
            # Lanzar tarea solo si la DB guardó bien
            lanzar_tarea_venta(email, pagador, pasajeros, total, meta.get('concepto'), id_e, num_f, meta.get('fuente'), meta.get('email_prov'))

        except Exception as e:
            print(f"❌ Error crítico en Webhook DB: {e}")
            if conn: conn.rollback() # Deshacer si hubo fallo a medias
            return str(e), 500
        finally:
            # CIERRE DE SEGURIDAD: Esto evita el 'Pool Exhausted'
            if conn and conn.is_connected():
                conn.close()

    return jsonify(success=True)

# ==========================================
# RUTAS ADMIN
# ==========================================

@app.route('/admin')
@requires_auth
def admin():
    busqueda = request.args.get('q', '') 
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = f"""SELECT f.fecha_emision as fecha, e.codigo_expediente as codigo, c.nombre_razon_social as pagador,
                p.nombre_completo as pasajero, CAST(AES_DECRYPT(p.dni_pasaporte_encriptado, '{encryption_key}') AS CHAR) as dni,
                f.total_factura as total, f.url_archivo_pdf as factura, f.numero_factura as num_factura
                FROM facturas f
                JOIN expedientes e ON f.id_expediente = e.id_expediente
                JOIN clientes c ON e.id_cliente_titular = c.id_cliente
                JOIN pasajeros p ON c.id_cliente = p.id_cliente_vinculado"""
        
        if busqueda:
            # BÚSQUEDA OPTIMIZADA CON HASH PARA DNI
            hash_busq = generar_hash_dni(busqueda)
            sql += " WHERE p.dni_blind_index = %s OR c.nombre_razon_social LIKE %s OR p.nombre_completo LIKE %s"
            cursor.execute(sql, (hash_busq, f"%{busqueda}%", f"%{busqueda}%"))
        else:
            cursor.execute(sql + " ORDER BY f.fecha_emision DESC")
        
        filas = cursor.fetchall()
        
        ventas = {}
        for f in filas:
            if f['num_factura'] not in ventas:
                ventas[f['num_factura']] = {'fecha': f['fecha'], 'codigo': f['codigo'], 'pagador': f['pagador'], 'total': f['total'], 'factura': f['factura'], 'pasajeros': []}
            ventas[f['num_factura']]['pasajeros'].append({'nombre': f['pasajero'], 'dni': f['dni']})
            
        return render_template('admin.html', ventas=ventas.values(), busqueda=busqueda)
    
    except Exception as e:
        return f"Error de conexión: {e}", 500
    finally:
        # CIERRE DE SEGURIDAD
        if conn and conn.is_connected():
            conn.close()

@app.route('/descargar/<path:filename>')
@requires_auth
def descargar(filename):
    return send_from_directory('.', filename, as_attachment=True)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/cancel')
def cancel():
    return "<h1>Cancelado</h1><a href='/'>Volver</a>"

if __name__ == '__main__':
    app.run(port=4242, debug=True)