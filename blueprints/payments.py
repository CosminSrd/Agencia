"""
Blueprint para rutas de pagos (Stripe)
"""

from flask import Blueprint, request, jsonify, url_for
import logging
import stripe
import os
import json
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

payments_bp = Blueprint('payments', __name__, url_prefix='/pagos')


def init_payments_blueprint(motor_busqueda, email_manager):
    """Inicializa el blueprint con dependencias"""
    
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    @payments_bp.route('/checkout-vuelos', methods=['POST'])
    def checkout_vuelos():
        """Crear sesión de pago Stripe para vuelo"""
        try:
            from database import ReservaVuelo, get_db_session
            
            data = request.json
            reserva_id = data.get('reserva_id')
            
            if not reserva_id:
                return jsonify({'error': 'reserva_id requerido'}), 400
            
            session = get_db_session()
            reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()
            
            if not reserva:
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404
            
            datos_vuelo = json.loads(reserva.datos_vuelo)
            pasajeros = json.loads(reserva.pasajeros)
            
            origen = datos_vuelo.get('origen', 'Origen')
            destino = datos_vuelo.get('destino', 'Destino')
            
            if reserva.es_viaje_redondo:
                nombre_producto = f"Vuelo Ida y Vuelta: {origen} ⇄ {destino}"
            else:
                nombre_producto = f"Vuelo: {origen} → {destino}"
            
            pasajero_principal = pasajeros[0]
            nombre_completo = f"{pasajero_principal.get('given_name', '')} {pasajero_principal.get('family_name', '')}"
            if len(pasajeros) > 1:
                nombre_completo += f" y {len(pasajeros) - 1} pasajero(s) más"
            
            descripcion = f"Reserva: {reserva.codigo_reserva}. Pasajeros: {nombre_completo}"
            
            # Crear Stripe Session
            stripe_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': nombre_producto,
                            'description': descripcion,
                            'images': ['https://cdn-icons-png.flaticon.com/512/2200/2200326.png'],
                        },
                        'unit_amount': int(float(reserva.precio_total) * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=url_for('success', reserva_id=reserva_id, _external=True),
                cancel_url=url_for('home', _external=True),
                metadata={
                    'tipo': 'VUELO_DUFFEL',
                    'reserva_id': str(reserva_id),
                    'codigo_reserva': reserva.codigo_reserva,
                    'offer_id_duffel': reserva.offer_id_duffel,
                    'email_cliente': reserva.email_cliente
                }
            )
            
            reserva.stripe_session_id = stripe_session.id
            session.commit()
            session.close()
            
            logger.info(f"✅ Stripe session creada para reserva {reserva.codigo_reserva}")
            
            return jsonify({'url': stripe_session.url})
            
        except Exception as e:
            logger.error(f"❌ Error checkout Duffel: {e}")
            return jsonify({'error': str(e)}), 500
    
    @payments_bp.route('/webhook', methods=['POST'])
    def stripe_webhook():
        """Webhook de Stripe para procesar eventos de pago"""
        payload = request.data
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            logger.error("⚠️ Webhook signature verification failed")
            return jsonify(success=False), 400
        except Exception as e:
            logger.error(f"⚠️ Webhook error: {e}")
            return jsonify(success=False), 400
        
        # Procesar evento
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            payment_status = session.get('payment_status')
            
            if payment_status != 'paid':
                return jsonify(success=False, error=f"Payment not completed: {payment_status}"), 400
            
            metadata = session.get('metadata', {})
            tipo_venta = metadata.get('tipo', 'PACK_PROPIO')
            
            logger.info(f"💰 PAGO RECIBIDO: {session['amount_total']/100}€ - TIPO: {tipo_venta}")
            
            # Manejo especial para vuelos Duffel
            if tipo_venta == 'VUELO_DUFFEL':
                try:
                    from database import ReservaVuelo, get_db_session
                    
                    reserva_id = int(metadata.get('reserva_id'))
                    db = get_db_session()
                    reserva = db.query(ReservaVuelo).filter_by(id=reserva_id).first()
                    
                    if not reserva:
                        logger.error(f"❌ Reserva {reserva_id} no encontrada")
                        db.close()
                        return jsonify(success=False, error='Reserva no encontrada'), 404
                    
                    # Actualizar estado
                    reserva.estado = 'PAGADO'
                    reserva.stripe_payment_intent_id = session.get('payment_intent')
                    reserva.fecha_pago = datetime.now()
                    db.commit()
                    
                    logger.info(f"✅ Reserva {reserva.codigo_reserva} marcada como PAGADA")
                    
                    # Crear Order en Duffel
                    pasajeros_data = json.loads(reserva.pasajeros)
                    resultado = motor_busqueda.crear_order_duffel(
                        offer_id=reserva.offer_id_duffel,
                        pasajeros_data=pasajeros_data
                    )
                    
                    if resultado['success']:
                        reserva.order_id_duffel = resultado['order_id']
                        reserva.estado = 'CONFIRMADO'
                        reserva.fecha_confirmacion = datetime.now()
                        reserva.notas = f"Booking Ref: {resultado['booking_reference']}"
                        db.commit()
                        
                        logger.info(f"🎫 Billetes emitidos para {reserva.codigo_reserva}: {resultado['booking_reference']}")
                        
                        # Enviar email con billetes
                        try:
                            email_manager.send_flight_tickets(reserva, resultado['order_data'])
                            logger.info(f"✅ Email de billetes enviado a {reserva.email_cliente}")
                        except Exception as e:
                            logger.error(f"❌ Error enviando email: {e}")
                    else:
                        reserva.estado = 'ERROR'
                        reserva.error_mensaje = resultado['error']
                        db.commit()
                        logger.error(f"❌ Error emitiendo billetes: {resultado['error']}")
                    
                    db.close()
                    return jsonify(success=True), 200
                    
                except Exception as e:
                    logger.error(f"❌ Error procesando pago Duffel: {e}")
                    return jsonify(success=False, error=str(e)), 500
        
        return jsonify(success=True), 200
    
    return payments_bp
