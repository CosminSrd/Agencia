"""
API Routes para Flight Scraper Service
"""

from flask import Blueprint, request, jsonify, current_app
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


@api_bp.route('/search', methods=['POST'])
def search_flights():
    """
    Buscar vuelos disponibles
    
    POST /api/search
    {
        "origin": "MAD",
        "destination": "BCN",
        "departure_date": "2024-06-15",
        "return_date": "2024-06-22",  // opcional
        "passengers": {
            "adults": 2,
            "children": 0,
            "infants": 0
        },
        "cabin_class": "economy"  // economy, premium_economy, business, first
    }
    """
    
    if not current_app.duffel:
        return jsonify({'error': 'Duffel API unavailable'}), 503
    
    data = request.get_json()
    
    # Validar datos requeridos
    required = ['origin', 'destination', 'departure_date', 'passengers']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields', 'required': required}), 400
    
    # Generar cache key
    cache_key = None
    if current_app.cache:
        cache_key = current_app.cache.generate_key('search', data)
        cached = current_app.cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for search: {cache_key}")
            return jsonify({
                'results': cached,
                'cache_hit': True,
                'source': 'cache'
            })
    
    # Buscar en Duffel API
    try:
        logger.info(f"Searching flights: {data['origin']} -> {data['destination']}")
        
        results = current_app.duffel.search_flights(
            origin=data['origin'],
            destination=data['destination'],
            departure_date=data['departure_date'],
            return_date=data.get('return_date'),
            passengers=data['passengers'],
            cabin_class=data.get('cabin_class', 'economy')
        )
        
        # Guardar en caché (5 minutos)
        if current_app.cache and cache_key:
            current_app.cache.set(cache_key, results, ttl=300)
        
        logger.info(f"Found {len(results.get('offers', []))} offers")
        
        return jsonify({
            'results': results,
            'cache_hit': False,
            'source': 'duffel_api'
        })
    
    except Exception as e:
        logger.error(f"Error searching flights: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/autocomplete', methods=['GET'])
def autocomplete():
    """
    Autocompletar aeropuertos
    
    GET /api/autocomplete?q=madrid
    """
    
    if not current_app.duffel:
        return jsonify({'error': 'Duffel API unavailable'}), 503
    
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    # Intentar desde caché
    if current_app.cache:
        cache_key = f"autocomplete:{query.lower()}"
        cached = current_app.cache.get(cache_key)
        if cached:
            return jsonify(cached)
    
    try:
        logger.info(f"Autocompleting: {query}")
        results = current_app.duffel.autocomplete_airports(query)
        
        # Cachear por 1 hora
        if current_app.cache:
            current_app.cache.set(cache_key, results, ttl=3600)
        
        return jsonify(results)
    
    except Exception as e:
        logger.error(f"Error in autocomplete: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/seats', methods=['GET'])
def get_seats():
    """
    Obtener asientos disponibles para una oferta
    
    GET /api/seats?offer_id=off_123abc
    """
    
    if not current_app.duffel:
        return jsonify({'error': 'Duffel API unavailable'}), 503
    
    offer_id = request.args.get('offer_id')
    
    if not offer_id:
        return jsonify({'error': 'offer_id required'}), 400
    
    try:
        logger.info(f"Fetching seats for offer: {offer_id}")
        seats = current_app.duffel.get_available_seats(offer_id)
        
        return jsonify(seats)
    
    except Exception as e:
        logger.error(f"Error getting seats: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/offers/<offer_id>', methods=['GET'])
def get_offer_details(offer_id):
    """
    Obtener detalles completos de una oferta
    
    GET /api/offers/off_123abc
    """
    
    if not current_app.duffel:
        return jsonify({'error': 'Duffel API unavailable'}), 503
    
    try:
        logger.info(f"Fetching offer details: {offer_id}")
        offer = current_app.duffel.get_offer(offer_id)
        
        return jsonify(offer)
    
    except Exception as e:
        logger.error(f"Error getting offer: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/services', methods=['GET'])
def get_services():
    """
    Obtener servicios adicionales disponibles
    
    GET /api/services?offer_id=off_123abc
    """
    
    if not current_app.duffel:
        return jsonify({'error': 'Duffel API unavailable'}), 503
    
    offer_id = request.args.get('offer_id')
    
    if not offer_id:
        return jsonify({'error': 'offer_id required'}), 400
    
    try:
        logger.info(f"Fetching services for offer: {offer_id}")
        services = current_app.duffel.get_available_services(offer_id)
        
        return jsonify(services)
    
    except Exception as e:
        logger.error(f"Error getting services: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Obtener estadísticas del servicio
    
    GET /api/stats
    """
    
    stats = {
        'cache_enabled': current_app.cache is not None,
        'duffel_api_status': 'connected' if current_app.duffel else 'unavailable'
    }
    
    if current_app.cache:
        cache_stats = current_app.cache.get_stats()
        stats.update(cache_stats)
    
    return jsonify(stats)
