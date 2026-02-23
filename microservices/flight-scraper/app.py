"""
Flight Scraper Microservice
Servicio independiente para búsqueda y gestión de vuelos
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Factory pattern para crear la aplicación"""
    
    app = Flask(__name__)
    
    # ==================== CONFIGURACIÓN ====================
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'flight-scraper-secret')
    app.config['DUFFEL_API_KEY'] = os.getenv('DUFFEL_API_KEY')
    app.config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
    app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', '')
    
    # ==================== EXTENSIONES ====================
    CORS(app)
    
    # Rate limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri=app.config['REDIS_URL'],
        default_limits=["100 per minute"]
    )
    app.limiter = limiter
    
    # ==================== SERVICIOS ====================
    from services.duffel_client import DuffelClient
    from services.cache_service import CacheService
    
    try:
        duffel_client = DuffelClient(app.config['DUFFEL_API_KEY'])
        app.duffel = duffel_client
        logger.info("✅ Duffel API client initialized")
    except Exception as e:
        logger.error(f"❌ Error initializing Duffel client: {e}")
        app.duffel = None
    
    try:
        cache_service = CacheService(app.config['REDIS_URL'])
        app.cache = cache_service
        logger.info("✅ Cache service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable, caching disabled: {e}")
        app.cache = None
    
    # ==================== BLUEPRINTS ====================
    from api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    logger.info("✅ API routes registered")
    
    # ==================== RUTAS BÁSICAS ====================
    
    @app.route('/')
    def index():
        """Información del servicio"""
        return jsonify({
            'service': 'flight-scraper',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'search': '/api/search',
                'autocomplete': '/api/autocomplete',
                'seats': '/api/seats',
                'offers': '/api/offers',
                'health': '/health'
            }
        })
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        health = {
            'status': 'healthy',
            'service': 'flight-scraper',
            'duffel_api': 'connected' if app.duffel else 'unavailable',
            'cache': 'available' if app.cache and app.cache.health_check() else 'unavailable'
        }
        
        status_code = 200 if app.duffel else 503
        return jsonify(health), status_code
    
    # ==================== ERROR HANDLERS ====================
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({'error': 'Rate limit exceeded'}), 429
    
    return app


if __name__ == '__main__':
    app = create_app()
    
    logger.info("\n" + "="*60)
    logger.info("🚀 Flight Scraper Microservice")
    logger.info("="*60)
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        logger.info(f"{rule.endpoint:30s} {methods:10s} {rule.rule}")
    logger.info("="*60 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=os.getenv('ENV') != 'production'
    )
