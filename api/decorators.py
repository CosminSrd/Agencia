"""
Decoradores para agregar documentación Swagger a los blueprints existentes
"""

from flasgger import swag_from
from api.schemas import (
    autocomplete_schema,
    buscar_vuelos_schema,
    asientos_schema,
    crear_reserva_schema,
    buscar_tours_schema,
    tour_detalle_schema,
    checkout_schema,
    webhook_schema,
    consultar_reserva_schema
)

def documentar_endpoints(app):
    """
    Agrega documentación Swagger a los endpoints existentes
    Esta función debe llamarse después de registrar todos los blueprints
    """
    
    # Vuelos
    if 'flights.autocomplete' in app.view_functions:
        app.view_functions['flights.autocomplete'].__doc__ = autocomplete_schema
    
    if 'flights.buscar' in app.view_functions:
        app.view_functions['flights.buscar'].__doc__ = buscar_vuelos_schema
    
    if 'flights.asientos' in app.view_functions:
        app.view_functions['flights.asientos'].__doc__ = asientos_schema
    
    if 'flights.crear_reserva' in app.view_functions:
        app.view_functions['flights.crear_reserva'].__doc__ = crear_reserva_schema
    
    # Tours
    if 'tours.buscar' in app.view_functions:
        app.view_functions['tours.buscar'].__doc__ = buscar_tours_schema
    
    if 'tours.detalle' in app.view_functions:
        app.view_functions['tours.detalle'].__doc__ = tour_detalle_schema
    
    # Pagos
    if 'payments.checkout' in app.view_functions:
        app.view_functions['payments.checkout'].__doc__ = checkout_schema
    
    if 'payments.webhook' in app.view_functions:
        app.view_functions['payments.webhook'].__doc__ = webhook_schema
