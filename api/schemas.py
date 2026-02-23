"""
OpenAPI Schemas
Definiciones de esquemas para request/response de la API
"""

# ==================== VUELOS ====================

autocomplete_schema = {
    "tags": ["Vuelos"],
    "summary": "Autocompletar aeropuertos",
    "description": "Busca aeropuertos por código IATA o ciudad. Rate limit: 30 req/min. Cache: 1 hora.",
    "parameters": [
        {
            "name": "q",
            "in": "query",
            "description": "Código IATA (ej: MAD) o nombre de ciudad (ej: Madrid)",
            "required": True,
            "schema": {
                "type": "string",
                "minLength": 2,
                "maxLength": 50,
                "example": "MAD"
            }
        }
    ],
    "responses": {
        "200": {
            "description": "Lista de aeropuertos encontrados",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "iata_code": {
                                    "type": "string",
                                    "example": "MAD"
                                },
                                "name": {
                                    "type": "string",
                                    "example": "Madrid Barajas"
                                },
                                "city_name": {
                                    "type": "string",
                                    "example": "Madrid"
                                },
                                "country": {
                                    "type": "string",
                                    "example": "España"
                                }
                            }
                        }
                    },
                    "examples": {
                        "madrid": {
                            "value": [
                                {
                                    "iata_code": "MAD",
                                    "name": "Madrid Barajas",
                                    "city_name": "Madrid",
                                    "country": "España"
                                }
                            ]
                        }
                    }
                }
            }
        },
        "400": {"$ref": "#/components/responses/BadRequest"},
        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

buscar_vuelos_schema = {
    "tags": ["Vuelos"],
    "summary": "Buscar vuelos disponibles",
    "description": "Realiza búsqueda de vuelos en Duffel API. Rate limit: 10 req/min. Cache: 5 minutos.",
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["origen", "destino", "fecha_ida", "pasajeros"],
                    "properties": {
                        "origen": {
                            "type": "string",
                            "description": "Código IATA del aeropuerto de origen",
                            "pattern": "^[A-Z]{3}$",
                            "example": "MAD"
                        },
                        "destino": {
                            "type": "string",
                            "description": "Código IATA del aeropuerto de destino",
                            "pattern": "^[A-Z]{3}$",
                            "example": "BCN"
                        },
                        "fecha_ida": {
                            "type": "string",
                            "format": "date",
                            "description": "Fecha de ida en formato ISO (YYYY-MM-DD)",
                            "example": "2024-06-15"
                        },
                        "fecha_vuelta": {
                            "type": "string",
                            "format": "date",
                            "description": "Fecha de vuelta (opcional para vuelos de ida y vuelta)",
                            "example": "2024-06-22"
                        },
                        "pasajeros": {
                            "type": "object",
                            "required": ["adultos"],
                            "properties": {
                                "adultos": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 9,
                                    "example": 2
                                },
                                "ninos": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 8,
                                    "example": 0
                                },
                                "bebes": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 4,
                                    "example": 0
                                }
                            }
                        },
                        "clase": {
                            "type": "string",
                            "enum": ["economy", "premium_economy", "business", "first"],
                            "default": "economy",
                            "example": "economy"
                        }
                    }
                },
                "examples": {
                    "ida_vuelta": {
                        "value": {
                            "origen": "MAD",
                            "destino": "BCN",
                            "fecha_ida": "2024-06-15",
                            "fecha_vuelta": "2024-06-22",
                            "pasajeros": {"adultos": 2, "ninos": 0, "bebes": 0},
                            "clase": "economy"
                        }
                    },
                    "solo_ida": {
                        "value": {
                            "origen": "MAD",
                            "destino": "NYC",
                            "fecha_ida": "2024-07-01",
                            "pasajeros": {"adultos": 1, "ninos": 0, "bebes": 0},
                            "clase": "business"
                        }
                    }
                }
            }
        }
    },
    "responses": {
        "200": {
            "description": "Ofertas de vuelos encontradas",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ofertas": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "precio_total": {"type": "string"},
                                        "moneda": {"type": "string"},
                                        "segmentos": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "origen": {"type": "string"},
                                                    "destino": {"type": "string"},
                                                    "salida": {"type": "string", "format": "date-time"},
                                                    "llegada": {"type": "string", "format": "date-time"},
                                                    "aerolinea": {"type": "string"},
                                                    "numero_vuelo": {"type": "string"},
                                                    "duracion": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "total_ofertas": {"type": "integer"},
                            "cache_hit": {"type": "boolean"}
                        }
                    }
                }
            }
        },
        "400": {"$ref": "#/components/responses/BadRequest"},
        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

