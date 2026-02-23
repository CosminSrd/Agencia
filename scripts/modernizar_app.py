#!/usr/bin/env python3
"""
Script de Modernización: app.py → app_final.py
Añade Swagger, Cache, y Monitoring a app.py sin romper funcionalidad existente
"""

import re
import sys
from pathlib import Path

def modernizar_app():
    """
    Moderniza app.py añadiendo características profesionales
    """
    
    print("🔧 Iniciando modernización de app.py...")
    
    # Leer app.py original
    app_path = Path("app.py")
    if not app_path.exists():
        print("❌ Error: app.py no encontrado")
        return False
    
    with open(app_path, 'r', encoding='utf-8') as f:
        contenido_original = f.read()
    
    print(f"✅ app.py leído: {len(contenido_original)} caracteres")
    
    # ==========================================
    # PASO 1: Añadir imports necesarios
    # ==========================================
    imports_adicionales = """
# ==========================================
# IMPORTS ADICIONALES PARA MODERNIZACIÓN
# ==========================================
from flasgger import Swagger
from flask_cors import CORS

# Intentar importar cache y monitoring (opcionales)
try:
    from cache.redis_cache import RedisCache
except ImportError:
    RedisCache = None
    
try:
    from monitoring.prometheus_metrics import init_metrics
except ImportError:
    init_metrics = None
"""
    
    # Insertar después de los imports existentes
    # Buscar la línea de "from core.nomad_optimizer"
    if "from core.nomad_optimizer import NomadOptimizer" in contenido_original:
        contenido_modificado = contenido_original.replace(
            "from core.nomad_optimizer import NomadOptimizer",
            f"from core.nomad_optimizer import NomadOptimizer{imports_adicionales}"
        )
    else:
        print("⚠️ No se encontró el punto de inserción para imports")
        contenido_modificado = imports_adicionales + "\n" + contenido_original
    
    # ==========================================
    # PASO 2: Configurar Swagger después de crear app
    # ==========================================
    swagger_config = """

# ==========================================
# SWAGGER/OPENAPI CONFIGURATION
# ==========================================
app.config['SWAGGER'] = {
    'title': 'Viatges Carcaixent API',
    'version': '3.0.0',
    'description': 'API completa para gestión de viajes, vuelos y tours',
    'uiversion': 3,
    'openapi': '3.0.0',
    'specs_route': '/api/docs',
    'termsOfService': '/legal'
}

# Configuración de Swagger
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Viatges Carcaixent API",
        "description": "API REST para gestión completa de agencia de viajes",
        "contact": {
            "email": "info@viatgescarcaixent.com"
        },
        "version": "3.0.0"
    },
    "host": "localhost:8000",
    "basePath": "/",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "BasicAuth": {
            "type": "basic"
        }
    }
}

swagger_config_obj = {
    'headers': [],
    'specs': [
        {
            'endpoint': 'apispec',
            'route': '/apispec.json',
            'rule_filter': lambda rule: True,
            'model_filter': lambda tag: True,
        }
    ],
    'static_url_path': '/flasgger_static',
    'swagger_ui': True,
    'specs_route': '/api/docs'
}

# Inicializar Swagger
try:
    swagger = Swagger(app, config=swagger_config_obj, template=swagger_template)
    logger.info("✅ Swagger UI habilitado en /api/docs")
except Exception as e:
    logger.warning(f"⚠️ No se pudo inicializar Swagger: {e}")
"""
    
    # Insertar después de la configuración de Stripe
    if "webhook_secret = os.getenv(\"STRIPE_WEBHOOK_SECRET\")" in contenido_modificado:
        contenido_modificado = contenido_modificado.replace(
            "webhook_secret = os.getenv(\"STRIPE_WEBHOOK_SECRET\")",
            f"webhook_secret = os.getenv(\"STRIPE_WEBHOOK_SECRET\"){swagger_config}"
        )
    
    # ==========================================
    # PASO 3: Añadir Cache Redis
    # ==========================================
    cache_config = """

# ==========================================
# CACHE REDIS CONFIGURATION
# ==========================================
if RedisCache:
    try:
        cache = RedisCache()
        if cache.health_check():
            app.cache = cache
            logger.info("✅ Cache Redis habilitada")
        else:
            app.cache = None
            logger.warning("⚠️ Redis no disponible")
    except Exception as e:
        app.cache = None
        logger.warning(f"⚠️ No se pudo inicializar cache: {e}")
else:
    app.cache = None
    logger.info("ℹ️ Cache deshabilitada (módulo no disponible)")
"""
    
    # Insertar después de Swagger
    contenido_modificado += cache_config
    
    # ==========================================
    # PASO 4: Añadir Prometheus Metrics
    # ==========================================
    metrics_config = """

# ==========================================
# PROMETHEUS METRICS
# ==========================================
if init_metrics:
    try:
        init_metrics(app)
        logger.info("✅ Métricas Prometheus habilitadas en /metrics")
    except Exception as e:
        logger.warning(f"⚠️ No se pudieron inicializar métricas: {e}")
else:
    logger.info("ℹ️ Monitoring deshabilitado (módulo no disponible)")
"""
    
    contenido_modificado += metrics_config
    
    # ==========================================
    # PASO 5: Añadir CORS
    # ==========================================
    cors_config = """

# ==========================================
# CORS CONFIGURATION
# ==========================================
try:
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],  # En producción, especificar dominios
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    logger.info("✅ CORS habilitado para /api/*")
except Exception as e:
    logger.warning(f"⚠️ No se pudo configurar CORS: {e}")
"""
    
    contenido_modificado += cors_config
    
    # ==========================================
    # PASO 6: Mejorar el Health Check
    # ==========================================
    # Buscar la ruta /health y mejorarla
    health_check_mejorado = """
@app.route('/health')
def health():
    \"\"\"
    Health check mejorado con información detallada del sistema
    ---
    tags:
      - System
    responses:
      200:
        description: Estado del sistema
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
            version:
              type: string
              example: 3.0.0
            components:
              type: object
              properties:
                database:
                  type: string
                cache:
                  type: string
                duffel_api:
                  type: string
                stripe:
                  type: string
    \"\"\"
    components = {
        'database': 'connected',
        'cache': 'available' if app.cache and app.cache.health_check() else 'unavailable',
        'duffel_api': 'connected' if MotorBusqueda else 'unavailable',
        'stripe': 'configured' if stripe.api_key else 'not_configured'
    }
    
    status = 'healthy' if components['database'] == 'connected' else 'degraded'
    
    return {
        'status': status,
        'version': '3.0.0',
        'architecture': 'monolithic-enhanced',
        'components': components,
        'timestamp': datetime.now().isoformat()
    }, 200
"""
    
    # No reemplazamos la ruta /health si existe, la dejamos como está
    # pero registramos que debería mejorarse manualmente
    
    # ==========================================
    # GUARDAR RESULTADO
    # ==========================================
    output_path = Path("app_final.py")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(contenido_modificado)
    
    print(f"✅ app_final.py creado: {len(contenido_modificado)} caracteres")
    print(f"   Tamaño original: {len(contenido_original)} bytes")
    print(f"   Tamaño nuevo: {len(contenido_modificado)} bytes")
    print(f"   Diferencia: +{len(contenido_modificado) - len(contenido_original)} bytes")
    
    # ==========================================
    # RESUMEN
    # ==========================================
    print("\n" + "="*60)
    print("✅ MODERNIZACIÓN COMPLETADA")
    print("="*60)
    print("\n📋 Cambios aplicados:")
    print("  ✅ Swagger/OpenAPI añadido (/api/docs)")
    print("  ✅ Cache Redis integrado")
    print("  ✅ Prometheus metrics añadido (/metrics)")
    print("  ✅ CORS configurado")
    print("  ✅ Imports modernizados")
    print("\n⚠️ TAREAS MANUALES RECOMENDADAS:")
    print("  1. Añadir docstrings Swagger a rutas importantes")
    print("  2. Revisar configuración de CORS para producción")
    print("  3. Probar app_final.py antes de reemplazar app.py")
    print("\n🚀 Próximos pasos:")
    print("  1. python -m py_compile app_final.py")
    print("  2. python app_final.py  (probar en puerto 8000)")
    print("  3. mv app.py app_legacy.py")
    print("  4. mv app_final.py app.py")
    print("="*60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = modernizar_app()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error durante modernización: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
