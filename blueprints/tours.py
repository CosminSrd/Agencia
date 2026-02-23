"""
Blueprint para rutas de tours
"""

from flask import Blueprint, request, jsonify
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

tours_bp = Blueprint('tours', __name__, url_prefix='/api/tours')


def init_tours_blueprint(limiter):
    """Inicializa el blueprint con dependencias"""
    
    @tours_bp.route('/buscar', methods=['GET'])
    def buscar_tours():
        """Búsqueda y filtrado de tours"""
        try:
            from database import Tour, get_db_session
            from sqlalchemy import func, or_
            
            session = get_db_session()
            
            # Parámetros de búsqueda
            query_text = request.args.get('q', '').strip()
            continente = request.args.get('continente')
            pais = request.args.get('pais')
            categoria = request.args.get('categoria')
            tipo_viaje = request.args.get('tipo_viaje')
            precio_min = request.args.get('precio_min', type=float)
            precio_max = request.args.get('precio_max', type=float)
            destacados = request.args.get('destacados', '').lower() == 'true'
            
            # Paginación
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            # Query base
            query = session.query(Tour).filter_by(activo=True)
            
            # Aplicar filtros
            if query_text:
                query = query.filter(
                    or_(
                        Tour.titulo.ilike(f'%{query_text}%'),
                        Tour.descripcion.ilike(f'%{query_text}%'),
                        Tour.destino.ilike(f'%{query_text}%')
                    )
                )
            
            if continente:
                query = query.filter_by(continente=continente)
            
            if pais:
                query = query.filter_by(pais=pais)
            
            if categoria:
                query = query.filter_by(categoria=categoria)
            
            if tipo_viaje:
                query = query.filter_by(tipo_viaje=tipo_viaje)
            
            if precio_min:
                query = query.filter(Tour.precio_desde >= precio_min)
            
            if precio_max:
                query = query.filter(Tour.precio_desde <= precio_max)
            
            if destacados:
                query = query.filter_by(destacado=True)
            
            # Ordenamiento
            order_by = request.args.get('order_by', 'popularidad')
            if order_by == 'precio_asc':
                query = query.order_by(Tour.precio_desde.asc())
            elif order_by == 'precio_desc':
                query = query.order_by(Tour.precio_desde.desc())
            elif order_by == 'popularidad':
                query = query.order_by(Tour.num_solicitudes.desc(), Tour.destacado.desc())
            else:
                query = query.order_by(Tour.fecha_creacion.desc())
            
            # Paginación
            total = query.count()
            tours = query.offset((page - 1) * per_page).limit(per_page).all()
            
            session.close()
            
            return jsonify({
                'tours': [tour.to_dict() for tour in tours],
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"❌ Error en búsqueda de tours: {e}")
            return jsonify({'error': str(e)}), 500
    
    @tours_bp.route('/<int:tour_id>/completo', methods=['GET'])
    def obtener_tour_completo(tour_id):
        """Obtener detalles completos de un tour"""
        try:
            from database import Tour, get_db_session
            
            session = get_db_session()
            tour = session.query(Tour).get(tour_id)
            
            if not tour:
                session.close()
                return jsonify({'error': 'Tour no encontrado'}), 404
            
            # Incrementar contador de visitas
            tour.num_visitas += 1
            session.commit()
            
            resultado = tour.to_dict(include_salidas=True)
            session.close()
            
            return jsonify(resultado)
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo tour: {e}")
            return jsonify({'error': str(e)}), 500
    
    @tours_bp.route('/destacados', methods=['GET'])
    def obtener_destacados():
        """Obtener tours destacados"""
        try:
            from database import Tour, get_db_session
            
            session = get_db_session()
            tours = session.query(Tour).filter_by(activo=True, destacado=True).order_by(Tour.num_solicitudes.desc()).limit(10).all()
            session.close()
            
            return jsonify([tour.to_dict() for tour in tours])
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo destacados: {e}")
            return jsonify({'error': str(e)}), 500
    
    @tours_bp.route('/reservar', methods=['POST'])
    @limiter.limit("10 per minute")
    def reservar_tour():
        """Crear solicitud de reserva de tour"""
        try:
            from database import SolicitudTour, Tour, get_db_session
            from core.email_service import email_service
            
            data = request.json
            session = get_db_session()
            
            # Crear solicitud
            solicitud = SolicitudTour(
                tour_id=data.get('tour_id'),
                nombre=data.get('nombre'),
                apellidos=data.get('apellidos'),
                email=data.get('email'),
                telefono=data.get('telefono'),
                num_personas=data.get('num_personas'),
                mensaje=data.get('mensaje'),
                estado='nueva'
            )
            
            session.add(solicitud)
            session.commit()
            
            # Obtener tour para email
            tour = session.query(Tour).get(data.get('tour_id'))
            
            if tour:
                # Incrementar contador
                tour.num_solicitudes += 1
                session.commit()
                
                # Enviar emails
                try:
                    email_service.enviar_solicitud_proveedor(solicitud, tour)
                except Exception as e:
                    logger.error(f"Error enviando email: {e}")
            
            session.close()
            
            return jsonify({'success': True, 'solicitud_id': solicitud.id})
            
        except Exception as e:
            logger.error(f"❌ Error creando solicitud: {e}")
            return jsonify({'error': str(e)}), 500
    
    return tours_bp