asientos_schema = {
    "tags": ["Vuelos"],
    "summary": "Obtener asientos disponibles",
    "description": "Consulta los asientos disponibles para una oferta específica. Rate limit: 10 req/min.",
    "parameters": [
        {
            "name": "offer_id",
            "in": "query",
            "description": "ID de la oferta de Duffel",
            "required": True,
            "schema": {
                "type": "string",
                "example": "off_123abc"
            }
        }
    ],
    "responses": {
        "200": {
            "description": "Mapa de asientos disponibles",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "asientos": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "designator": {"type": "string", "example": "12A"},
                                        "tipo": {"type": "string", "enum": ["window", "aisle", "middle"]},
                                        "precio": {"type": "string"},
                                        "disponible": {"type": "boolean"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "400": {"$ref": "#/components/responses/BadRequest"},
        "404": {"$ref": "#/components/responses/NotFound"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

crear_reserva_schema = {
    "tags": ["Vuelos"],
    "summary": "Crear reserva de vuelo",
    "description": "Crea una reserva en Duffel y genera sesión de pago. Rate limit: 5 req/min.",
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["offer_id", "pasajeros", "email", "telefono"],
                    "properties": {
                        "offer_id": {
                            "type": "string",
                            "description": "ID de la oferta seleccionada",
                            "example": "off_123abc"
                        },
                        "pasajeros": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["nombre", "apellidos", "fecha_nacimiento", "tipo"],
                                "properties": {
                                    "nombre": {"type": "string", "example": "Juan"},
                                    "apellidos": {"type": "string", "example": "García López"},
                                    "fecha_nacimiento": {"type": "string", "format": "date", "example": "1990-05-15"},
                                    "tipo": {"type": "string", "enum": ["adulto", "nino", "bebe"], "example": "adulto"},
                                    "genero": {"type": "string", "enum": ["M", "F"], "example": "M"},
                                    "documento": {"type": "string", "example": "12345678A"},
                                    "email": {"type": "string", "format": "email", "example": "juan@email.com"},
                                    "telefono": {"type": "string", "example": "+34600123456"}
                                }
                            }
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "description": "Email de contacto principal",
                            "example": "reservas@email.com"
                        },
                        "telefono": {
                            "type": "string",
                            "description": "Teléfono de contacto",
                            "example": "+34600123456"
                        },
                        "asientos_seleccionados": {
                            "type": "array",
                            "description": "IDs de asientos seleccionados (opcional)",
                            "items": {"type": "string"}
                        },
                        "servicios_adicionales": {
                            "type": "array",
                            "description": "IDs de servicios adicionales (opcional)",
                            "items": {"type": "string"}
                        }
                    }
                }
            }
        }
    },
    "responses": {
        "201": {
            "description": "Reserva creada exitosamente",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "booking_reference": {"type": "string", "example": "ABC123"},
                            "order_id": {"type": "string", "example": "ord_123abc"},
                            "precio_total": {"type": "string", "example": "459.90"},
                            "moneda": {"type": "string", "example": "EUR"},
                            "estado": {"type": "string", "example": "pendiente_pago"},
                            "url_pago": {"type": "string", "example": "https://checkout.stripe.com/..."}
                        }
                    }
                }
            }
        },
        "400": {"$ref": "#/components/responses/BadRequest"},
        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

# ==================== TOURS ====================

