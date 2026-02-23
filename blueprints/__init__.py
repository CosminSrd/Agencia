"""
Blueprints package
"""

from .flights import init_flights_blueprint
from .tours import init_tours_blueprint
from .payments import init_payments_blueprint

__all__ = ['init_flights_blueprint', 'init_tours_blueprint', 'init_payments_blueprint']
