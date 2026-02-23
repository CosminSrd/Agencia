"""
API Documentation Package
Provides OpenAPI/Swagger documentation for the Agencia API
"""

from .swagger_config import swagger_config, swagger_ui_config
from .schemas import *

__all__ = ['swagger_config', 'swagger_ui_config']
