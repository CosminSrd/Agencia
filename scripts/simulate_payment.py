
import requests
import json
import time
import os
from datetime import datetime

# URL local
BASE_URL = 'http://127.0.0.1:8000'

# Payload simulado de Stripe
def simulate_webhook_payment(reserva_id):
    # Construir payload manual ya que no podemos firmarlo correctamente sin la secret key real de Stripe usada para firmar
    # Pero el endpoint valida la firma. 
    # Mmm, si el endpoint valida la firma con `stripe.Webhook.construct_event`, no podemos falsificarla fácilmente sin la signing secret.
    
    # OPCIÓN ALTERNATIVA:
    # Usar un script Python que importe 'app' y llame a la lógica interna, 
    # O parchear temporalmente la validación de firma en app.py (no recomendado),
    # O usar stripe CLI.
    
    # Mejor opción: Script que emula lo que hace el webhook pero llamando a las funciones directamente.
    pass

if __name__ == "__main__":
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    from app import app
    from database import get_db_session, ReservaVuelo
    from core.scraper_motor import MotorBusqueda
    
    print("🚀 Iniciando simulación de confirmación de pago...")
    
    session = get_db_session()
    try:
        # Buscar la última reserva pendiente
        reserva = session.query(ReservaVuelo).filter_by(estado='PENDIENTE').order_by(ReservaVuelo.id.desc()).first()
        
        if not reserva:
            print("⚠️ No hay reservas pendientes para procesar.")
            exit()
            
        print(f"📋 Procesando reserva: {reserva.codigo_reserva} (ID: {reserva.id})")
        print(f"💰 Precio: {reserva.precio_total}€")
        
        # Simular pago exitoso
        reserva.estado = 'PAGADO'
        reserva.stripe_payment_intent_id = 'pi_simulated_' + str(int(time.time()))
        reserva.fecha_pago = datetime.now()
        session.commit()
        print("✅ Estado actualizado a PAGADO en BD")
        
        # Simular emisión de billetes Duffel
        print("🎫 Emitiendo billetes con Duffel API...")
        pasajeros_data = json.loads(reserva.pasajeros)
        motor = MotorBusqueda()
        
        # NOTA: Esto hará una llamada REAL a Duffel. 
        # Asegurarse que el offer_id sigue siendo válido (expiran en 20-30 mins).
        resultado = motor.crear_order_duffel(
            offer_id=reserva.offer_id_duffel,
            pasajeros_data=pasajeros_data
        )
        
        if resultado['success']:
            reserva.order_id_duffel = resultado['order_id']
            reserva.estado = 'CONFIRMADO'
            reserva.fecha_confirmacion = datetime.now()
            reserva.notas = f"Booking Ref: {resultado['booking_reference']}"
            session.commit()
            print(f"✅ ÉXITO TOTAL: Billetes emitidos. Ref: {resultado['booking_reference']}")
        else:
            reserva.estado = 'ERROR'
            reserva.error_mensaje = resultado['error']
            session.commit()
            print(f"❌ ERROR DUFFEL: {resultado['error']}")
            
    except Exception as e:
        print(f"❌ Error crítico: {e}")
    finally:
        session.close()
