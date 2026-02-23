"""
OpenAPI/Swagger Configuration
Configuración completa para documentación de la API con flasgger
"""

# Configuración principal de Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

# Plantilla base OpenAPI 3.0
swagger_template = {
    "openapi": "3.0.0",
    "info": {
        "title": "Agencia de Viajes API",
        "description": """
        API completa para gestión de reservas de vuelos y tours.
        
        ## Características principales
        - Búsqueda de vuelos en tiempo real (Duffel API)
        - Autocompletado de aeropuertos
        - Selección de asientos y servicios adicionales
        - Gestión de reservas y pagos (Stripe)
        - Catálogo de tours y cruceros
        - Sistema de emails automatizado
        
        ## Autenticación
        Algunos endpoints requieren autenticación mediante sesión Flask.
        
        ## Rate Limiting
        - Autocompletado: 30 solicitudes/minuto
        - Búsqueda de vuelos: 10 solicitudes/minuto
        - Creación de reservas: 5 solicitudes/minuto
        
        ## Caché
        Los resultados de búsquedas se cachean por 5 minutos.
        El autocompletado de aeropuertos se cachea por 1 hora.
        """,
        "version": "2.0.0",
        "contact": {
            "name": "Agencia de Viajes",
            "url": "https://agencia.com",
            "email": "soporte@agencia.com"
        },
        "license": {
            "name": "Propietario",
            "url": "https://agencia.com/legal"
        }
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Servidor de desarrollo"
        },
        {
            "url": "https://api.agencia.com",
            "description": "Servidor de producción"
        }
    ],
    "tags": [
        {
            "name": "Vuelos",
            "description": "Operaciones relacionadas con búsqueda y reserva de vuelos"
        },
        {
            "name": "Tours",
            "description": "Catálogo y reservas de tours y paquetes"
        },
        {
            "name": "Pagos",
            "description": "Procesamiento de pagos con Stripe"
        },
        {
            "name": "Gestión",
            "description": "Gestión de reservas existentes"
        },
        {
            "name": "Admin",
            "description": "Endpoints administrativos (requieren autenticación)"
        }
    ],
    "components": {
        "securitySchemes": {
            "sessionAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "session"
            }
        },
        "schemas": {},  # Se llenará con los schemas definidos
        "responses": {
            "BadRequest": {
                "description": "Solicitud inválida",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "Unauthorized": {
                "description": "No autenticado",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "NotFound": {
                "description": "Recurso no encontrado",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "RateLimitExceeded": {
                "description": "Límite de solicitudes excedido",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "ServerError": {
                "description": "Error interno del servidor",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    }
}

# Configuración de la UI de Swagger
swagger_ui_config = {
    "docExpansion": "list",
    "defaultModelsExpandDepth": 3,
    "defaultModelExpandDepth": 3,
    "displayRequestDuration": True,
    "filter": True,
    "syntaxHighlight.theme": "monokai",
    "tryItOutEnabled": True,
    "persistAuthorization": True
}
