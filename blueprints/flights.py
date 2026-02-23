"""
Blueprint para rutas de vuelos (API Duffel)
"""

from flask import Blueprint, request, jsonify
from decimal import Decimal
import logging
import json
from datetime import datetime
from core.autocomplete_i18n import construir_terminos_busqueda, buscar_fallback_es

logger = logging.getLogger(__name__)

flights_bp = Blueprint('flights', __name__, url_prefix='/api/vuelos')


def init_flights_blueprint(motor_busqueda, limiter):
    """Inicializa el blueprint con dependencias"""
    
    @flights_bp.route('/autocomplete', methods=['GET'])
    @limiter.limit("30 per minute")
    def autocomplete():
        """Autocompletado de aeropuertos"""
        termino_raw = request.args.get('term', '').strip()
        termino = termino_raw.lower()
        
        if not termino or len(termino) < 2:
            return jsonify([])

        search_terms = construir_terminos_busqueda(termino)

        for term in search_terms:
            try:
                logger.info(f"🔮 Autocomplete API: Intentando buscar '{term}' con Duffel...")
                sugerencias = motor_busqueda.autocompletar_aeropuerto(term)
                logger.info(f"🔮 Duffel devolvió: {len(sugerencias) if sugerencias else 0} resultados")
                
                if sugerencias:
                    return jsonify(sugerencias)
            except Exception as e:
                logger.error(f"❌ Error en Autocomplete API: {e}")
        
        # Fallback local mejorado (ES/EN)
        resultados_fallback = buscar_fallback_es(termino)
        return jsonify(resultados_fallback)
    
    @flights_bp.route('/buscar', methods=['POST'])
    @limiter.limit("10 per minute")
    def buscar_vuelos():
        """Búsqueda de vuelos"""
        try:
            data = request.json
            logger.info(f"🔎 Buscando vuelos: {data.get('origen')} -> {data.get('destino')} para el {data.get('fecha')}")
            
            resultados = motor_busqueda.buscar_vuelos(
                data.get('origen'),
                data.get('destino'),
                data.get('fecha'),
                adultos=data.get('adultos', 1),
                ninos=data.get('ninos', 0),
                bebes=data.get('bebes', 0),
                clase=data.get('clase', 'economy')
            )
            return jsonify(resultados)
        except Exception as e:
            logger.error(f"❌ Error crítico en API Búsqueda: {e}")
            return jsonify([]), 500
    
    @flights_bp.route('/asientos/<offer_id>', methods=['GET'])
    def obtener_asientos(offer_id):
        """Obtener mapa de asientos"""
        try:
            asientos = motor_busqueda.get_seat_maps(offer_id)
            
            if asientos:
                return jsonify({'success': True, 'data': asientos})
            else:
                return jsonify({'success': False, 'error': 'No se pudo obtener el mapa de asientos'}), 404
        except Exception as e:
            logger.error(f"❌ Error en API Asientos: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flights_bp.route('/detalles/<offer_id>', methods=['GET'])
    def obtener_detalles(offer_id):
        """Obtener detalles completos del vuelo"""
        try:
            detalles = motor_busqueda.get_offer_details(offer_id)
            
            if detalles:
                return jsonify({'success': True, 'data': detalles})
            else:
                return jsonify({'success': False, 'error': 'No se pudieron obtener detalles'}), 404
        except Exception as e:
            logger.error(f"❌ Error endpoint detalles vuelo: {e}")
            return jsonify({'error': str(e)}), 500
    
    @flights_bp.route('/crear-reserva', methods=['POST'])
    @limiter.limit("5 per minute")
    def crear_reserva():
        """Crear pre-reserva de vuelo"""
        try:
            from database import ReservaVuelo, get_db_session
            import secrets
            
            data = request.json
            session = get_db_session()
            
            # Generar código único
            codigo_reserva = f"VGT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
            
            nueva_reserva = ReservaVuelo(
                codigo_reserva=codigo_reserva,
                offer_id_duffel=data.get('offer_id'),
                pasajeros=json.dumps(data.get('pasajeros')),
                datos_vuelo=json.dumps(data.get('datos_vuelo')),
                precio_total=Decimal(str(data.get('precio_total'))),
                email_cliente=data.get('email_cliente'),
                telefono_cliente=data.get('telefono_cliente'),
                es_viaje_redondo=data.get('es_viaje_redondo', False),
                estado='PENDIENTE'
            )
            
            session.add(nueva_reserva)
            session.commit()
            
            reserva_id = nueva_reserva.id
            session.close()
            
            logger.info(f"✅ Pre-reserva creada: {codigo_reserva} (ID: {reserva_id})")
            
            return jsonify({
                'success': True,
                'reserva_id': reserva_id,
                'codigo_reserva': codigo_reserva
            })
            
        except Exception as e:
            logger.error(f"❌ Error creando reserva: {e}")
            return jsonify({'error': str(e)}), 500
    
    @flights_bp.route('/payment-intent', methods=['POST'])
    def crear_payment_intent():
        """Crear Payment Intent en Duffel"""
        try:
            data = request.json
            amount = data.get('amount')
            currency = data.get('currency')
            
            if not amount or not currency:
                return jsonify({'error': 'Monto y moneda requeridos'}), 400
            
            resultado = motor_busqueda.crear_payment_intent(Decimal(str(amount)), currency)
            
            if resultado and resultado.get('success'):
                data_intent = resultado['data']
                intent_id = data_intent['id']
                
                # Guardar ID en la reserva
                reserva_id = data.get('reserva_id')
                if reserva_id:
                    from database import ReservaVuelo, get_db_session
                    session = get_db_session()
                    reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()
                    if reserva:
                        reserva.stripe_payment_intent_id = intent_id
                        session.commit()
                    session.close()
                
                return jsonify({'success': True, 'client_token': data_intent['client_token'], 'id': intent_id})
            else:
                error_msg = resultado.get('error') if resultado else 'Error desconocido creando Payment Intent'
                return jsonify({'success': False, 'error': error_msg}), 400
                
        except Exception as e:
            logger.error(f"❌ Error payment-intent endpoint: {e}")
            return jsonify({'error': str(e)}), 500
    
    return flights_bp