buscar_tours_schema = {
    "tags": ["Tours"],
    "summary": "Buscar tours disponibles",
    "description": "Busca tours con filtros avanzados y paginación.",
    "parameters": [
        {
            "name": "destino",
            "in": "query",
            "description": "Filtrar por destino",
            "schema": {"type": "string", "example": "Tailandia"}
        },
        {
            "name": "categoria",
            "in": "query",
            "description": "Filtrar por categoría",
            "schema": {
                "type": "string",
                "enum": ["aventura", "cultural", "playa", "gastronomico", "lujo", "familiar"],
                "example": "aventura"
            }
        },
        {
            "name": "precio_min",
            "in": "query",
            "schema": {"type": "number", "example": 500}
        },
        {
            "name": "precio_max",
            "in": "query",
            "schema": {"type": "number", "example": 2000}
        },
        {
            "name": "duracion_min",
            "in": "query",
            "description": "Duración mínima en días",
            "schema": {"type": "integer", "example": 5}
        },
        {
            "name": "duracion_max",
            "in": "query",
            "description": "Duración máxima en días",
            "schema": {"type": "integer", "example": 15}
        },
        {
            "name": "ordenar",
            "in": "query",
            "description": "Campo de ordenación",
            "schema": {
                "type": "string",
                "enum": ["precio_asc", "precio_desc", "duracion_asc", "duracion_desc", "popularidad"],
                "default": "popularidad"
            }
        },
        {
            "name": "pagina",
            "in": "query",
            "schema": {"type": "integer", "minimum": 1, "default": 1}
        },
        {
            "name": "por_pagina",
            "in": "query",
            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
        }
    ],
    "responses": {
        "200": {
            "description": "Lista de tours encontrados",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "tours": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "integer"},
                                        "nombre": {"type": "string"},
                                        "destino": {"type": "string"},
                                        "categoria": {"type": "string"},
                                        "precio": {"type": "string"},
                                        "duracion_dias": {"type": "integer"},
                                        "descripcion_corta": {"type": "string"},
                                        "imagen_principal": {"type": "string"}
                                    }
                                }
                            },
                            "total": {"type": "integer"},
                            "pagina": {"type": "integer"},
                            "paginas_totales": {"type": "integer"},
                            "por_pagina": {"type": "integer"}
                        }
                    }
                }
            }
        },
        "400": {"$ref": "#/components/responses/BadRequest"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

tour_detalle_schema = {
    "tags": ["Tours"],
    "summary": "Obtener detalles completos de un tour",
    "description": "Retorna toda la información de un tour específico incluyendo itinerario.",
    "parameters": [
        {
            "name": "tour_id",
            "in": "path",
            "required": True,
            "description": "ID del tour",
            "schema": {"type": "integer", "example": 42}
        }
    ],
    "responses": {
        "200": {
            "description": "Detalles completos del tour",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "nombre": {"type": "string"},
                            "destino": {"type": "string"},
                            "categoria": {"type": "string"},
                            "precio": {"type": "string"},
                            "duracion_dias": {"type": "integer"},
                            "descripcion_completa": {"type": "string"},
                            "itinerario": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "dia": {"type": "integer"},
                                        "titulo": {"type": "string"},
                                        "descripcion": {"type": "string"},
                                        "actividades": {"type": "array", "items": {"type": "string"}}
                                    }
                                }
                            },
                            "incluye": {"type": "array", "items": {"type": "string"}},
                            "no_incluye": {"type": "array", "items": {"type": "string"}},
                            "imagenes": {"type": "array", "items": {"type": "string"}},
                            "disponibilidad": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "fecha_salida": {"type": "string", "format": "date"},
                                        "plazas_disponibles": {"type": "integer"},
                                        "precio_especial": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "404": {"$ref": "#/components/responses/NotFound"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

# ==================== PAGOS ====================

checkout_schema = {
    "tags": ["Pagos"],
    "summary": "Crear sesión de pago Stripe",
    "description": "Genera una sesión de pago en Stripe para procesar la reserva.",
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["booking_reference", "email"],
                    "properties": {
                        "booking_reference": {
                            "type": "string",
                            "description": "Referencia de la reserva",
                            "example": "ABC123"
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "example": "cliente@email.com"
                        }
                    }
                }
            }
        }
    },
    "responses": {
        "200": {
            "description": "Sesión de pago creada",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "checkout_url": {"type": "string"},
                            "session_id": {"type": "string"}
                        }
                    }
                }
            }
        },
        "400": {"$ref": "#/components/responses/BadRequest"},
        "404": {"$ref": "#/components/responses/NotFound"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

webhook_schema = {
    "tags": ["Pagos"],
    "summary": "Webhook de Stripe",
    "description": "Endpoint para procesar eventos de Stripe (uso interno).",
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "description": "Evento de Stripe"
                }
            }
        }
    },
    "responses": {
        "200": {
            "description": "Evento procesado correctamente"
        },
        "400": {
            "description": "Firma inválida o evento no reconocido"
        }
    }
}

# ==================== GESTIÓN DE RESERVAS ====================

consultar_reserva_schema = {
    "tags": ["Gestión"],
    "summary": "Consultar reserva existente",
    "description": "Obtiene los detalles de una reserva mediante su referencia y email.",
    "parameters": [
        {
            "name": "booking_reference",
            "in": "query",
            "required": True,
            "description": "Código de reserva",
            "schema": {"type": "string", "example": "ABC123"}
        },
        {
            "name": "email",
            "in": "query",
            "required": True,
            "description": "Email asociado a la reserva",
            "schema": {"type": "string", "format": "email"}
        }
    ],
    "responses": {
        "200": {
            "description": "Detalles de la reserva",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "booking_reference": {"type": "string"},
                            "estado": {"type": "string", "enum": ["pendiente_pago", "confirmada", "cancelada"]},
                            "fecha_creacion": {"type": "string", "format": "date-time"},
                            "precio_total": {"type": "string"},
                            "detalles_vuelo": {"type": "object"},
                            "pasajeros": {"type": "array"}
                        }
                    }
                }
            }
        },
        "404": {"$ref": "#/components/responses/NotFound"},
        "500": {"$ref": "#/components/responses/ServerError"}
    }
}

# Exportar todos los schemas
__all__ = [
    'autocomplete_schema',
    'buscar_vuelos_schema',
    'asientos_schema',
    'crear_reserva_schema',
    'buscar_tours_schema',
    'tour_detalle_schema',
    'checkout_schema',
    'webhook_schema',
    'consultar_reserva_schema'
]
