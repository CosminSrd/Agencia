"""
Configuración de Prometheus para monitoreo
"""

from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram, Gauge, Info
import logging

logger = logging.getLogger(__name__)


class AppMetrics:
    """Clase para gestionar métricas de la aplicación"""
    
    def __init__(self, app=None):
        self.metrics = None
        self.app = app
        
        # Métricas personalizadas
        self.vuelos_buscados = Counter(
            'agencia_vuelos_buscados_total',
            'Total de búsquedas de vuelos realizadas',
            ['origen', 'destino']
        )
        
        self.reservas_creadas = Counter(
            'agencia_reservas_creadas_total',
            'Total de reservas creadas',
            ['tipo']  # vuelo o tour
        )
        
        self.pagos_completados = Counter(
            'agencia_pagos_completados_total',
            'Total de pagos completados',
            ['tipo', 'estado']
        )
        
        self.monto_pagos = Histogram(
            'agencia_monto_pagos_euros',
            'Montos de pagos en euros',
            ['tipo']
        )
        
        self.errores_api = Counter(
            'agencia_errores_api_total',
            'Total de errores en llamadas a APIs',
            ['api', 'endpoint']
        )
        
        self.tiempo_respuesta_duffel = Histogram(
            'agencia_duffel_response_seconds',
            'Tiempo de respuesta de Duffel API',
            ['endpoint'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.cache_hits = Counter(
            'agencia_cache_hits_total',
            'Total de cache hits',
            ['tipo']
        )
        
        self.cache_misses = Counter(
            'agencia_cache_misses_total',
            'Total de cache misses',
            ['tipo']
        )
        
        self.tours_activos = Gauge(
            'agencia_tours_activos',
            'Número de tours activos en catálogo'
        )
        
        self.reservas_pendientes = Gauge(
            'agencia_reservas_pendientes',
            'Número de reservas pendientes de confirmación'
        )
        
        # Info
        self.app_info = Info(
            'agencia_app',
            'Información de la aplicación'
        )
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa las métricas con la aplicación Flask"""
        self.app = app
        
        # Inicializar Prometheus Flask Exporter
        self.metrics = PrometheusMetrics(
            app,
            group_by='endpoint',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            path='/metrics',
            export_defaults=True,
            defaults_prefix='flask'
        )
        
        # Excluir el endpoint de métricas de las métricas
        self.metrics.info('app_info', 'Application info', version='2.0.0', environment='production')
        
        # Registrar hooks
        self._register_hooks()
        
        logger.info("✅ Prometheus metrics initialized")
    
    def _register_hooks(self):
        """Registra hooks para capturar eventos"""
        if not self.app:
            return
        
        @self.app.before_request
        def before_request():
            """Hook antes de cada request"""
            pass
        
        @self.app.after_request
        def after_request(response):
            """Hook después de cada request"""
            return response
    
    def track_flight_search(self, origen, destino):
        """Registra una búsqueda de vuelo"""
        self.vuelos_buscados.labels(origen=origen, destino=destino).inc()
    
    def track_reservation(self, tipo='vuelo'):
        """Registra una nueva reserva"""
        self.reservas_creadas.labels(tipo=tipo).inc()
    
    def track_payment(self, tipo, estado, monto):
        """Registra un pago"""
        self.pagos_completados.labels(tipo=tipo, estado=estado).inc()
        self.monto_pagos.labels(tipo=tipo).observe(float(monto))
    
    def track_api_error(self, api, endpoint):
        """Registra un error de API"""
        self.errores_api.labels(api=api, endpoint=endpoint).inc()
    
    def track_duffel_response_time(self, endpoint, duration):
        """Registra tiempo de respuesta de Duffel"""
        self.tiempo_respuesta_duffel.labels(endpoint=endpoint).observe(duration)
    
    def track_cache_hit(self, tipo='vuelo'):
        """Registra un cache hit"""
        self.cache_hits.labels(tipo=tipo).inc()
    
    def track_cache_miss(self, tipo='vuelo'):
        """Registra un cache miss"""
        self.cache_misses.labels(tipo=tipo).inc()
    
    def update_tours_count(self, count):
        """Actualiza el contador de tours activos"""
        self.tours_activos.set(count)
    
    def update_pending_reservations(self, count):
        """Actualiza el contador de reservas pendientes"""
        self.reservas_pendientes.set(count)


# Instancia global
app_metrics = AppMetrics()


def init_metrics(app):
    """Initialize Prometheus metrics with the Flask app."""
    app_metrics.init_app(app)
    return app_metrics
